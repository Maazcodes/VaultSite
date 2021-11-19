import json
import logging
import os

import fs.errors
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import BadRequest
from django.db.models import Count, Sum, Max
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

from fs.osfs import OSFS

from vault import models
from vault.forms import (
    FlowChunkGet,
    FlowChunkPost,
    FlowChunkGetForm,
    FlowChunkPostForm,
    RegisterDepositForm,
    RegisterDepositFileForm,
)


logger = logging.getLogger(__name__)


@login_required
def collections(request):
    org = request.user.organization
    collections = models.Collection.objects.filter(organization=org)
    return JsonResponse(
        {
            "collections": [
                {"id": collection.pk, "name": collection.name}
                for collection in collections
            ]
        }
    )


@login_required
def reports(request):
    org = request.user.organization
    reports = models.Report.objects.filter(collection__organization=org).order_by(
        "-ended_at"
    )
    return JsonResponse(
        {
            "reports": [
                {
                    "id": report.pk,
                    "reportType": report.get_report_type_display(),
                    "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection_name": report.collection.name,
                    "collection_id": report.collection.pk,
                }
                for report in reports
            ]
        }
    )


@csrf_exempt
@login_required
def collections_stats(request):
    org_id = request.user.organization_id
    org_node_id = request.user.organization.tree_node_id
    if org_node_id:
        collections = org_collection_sizes(org_node_id)
    else:
        collections = []
    reports = models.Report.objects.filter(
        collection__organization=org_id, report_type=models.Report.ReportType.FIXITY
    ).order_by("-ended_at")
    latest_report = (
        reports.values(
            "pk", "file_count", "total_size", "error_count", "ended_at"
        ).first()
        if len(reports) > 0
        else {}
    )

    return JsonResponse(
        {
            "collections": [
                {
                    "id": collection.collection_id,
                    "time": collection.last_modified,
                    "fileCount": collection.file_count,
                    "totalSize": collection.total_size,
                    "latestReport": reports.filter(collection__pk=collection.pk)
                    .values("pk", "file_count", "total_size", "error_count", "ended_at")
                    .first(),
                }
                for collection in collections
            ],
            "latestReport": latest_report,
        }
    )


def org_collection_sizes(org_node_id):
    org_root = str(org_node_id)
    return models.TreeNode.objects.raw(
        """
    select coll.id as collection_id, 
           stats.* 
    from vault_collection coll
        join (
            select colln.*, 
                   Cast(coalesce(sum(descn.size), 0) as bigint) as total_size, 
                   -- subtract 1 from file_count as nodes are own descendants
                   -- could also filter on node_type to disallow FOLDER
                   count(descn.id) - 1 as file_count,
                   max(descn.modified_at) as last_modified 
            from vault_treenode colln, vault_treenode descn
            where colln.node_type = 'COLLECTION' 
                  and descn.path <@ colln.path 
                  and colln.path <@ Cast(%s as ltree)
            group by colln.id
        ) stats on coll.tree_node_id = stats.id""",
        [org_root],
    )


@login_required
def reports_files(request):
    org = request.user.organization
    reports = models.Report.objects.filter(collection__organization=org).order_by(
        "ended_at"
    )
    return JsonResponse(
        {
            "reports": [
                {
                    "id": report.pk,
                    "reportType": report.get_report_type_display(),
                    "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection": report.collection.pk,
                    "fileCount": report.collection_file_count,
                }
                for report in reports
            ]
        }
    )


@login_required
def collections_summary(request):
    org = request.user.organization
    tree_node_id = str(org.tree_node_id)
    collection_stats = org_collection_sizes(tree_node_id)
    collections = models.Collection.objects.filter(organization=org)
    collection_output = []
    for collection in collections:
        stats = None
        if collection_stats:
            for possible_stats in collection_stats:
                if possible_stats.collection_id == collection.pk:
                    stats = possible_stats
        collection_output.append(
            {
                "id": collection.pk,
                "name": collection.name,
                "fileCount": stats.file_count if stats else 0,
                "regions": {
                    region: stats.file_count if stats else 0
                    for region in collection.target_geolocations.values_list(
                        "name", flat=True
                    )
                },
                "avgReplication": collection.target_replication,
            }
        )

    return JsonResponse({"collections": collection_output})


