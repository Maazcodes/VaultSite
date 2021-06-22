import os
import re
import logging
import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Max, Sum, Count
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from . import forms
from . import models
from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def index(request):
    return redirect("dashboard")


@login_required
def dashboard(request):
    return TemplateResponse(request, "vault/dashboard.html", {})


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
        collections = models.Collection.objects.filter(organization=org).annotate(
            total_size    = Sum("file__size"),
            file_count    = Count("file"),
            last_modified = Max("file__modified_date"),
            last_report   = Max('report__ended_at'),
        )
        return TemplateResponse(request, "vault/collections.html", {
            "collections": collections,
            "form": form,
        })


@login_required
def collection(request, collection_id):
    org = request.user.organization
    if request.method == "POST":
        form = forms.EditCollectionSettingsForm(request.POST)
        collection = models.Collection.objects.select_for_update().get(pk=collection_id)
        if form.is_valid() and collection.organization == org:
            with transaction.atomic():
                collection.target_replication = form.cleaned_data["target_replication"]
                collection.fixity_frequency = form.cleaned_data["fixity_frequency"]
                collection.target_geolocations.set(form.cleaned_data["target_geolocations"])
                collection.save()
            messages.success(request, 'Collection settings updated.')

    collection = models.Collection.objects.filter(organization=org, pk=collection_id).annotate(
        file_count=Count("file"),
        total_size=Sum("file__size"),
        last_modified=Max("file__modified_date"),
        last_report=Max('report__ended_at'),
    ).first()
    form = forms.EditCollectionSettingsForm(initial=({
        "target_replication": collection.target_replication,
        "fixity_frequency": collection.fixity_frequency,
        "target_geolocations": collection.target_geolocations.all(),
    }))
    reports = models.Report.objects.filter(collection=collection.pk).order_by("-ended_at")
    return TemplateResponse(request, "vault/collection.html", {
        "collection": collection,
        "form": form,
        "reports": reports,
    })


@login_required
def report(request, report_id):
    org = request.user.organization
    report = get_object_or_404(models.Report, pk=report_id)
    if report.collection.organization != org:
        raise Http404
    return TemplateResponse(request, "vault/report.html", {
        "collection": report.collection,
        "report": report,
        "page_number": 1,
    })


@login_required
def deposit(request):
    return redirect("deposit_web")

def create_or_update_file(request, attribs):
    collection = models.Collection.objects.get(pk=attribs['collection'])

    models.File.objects.update_or_create(
        collection       = collection,
        client_filename  = attribs['name'],
        staging_filename = attribs['staging_filename'],
        md5_sum          = attribs['md5sumV'],
        sha1_sum         = attribs['sha1sumV'],
        sha256_sum       = attribs['sha256sumV'],
        defaults = {
                 'size': attribs['sizeV'],
            'file_type': attribs.get('file_type', None),
          'uploaded_by': request.user,
              'comment': attribs['comment'],
        }
    )


def generateHashes(filename):
    hashes = dict()
    import hashlib
    md5_hash    = hashlib.md5()
    sha1_hash   = hashlib.sha1()
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
            sha1_hash.update(byte_block)
            sha256_hash.update(byte_block)
    f.close()
    hashes['md5']    =    md5_hash.hexdigest()
    hashes['sha1']   =   sha1_hash.hexdigest()
    hashes['sha256'] = sha256_hash.hexdigest()
    return hashes


def create_attribs_dict(request):
    retval = dict()
    retval['comment']       = request.POST.get('comment', "")
    retval['client']        = request.POST.get('client', "")
    retval['collection']    = request.POST.get('collection', None)
    retval['username']      = request.META.get('REMOTE_USER', "")

    org = request.user.organization

    if org:
        retval['organization'] = request.user.organization.id
        retval['orgname']      = request.user.organization.name
        try:
            pk_id = retval['collection']
            retval['collname'] = models.Collection.objects.get(pk=pk_id).name
        except:
            retval['collname'] = ""
    return retval


def move_temp_file(request, attribs):
    import filetype
    from pathlib import Path
    from sanitize_filename import sanitize
    from django.conf import settings

    root = settings.MEDIA_ROOT

    temp_file = attribs['tempfile']
    ftype = filetype.guess(temp_file)
    if ftype:
        attribs['file_type'] = ftype.mime
    org      = Path(attribs['orgname'])
    coll     = Path(attribs['collname'])
    filepath = Path(attribs['name'])

    fname = os.path.basename(filepath)
    fname = sanitize(fname)

    userdir = os.path.dirname(filepath)
    target_path = os.path.join(root, org, coll, userdir)
    target_path = re.sub('[^a-zA-Z0-9_\-\/\.]', '_', target_path)
    target_path = os.path.normpath(target_path)
    Path(target_path).mkdir(parents=True, exist_ok=True)
    target_file = target_path + '/' + fname
    attribs['staging_filename'] = target_file
    # Move the file on the filesystem
    os.rename(temp_file.encode('U8'), target_file.encode('U8'))
    create_or_update_file(request, attribs)


def format_doaj_json(attribs):
    attr = {
            'files': {
                'name'  : attribs['name'],
                'sha256': attribs['sha256sumV'],
                }
            }
    return json.dumps(attr)


def return_doaj_report(attribs):
        data = format_doaj_json(attribs)
        return HttpResponse(data, content_type='application/json')


def return_text_report(data):
    return HttpResponse(data, content_type='application/json')


def return_reload_deposit_web(request):
    collections = models.Collection.objects.filter(organization=request.user.organization)
    form = forms.FileFieldForm(collections)
    return TemplateResponse(request, "vault/deposit_web.html", {
        "collections": collections,
        "filenames": "",
        "form": form,
    })


#
# @csrf_exempt required for curl, for example.
#
@login_required
@csrf_exempt
def deposit_web(request):
    reply = []
    # Accumulate request global attributes
    # Possibly to be overwritten by file iteration below
    attribs = create_attribs_dict(request)

    directories = request.POST.get("directories", "")
    directories = directories.split(",")

    shasums = request.POST.get("shasums", "")
    shasums = shasums.split(",")

    sizes = request.POST.get("sizes", "")
    sizes = sizes.split(",")

    inputs = [ 'file_field', 'dir_field' ]

    for field in inputs:
        files = request.FILES.getlist(field)
        for f in files:
            tempfile              = f.temporary_file_path()
            attribs['sizeV']      = f.size
            attribs['tempfile']   = tempfile
            hashes                = generateHashes(tempfile)
            attribs['md5sumV']    = hashes['md5']
            attribs['sha1sumV']   = hashes['sha1']
            attribs['sha256sumV'] = hashes['sha256']
            attribs['name']       = directories.pop(0)
            attribs['sha256sum']  = shasums.pop(0)
            attribs['size']       = sizes.pop(0)

            move_temp_file(request, attribs)
            logger.info(json.dumps(attribs))
            reply.append(json.dumps(attribs))

    if attribs.get('client', None) == 'DOAJ_CLI':
        return return_doaj_report(attribs)
    elif reply:
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
        return TemplateResponse(request, "vault/administration_plan.html", {
            "organization": org,
            "plan": plan,
        })
    else:
        return redirect("dashboard")


@login_required
def administration_users(request):
    return TemplateResponse(request, "vault/administration_users.html", {})


@login_required
def administration_help(request):
    return TemplateResponse(request, "vault/administration_help.html", {})
