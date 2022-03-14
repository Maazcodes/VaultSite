"""API view functions for use with the Hadoop Fixitter API"""

import json
import logging
import os
import requests

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import MultipleObjectsReturned
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt

from vault import models

logger = logging.getLogger(__name__)


FIXITY_REPORT_JSON_VERSION = 1


def _api_key_required(action):
    def wrapper(request, *args, **kwargs):
        if request.GET.get("api_key", "") != settings.FIXITY_API_KEY:
            return HttpResponseForbidden("Unauthorized.")
        return action(request, *args, **kwargs)

    return wrapper


def _locations(url_prefix, org_id, file):
    accum = []
    org_tmp_path = str(org_id)
    shafs_root = os.path.join(settings.SHADIR_ROOT, org_tmp_path)
    shafs_path = os.path.join(shafs_root, file.sha256_sum)

    if os.path.exists(shafs_path):
        accum.append(f"{url_prefix}/shafs/{org_id}/{file.sha256_sum}")
    if file.pbox_path and "/" in file.pbox_path:
        accum.append(f"https://archive.org/download/{file.pbox_path}")

    return accum


@_api_key_required
def list_files(request, org_id, path):
    org = get_object_or_404(models.Organization, id=org_id)
    parent = org.tree_node
    path = path.strip("/ ")
    split_path = path.split("/") if path else []

    for node in split_path:
        try:
            # this lookup assumes there is only one child node with a given name
            child = get_object_or_404(models.TreeNode, name=node, parent=parent)
            parent = child
        except MultipleObjectsReturned:
            error_msg = f"multiple TreeNodes returned for {path}"
            logger.error(error_msg)
            return HttpResponseNotFound(error_msg)

    files = parent.children.filter(node_type="FILE")
    children = parent.children.exclude(node_type="FILE")
    name_prefix = "/".join(split_path[1:])
    name_prefix = name_prefix + "/" if name_prefix else ""
    url_path = path + "/" if path else ""
    url_prefix = request.build_absolute_uri().split("/files/", 1)[0]

    return JsonResponse(
        {
            "files": [
                {
                    "id": "treeNode-" + str(file.id),
                    "name": file.name,
                    "filename": name_prefix + file.name,
                    "size": file.size,
                    "time": file.uploaded_at,
                    "checksums": {
                        "md5": file.md5_sum,
                        "sha1": file.sha1_sum,
                        "sha256": file.sha256_sum,
                    },
                    "locations": _locations(url_prefix, org_id, file),
                }
                for file in files
            ],
            "children": {
                child.name: f"{url_prefix}/files/{org_id}/{url_path}{child.name}"
                for child in children
            },
        }
    )


@_api_key_required
def stream_from_shafs(request, org_id, sha256_sum):
    org_tmp_path = str(org_id)
    shafs_root = os.path.join(settings.SHADIR_ROOT, org_tmp_path)
    shafs_path = os.path.join(shafs_root, sha256_sum)

    if os.path.exists(shafs_path):
        return FileResponse(open(shafs_path, "rb"))

    return HttpResponseNotFound(f"{org_id}/{sha256_sum} not found.")


def run_collection(request, org, collection, token):
    collection_name = f"{org.id}_{collection.name}"
    base = settings.FIXITTER_URL_PREFIX
    api_key = settings.FIXITTER_API_KEY
    fixitter_url = f"{base}/run/VaultFixityCheck?apikey={api_key}"
    url_prefix = request.build_absolute_uri().split("/run/", 1)[0]
    file_list_url = f"{url_prefix}/files/{org.id}/{collection.name}"
    postback_url = f"{url_prefix}/postback/{org.id}/{collection.id}/{token}"
    response = requests.post(
        fixitter_url,
        json={
            "collection": collection_name,
            "fileListUrl": file_list_url,
            "postBackUrl": postback_url,
        },
    )

    return HttpResponse(
        content=response.content,
        status=response.status_code,
        content_type=response.headers["Content-Type"],
    )


@_api_key_required
def run_collection_name(request, org_id, collection_name, token):
    org = get_object_or_404(models.Organization, id=org_id)
    collection = get_object_or_404(
        models.Collection, organization=org, name=collection_name
    )
    return run_collection(request, org, collection, token)


@_api_key_required
def run_collection_id(request, org_id, collection_id, token):
    org = get_object_or_404(models.Organization, id=org_id)
    collection = get_object_or_404(
        models.Collection, organization=org, id=collection_id
    )
    return run_collection(request, org, collection, token)


@csrf_exempt
@_api_key_required
def postback(request, org_id, collection_id, token):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        collection = models.Collection.objects.get(
            pk=collection_id,
            organization_id=org_id,
        )
    except models.Collection.DoesNotExist:
        return HttpResponseNotFound()

    body = json.loads(request.body)
    report_url = body["reportUrl"]
    api_key = settings.FIXITTER_API_KEY
    response = requests.get(report_url, params={"apikey": api_key, "format": "json"})
    report_json = response.json()
    report_errors = report_json.get("errors", {})

    # pylint: disable=invalid-name
    TODO = 0

    report = models.Report(
        collection=collection,
        report_type=models.Report.ReportType.FIXITY,
        started_at=report_json["startTime"],
        ended_at=report_json["endTime"],
        total_size=report_json["totalSize"],
        file_count=report_json["fileCount"],
        collection_total_size=TODO,
        collection_file_count=TODO,
        error_count=report_json["errorCount"],
        missing_location_count=report_errors.get("missingLocationCount", 0),
        mismatch_count=report_errors.get("mismatchCount", 0),
        avg_replication=TODO,
        report_json=report_json,
        report_json_version=FIXITY_REPORT_JSON_VERSION,
    )

    report.save()

    return HttpResponse(status=202)  # 202 = Accepted
