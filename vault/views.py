import os
import re
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
                name=form.cleaned_data["name"],
                target_replication=org.plan.default_replication,
                fixity_frequency=org.plan.default_fixity_frequency,
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
def collection(request, pk):
    org = request.user.organization
    collection = models.Collection.objects.get(organization=org, pk=pk)
    return TemplateResponse(request, "vault/collection.html", {
        "collection": collection,
    })


@login_required
def reports(request):
    org = request.user.organization
    collection = models.Collection.objects.filter(organization=org).first()
    report = models.Report.objects.filter(collection=collection).first()
    return TemplateResponse(request, "vault/reports.html", {
        "collection": collection,
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
        sha256_sum       = attribs['sha256sumV'],
        defaults = {
                 'size': attribs['sizeV'],
            'file_type': attribs['file_type'],
          'uploaded_by': request.user,
              'comment': attribs['comment'],
        }
    )


@csrf_exempt
def sha256sum(filename):
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(filename,"rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    f.close()
    return sha256_hash.hexdigest()

#
# Note the KeyError exception handler.
# This should not be triggered during initial page
# loading, but it is - I suspect that there is something
# slightly (haha) buggy in Django's debug mode that
# is responsible.
#
@csrf_exempt
def create_attribs_dict(request):
    retval = dict()
    retval['comment'] = ""
    metadata_fields = [ 'client', 'username',  'organization', 'collection',
            'sha256sum', 'webkitRelativePath', 'name', 'size', 'collname' ]
    data = dict()
    if request.method == 'POST':
        data = request.POST
        for key, value in data.items():
            if key in metadata_fields:
                retval[key] = value
    retval['username'] = request.META['REMOTE_USER']
    retval['orgname']  = request.user.organization.name
    try:
        some_id = retval['collection']
        retval['collname'] = models.Collection.objects.get(pk=some_id).name
    except KeyError:
        retval['collname'] = {}
    return retval

@csrf_exempt
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
    org = Path(attribs['orgname'])
    coll = Path(attribs['collname'])
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
    os.rename(temp_file, target_file)
    create_or_update_file(request, attribs)

#
# If you don't use @csrf_exempt the extra javascript code is passed over!
# The same is true of the above functions called from here.
# There is also a bug, possibly in Django's debug mode, that raises
# an error about typeError being undefined.
#
# The exception handling can be obviated by doing the proper tests
# on each item . :FIXME:
#
@login_required
@csrf_exempt
def deposit_web(request):
    # Accumulate request global attributes
    # Possibly to be overwritten by file iteration below
    attribs = create_attribs_dict(request)

    dir_json = request.POST.get("directories", "")
    sha_json = request.POST.get("shasums", "")
    if dir_json:
        dir_json  = json.loads(dir_json)
    if sha_json:
        sha_json  = json.loads(sha_json)

    inputs = [ 'file_field', 'dir_field' ]
    for field in inputs:
        files = request.FILES.getlist(field)
        for f in files:
            try:
                attribs['sizeV'] = f.size
                tempfile = f.temporary_file_path()
                attribs['name'] = dir_json[f.name]
                attribs['sha256sum'] = sha_json[f.name]
                attribs['tempfile'] = tempfile
                attribs['sha256sumV'] = sha256sum(tempfile)
            except (KeyError, TypeError, AttributeError) as e:
                try:
                    attribs['sizeV'] = f.size
                    tempfile = f.temporary_file_path()
                    attribs['name'] = f.name
                    attribs['tempfile'] = tempfile
                    attribs['sha256sumV'] = sha256sum(tempfile)
                except AttributeError:
                    attribs['sizeV'] = f.size
                    attribs['name'] = f.name
                    # expected str, bytes or os.PathLike object, not _io.BytesIO
                    #attribs['sha256sumV'] = sha256sum(f.file)

            move_temp_file(request, attribs)
            logger.info(attribs)

    collections = models.Collection.objects.filter(organization=request.user.organization)
    form = forms.FileFieldForm(collections)
    return TemplateResponse(request, "vault/deposit_web.html", {
        "collections": collections,
        "filenames": "",
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