@login_required
def reports_files_by_collection(request, collection_id):
    org = request.user.organization
    collection = get_object_or_404(models.Collection, pk=collection_id)
    if collection.organization != org:
        raise Http404
    reports = models.Report.objects.filter(collection=collection)
    return JsonResponse(
        {
            "reports": [
                {
                    "id": report.pk,
                    "reportType": report.get_report_type_display(),
                    "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                    "collection": report.collection.pk,
                    "fileCount": report.collection_file_count,
                }
                for report in reports
            ]
        }
    )


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
    return JsonResponse({"files": []})
    # return JsonResponse({
    #     "files": [
    #         {
    #             "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz",
    #             "checkTime": "2021-05-26T20:42:35.696Z",
    #             "initialCheckTime": "2021-05-25T06:19:56.176Z",
    #             "previousCheckTime": "2021-05-25T06:49:35.238Z",
    #             "size": 22381003,
    #             "success": True,
    #             "checksums": [
    #                 "md5:365fa1c3234a7afc0f2a728df845f0dd",
    #                 "sha1:b200c07d7cf512bb157a826b2cff0fc9cc9307f6",
    #                 "sha256:c53b2d161cb37ee21ba166e1ad66aa0811c05d5a6781fa6a3030cd8eb2d1c805"
    #             ],
    #             "sources": [
    #                 {
    #                     "source": "PBOX",
    #                     "region": "us-west-1",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "AIT",
    #                     "region": "us-west-2",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "PBOX",
    #                     "region": "us-west-1",
    #                     "type": "generated",
    #                     "location": "https://archive.org/serve/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817-00000/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz"
    #                 },
    #                 {
    #                     "source": "HDFS",
    #                     "region": "us-west-2",
    #                     "type": "generated",
    #                     "location": "hdfs:///search/ait/10923/arcs/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz"
    #                 }
    #             ]
    #         },
    #         {
    #             "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000_warc.wat.gz",
    #             "checkTime": "2021-05-26T20:42:36.163Z",
    #             "initialCheckTime": "2021-05-25T06:19:43.400Z",
    #             "previousCheckTime": "2021-05-25T06:49:33.703Z",
    #             "size": 3050297,
    #             "success": False,
    #             "checksums": [
    #                 "md5:754ba6eefe7336d812aa1681ac5f05e6",
    #                 "sha1:61fae3fc51867e15466b8dff4bece42835fc3278",
    #                 "sha256:65f3d1edfe81df15f591df2d4080379dfc9c71e150983320870095964ab3f705"
    #             ],
    #             "sources": [
    #                 {
    #                     "source": "PBOX",
    #                     "region": "us-west-1",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "AIT",
    #                     "region": "us-west-2",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "HDFS",
    #                     "region": "us-west-2",
    #                     "type": "prior"
    #                 }
    #             ],
    #             "missingLocations": [
    #                 "HDFS",
    #                 "archive.org"
    #             ]
    #         },
    #         {
    #             "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz",
    #             "checkTime": "2021-05-26T20:42:22.814Z",
    #             "initialCheckTime": "2021-05-25T06:19:33.990Z",
    #             "previousCheckTime": "2021-05-25T06:49:35.124Z",
    #             "size": 6866346,
    #             "success": True,
    #             "checksums": [
    #                 "md5:f7334b620ebb46442d14875452bf3d80",
    #                 "sha1:818a693ad93ec43c65ca23b0ec294cf5bdf5e8aa",
    #                 "sha256:2052e8ce69faf7b5463b8f80df3965348542af6c681357c23d786cfd8d3aaaf1"
    #             ],
    #             "sources": [
    #                 {
    #                     "source": "PBOX",
    #                     "region": "us-west-1",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "AIT",
    #                     "region": "us-west-2",
    #                     "type": "prior"
    #                 },
    #                 {
    #                     "source": "PBOX",
    #                     "region": "us-west-1",
    #                     "type": "generated",
    #                     "location": "https://archive.org/serve/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817-00000/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz"
    #                 },
    #                 {
    #                     "source": "HDFS",
    #                     "region": "us-west-2",
    #                     "type": "generated",
    #                     "location": "hdfs:///search/ait/10923/arcs/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz"
    #                 }
    #             ]
    #         }
    #     ]
    # })


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

    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    try:
        body = json.loads(request.body)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    if "files" not in body:
        return JsonResponse({"files": ["Missing file list"]}, status=400)

    org_id = request.user.organization_id
    collection_id = body.get("collection_id")

    # Include organization_id in filter to ensure we have permission
    collection = get_object_or_404(
        models.Collection, pk=collection_id, organization_id=org_id
    )

    deposit = models.Deposit.objects.create(
        organization_id=org_id,
        collection=collection,
        user=request.user,
    )

    deposit_files = []
    for file in body.get("files", []):
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


