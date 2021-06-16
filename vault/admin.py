from django.contrib import admin
from django.db.models import Count, Sum, Max
from django.template.defaultfilters import filesizeformat

from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "organization", "email")


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    readonly_fields = ("name",)


@admin.register(models.Plan)
class PlanAdmin(admin.ModelAdmin):
    def geolocations(self, obj):
        return ", ".join(str(loc) for loc in obj.default_geolocations.values_list("name", flat=True))

    list_display = ("name", "price_per_terabyte", "default_replication", "default_fixity_frequency", "geolocations")


@admin.register(models.Collection)
class CollectionAdmin(admin.ModelAdmin):
    readonly_fields = ("name",)

    def get_queryset(self, request):
        qs = super(CollectionAdmin, self).get_queryset(request)
        return qs.annotate(
            file_count=Count('file'),
            total_size=Sum('file__size'),
            last_modified=Max('file__modified_date'),
        )

    def file_count(self, obj):
        return obj.file_count

    def total_size(self, obj):
        return filesizeformat(obj.total_size)

    def last_modified(self, obj):
        return obj.last_modified

    list_display = ("name", "organization", "file_count", "total_size", "last_modified")


@admin.register(models.Report)
class ReportAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Geolocation)
class GeolocationAdmin(admin.ModelAdmin):
    pass


@admin.register(models.File)
class FileAdmin(admin.ModelAdmin):
    def organization(self, file):
        return file.collection.organization

    list_display = ("organization", "collection", "client_filename", "size", "file_type", "modified_date")


admin.site.site_header = "Vault Administration"
