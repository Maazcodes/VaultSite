from django.contrib import admin
from django.db.models import Count, Sum, Max
from django.db.models.functions import Coalesce
from django.template.defaultfilters import filesizeformat

from vault import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "organization", "email")


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "get_quota")
    list_filter = ("plan",)

    def get_readonly_fields(self, request, obj=None):
        # We need to be able to set an organization name at creation time
        # but disallow editing it in the admin later.
        if obj:  # obj is not None, so this is an edit
            return ("name", "tree_node")
        else:  # This is an addition
            return ("tree_node",)

    @admin.display(description="Quota", ordering="quota_bytes")
    def get_quota(self, organization):
        return filesizeformat(organization.quota_bytes)


@admin.register(models.Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_per_terabyte",
        "default_replication",
        "default_fixity_frequency",
        "geolocations",
    )

    def geolocations(self, plan):
        return ", ".join(
            str(loc) for loc in plan.default_geolocations.values_list("name", flat=True)
        )


@admin.register(models.Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "file_count", "total_size", "last_modified")

    def get_readonly_fields(self, request, obj=None):
        # We need to be able to set an collection name at creation time
        # but disallow editing it in the admin later.
        if obj:  # obj is not None, so this is an edit
            return ("name", "tree_node")
        else:  # This is an addition
            return ("tree_node",)

    def get_queryset(self, request):
        qs = super(CollectionAdmin, self).get_queryset(request)
        return qs.annotate(
            file_count=Coalesce(Count("file"), 0),
            total_size=Coalesce(Sum("file__size"), 0),
            last_modified=Max("file__modified_date"),
        )

    @admin.display(description="File Count", ordering="-file_count")
    def file_count(self, collection):
        return collection.file_count

    @admin.display(description="Total Size", ordering="-total_size")
    def total_size(self, collection):
        return filesizeformat(collection.total_size)

    @admin.display(ordering="-last_modified")
    def last_modified(self, collection):
        return collection.last_modified


@admin.register(models.Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "get_organization",
        "collection",
        "report_type",
        "get_total_size",
        "file_count",
        "ended_at",
    )
    list_filter = ("report_type",)

    @admin.display(
        description="Organization", ordering="collection__organization__name"
    )
    def get_organization(self, report):
        return report.collection.organization

    @admin.display(description="Total Size", ordering="-total_size")
    def get_total_size(self, report):
        return filesizeformat(report.total_size)


@admin.register(models.Geolocation)
class GeolocationAdmin(admin.ModelAdmin):
    pass


@admin.register(models.File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        "get_organization",
        "collection",
        "client_filename",
        "get_size",
        "file_type",
        "modified_date",
    )

    @admin.display(description="Organization", ordering="collection__organization")
    def get_organization(self, file):
        return file.collection.organization

    @admin.display(description="Size", ordering="-size")
    def get_size(self, file):
        return filesizeformat(file.size)


admin.site.site_header = "Vault Administration"
