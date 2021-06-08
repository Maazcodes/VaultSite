from django.contrib import admin
from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price_per_terabyte", "default_replication")


@admin.register(models.Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "organization")


@admin.register(models.Report)
class ReportAdmin(admin.ModelAdmin):
    pass

admin.site.site_header = "Vault Administration"
