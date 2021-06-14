from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Max
from django.http import JsonResponse

from . import models

@login_required
def collections(request):
    if request.GET.get("demo"):
        return JsonResponse({
            "collections": [
                {
                    "id": "ARCHIVEIT-15228",
                    "name": "Alex Dempsey's Public Bookmarks"
                }
            ]
        })

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
    if request.GET.get("demo"):
        return JsonResponse({
            "reports": [
                {
                    "id": "2021-05-26T20-42-18-167Z",
                    "collection": "ARCHIVEIT-16740"
                }
            ]
        })

    org = request.user.organization
    reports = models.Report.objects.filter(collection__organization=org).order_by("-ended_at")
    return JsonResponse({
        "reports": [
            {
                "id": report.ended_at.strftime("%B %-d, %Y"),
                "collection": report.collection.name
            }
            for report in reports
        ]
    })


@login_required
def collections_stats(request):
    return JsonResponse({
        "collections": [
            {
                "id": "ARCHIVEIT-15228",
                "latestReport": "2021-05-25T07-23-41-450Z",
                "time": "2021-05-25T09:26:30.564Z",
                "fileCount": 46513,
                "totalSize": 4732002614004,
                "errorCount": 1
            }
        ]
    })

    # org = request.user.organization
    # collection = models.Collection.objects.filter(organization=org).annotate(
    #     file_count=Count("file"),
    #     total_size=Sum("file__size"),
    #     last_report=Max('report__ended_at'),
    # )


@login_required
def reports_files(request):
    return JsonResponse({
        "reports": [
            {
                "id": "2021-05-14T11-44-51-494Z",
                "collection": "ARCHIVEIT-15228",
                "fileCount": 46335
            }
        ]
    }
    )


@login_required
def collections_summary(request):
    return JsonResponse({
        "collections": [
            {
                "id": "ARCHIVEIT-15228",
                "latestReport": "2021-05-25T07-23-41-450Z",
                "fileCount": 46513,
                "regions": {
                    "us-west-1": 46513,
                    "us-west-2": 46513
                },
                "fileTypes": {
                    "WARC": 46488,
                    "ARC": 25
                },
                "avgReplication": 3.0
            }
        ]
    })


@login_required
def reports_files_by_collection(request, collection_id):
    return JsonResponse({
        "reports": [
            {
                "id": "2021-05-14T11-44-51-494Z",
                "collection": "ARCHIVEIT-15228",
                "fileCount": 46335
            }
        ]
    })


@login_required
def report_summary(request, collection_id, report_id):
    return JsonResponse({
        "id": "2021-05-26T20-42-18-167Z",
        "fileCount": 148,
        "totalSize": 151653723502,
        "errorCount": 19,
        "regions": {
            "us-west-1": 148,
            "us-west-2": 148
        },
        "fileTypes": {
            "WARC": 129,
            "WAT": 19
        },
        "avgReplication": 3.0
    })


@login_required
def report_files(request, collection_id, report_id):
    return JsonResponse({
        "files": [
            {
                "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz",
                "checkTime": "2021-05-26T20:42:35.696Z",
                "initialCheckTime": "2021-05-25T06:19:56.176Z",
                "previousCheckTime": "2021-05-25T06:49:35.238Z",
                "size": 22381003,
                "success": True,
                "checksums": [
                    "md5:365fa1c3234a7afc0f2a728df845f0dd",
                    "sha1:b200c07d7cf512bb157a826b2cff0fc9cc9307f6",
                    "sha256:c53b2d161cb37ee21ba166e1ad66aa0811c05d5a6781fa6a3030cd8eb2d1c805"
                ],
                "sources": [
                    {
                        "source": "PBOX",
                        "region": "us-west-1",
                        "type": "prior"
                    },
                    {
                        "source": "AIT",
                        "region": "us-west-2",
                        "type": "prior"
                    },
                    {
                        "source": "PBOX",
                        "region": "us-west-1",
                        "type": "generated",
                        "location": "https://archive.org/serve/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817-00000/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz"
                    },
                    {
                        "source": "HDFS",
                        "region": "us-west-2",
                        "type": "generated",
                        "location": "hdfs:///search/ait/10923/arcs/ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000.warc.gz"
                    }
                ]
            },
            {
                "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674475-20180817084026334-00000_warc.wat.gz",
                "checkTime": "2021-05-26T20:42:36.163Z",
                "initialCheckTime": "2021-05-25T06:19:43.400Z",
                "previousCheckTime": "2021-05-25T06:49:33.703Z",
                "size": 3050297,
                "success": False,
                "checksums": [
                    "md5:754ba6eefe7336d812aa1681ac5f05e6",
                    "sha1:61fae3fc51867e15466b8dff4bece42835fc3278",
                    "sha256:65f3d1edfe81df15f591df2d4080379dfc9c71e150983320870095964ab3f705"
                ],
                "sources": [
                    {
                        "source": "PBOX",
                        "region": "us-west-1",
                        "type": "prior"
                    },
                    {
                        "source": "AIT",
                        "region": "us-west-2",
                        "type": "prior"
                    },
                    {
                        "source": "HDFS",
                        "region": "us-west-2",
                        "type": "prior"
                    }
                ],
                "missingLocations": [
                    "HDFS",
                    "archive.org"
                ]
            },
            {
                "filename": "ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz",
                "checkTime": "2021-05-26T20:42:22.814Z",
                "initialCheckTime": "2021-05-25T06:19:33.990Z",
                "previousCheckTime": "2021-05-25T06:49:35.124Z",
                "size": 6866346,
                "success": True,
                "checksums": [
                    "md5:f7334b620ebb46442d14875452bf3d80",
                    "sha1:818a693ad93ec43c65ca23b0ec294cf5bdf5e8aa",
                    "sha256:2052e8ce69faf7b5463b8f80df3965348542af6c681357c23d786cfd8d3aaaf1"
                ],
                "sources": [
                    {
                        "source": "PBOX",
                        "region": "us-west-1",
                        "type": "prior"
                    },
                    {
                        "source": "AIT",
                        "region": "us-west-2",
                        "type": "prior"
                    },
                    {
                        "source": "PBOX",
                        "region": "us-west-1",
                        "type": "generated",
                        "location": "https://archive.org/serve/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817-00000/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz"
                    },
                    {
                        "source": "HDFS",
                        "region": "us-west-2",
                        "type": "generated",
                        "location": "hdfs:///search/ait/10923/arcs/ARCHIVEIT-16740-ONE_TIME-JOB674476-20180817084425211-00000.warc.gz"
                    }
                ]
            }
        ]
    })
