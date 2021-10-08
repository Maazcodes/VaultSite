import datetime
import re

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint, IntegerChoices, Sum, Count
from django.db.models.signals import post_save
from django.dispatch import receiver

from vault.ltree import LtreeField

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
    name = models.CharField(max_length=255, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    quota_bytes = models.PositiveBigIntegerField(default=TEBIBYTE)
    tree_node = models.ForeignKey(
        "TreeNode", blank=True, null=True, on_delete=models.PROTECT
    )
    pbox_collection = models.CharField(max_length=255, blank=True, null=True)

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
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, db_index=False
    )
    target_replication = models.IntegerField(
        choices=ReplicationFactor.choices, default=ReplicationFactor.DEFAULT
    )
    target_geolocations = models.ManyToManyField(Geolocation)
    fixity_frequency = models.CharField(
        choices=FixityFrequency.choices, default=FixityFrequency.DEFAULT, max_length=50
    )
    tree_node = models.ForeignKey(
        "TreeNode", blank=True, null=True, on_delete=models.PROTECT
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

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "name"], name="vault_collection_org_and_name"
            )
        ]


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

    def make_deposit_report(self):
        deposit_stats = TreeNode.objects.filter(depositfile__deposit=self).aggregate(
            total_size=Sum("size"), file_count=Count("*")
        )
        collection_root = self.collection.tree_node
        collection_stats = TreeNode.objects.filter(
            path__descendant=collection_root.path
        ).aggregate(collection_total_size=Sum("size"), collection_file_count=Count("*"))
        report = Report(
            collection=self.collection,
            report_type=Report.ReportType.DEPOSIT,
            started_at=self.registered_at,
            ended_at=datetime.datetime.now(
                datetime.timezone.utc
            ),  # TODO: should this be replicated_at?
            total_size=deposit_stats["total_size"],
            file_count=deposit_stats["file_count"],
            collection_total_size=collection_stats["collection_total_size"],
            collection_file_count=collection_stats["collection_file_count"],
            error_count=0,
            missing_location_count=0,
            mismatch_count=0,
            avg_replication=self.collection.target_replication,
        )
        report.save()


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
    pre_deposit_modified_at = models.DateTimeField(blank=True, null=True)

    state = models.CharField(
        choices=State.choices, default=State.REGISTERED, max_length=50
    )

    md5_sum = models.CharField(max_length=32, blank=True, null=True, default=None)
    sha1_sum = models.CharField(max_length=40, blank=True, null=True, default=None)
    sha256_sum = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        default=None,
    )

    tree_node = models.ForeignKey(
        "TreeNode", blank=True, null=True, on_delete=models.PROTECT
    )

    registered_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)
    hashed_at = models.DateTimeField(blank=True, null=True)
    replicated_at = models.DateTimeField(blank=True, null=True)


class TreeNode(models.Model):
    class Type(models.TextChoices):
        FILE = "FILE", "File"  # A file uploaded by the user
        FOLDER = (
            "FOLDER",
            "Folder",
        )  # folder node other than collection node
        COLLECTION = "COLLECTION", "Collection"  # collection node
        ORGANIZATION = (
            "ORGANIZATION",
            "Organization",
        )  # organization node - which will be the top level node with not parent

    node_type = models.CharField(choices=Type.choices, default=Type.FILE, max_length=50)
    parent = models.ForeignKey(
        "self",
        null=True,
        related_name="children",
        on_delete=models.CASCADE,
        db_index=False,
    )  # index (parent, name) created separately
    path = LtreeField()  # index created separately
    name = models.TextField()  # Name would be the client filename / folder name

    md5_sum = models.CharField(
        max_length=32, validators=[md5_validator], blank=True, null=True
    )
    sha1_sum = models.CharField(
        max_length=40, validators=[sha1_validator], blank=True, null=True
    )
    sha256_sum = models.CharField(
        max_length=64,
        validators=[sha256_validator],
        blank=True,
        null=True,
        db_index=True,
    )

    size = models.PositiveBigIntegerField(blank=True, null=True)
    file_type = models.CharField(max_length=255, blank=True, null=True)
    pbox_item = models.CharField(max_length=255, blank=True, null=True)

    uploaded_at = models.DateTimeField(
        auto_now_add=True, blank=True, null=True
    )  # Date on which the file was uploaded
    pre_deposit_modified_at = models.DateTimeField(
        blank=True, null=True
    )  # Date on which the file was created on the users system
    modified_at = models.DateTimeField(
        auto_now=True, blank=True, null=True
    )  # if the file was modified on the server.
    deleted_at = models.DateTimeField(blank=True, null=True)

    uploaded_by = models.ForeignKey(
        User, on_delete=models.PROTECT, blank=True, null=True
    )
    comment = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("parent", "name"), name="vault_treenode_parent_and_name"
            ),
        ]


@receiver(post_save, sender=Organization)
def create_organization_handler(sender, **kwargs):
    if kwargs["created"]:
        org = kwargs["instance"]
        if not org.tree_node:
            org_node = TreeNode.objects.create(
                node_type=TreeNode.Type.ORGANIZATION, name=org.name
            )
            org.tree_node = org_node
            org.save()


@receiver(post_save, sender=Collection)
def create_collection_handler(sender, **kwargs):
    if kwargs["created"]:
        coll = kwargs["instance"]
        org = coll.organization
        if not org.tree_node:
            org_node = TreeNode.objects.filter(
                node_type=TreeNode.Type.ORGANIZATION, name=org.name
            ).first()
            if not org_node:
                org_node = TreeNode.objects.create(
                    node_type=TreeNode.Type.ORGANIZATION, name=org.name
                )
            org.tree_node = org_node
            org.save()
        if not coll.tree_node:
            coll_node = TreeNode.objects.create(
                node_type=TreeNode.Type.COLLECTION, name=coll.name, parent=org.tree_node
            )
            coll.tree_node = coll_node
            coll.save()
