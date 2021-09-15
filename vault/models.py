import re

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint, IntegerChoices


TEBIBYTE = 2 ** 40


class ReplicationFactor(IntegerChoices):
    DEFAULT = 2, "2x"
    THREE = 3, "3x"
    FOUR = 4, "4x"


class FixityFrequency(models.TextChoices):
    DEFAULT = "TWICE_YEARLY", "Twice Yearly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    MONTHLY = "MONTHLY", "Monthly"


class Geolocation(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Plan(models.Model):
    name = models.CharField(max_length=255)
    price_per_terabyte = models.DecimalField(max_digits=10, decimal_places=2)
    default_replication = models.IntegerField(
        choices=ReplicationFactor.choices, default=ReplicationFactor.DEFAULT
    )
    default_geolocations = models.ManyToManyField(Geolocation)
    default_fixity_frequency = models.CharField(
        choices=FixityFrequency.choices, default=FixityFrequency.DEFAULT, max_length=50
    )

    def __str__(self):
        return self.name


class Organization(models.Model):
    name = models.CharField(max_length=255)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    quota_bytes = models.PositiveBigIntegerField(default=TEBIBYTE)

    def filepath(self):
        return "/files/{org}/".format(org=re.sub("[^a-zA-Z0-9_\-\/\.]", "_", self.name))

    def __str__(self):
        return self.name


class User(AbstractUser):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, null=True)

    def __str__(self):
        return self.username


class Collection(models.Model):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    target_replication = models.IntegerField(
        choices=ReplicationFactor.choices, default=ReplicationFactor.DEFAULT
    )
    target_geolocations = models.ManyToManyField(Geolocation)
    fixity_frequency = models.CharField(
        choices=FixityFrequency.choices, default=FixityFrequency.DEFAULT, max_length=50
    )

    def filepath(self):
        return "{org_filepath}{col}/".format(
            org_filepath=self.organization.filepath(),
            col=re.sub("[^a-zA-Z0-9_\-\/\.]", "_", self.name),
        )

    def last_fixity_report(self):
        return (
            Report.objects.filter(
                collection__pk=self.pk, report_type=Report.ReportType.FIXITY
            )
            .order_by("-ended_at")
            .first()
        )

    def __str__(self):
        return self.name


class Report(models.Model):
    class ReportType(models.TextChoices):
        FIXITY = "FIXITY", "Fixity"
        DEPOSIT = "DEPOSIT", "Deposit"

    collection = models.ForeignKey(Collection, on_delete=models.PROTECT)
    report_type = models.CharField(
        choices=ReportType.choices, max_length=20, default=ReportType.FIXITY
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    total_size = models.PositiveBigIntegerField()
    file_count = models.PositiveBigIntegerField()
    collection_total_size = models.PositiveBigIntegerField()
    collection_file_count = models.PositiveBigIntegerField()
    error_count = models.PositiveBigIntegerField()
    missing_location_count = models.PositiveBigIntegerField()
    mismatch_count = models.PositiveBigIntegerField()
    avg_replication = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.report_type}-{self.collection.pk}-{self.started_at}"


md5_validator = RegexValidator(
    r"^[a-zA-Z0-9]{32}$", "only hex-encoded md5 hashes are allowed"
)
sha1_validator = RegexValidator(
    r"^[a-zA-Z0-9]{40}$", "only hex-encoded sha1 hashes are allowed"
)
sha256_validator = RegexValidator(
    r"^[a-zA-Z0-9]{64}$", "only hex-encoded sha256 hashes are allowed"
)


class File(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT)
    client_filename = models.TextField()
    staging_filename = models.TextField()
    md5_sum = models.CharField(
        max_length=32, validators=[md5_validator], blank=True, null=True
    )
    sha1_sum = models.CharField(
        max_length=40, validators=[sha1_validator], blank=True, null=True
    )
    sha256_sum = models.CharField(max_length=64, validators=[sha256_validator])
    size = models.PositiveBigIntegerField()
    file_type = models.CharField(max_length=255, blank=True, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    deletion_date = models.DateTimeField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.PROTECT, blank=True, null=True
    )
    comment = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "collection",
                    "client_filename",
                    "staging_filename",
                    "sha256_sum",
                ],
                name="unique_file",
            )
        ]

    def __str__(self):
        return self.client_filename


class Deposit(models.Model):
    class State(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        UPLOADED = "UPLOADED", "Uploaded"
        HASHED = "HASHED", "Hashed"
        REPLICATED = "REPLICATED", "Replicated"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT)
    # TODO: add ForeignKey to parent once we have the FileNode model
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    state = models.CharField(
        choices=State.choices, default=State.REGISTERED, max_length=50
    )

    registered_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)
    hashed_at = models.DateTimeField(blank=True, null=True)
    replicated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Deposit-{self.organization_id}-{self.collection_id}-{self.registered_at.strftime('%Y-%m-%d %H:%M:%S')}"


class DepositFile(models.Model):
    class State(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        UPLOADED = "UPLOADED", "Uploaded"
        HASHED = "HASHED", "Hashed"
        REPLICATED = "REPLICATED", "Replicated"

    deposit = models.ForeignKey(Deposit, on_delete=models.PROTECT, related_name="files")

    flow_identifier = models.CharField(max_length=255)
    name = models.TextField()
    relative_path = models.TextField()
    size = models.PositiveBigIntegerField()
    type = models.CharField(max_length=255, blank=True)
    original_last_modified_at = models.DateTimeField(blank=True, null=True)

    state = models.CharField(
        choices=State.choices, default=State.REGISTERED, max_length=50
    )

    md5_sum = models.CharField(
        max_length=32, validators=[md5_validator], blank=True, null=True, default=None
    )
    sha1_sum = models.CharField(
        max_length=40, validators=[sha1_validator], blank=True, null=True, default=None
    )
    sha256_sum = models.CharField(max_length=64, validators=[sha256_validator], blank=True, null=True, default=None)

    registered_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)
    hashed_at = models.DateTimeField(blank=True, null=True)
    replicated_at = models.DateTimeField(blank=True, null=True)
