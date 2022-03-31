import json
import logging
import os
from collections import defaultdict
from functools import partial
from itertools import chain
from typing import Union

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import F, Q, Sum, Count, Value
from django.db.models.functions import Coalesce
from django.http import (
    Http404,
    JsonResponse,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import fs.errors
from fs.osfs import OSFS

from vault import models
from vault.filters import ExtendedJSONEncoder
from vault.forms import (
    FlowChunkGetForm,
    FlowChunkPostForm,
    RegisterDepositFileForm,
)

DATE_FORMAT = "%B %-d, %Y"
ExtendedJsonResponse = partial(JsonResponse, encoder=ExtendedJSONEncoder)

logger = logging.getLogger(__name__)


@login_required
def collections(request):
    org_id = request.user.organization_id
    _collections = models.Collection.objects.filter(organization_id=org_id).values(
        "id", "name"
    )
    return JsonResponse(
        {
            "collections": list(_collections),
        }
    )


@login_required
def reports(request):
    org_id = request.user.organization_id
    _reports = models.Report.objects.filter(collection__organization_id=org_id)
    deposits = models.Deposit.objects.filter(organization_id=org_id)

    def event_time(event):
        if isinstance(event, models.Deposit):
            return event.registered_at

        return event.started_at

    events = sorted(chain(deposits, _reports), key=event_time, reverse=True)
    formatted_events = []
    for event in events:
        if isinstance(event, models.Deposit):
            formatted_events.append(
                {
                    "id": event.id,
                    "reportType": "Migration" if 15 <= event.id <= 96 else "Deposit",
                    "model": "Deposit",
                    "endedAt": event.registered_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection_id": event.collection_id,
                }
            )
        elif isinstance(event, models.Report):
            formatted_events.append(
                {
                    "id": event.id,
                    "reportType": event.get_report_type_display(),
                    "model": event.report_type,
                    "endedAt": event.started_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection_id": event.collection_id,
                }
            )
    return JsonResponse(
        {
            "reports": formatted_events,
        }
    )


@csrf_exempt
@login_required
def collections_stats(request):
    org_id = request.user.organization_id
    org_node_id = request.user.organization.tree_node_id
    if org_node_id:
        _collections = models.Collection.objects.filter(
            organization_id=org_id
        ).annotate(
            last_modified=F("tree_node__modified_at"),
            file_count=Coalesce(F("tree_node__file_count"), 0),
            size=Coalesce(F("tree_node__size"), 0),
        )
    else:
        _collections = []
    _reports = models.Report.objects.filter(
        collection__organization=org_id, report_type=models.Report.ReportType.FIXITY
    ).order_by("-ended_at")
    latest_report = (
        _reports.values(
            "pk", "file_count", "total_size", "error_count", "ended_at"
        ).first()
        if len(_reports) > 0
        else {}
    )

    return JsonResponse(
        {
            "collections": [
                {
                    "id": collection.id,
                    "time": collection.last_modified,
                    "fileCount": collection.file_count,
                    "totalSize": collection.size,
                }
                for collection in _collections
            ],
            "latestReport": latest_report,
        }
    )


@login_required
def reports_files(request, collection_id=None):
    org_id = request.user.organization_id
    if collection_id:
        collection = get_object_or_404(
            models.Collection, pk=collection_id, organization_id=org_id
        )
        _reports = models.Report.objects.filter(collection=collection)
        deposits = models.Deposit.objects.filter(collection=collection).annotate(
            file_count=Coalesce(Count("files"), 0),
        )
    else:
        _reports = models.Report.objects.filter(collection__organization_id=org_id)
        deposits = models.Deposit.objects.filter(organization_id=org_id).annotate(
            file_count=Coalesce(Count("files"), 0),
        )

    def event_time(event):
        if isinstance(event, models.Deposit):
            return event.registered_at

        return event.started_at

    events = sorted(chain(deposits, _reports), key=event_time, reverse=False)

    formatted_events = []
    for event in events:
        if isinstance(event, models.Deposit):
            # filter out the "Migration" deposits
            if 15 <= event.id <= 96:
                continue
            formatted_events.append(
                {
                    "id": event.id,
                    "reportType": "Deposit",
                    "endedAt": event.registered_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection": event.collection_id,
                    "fileCount": event.file_count,
                }
            )
        elif isinstance(event, models.Report):
            formatted_events.append(
                {
                    "id": event.id,
                    "reportType": event.get_report_type_display(),
                    "endedAt": event.started_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection": event.collection_id,
                    "fileCount": event.file_count,
                }
            )

    return JsonResponse(
        {
            "reports": formatted_events,
        }
    )


@login_required
def collections_summary(request):
    org = request.user.organization
    collection_stats = models.Collection.objects.filter(
        organization_id=org.id
    ).annotate(
        file_count=Coalesce(F("tree_node__file_count"), 0),
        size=Coalesce(F("tree_node__size"), 0),
        regions=ArrayAgg(F("target_geolocations__name"), default=Value([])),
    )
    collection_output = []
    for collection in collection_stats:
        collection_output.append(
            {
                "id": collection.pk,
                "name": collection.name,
                "fileCount": collection.file_count,
                "regions": {
                    region: collection.file_count
                    for region in collection.regions
                    if region
                },
                "avgReplication": collection.target_replication,
            }
        )

    return JsonResponse({"collections": collection_output})


@login_required
def report_summary(request, collection_id, report_id):
    user_org = request.user.organization
    collection = get_object_or_404(models.Collection, pk=collection_id)
    if collection.organization != user_org:
        raise Http404

    report = get_object_or_404(models.Report, pk=report_id)
    if report.collection != collection:
        raise Http404

    return JsonResponse(
        {
            "id": report.pk,
            "reportType": report.get_report_type_display(),
            "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
            "fileCount": report.collection_file_count,
            "totalSize": report.collection_total_size,
            "errorCount": report.error_count,
            "regions": {
                region: report.collection_file_count
                for region in collection.target_geolocations.values_list(
                    "name", flat=True
                )
            },
            "fileTypes": {},
            "avgReplication": collection.target_replication,
        }
    )


@login_required
def report_files(request, collection_id, report_id):
    # pylint: disable=unused-argument
    return JsonResponse({"files": []})


def _chunk_out_filename(file_identifier: str, chunk_number: int) -> str:
    """Return a different filename for the chunk while it is being written
    so we don't erroneously assume all chunks are fully written to disk.
    """
    return f"{file_identifier}-{chunk_number}.out"


def _chunk_filename(file_identifier: str, chunk_number: int) -> str:
    return f"{file_identifier}-{chunk_number}.tmp"


@csrf_exempt
@login_required
def register_deposit(request):
    # pylint: disable=too-many-return-statements
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    try:
        request_payload = json.loads(request.body)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    if "files" not in request_payload:
        return JsonResponse({"files": ["Missing file list"]}, status=400)

    _parent_node_id = request_payload.get("parent_node_id")
    org_id = request.user.organization_id
    collection_id = request_payload.get("collection_id")

    if all((collection_id, _parent_node_id)):
        return HttpResponseBadRequest(
            "one of parent_node_id or collection_id must be supplied"
        )

    # determine collection and parent_node from request payload params
    if collection_id is not None:
        # Include organization_id in filter to ensure we have permission
        collection = get_object_or_404(
            models.Collection, pk=collection_id, organization_id=org_id
        )
        parent_node = collection.tree_node
    elif _parent_node_id is not None:
        parent_node = models.TreeNode.get_owned_by(
            _parent_node_id,
            request.user.id,
        )
        if parent_node.node_type != models.TreeNode.Type.FOLDER:
            return HttpResponseBadRequest(
                "parent_node_id must correspond to a FOLDER-type node",
            )
        collection = parent_node.get_collection()
    else:
        # case: neither `collection_id` nor `parent_node_id` were provided
        return HttpResponseBadRequest(
            "one of parent_node_id or collection_id must be supplied"
        )

    deposit = models.Deposit.objects.create(
        organization_id=org_id,
        collection=collection,
        user=request.user,
        parent_node=parent_node,
    )

    deposit_files = []
    for file in request_payload.get("files", []):
        deposit_file_form = RegisterDepositFileForm(file)
        if not deposit_file_form.is_valid():
            return JsonResponse(deposit_file_form.errors, status=400)
        deposit_files.append(
            models.DepositFile(
                deposit=deposit,
                **deposit_file_form.cleaned_data,
            )
        )
    models.DepositFile.objects.bulk_create(deposit_files)

    return JsonResponse(
        {
            "deposit_id": deposit.pk,
        }
    )


def _check_file_in_db(file_path_dict, node, full_path_dict, list_of_path):
    """To check if the file exists in database. If it exists, append and show
    it to the user.
    """
    # TODO (mwilson): this function should be rewritten to eliminate doing ORM
    # queries in a loop
    try:
        for file in file_path_dict[node]:
            file_match = models.TreeNode.objects.filter(
                name=file, parent=int(full_path_dict[node][1])
            ).first()

            if file_match:
                list_of_path.append(node + file)
    except:  # pylint: disable=bare-except
        file_path_dict[node] = []


@csrf_exempt
@login_required
def warning_deposit(request):
    # pylint: disable=too-many-statements,too-many-locals,too-many-branches
    # TODO (mwilson): this view should be refactored to reduce complexity and
    # length. Suggestions: move db behavior into models (and add tests);
    # introduce private functions to do some of the work (and test them).

    try:
        request_payload = json.loads(request.body)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    coll_id = request_payload.get("collection_id")
    _parent_node_id = request_payload.get("parent_node_id")
    relative_path_list = [i["relative_path"] for i in request_payload.get("files")]

    if all((coll_id, _parent_node_id)):
        # only one of `collection_id`, `parent_node_id` may be supplied
        return HttpResponseBadRequest()

    # determine id of parent treenode
    if coll_id:
        # case: using Collection.tree_node as parent
        org_id = request.user.organization_id
        collection = get_object_or_404(
            models.Collection, pk=coll_id, organization_id=org_id
        )
        parent_node_id = collection.tree_node.id
    else:
        # case: using explicitly-supplied parent TreeNode id
        parent_node_id = _parent_node_id

    list_of_matched_files = []

    # Only for files
    files_list = []
    for file_path in relative_path_list:
        path_list = file_path.split("/")
        if len(path_list) == 1 and not path_list[0].endswith("/"):
            # If it is a file and it contains directly in collection, append it to files_list
            files_list.append(path_list[0])

    for file in files_list:
        # Check if the file exists in database. If yes, append to list_of_matched_files
        matched_file = models.TreeNode.objects.filter(
            name=file, parent=parent_node_id
        ).first()
        if matched_file:
            list_of_matched_files.append(matched_file)

    unique_path_list = sorted(
        set(
            map(
                lambda x: "/".join(x.split("/")[:-1]) + "/"
                if not x.endswith("/")
                else x,
                relative_path_list,
            )
        )
    )

    all_paths_list = []
    for path in unique_path_list:
        paths_without_file = path.split("/")[:-1]
        prev_path_element = ""
        for current_path_element in paths_without_file:
            all_paths_list.append(prev_path_element + current_path_element + "/")
            prev_path_element += current_path_element + "/"

    sorted_path_list = sorted(set(all_paths_list))

    # Making all the values of paths as False initially in full_path_dict
    full_path_dict = {x: False for x in sorted_path_list}

    file_path_dict = {}
    # Keeping a key as path and its value as list of files
    for rel_path in relative_path_list:
        file_name = rel_path.split("/")[-1]
        parent_relative_path = "/".join(rel_path.split("/")[:-1]) + "/"

        if parent_relative_path not in file_path_dict:
            # Assigning empty list to all keys initially
            file_path_dict[parent_relative_path] = []

        file_path_dict[parent_relative_path].append(file_name)

    list_of_path = []
    stack_list = []

    for node in full_path_dict:
        node_list = node.split("/")
        if len(node_list) > 2 and len(stack_list) == 0:
            # to access first element(folder) of path in the beginning
            # eg. "Parent/Child/GrandChild" - get only the word "Parent"
            node_name = node.split("/")[0]
        else:
            # to access last element(folder) of path after first iteration
            # eg. "Parent/Child/GrandChild" - get only the word "GrandChild"
            node_name = node.split("/")[-2]

        if len(stack_list) == 0:
            # check if the first folder is a child of collection
            match_node = models.TreeNode.objects.filter(
                name=node_name, parent=parent_node_id
            ).first()
            if match_node:
                stack_list.append(node)
                full_path_dict[node] = [True, match_node.id]
                _check_file_in_db(file_path_dict, node, full_path_dict, list_of_path)
        else:
            while len(stack_list) > 0:
                if node.startswith(stack_list[-1]):
                    if models.TreeNode.objects.filter(
                        name=node.split("/")[-2],
                        parent=int(full_path_dict[stack_list[-1]][1]),
                    ).first():
                        match_folder = models.TreeNode.objects.filter(
                            name=node.split("/")[-2],
                            parent=int(full_path_dict[stack_list[-1]][1]),
                        ).first()
                        full_path_dict[node] = [True, match_folder.id]

                        stack_list.append(
                            node
                        )  # to get the parent element in next iteration

                        _check_file_in_db(
                            file_path_dict, node, full_path_dict, list_of_path
                        )
                        break

                    full_path_dict[node] = [False]
                    break

                # if the last element of path does not match with the last
                # element of stack_list, remove the last element And keep on
                # removing until it matches with the one in stack_list
                stack_list.pop()

    return JsonResponse(
        {
            "objects": [
                {
                    "id": matched_file.pk,
                    "name": matched_file.name,
                    "parent": matched_file.parent.id if matched_file.parent else 0,
                    "parent_name": matched_file.parent.name
                    if matched_file.parent
                    else None,
                }
                for matched_file in list_of_matched_files
            ],
            "relative_path": sorted(set(list_of_path)),
        }
    )


@csrf_exempt
@login_required
def flow_chunk(request):
    if request.method not in ["GET", "POST"]:
        return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])
    if request.method == "GET":
        form = FlowChunkGetForm(request.GET)
    else:
        form = FlowChunkPostForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse(status=400, data=form.errors)

    # auth - check the org matches the chunk deposit
    chunk = form.flow_chunk()
    deposit = get_object_or_404(
        models.Deposit,
        pk=chunk.deposit_id,
        organization_id=request.user.organization_id,
    )

    org_tmp_path = str(request.user.organization_id)
    org_chunk_tmp_path = os.path.join(org_tmp_path, "chunks")
    chunk_filename = _chunk_filename(chunk.file_identifier, chunk.number)
    chunk_out_filename = _chunk_out_filename(chunk.file_identifier, chunk.number)

    if request.method == "GET":
        # do we need this chunk?
        with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
            no_tmp = not tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_filename}")
            no_out = not tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_out_filename}")
        if no_tmp and no_out:
            return HttpResponse(status=204)  # please send us this chunk

    if request.method == "POST":
        # Save the chunk to the org's tmp chunks dir
        logger.info("saving chunk to tmp: %s", chunk_filename)
        with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
            with tmp_fs.makedirs(org_chunk_tmp_path, recreate=True) as org_fs:
                if org_fs.exists(chunk_filename) or org_fs.exists(chunk_out_filename):
                    logger.warning("chunk already exists, skipping: %s", chunk_filename)
                    return HttpResponse()
                chunk_out = org_fs.openbin(chunk_out_filename, "a")
                for chunk_bytes in chunk.file.chunks():
                    chunk_out.write(chunk_bytes)
                chunk_out.flush()
                os.fsync(chunk_out.fileno())
                chunk_out.close()
                org_fs.move(chunk_out_filename, chunk_filename, overwrite=True)

    if all_chunks_uploaded(chunk, org_chunk_tmp_path):
        logger.info("all chunks saved for %s", chunk.file_identifier)
        deposit_file = get_object_or_404(
            models.DepositFile,
            deposit=deposit,
            flow_identifier=chunk.file_identifier,
        )
        if deposit_file.state != models.DepositFile.State.REGISTERED:
            logger.warning("chunk request for already uploaded file")
            return HttpResponse()  # this DepositFile is already uploaded
        deposit_file.state = models.DepositFile.State.UPLOADED
        deposit_file.uploaded_at = timezone.now()
        deposit_file.save()
    return HttpResponse()


