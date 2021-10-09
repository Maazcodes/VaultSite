import datetime
import json
import logging
from functools import reduce

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Max, Sum, Count
from django.db.models.functions import Coalesce
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt

from vault import forms
from vault import models
from vault.file_management import generateHashes, move_temp_file

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
            collection = models.Collection.objects.filter(organization=org, name=name)
            if collection:
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
        else:
            return redirect("dashboard")
    else:
        form = forms.CreateCollectionForm()
        org_root = str(org.tree_node_id)
        collections = models.TreeNode.objects.raw(
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
        # collections = models.Collection.objects.filter(organization=org).annotate(
        #     total_size=Sum("file__size"),
        #     file_count=Count("file"),
        #     last_modified=Max("file__modified_date"),
        # )
        return TemplateResponse(
            request,
            "vault/collections.html",
            {
                "collections": collections,
                "form": form,
            },
        )


@login_required
def collection(request, collection_id):
    org = request.user.organization
    if request.method == "POST":
        form = forms.EditCollectionSettingsForm(request.POST)
        collection = models.Collection.objects.get(pk=collection_id)
        if form.is_valid() and collection.organization == org:
            collection.target_replication = form.cleaned_data["target_replication"]
            collection.fixity_frequency = form.cleaned_data["fixity_frequency"]
            collection.target_geolocations.set(form.cleaned_data["target_geolocations"])
            collection.save()
            messages.success(request, "Collection settings updated.")

    collection = get_object_or_404(
        models.Collection, organization=org, pk=collection_id
    )
    collection_stats = models.TreeNode.objects.filter(
        path__descendant=collection.tree_node.path
    ).aggregate(
        file_count=Coalesce(Count("*"), 0),
        total_size=Coalesce(Sum("size"), 0),
        last_modified=Max("modified_at"),
    )
    collection_stats["file_count"] -= 1
    # collection = (
    #     models.Collection.objects.filter(organization=org, pk=collection_id)
    #     .annotate(
    #         file_count=Count("file"),
    #         total_size=Sum("file__size"),
    #         last_modified=Max("file__modified_date"),
    #     )
    #     .first()
    # )
    form = forms.EditCollectionSettingsForm(
        initial=(
            {
                "target_replication": collection.target_replication,
                "fixity_frequency": collection.fixity_frequency,
                "target_geolocations": collection.target_geolocations.all(),
            }
        )
    )
    reports = models.Report.objects.filter(collection=collection.pk).order_by(
        "-ended_at"
    )
    return TemplateResponse(
        request,
        "vault/collection.html",
        {
            "collection": collection,
            "collection_stats": collection_stats,
            "form": form,
            "reports": reports,
        },
    )


@login_required
def report(request, report_id):
    org = request.user.organization
    report = get_object_or_404(models.Report, pk=report_id)
    if report.collection.organization != org:
        raise Http404
    return TemplateResponse(
        request,
        "vault/report.html",
        {
            "collection": report.collection,
            "report": report,
            "page_number": 1,
        },
    )


@login_required
def deposit(request):
    return redirect("deposit_flow")


def create_attribs_dict(request):
    retval = dict()
    retval["comment"] = request.POST.get("comment", "")
    retval["client"] = request.POST.get("client", "")
    retval["collection"] = request.POST.get("collection", None)
    retval["username"] = request.META.get("REMOTE_USER", "")
    retval["organization"] = request.user.organization.id
    retval["orgname"] = request.user.organization.name
    try:
        pk_id = retval["collection"]
        retval["collname"] = models.Collection.objects.get(pk=pk_id).name
    except:
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
def format_filelist_json(request):
    collpk = request.POST.get("collection", None)
    try:
        collname = models.Collection.objects.get(pk=collpk).name
    except:
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
    return HttpResponse(data, content_type="application/json")


def return_text_report(data):
    return HttpResponse(data, content_type="application/json")


def return_total_used_quota(collections=None, organization=None):
    if not collections:
        collections = models.Collection.objects.filter(
            organization=organization
        ).annotate(
            file_count=Count("file"),
            total_size=Sum("file__size"),
        )
        if not collections:
            return 0
    return reduce(
        lambda x, y: x + y,
        list(
            map(lambda x: x.total_size if x.total_size is not None else 0, collections)
        ),
    )


def return_reload_deposit_web(request):
    collections = models.Collection.objects.filter(
        organization=request.user.organization
    ).annotate(
        file_count=Count("file"),
        total_size=Sum("file__size"),
    )
    form = forms.FileFieldForm(collections)
    total_used_quota = return_total_used_quota(collections=collections)
    return TemplateResponse(
        request,
        "vault/deposit_web.html",
        {
            "collections": collections,
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
    collection = get_object_or_404(models.Collection, pk=collection_id)
    if collection.organization != user_org:
        raise Http404
    return collection_id


#
# @csrf_exempt required for curl, for example.
#
@login_required
@csrf_exempt
def deposit_web(request):
    if request.method != "POST":
        return return_reload_deposit_web(request)

    collection_id = validate_collection(request)
    collection = get_object_or_404(models.Collection, pk=collection_id)

    reply = []
    logger.info(format_filelist_json(request))
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
        for f in files:
            tempfile = f.temporary_file_path()
            attribs["sizeV"] = f.size
            attribs["tempfile"] = tempfile
            hashes = generateHashes(tempfile)
            attribs["md5sumV"] = hashes["md5"]
            attribs["sha1sumV"] = hashes["sha1"]
            attribs["sha256sumV"] = hashes["sha256"]
            attribs["name"] = directories.pop(0)

            try:
                attribs["sha256sum"] = shasums.pop(0)
            except IndexError:
                attribs["sha256sum"] = "0" * 64
                logger.error(f"sha256sum for {attribs['name']} not in shasums list")
            try:
                attribs["size"] = sizes.pop(0)
            except IndexError:
                attribs["size"] = 0
                logger.error(f"size for {attribs['name']} not in sizes list")

            move_temp_file(request, attribs)
            logger.info(json.dumps(attribs))
            reply.append(json.dumps(attribs))
            validated_total_size += f.size
            validated_file_count += 1

    collection = (
        models.Collection.objects.filter(pk=collection_id)
        .annotate(
            file_count=Count("file"),
            total_size=Sum("file__size"),
        )
        .first()
    )

    # TODO: get actual started_at value so we can keep track of upload duration
    models.Report.objects.create(
        collection=collection,
        report_type=models.Report.ReportType.DEPOSIT,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        ended_at=datetime.datetime.now(datetime.timezone.utc),
        total_size=validated_total_size,
        file_count=validated_file_count,
        collection_total_size=collection.total_size,
        collection_file_count=collection.file_count,
        error_count=0,
        missing_location_count=0,
        mismatch_count=0,
        avg_replication=collection.target_replication,
    )

    report = (
        models.Report.objects.filter(collection=collection.pk)
        .order_by("-ended_at")
        .first()
    )
    if report:
        reply.append({"report_id": report.id})

    total_used_quota = return_total_used_quota(organization=request.user.organization)
    reply.append({"total_used_quota": total_used_quota})

    if attribs.get("client", None) == "DOAJ_CLI":
        return return_doaj_report(attribs)
    elif reply:
        # HOW TO FAKE A 408? - Set this to True!
        DEBUG_408 = False
        if DEBUG_408:
            response = HttpResponse("Timeout!")
            response["status"] = 408
            return response
        else:
            return return_text_report(json.dumps(reply))
    else:
        return return_reload_deposit_web(request)


@login_required
def deposit_cli(request):
    return TemplateResponse(request, "vault/deposit_cli.html", {})


@login_required
def deposit_mail(request):
    return TemplateResponse(request, "vault/deposit_mail.html", {})


# @login_required
# def deposit_debug(request):
#     return TemplateResponse(request, "vault/deposit_debug.html", {})


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
    else:
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
    collections = models.Collection.objects.filter(organization=org)
    org_root = org.tree_node
    if org_root:
        total_used_quota = models.TreeNode.objects.filter(
            path__descendant=org_root.path
        ).aggregate(total=Coalesce(Sum("size"), 0))["total"]
    else:
        total_used_quota = 0
    collection_form = forms.RegisterDepositForm(collections=collections)
    return TemplateResponse(
        request,
        "vault/deposit_flow.html",
        {
            "collection_form": collection_form,
            "collections": collections,
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
            logger.error(f"multiple TreeNodes returned for {path}")
            return TemplateResponse(
                request, "vault/files_view.html", {"status": 404}, status=404
            )
    children = parent.children.all()
    return TemplateResponse(
        request,
        "vault/files_view.html",
        {"items": children, "path": output_path},
    )
