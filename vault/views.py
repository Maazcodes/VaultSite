import datetime
import json
import logging
import os
import random
import time
from collections import defaultdict
from functools import reduce
from itertools import chain
from typing import Union

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from fs.osfs import OSFS

import requests

from vault import forms
from vault import models
from vault.file_management import generate_hashes, move_temp_file

logger = logging.getLogger(__name__)


def index(request):
    return redirect("dashboard")


@login_required
def dashboard(request):
    return TemplateResponse(request, "vault/dashboard.html", {})


@login_required
@csrf_exempt
def create_collection(request):
    response = {}
    if request.method == "POST":
        org = request.user.organization
        name = request.POST.get("name")
        if org:
            _collection = models.Collection.objects.filter(organization=org, name=name)
            if _collection:
                response["code"] = 0
                response["message"] = (
                    "Collection with name '" + name + "' already exists."
                )
                return return_text_report(json.dumps(response))

            new_collection = models.Collection.objects.create(
                organization=org,
                name=name,
                target_replication=org.plan.default_replication,
                fixity_frequency=org.plan.default_fixity_frequency,
            )
            new_collection.target_geolocations.set(org.plan.default_geolocations.all())
            new_collection.save()
            response["code"] = 1
            response["message"] = "Collection created Successfully."
            response["collection_id"] = new_collection.pk
    return return_text_report(json.dumps(response))


