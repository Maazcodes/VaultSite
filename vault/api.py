from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404

from . import models


@login_required
def collections(request):
    org = request.user.organization
    collections = models.Collection.objects.filter(organization=org)
    return JsonResponse({
        "collections": [
            {"id": collection.pk, "name": collection.name}
            for collection in collections
        ]
    })


@login_required
def reports(request):
    org = request.user.organization
    reports = models.Report.objects.filter(collection__organization=org).order_by("-ended_at")
    return JsonResponse({
        "reports": [
            {
                "id": report.pk,
                "reportType": report.get_report_type_display(),
                "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
                "collection_name": report.collection.name,
                "collection_id": report.collection.pk
            }
            for report in reports
        ]
    })


@login_required
def collections_stats(request):
    org = request.user.organization
    collections = models.Collection.objects.filter(organization=org).annotate(
        file_count=Count("file"),
        total_size=Sum("file__size"),
        last_modified=Max('file__modified_date'),
    )
    reports = (
        models.Report.objects
            .filter(collection__organization=org, report_type=models.Report.ReportType.FIXITY)
            .order_by("-ended_at")
    )
    latest_report = reports.values("pk", "file_count", "total_size", "error_count", "ended_at").first() if len(
        reports) > 0 else {}

    return JsonResponse({
        "collections": [
            {
                "id": collection.pk,
                "time": collection.last_modified,
                "fileCount": collection.file_count,
                "totalSize": collection.total_size,
                "latestReport": reports.filter(collection__pk=collection.pk).values("pk", "file_count", "total_size",
                                                                                    "error_count", "ended_at").first(),
            }
            for collection in collections
        ],
        "latestReport": latest_report,
    })


@login_required
def reports_files(request):
    org = request.user.organization
    reports = models.Report.objects.filter(collection__organization=org).order_by("ended_at")
    return JsonResponse({
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
    })


@login_required
def collections_summary(request):
    org = request.user.organization
    collections = (
        models.Collection.objects
            .filter(organization=org)
            .annotate(file_count=Count("file"))
    )
    return JsonResponse({
        "collections": [
            {
                "id": collection.pk,
                "name": collection.name,
                "fileCount": collection.file_count,
                "regions": {
                    region: collection.file_count
                    for region in collection.target_geolocations.values_list("name", flat=True)
                },
                "avgReplication": collection.target_replication,
            }
            for collection in collections
        ]
    })


@login_required
def reports_files_by_collection(request, collection_id):
    org = request.user.organization
    collection = get_object_or_404(models.Collection, pk=collection_id)
    if collection.organization != org:
        raise Http404
    reports = models.Report.objects.filter(collection=collection)
    return JsonResponse({
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
    })


@login_required
def report_summary(request, collection_id, report_id):
    user_org = request.user.organization
    collection = get_object_or_404(models.Collection, pk=collection_id)
    if collection.organization != user_org:
        raise Http404

    report = get_object_or_404(models.Report, pk=report_id)
    if report.collection != collection:
        raise Http404

    return JsonResponse({
        "id": report.pk,
        "reportType": report.get_report_type_display(),
        "endedAt": report.ended_at.strftime("%Y-%m-%dT%H-%M-%S-000Z"),
        "fileCount": report.collection_file_count,
        "totalSize": report.collection_total_size,
        "errorCount": report.error_count,
        "regions": {
            region: report.collection_file_count
            for region in collection.target_geolocations.values_list("name", flat=True)
        },
        "fileTypes": {},
        "avgReplication": collection.target_replication
    })


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
