from django.contrib.auth.models import AbstractUser
from django.db import models


class Plan(models.Model):
    name = models.CharField(max_length=255)
    price_per_terabyte = models.DecimalField(max_digits=10, decimal_places=2)
    default_replication = models.IntegerField()

    def __str__(self):
        return self.name


class Organization(models.Model):
    name = models.CharField(max_length=255)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class User(AbstractUser):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, null=True)

    def __str__(self):
        return self.username


class Collection(models.Model):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Report(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    total_size = models.PositiveBigIntegerField()
    file_count = models.PositiveBigIntegerField()
    error_count = models.PositiveBigIntegerField()
    missing_location_count = models.PositiveBigIntegerField()
    mismatch_count = models.PositiveBigIntegerField()