@login_required
def collections(request):
    org = request.user.organization
    if request.method == "POST":
        form = forms.CreateCollectionForm(request.POST)
        if org and form.is_valid():
            new_collection = models.Collection.objects.create(
                organization=org,
                name=form.cleaned_data["name"],
                target_replication=org.plan.default_replication,
                fixity_frequency=org.plan.default_fixity_frequency,
            )
            new_collection.target_geolocations.set(org.plan.default_geolocations.all())
            new_collection.save()
            return redirect("collections")

        return redirect("dashboard")

    form = forms.CreateCollectionForm()
    org_root = str(org.tree_node_id)
    _collections = models.TreeNode.objects.raw(
        """
    select coll.id as collection_id,
           NULL as last_fixity_report,
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
    # _collections = models.Collection.objects.filter(organization=org).annotate(
    #     total_size=Sum("file__size"),
    #     file_count=Count("file"),
    #     last_modified=Max("file__modified_date"),
    # )
    return TemplateResponse(
        request,
        "vault/collections.html",
        {
            "collections": _collections,
            "form": form,
        },
    )


@login_required
def collection(request, collection_id):
    org_id = request.user.organization_id
    _collection = get_object_or_404(
        models.Collection, organization_id=org_id, pk=collection_id
    )
    if request.method == "POST":
        form = forms.EditCollectionSettingsForm(request.POST)
        if form.is_valid():
            _collection.target_replication = form.cleaned_data["target_replication"]
            _collection.fixity_frequency = form.cleaned_data["fixity_frequency"]
            _collection.target_geolocations.set(
                form.cleaned_data["target_geolocations"]
            )
            _collection.save()
            messages.success(request, "Collection settings updated.")

    collection_stats = models.TreeNode.objects.filter(
        path__descendant=_collection.tree_node.path
    ).aggregate(
        file_count=Coalesce(Count("pk"), 0),
        total_size=Coalesce(Sum("size"), 0),
        last_modified=Max("modified_at"),
    )
    collection_stats["file_count"] -= 1  # Collection's TreeNode included in count
    form = forms.EditCollectionSettingsForm(
        initial=(
            {
                "target_replication": _collection.target_replication,
                "fixity_frequency": _collection.fixity_frequency,
                "target_geolocations": _collection.target_geolocations.all(),
            }
        )
    )
    reports = models.Report.objects.filter(collection=_collection.pk)
    deposits = models.Deposit.objects.filter(collection=_collection).annotate(
        file_count=Count("files"),
        total_size=Coalesce(Sum("files__size"), 0),
        error_count=Count("pk", filter=Q(files__state=models.DepositFile.State.ERROR)),
    )

    def event_sort(event: Union[models.Deposit, models.Report]):
        if isinstance(event, models.Deposit):
            return event.registered_at

        return event.started_at

    events = sorted(chain(deposits, reports), key=event_sort, reverse=True)

    return TemplateResponse(
        request,
        "vault/collection.html",
        {
            "collection": _collection,
            "collection_stats": collection_stats,
            "collection_id": str(_collection.id),
            "form": form,
            "events": events,
        },
    )


@login_required
def report(request, report_id):
    org = request.user.organization
    _report = get_object_or_404(models.Report, pk=report_id)
    if _report.collection.organization != org:
        raise Http404
    return TemplateResponse(
        request,
        "vault/report.html",
        {
            "collection": _report.collection,
            "collection_id": str(_report.collection.id),
            "report_id": str(_report.id),
            "report": _report,
            "page_number": 1,
        },
    )


@login_required
def deposit_report(request, deposit_id):
    org_id = request.user.organization_id
    _deposit = get_object_or_404(models.Deposit, pk=deposit_id, organization_id=org_id)
    _collection = _deposit.collection
    deposit_files = _deposit.files.all()
    file_count = len(deposit_files)
    total_size = 0
    state_count = defaultdict(int)
    state_sizes = defaultdict(float)
    for deposit_file in deposit_files:
        total_size += deposit_file.size
        state_count[deposit_file.state] += 1
        state_sizes[deposit_file.state] += deposit_file.size
    processed_states = (
        models.DepositFile.State.HASHED,
        models.DepositFile.State.REPLICATED,
    )
    processed_count = sum(state_count[state] for state in processed_states)
    processed_size = sum(state_sizes[state] for state in processed_states)
    if _deposit.state in (models.Deposit.State.REPLICATED, models.Deposit.State.HASHED):
        display_state = "Complete"
    elif _deposit.state == models.Deposit.State.COMPLETE_WITH_ERRORS:
        display_state = "Complete with Errors"
    elif _deposit.state == models.Deposit.State.UPLOADED:
        display_state = "Processing"
    elif _deposit.state == models.Deposit.State.REGISTERED:
        display_state = "Registered"
    else:
        display_state = "Error"
    return TemplateResponse(
        request,
        "vault/deposit_report.html",
        {
            "collection": _collection,
            "deposit": _deposit,
            "deposit_files": deposit_files,
            "file_count": file_count,
            "total_size": total_size,
            "state_count": state_count,
            "state_sizes": state_sizes,
            "processed_count": processed_count,
            "processed_size": processed_size,
            "display_state": display_state,
        },
    )


@login_required
def fixity_report(request, report_id):
    """Display a fixity report."""
    org_id = request.user.organization_id
    rep = get_object_or_404(
        models.Report.objects.select_related("collection"),
        pk=report_id,
        collection__organization_id=org_id,
        report_type=models.Report.ReportType.FIXITY,
    )
    coll = rep.collection
    return TemplateResponse(
        request,
        "vault/fixity_report.html",
        {
            "collection": coll,
            "report": rep,
        },
    )


@login_required
def deposit(request):
    return redirect("deposit_flow")


def create_attribs_dict(request):
    retval = {}
    retval["comment"] = request.POST.get("comment", "")
    retval["client"] = request.POST.get("client", "")
    retval["collection"] = request.POST.get("collection", None)
    retval["username"] = request.META.get("REMOTE_USER", "")
    retval["organization"] = request.user.organization.id
    retval["orgname"] = request.user.organization.name
    try:
        pk_id = retval["collection"]
        retval["collname"] = models.Collection.objects.get(pk=pk_id).name
    except:  # pylint: disable=bare-except
        retval["collname"] = ""
    return retval


def format_doaj_json(attribs):
    attr = {
        "files": {
            "name": attribs["name"],
            "sha256": attribs["sha256sumV"],
        }
    }
    return json.dumps(attr)


# Format all the string data from the request as a JSON blob
def _format_filelist_json(request):
    collpk = request.POST.get("collection", None)
    try:
        collname = models.Collection.objects.get(pk=collpk).name
    except:  # pylint: disable=bare-except
        collname = ""
    org = request.user.organization.name
    dirs = request.POST.get("directories", "")
    shasums = request.POST.get("shasums", "")
    sizes = request.POST.get("sizes", "")

    request_list = {
        "filelist": {
            "org": org,
            "collection": collname,
            "directories": dirs,
            "sha256sums": shasums,
            "sizes": sizes,
        }
    }

    return json.dumps(request_list)


def return_doaj_report(attribs):
    data = format_doaj_json(attribs)
    return JsonResponse(data)


def return_text_report(data):
    return JsonResponse(data)


def return_total_used_quota(_collections=None, organization=None):
    if not _collections:
        _collections = models.Collection.objects.filter(
            organization=organization
        ).annotate(
            file_count=Count("file"),
            total_size=Sum("file__size"),
        )
        if not _collections:
            return 0
    return reduce(
        lambda x, y: x + y,
        list(
            map(lambda x: x.total_size if x.total_size is not None else 0, _collections)
        ),
    )


def return_reload_deposit_web(request):
    _collections = models.Collection.objects.filter(
        organization=request.user.organization
    ).annotate(
        file_count=Count("file"),
        total_size=Sum("file__size"),
    )
    form = forms.FileFieldForm(_collections)
    total_used_quota = return_total_used_quota(_collections=_collections)
    return TemplateResponse(
        request,
        "vault/deposit_web.html",
        {
            "collections": _collections,
            "filenames": "",
            "form": form,
            "total_used_quota": total_used_quota,
        },
    )


def validate_collection(request):
    user_org = request.user.organization
    if not user_org:
        return redirect("dashboard")

    collection_id = request.POST.get("collection", None)
    _collection = get_object_or_404(models.Collection, pk=collection_id)
    if _collection.organization != user_org:
        raise Http404
    return collection_id


@login_required
@csrf_exempt
def deposit_compat(request):
    """
    Compatibility deposit for "curl-DOAJ.sh" and similar upload methods, using
    flow/deposit workflow on the server side.

    This endpoint succeeds, if all the required fields are supplied. It does not
    fail, if extra, unused fields are received.

    If a file with the same name is pushed to the same organization and
    collection, there is no logic here to handle force overwrites, we simple
    create a new deposit. Duplication may or may not be solved by successive
    layers of vault.

    Expected to work with: c59ae05:vault/utilities/curl-DOAJ.sh and https://is.gd/OLydc8

    curl ...
        --user    $USER                                 # admin:admin
        --form    client=DOAJ_CLI
        --form    size=$size_bytes                      # file size
        --form    directories=$filepath                 # file path (no directory, actually)
        --form    organization=$ORGANIZATION_ID         # 1
        --form    collection=$COLLECTION_ID             # 2
        --form    file_field=$EMPTY                     # "{}"
        --form    dir_field=@$filepath                  # == file data
        --form    webkitRelativePath=$filepath          # == directories
        --form    sha256sum=$SHA_256_SUM                # SHA256
        --cookie  $COOKIEJAR --cookie-jar $COOKIEJAR    # ...
        --referer $UPLOADER                             # URL of upload form
        $UPLOADER'                                      # URL of upload form

    We need to accept curl requests coming from "curl-DOAJ.sh" - on success, a
    JSON response is sent back (per curl call, one per file); pretty-printed:

        {
          "files": {
            "name": "README.md",
            "sha256": "9d9b266cf8247e0ad868a717c99b73ab11ce6f7b7b3a44b39f1c695fdd41942e"
          }
        }

    The "curl-DOAJ.sh" script treats a non-zero exit code from curl as an
    error; but it does not check HTTP status codes (e.g. no --fail or
    --fail-with-body); it also treats an zero length response body as an error.
    For compatibility, on failure, we return a suitable HTTP status code, but keep a
    zero length body (even though some diagnostics would be nice).

    Open question(s):

    * [ ] [reporting] Do we need a DepositReport here? Since "curl-DOAJ.sh" issues multiple
          requests to this endpoint, we do not know how many files we need to
          consider for a single deposit. Or should be just create a report and
          overwrite/update on each request?
    * [ ] [force overwrite] How about the client uploading a new file with the
          same name to the same organization/collection? We should overwrite, but how
          can we detect that? Uploads go to a few stages before they end up in
          "storage" and treenode tables are updated? If a user uploads two different
          files with the same name in quick succession, how do we handle that?
    """
    # pylint: disable=too-many-return-statements,too-many-locals,too-many-branches
    if request.method != "POST":
        return HttpResponse(status=405)

    if request.POST.get("client") != "DOAJ_CLI":
        # Limit usage to the DOAJ client for now. Remove this to allow other
        # clients to use this endpoint.
        return HttpResponse(status=501)

    # This is like "validate_collection", but we use zero-body responses (so
    # curl-DOAJ.sh considers errors here as failure).
    if not request.user.organization:
        return HttpResponse(status=400)
    collection_id = request.POST.get("collection", None)
    if not collection_id:
        return HttpResponse(status=400)
    try:
        _collection = models.Collection.objects.get(pk=collection_id)
        if _collection.organization != request.user.organization:
            return HttpResponse(status=400)
    except models.Collection.DoesNotExist:
        return HttpResponse(status=400)

    # "curl-DOAJ.sh" uses "dir_field", whereas doaj upload python script
    # (https://is.gd/OLydc8) uses "file_field".
    filekey = "file_field" if "file_field" in request.FILES else "dir_field"

    filenames = request.POST.get("directories", "").split(",")
    if len(filenames) == 0:
        return HttpResponse(status=400)
    filename = filenames[0]
    try:
        sha256sum = request.POST["sha256sum"]
        _ = request.FILES[filekey]
    except (ValueError, KeyError):
        return HttpResponse(status=400)

    # Web uploads use https://github.com/flowjs/flow.js/ for uploads, using
    # flow identifiers; we only have a dummy identifier: unique and can be
    # generated with stdlib. Example: 'compat-1646859646-28990082667'
    dummy_flow_identifier = f"compat-{int(time.time())}-{random.randrange(1e10, 9e10)}"

    # Write out file so that "process_chunked_files.py" will pick it up. We use
    # chunk subdir, but we only really have one chunk per file.
    with OSFS(settings.FILE_UPLOAD_TEMP_DIR) as tmp_fs:
        chunk_path = os.path.join(str(request.user.organization.id), "chunks")
        with tmp_fs.makedirs(chunk_path, recreate=True) as chunk_fs:
            temp_fname = f"{dummy_flow_identifier}.uploading"
            fout = chunk_fs.openbin(temp_fname, mode="a")
            for chunk in request.FILES[filekey].chunks():
                fout.write(chunk)
            fout.flush()
            os.fsync(fout.fileno())
            fout.close()
            # the vault/utilities/process_chunked_files.py will look for
            # [flow-id]-[#].tmp files
            dst = f"{dummy_flow_identifier}-1.tmp"
            chunk_fs.move(temp_fname, dst, overwrite=True)
            # DOAJ has confirmed they are not providing `size`, so we substitute.
            size = chunk_fs.getsize(dst)
            if sha256sum != chunk_fs.hash(dst, "sha256"):
                return HttpResponse(status=409)  # CONFLICT

    # > I think we should make a new Deposit for every call to your endpoint;
    # so 1 new Deposit and 1 new DepositFile
    _deposit = models.Deposit.objects.create(
        organization_id=request.user.organization.id,
        collection_id=collection_id,
        user=request.user,
        state=models.DepositFile.State.UPLOADED,
        uploaded_at=timezone.now(),
    )
    deposit_file_form = forms.RegisterDepositFileForm(
        {
            "flow_identifier": dummy_flow_identifier,
            "name": os.path.basename(filename),
            # despite the name, "relative_path" can be an absolute path as
            # well, depending on what is passed to the upload script.
            "relative_path": filename,
            "size": size,
        }
    )
    if not deposit_file_form.is_valid():
        return HttpResponse(status=400)
    models.DepositFile.objects.create(
        deposit=_deposit,
        **deposit_file_form.cleaned_data,
        state=models.DepositFile.State.UPLOADED,
        uploaded_at=timezone.now(),
    )
    if settings.SLACK_WEBHOOK:
        try:
            org = request.user.organization
            msg = f"<@avdempsey> {org.name} used the new deposit uploader."
            requests.post(settings.SLACK_WEBHOOK, data=json.dumps({"text": msg}))
        except Exception:  # pylint: disable=broad-except
            pass
    return JsonResponse(
        {
            "files": {
                "name": filename,
                "sha256": sha256sum,
            },
        }
    )


#
# @csrf_exempt required for curl, for example.
#
@login_required
@csrf_exempt
def deposit_web(request):  # pylint: disable=too-many-statements,too-many-locals
    if request.method != "POST":
        return return_reload_deposit_web(request)

    collection_id = validate_collection(request)
    get_object_or_404(models.Collection, pk=collection_id)

    reply = []
    logger.info(_format_filelist_json(request))
    # Accumulate request global attributes
    # Possibly to be overwritten by file iteration below
    attribs = create_attribs_dict(request)

    directories = request.POST.get("directories", "")
    directories = directories.split(",")

    shasums = request.POST.get("shasums", "")
    shasums = shasums.split(",")

    sizes = request.POST.get("sizes", "")
    sizes = sizes.split(",")

    validated_total_size = 0
    validated_file_count = 0

    inputs = ["file_field", "dir_field"]

    for field in inputs:
        files = request.FILES.getlist(field)
        for file in files:
            tempfile = file.temporary_file_path()
            attribs["sizeV"] = file.size
            attribs["tempfile"] = tempfile
            hashes = generate_hashes(tempfile)
            attribs["md5sumV"] = hashes["md5"]
            attribs["sha1sumV"] = hashes["sha1"]
            attribs["sha256sumV"] = hashes["sha256"]
            attribs["name"] = directories.pop(0)

            try:
                attribs["sha256sum"] = shasums.pop(0)
            except IndexError:
                attribs["sha256sum"] = "0" * 64
                logger.error("sha256sum for %s not in shasums list", attribs["name"])
            try:
                attribs["size"] = sizes.pop(0)
            except IndexError:
                attribs["size"] = 0
                logger.error("size for %s not in sizes list", attribs["name"])

            move_temp_file(request, attribs)
            logger.info(json.dumps(attribs))
            reply.append(json.dumps(attribs))
            validated_total_size += file.size
            validated_file_count += 1

    _collection = (
        models.Collection.objects.filter(pk=collection_id)
        .annotate(
            file_count=Count("file"),
            total_size=Sum("file__size"),
        )
        .first()
    )

    # TODO: get actual started_at value so we can keep track of upload duration
    models.Report.objects.create(
        collection=_collection,
        report_type=models.Report.ReportType.DEPOSIT,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        ended_at=datetime.datetime.now(datetime.timezone.utc),
        total_size=validated_total_size,
        file_count=validated_file_count,
        collection_total_size=_collection.total_size,
        collection_file_count=_collection.file_count,
        error_count=0,
        missing_location_count=0,
        mismatch_count=0,
        avg_replication=_collection.target_replication,
    )

    _report = (
        models.Report.objects.filter(collection=_collection.pk)
        .order_by("-ended_at")
        .first()
    )
    if _report:
        reply.append({"report_id": _report.id})

    total_used_quota = return_total_used_quota(organization=request.user.organization)
    reply.append({"total_used_quota": total_used_quota})

    if settings.SLACK_WEBHOOK:
        try:
            org = request.user.organization
            msg = f"<@avdempsey> {org.name} used the old uploader."
            requests.post(settings.SLACK_WEBHOOK, data=json.dumps({"text": msg}))
        except Exception:  # pylint: disable=broad-except
            pass

    if attribs.get("client", None) == "DOAJ_CLI":
        return return_doaj_report(attribs)

    if reply:
        # HOW TO FAKE A 408? - Set this to True!
        debug_408 = False
        if debug_408:
            response = HttpResponse("Timeout!")
            response["status"] = 408
            return response

        return return_text_report(json.dumps(reply))

    return return_reload_deposit_web(request)


@login_required
def deposit_cli(request):
    return TemplateResponse(request, "vault/deposit_cli.html", {})


@login_required
def deposit_mail(request):
    return TemplateResponse(request, "vault/deposit_mail.html", {})


@login_required
def deposit_ait(request):
    return TemplateResponse(request, "vault/deposit_ait.html", {})


@login_required
def administration(request):
    return redirect("administration_plan")


@login_required
def administration_plan(request):
    org = request.user.organization
    if org:
        plan = org.plan
        return TemplateResponse(
            request,
            "vault/administration_plan.html",
            {
                "organization": org,
                "plan": plan,
            },
        )

    return redirect("dashboard")


@login_required
def administration_users(request):
    return TemplateResponse(request, "vault/administration_users.html", {})


@login_required
def administration_help(request):
    return TemplateResponse(request, "vault/administration_help.html", {})


@login_required
def deposit_flow(request):
    org = request.user.organization
    colls = models.Collection.objects.filter(organization=org)
    org_root = org.tree_node
    if org_root:
        total_used_quota = models.TreeNode.objects.filter(
            path__descendant=org_root.path
        ).aggregate(total=Coalesce(Sum("size"), 0))["total"]
    else:
        total_used_quota = 0
    collection_form = forms.RegisterDepositForm(collections=colls)
    return TemplateResponse(
        request,
        "vault/deposit_flow.html",
        {
            "collection_form": collection_form,
            "collections": colls,
            "total_used_quota": total_used_quota,
        },
    )


@login_required
def render_file_view(request, path):
    org = request.user.organization
    output_path = ""
    if not path:
        path = org.name
    else:
        path = f"{org.name}/{path}"
    parent = org.tree_node
    split_path = path.split("/")[1:]
    for node in split_path:
        try:
            # this lookup assumes there is only one child node with a given name
            child = get_object_or_404(models.TreeNode, name=node, parent=parent)
            output_path = f"{output_path}/{child.name}"
            parent = child
        except Http404:
            return TemplateResponse(
                request, "vault/files_view.html", {"status": 404}, status=404
            )
        except MultipleObjectsReturned:
            logger.error("multiple TreeNodes returned for %s", path)
            return TemplateResponse(
                request, "vault/files_view.html", {"status": 404}, status=404
            )
    children = parent.children.all()
    return TemplateResponse(
        request,
        "vault/files_view.html",
        {"items": children, "path": output_path},
    )


@login_required
def render_web_components_file_view(request, path):
    path = path.lstrip("/")
    parent = request.user.organization.tree_node
    for node in path.split("/") if path else ():
        child = get_object_or_404(models.TreeNode, name=node, parent=parent)
        parent = child
    node = parent
    org_node = request.user.organization.tree_node
    org_id = org_node.id
    node_path_list = node.path.split(".")
    parent_child_dict = {
        node.id: []
        for node in models.TreeNode.objects.filter(id__in=node_path_list)
        # Get all the objects from TreeNode whose id matches in node path list
    }

    for child in models.TreeNode.objects.filter(parent__in=node_path_list).exclude(
        node_type="FILE"
    ):
        # Get all the objects from TreeNode whose parent id matches in node path list
        parent_child_dict[child.parent_id].append(child)

    org = request.user.organization
    colls = models.Collection.objects.filter(organization=org)
    node_collections = {c.tree_node_id: c.id for c in colls}

    node_dict = {
        "id": node.id,
        "node_type": node.node_type,
        "parent": node.parent.id if node.parent else 0,
        "name": node.name,
        "uploaded_at": str(node.uploaded_at),
        "size": node.size if node.size else "-",
        "path": node.path,
    }
    return TemplateResponse(
        request,
        "vault/web_components_files_view.html",
        {
            "node_collections": node_collections,
            "node": node_dict,
            "path": f"/{path}",
            "org_id": org_id,
            "parent_child_dict": parent_child_dict,
        },
    )
