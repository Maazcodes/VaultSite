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


@login_required
@csrf_exempt
def deposit_web(request):
    inputs = [ 'file_field', 'dir_field' ]
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
                fnames += f" {f.name} {dir_json[f.name]} - {f.temporary_file_path()} : {f.size}"
            except (KeyError, TypeError) as e:
                try:
                    fnames += f" {f.name} {f.name} - {f.temporary_file_path()} : {f.size}"
                except AttributeError:
                    fnames += f" {f.name} {f.name} - No path : {f.size}"
    logger.info(fnames)
    return TemplateResponse(request, "vault/deposit_web.html", {
        "collections": collections,
        "filenames": fnames,
        "form": form,
    })
    #messages.error(request, 'Must select Files and/or Directories!')


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