def all_chunks_uploaded(chunk, org_chunk_tmp_path) -> bool:
    # Check if we have all chunks for the file
    with OSFS(
        os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_chunk_tmp_path)
    ) as org_fs:
        total_saved_size = 0
        for i in reversed(range(1, chunk.file_total_chunks + 1)):
            try:
                saved_size = org_fs.getsize(_chunk_filename(chunk.file_identifier, i))
                total_saved_size += saved_size
            except fs.errors.ResourceNotFound:
                return False
        if not total_saved_size == chunk.file_total_size:
            logger.warning(
                "file has all chunks but wrong total size: %s", chunk.file_identifier
            )
            raise DepositException

        return True


class DepositException(Exception):
    pass


@csrf_exempt
@login_required
def hashed_status(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(permitted_methods=["GET"])
    org_id = request.user.organization_id
    deposit_id = request.GET.get("deposit_id")
    if not deposit_id:
        return HttpResponseBadRequest()
    deposit = get_object_or_404(models.Deposit, pk=deposit_id, organization_id=org_id)

    state_count_qs = (
        models.DepositFile.objects.filter(deposit=deposit)
        .values_list("state")
        .annotate(files=Count("state"))
    )

    total_files = 0
    state_count = defaultdict(int)
    for state, file_count in state_count_qs:
        state_count[state] = file_count
        total_files += file_count

    return JsonResponse(
        {
            "hashed_files": state_count[models.DepositFile.State.HASHED],
            "replicated_files": state_count[models.DepositFile.State.REPLICATED],
            "errored_files": state_count[models.DepositFile.State.ERROR],
            "total_files": total_files,
            "file_queue": state_count[models.DepositFile.State.UPLOADED],
        }
    )


def render_tree_file_view(request):
    user_org = request.user.organization.tree_node
    all_obj = models.TreeNode.objects.filter(path__descendant=user_org.path).exclude(
        path=user_org.path
    )

    return JsonResponse(
        {
            "objects": [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "parent": obj.parent.id if obj.parent else 0,
                    "type": obj.node_type,
                }
                for obj in all_obj
            ]
        }
    )