def save_file_in_db(img_path_dict, node, full_path_dict, list_of_path):
    """ To check if the file exists in database. If it exists, append and show it to the user. """
    try:
        for img in img_path_dict[node]:

            file_match = models.TreeNode.objects.filter(
                name=img, parent=int(full_path_dict[node][1])
            ).first()

            if file_match:
                list_of_path.append(node + img)
    except:
        img_path_dict[node] = []


@csrf_exempt
@login_required
def warning_deposit(request):
    try:
        body = json.loads(request.body)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest()

    collection_table_coll_id = body.get("collection_id")

    org_id = request.user.organization_id

    collection = get_object_or_404(
        models.Collection, pk=collection_table_coll_id, organization_id=org_id
    )

    collection_object = models.TreeNode.objects.filter(name=collection.name).first()

    collection_id = collection_object.id

    list_of_files = []

    relative_path_list = [i["relative_path"] for i in body.get("files")]

    # Only for files
    files_list = []
    for file_path in relative_path_list:
        path_list = file_path.split("/")
        if len(path_list) == 1 and path_list[0][-1] != "/":
            # this means that it is a file or image and it contains directly in collection
            files_list.append(path_list[0])

    if len(files_list) > 0:
        for file in files_list:
            matched_file = models.TreeNode.objects.filter(
                name=file, parent=collection_id
            ).first()
            if matched_file:
                list_of_files.append(matched_file)

    unique_path_list = sorted(
        list(
            set(
                map(
                    lambda x: "/".join(x.split("/")[:-1]) + "/"
                    if not x.endswith("/")
                    else x,
                    relative_path_list,
                )
            )
        )
    )

    allPathsList = []

    for path in unique_path_list:
        pathList = path.split("/")[:-1]
        prev_path_element = ""
        for current_path_element in pathList:
            allPathsList.append(prev_path_element + current_path_element + "/")
            prev_path_element += current_path_element + "/"

    sorted_path_list = sorted(list(set(allPathsList)))

    full_path_dict = {x: False for x in sorted_path_list}

    img_path_dict = {}  # value will be array

    for i in range(len(relative_path_list)):

        file_name = relative_path_list[i].split("/")[-1]
        parent_relative_path = "/".join(relative_path_list[i].split("/")[:-1]) + "/"

        if not parent_relative_path in img_path_dict.keys():
            img_path_dict[parent_relative_path] = []

        img_path_dict[parent_relative_path].append(file_name)

    list_of_path = []

    stack_list = []

    for node in full_path_dict.keys():

        node_list = node.split("/")
        if len(node_list) > 2 and len(stack_list) == 0:
            # to access first element(folder) of path in the beginning
            node_name = node.split("/")[0]
        else:
            # to access last element(folder) of path after first iteration
            node_name = node.split("/")[-2]

        if len(stack_list) == 0:

            # check if the first folder is a child of collection
            match_object = models.TreeNode.objects.filter(
                name=node_name, parent=collection_id
            ).first()

            if match_object:
                stack_list.append(node)
                full_path_dict[node] = [True, match_object.id]

                save_file_in_db(img_path_dict, node, full_path_dict, list_of_path)

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

                        save_file_in_db(
                            img_path_dict, node, full_path_dict, list_of_path
                        )

                        break

                    else:
                        full_path_dict[node] = [False]
                        break

                else:
                    stack_list.pop()

    return JsonResponse(
        {
            "objects": [
                {
                    "id": obj.pk,
                    "name": obj.name,
                    "parent": obj.parent.id if obj.parent else 0,
                    "parent_name": obj.parent.name if obj.parent else None,
                }
                for obj in list_of_files
            ],
            "relative_path": sorted(list(set(list_of_path))),
        }
    )


