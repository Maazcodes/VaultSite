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
    return JsonResponse({"deposit_id": deposit.pk})


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
    org_id = request.user.organization_id
    deposit = get_object_or_404(
        models.Deposit, pk=chunk.deposit_id, organization_id=org_id
    )
    deposit_file = get_object_or_404(
        models.DepositFile,
        deposit=deposit,
        flow_identifier=chunk.file_identifier,
    )
    if deposit_file.state != models.DepositFile.State.REGISTERED:
        logger.warning("chunk request for already uploaded file")
        return HttpResponse()  # this DepositFile is already uploaded

    org_tmp_path = str(org_id)
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

    if all_chunks_uploaded(chunk, org_chunk_tmp_path):
        logger.info(f"all chunks saved for {chunk.file_identifier}")
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
    org_id = request.user.organization_id
    deposit_id = request.GET.get("deposit_id")
    if not deposit_id:
        return HttpResponseBadRequest()
    deposit = get_object_or_404(models.Deposit, pk=deposit_id, organization_id=org_id)

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

    file_queue = models.DepositFile.objects.filter(
        state=models.DepositFile.State.UPLOADED
    ).aggregate(file_count=Coalesce(Count("*"), 0))["file_count"]

    return JsonResponse(
        {
            "hashed_files": state["HASHED"],
            "total_files": total_files,
            "file_queue": file_queue,
        }
    )