def get_events(request, collection_id):
    user_org = request.user.organization
    collection_node = get_object_or_404(
        models.Collection, id=collection_id, organization=user_org
    )
    collection_node_id = collection_node.id
    _reports = models.Report.objects.filter(collection=collection_node_id)
    deposits = models.Deposit.objects.filter(collection=collection_node).annotate(
        file_count=Count("files"),
        total_size=Coalesce(Sum("files__size"), 0),
        error_count=Count("pk", filter=Q(files__state=models.DepositFile.State.ERROR)),
    )

    def extract_event_sort_key(event: Union[models.Deposit, models.Report]):
        if isinstance(event, models.Deposit):
            return event.registered_at

        return event.started_at

    formatted_events = []
    deposit_events = []
    fixity_events = []
    events = sorted(chain(deposits, _reports), key=extract_event_sort_key, reverse=True)
    for event in events:
        if isinstance(event, models.Deposit):
            deposit_events.append(
                {
                    "Event Id": event.id,
                    "Event Type": "Migration" if is_migration(event.id) else "Deposit",
                    "Started": event.registered_at.strftime(DATE_FORMAT),
                    "File Count": event.file_count,
                    "Completed": event.hashed_at.strftime(DATE_FORMAT)
                    if event.hashed_at
                    else "--",
                    "Total Size": event.total_size,
                    "Error Count": event.error_count,
                }
            )
        elif isinstance(event, models.Report):
            fixity_events.append(
                {
                    "Event Id": event.id,
                    "Event Type": event.get_report_type_display(),
                    "Started": event.started_at.strftime(DATE_FORMAT),
                    "Completed": event.ended_at.strftime(DATE_FORMAT),
                    "File Count": event.file_count,
                    "Error Count": event.error_count,
                    "Total Size": event.total_size,
                }
            )
    formatted_events = list(chain(deposit_events, fixity_events))
    return JsonResponse(
        {
            "formatted_events": formatted_events,
            "deposit_events": deposit_events,
            "fixity_events": fixity_events,
        }
    )


def is_migration(event_id):
    """
    Deposits records between 15 and 96 on production environment are
    migrated files from the old system into the new system.
    """
    return 15 <= event_id <= 96