@csrf_exempt
@login_required
def flow_chunk(request):

    if request.method not in ["GET", "POST"]:
        return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])

    org_id = request.user.organization_id
    org_tmp_path = str(org_id)
    org_chunk_tmp_path = os.path.join(org_tmp_path, "chunks")

    if request.method == "GET":
        form = FlowChunkGetForm(request.GET)
        if not form.is_valid():
            return JsonResponse(status=400, data=form.errors)
        chunk = form.flow_chunk_get()

        # check the org matches the deposit
        deposit = get_object_or_404(
            models.Deposit, pk=chunk.deposit_id, organization_id=org_id
        )

        chunk_filename = _chunk_filename(chunk.file_identifier, chunk.number)
        chunk_out_filename = _chunk_out_filename(chunk.file_identifier, chunk.number)

        # do we need this chunk?
        with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
            have_tmp = tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_filename}")
            have_out = tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_out_filename}")
        if have_tmp or have_out:
            if not all_chunks_uploaded(chunk, org_chunk_tmp_path):
                return HttpResponse()
            else:
                logger.info(f"all chunks saved for {chunk.file_identifier}")
                deposit_file = get_object_or_404(
                    models.DepositFile,
                    deposit=deposit,
                    flow_identifier=chunk.file_identifier,
                )
                deposit_file.state = models.DepositFile.State.UPLOADED
                deposit_file.uploaded_at = timezone.now()
                deposit_file.save()

            return HttpResponse(status=200)  # we have the chunk don't send it again
        else:
            return HttpResponse(status=204)  # please send us this chunk

    if request.method == "POST":
        form = FlowChunkPostForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse(status=400, data=form.errors)
        chunk = form.flow_chunk_post()
        deposit = get_object_or_404(
            models.Deposit, id=chunk.deposit_id, organization_id=org_id
        )
        deposit_file = get_object_or_404(
            models.DepositFile, deposit=deposit, flow_identifier=chunk.file_identifier
        )
        if deposit_file.state != models.DepositFile.State.REGISTERED:
            logger.warning("chunk posted for already uploaded file")
            return HttpResponse()

        # Save the chunk to the org's tmp chunks dir
        chunk_out_filename = _chunk_out_filename(chunk.file_identifier, chunk.number)
        chunk_filename = _chunk_filename(chunk.file_identifier, chunk.number)
        logger.info(f"saving chunk to tmp: {chunk_filename}")
        with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
            with tmp_fs.makedirs(org_chunk_tmp_path, recreate=True) as org_fs:
                if org_fs.exists(chunk_filename) or org_fs.exists(chunk_out_filename):
                    logger.warning(f"chunk already exists, skipping: {chunk_filename}")
                    return HttpResponse()
                chunk_out = org_fs.openbin(chunk_out_filename, "a")
                for chunk_bytes in chunk.file.chunks():
                    chunk_out.write(chunk_bytes)
                chunk_out.flush()
                os.fsync(chunk_out.fileno())
                chunk_out.close()
                org_fs.move(chunk_out_filename, chunk_filename, overwrite=True)

        if not all_chunks_uploaded(chunk, org_chunk_tmp_path):
            return HttpResponse()
        else:
            logger.info(f"all chunks saved for {chunk.file_identifier}")
            deposit_file.state = models.DepositFile.State.UPLOADED
            deposit_file.uploaded_at = timezone.now()
            deposit_file.save()

        return HttpResponse()


def all_chunks_uploaded(chunk, org_chunk_tmp_path):
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
                f"file has all chunks but wrong total size: {chunk.file_identifier}"
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
    deposit_id = request.GET.get("deposit_id")
    if not deposit_id:
        return HttpResponseBadRequest()
    deposit = get_object_or_404(
        models.Deposit,
        pk=deposit_id,
        organization=get_object_or_404(
            models.Organization, pk=request.user.organization_id
        ),
    )

    from functools import reduce

    state = {"REGISTERED": 0, "UPLOADED": 0, "HASHED": 0, "REPLICATED": 0}

    deposit_files = (
        models.DepositFile.objects.filter(deposit=deposit)
        .values("state")
        .annotate(files=Count("state"))
        .order_by("state")
    )

    total_files = 0

    for deposit_file in deposit_files:
        state[deposit_file["state"]] = deposit_file["files"]
        total_files += deposit_file["files"]

    return JsonResponse(
        {
            "hashed_files": state["HASHED"],
            "total_files": total_files,
        }
    )


def render_tree_file_view(request):
    # child = get_object_or_404(models.TreeNode, parent=request.user.organization)
    user_org = models.TreeNode.objects.get(name=request.user.organization)

    all_obj = models.TreeNode.objects.filter(path__startswith=user_org.id)
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
