from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from . import forms
from . import models


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
def deposit_web(request):
    collections = models.Collection.objects.filter(organization=request.user.organization)
    form = forms.BasicFileUploadForm(collections)
    return TemplateResponse(request, "vault/deposit_web.html", {
        "collections": collections,
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
