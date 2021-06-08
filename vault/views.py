import logging
import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from . import forms
from . import models

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
        form = forms.CollectionForm(request.POST)
        if form.is_valid():
            models.Collection.objects.create(
                organization=org,
                name=form.cleaned_data["name"]
            )
        return redirect("collections")
    else:
        form = forms.CollectionForm()
        collections = models.Collection.objects.filter(organization=org)
        return TemplateResponse(request, "vault/collections.html", {
            "collections": collections,
            "form": form,
        })


@login_required
def reports(request):
    return TemplateResponse(request, "vault/reports.html", {})


@login_required
def deposit(request):
    return redirect("deposit_web")

def sha256sum(filename):
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    f.close()
    return sha256_hash.hexdigest()

@login_required
def cli_web_deposit(request):
    retval = dict()
    metadata_fields = [ 'client', 'username', 'organization', 'collection',
    'sha256sum', 'webkitRelativePath', 'name', 'size' ]
    data = dict()
    if request.method == 'POST':
        data = request.POST
        for key, value in data.items():
            if key in metadata_fields:
                retval[key] = value
    return retval

@login_required
@csrf_exempt
def deposit_web(request):
    inputs = [ 'file_field', 'dir_field' ]
    attribs = cli_web_deposit(request)
    logger.info(attribs)
    dir_json = request.POST.get("directories", "")
    if dir_json:
        dir_json  = json.loads(dir_json)
    fnames = ""
    collections = models.Collection.objects.filter(organization=request.user.organization)
    form = forms.FileFieldForm(collections)
    for field in inputs:
        files = request.FILES.getlist(field)
        for f in files:
            try:
                attribs['sizeV'] = f.size
                tempfile = f.temporary_file_path()
                attribs['name'] = dir_json[f.name]
                attribs['tempfile'] = tempfile 
                attribs['sha256sumV'] = sha256sum(tempfile)
            except (KeyError, TypeError, AttributeError) as e:
                try:
                    attribs['sizeV'] = f.size
                    tempfile = f.temporary_file_path()
                    #attribs['name'] = dir_json[f.name]
                    attribs['name'] = f.name
                    attribs['tempfile'] = tempfile 
                    attribs['sha256sumV'] = sha256sum(tempfile)
                except AttributeError:
                    attribs['sizeV'] = f.size
                    # 'InMemoryUploadedFile' object has no attribute 'temporary_file_path'
                    #tempfile = f.temporary_file_path()
                    #attribs['name'] = dir_json[f.name]
                    attribs['name'] = f.name
                    #attribs['tempfile'] = tempfile
                    # expected str, bytes or os.PathLike object, not _io.BytesIO
                    #attribs['sha256sumV'] = sha256sum(f.file)
            logger.info(attribs)
    return TemplateResponse(request, "vault/deposit_web.html", {
        "collections": collections,
        "filenames": fnames,
        "form": form,
    })


@login_required
def deposit_cli(request):
    return TemplateResponse(request, "vault/deposit_cli.html", {})


@login_required
def deposit_mail(request):
    return TemplateResponse(request, "vault/deposit_mail.html", {})


@login_required 
def deposit_debug(request):
    return TemplateResponse(request, "vault/deposit_debug.html", {})


@login_required
def deposit_ait(request):
    return TemplateResponse(request, "vault/deposit_ait.html", {})


@login_required
def administration(request):
    return redirect("administration_plan")


@login_required
def administration_plan(request):
    org = request.user.organization
    plan = org.plan
    return TemplateResponse(request, "vault/administration_plan.html", {
        "organization": org,
        "plan": plan,
    })


@login_required
def administration_users(request):
    return TemplateResponse(request, "vault/administration_users.html", {})


@login_required
def administration_help(request):
    return TemplateResponse(request, "vault/administration_help.html", {})
