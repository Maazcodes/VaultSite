import json
import logging
import os

import fs.errors
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Max
from django.http import (
    Http404,
    JsonResponse,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
)
from django.shortcuts import get_object_or_404
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
    org = request.user.organization
    collections = models.Collection.objects.filter(organization=org).annotate(
        file_count=Count("file"),
        total_size=Sum("file__size"),
        last_modified=Max("file__modified_date"),
    )
    reports = models.Report.objects.filter(
        collection__organization=org, report_type=models.Report.ReportType.FIXITY
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
                    "id": collection.pk,
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
    collections = models.Collection.objects.filter(organization=org).annotate(
        file_count=Count("file")
    )
    return JsonResponse(
        {
            "collections": [
                {
                    "id": collection.pk,
                    "name": collection.name,
                    "fileCount": collection.file_count,
                    "regions": {
                        region: collection.file_count
                        for region in collection.target_geolocations.values_list(
                            "name", flat=True
                        )
                    },
                    "avgReplication": collection.target_replication,
                }
                for collection in collections
            ]
        }
    )


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

    org_id = request.user.organization_id
    org_tmp_path = str(org_id)
    org_chunk_tmp_path = os.path.join(org_tmp_path, "chunks")

    if request.method == "GET":
        form = FlowChunkGetForm(request.GET)
        if not form.is_valid():
            return JsonResponse(status=400, data=form.errors)
        chunk = form.flow_chunk_get()

        # check the org matches the deposit
        get_object_or_404(models.Deposit, pk=chunk.deposit_id, organization_id=org_id)

        chunk_filename = _chunk_filename(chunk.file_identifier, chunk.number)
        chunk_out_filename = _chunk_out_filename(chunk.file_identifier, chunk.number)

        # do we need this chunk?
        with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
            have_tmp = tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_filename}")
            have_out = tmp_fs.exists(f"{org_chunk_tmp_path}/{chunk_out_filename}")
        if have_tmp or have_out:
            # TODO: we could check here if we have all chunks for the file
            # TODO: if all chunks, set DepositFile.state = UPLOADED
            # TODO: or maybe it doesn't matter, the DepositFile just stays REGISTERED?
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

        # Check if we have all chunks for the file
        with OSFS(
            os.path.join(settings.FILE_UPLOAD_TEMP_DIR, org_chunk_tmp_path)
        ) as org_fs:
            total_saved_size = 0
            for i in reversed(range(1, chunk.file_total_chunks + 1)):
                try:
                    saved_size = org_fs.getsize(
                        _chunk_filename(chunk.file_identifier, i)
                    )
                    total_saved_size += saved_size
                except fs.errors.ResourceNotFound:
                    return HttpResponse()
            if not total_saved_size == chunk.file_total_size:
                logger.warning(
                    f"file has all chunks but wrong total size: {chunk.file_identifier}"
                )
                return HttpResponseBadRequest()
        logger.info(f"all chunks saved for {chunk.file_identifier}")
        deposit_file.state = models.DepositFile.State.UPLOADED
        deposit_file.save()

        return HttpResponse()


@csrf_exempt
@login_required
def hashed_status(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(permitted_methods=["GET"])
    deposit_id = request.GET.get('deposit_id')
    if not deposit_id:
        return HttpResponseBadRequest()
    deposit = get_object_or_404(
        models.Deposit,
        pk=deposit_id,
        organization=get_object_or_404(models.Organization, pk=request.user.organization_id)
    )
    from functools import reduce
    deposit_files = models.DepositFile.objects.filter(deposit = deposit).values("state").annotate(files=Count("state")).order_by("state")
    total_files = reduce(lambda t, t1: t1['files'] +  t['files'], deposit_files) if len(deposit_files) > 1 else deposit_files[0]['files']
    return JsonResponse(
        {
            "hashed_files": deposit_files[2]['files'] if deposit_files and len(deposit_files) >= 3 else 0,
            "total_files": total_files,
        }
    )
