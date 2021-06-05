from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def collections(request):
    return JsonResponse({
        "collections": [
            {
                "id": "ARCHIVEIT-15228",
                "name": "Alex Dempsey's Public Bookmarks"
            }
        ]
    })


@login_required
def reports(request):
    return JsonResponse({
        "reports": [
            {
                "id": "2021-05-26T20-42-18-167Z",
                "collection": "ARCHIVEIT-16740"
            }
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
