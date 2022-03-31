# pylint: disable=too-few-public-methods

import logging
import re
import typing

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import FieldError
from django.core.mail import send_mail
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint, IntegerChoices, Sum, Count
from django.db.models.functions import Coalesce
from django.dispatch import receiver
from django.db.models.signals import (
    pre_save,
    post_save,
)

from vault.ltree import LtreeField
from vault.pb_utils import (
    InvalidPetaboxPath,
    get_presigned_url,
)

from vault import utils

TEBIBYTE = 2**40
logger = logging.getLogger(__name__)


class TreeNodeException(Exception):
    """Raised when an invalid TreeNode operation is requested"""


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
        org = re.sub(r"[^a-zA-Z0-9_\-\/\.]", "_", self.name)
        return f"/files/{org}/"

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
        collection_name = re.sub(r"[^a-zA-Z0-9_\-\/\.]", "_", self.name)
        return f"{self.organization.filepath()}{collection_name}/"

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


class DeferredJSONReportManager(models.Manager):
    """Report model manager which defers load of report_json field.

    The report_json can be large (particularly for large collections). There are several
    cases where we load all reports for a Collection or Organization.
    """

    def get_queryset(self):
        return super().get_queryset().defer("report_json")


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
    # report_json format see conftest.py:make_fixity_report()
    report_json = models.JSONField(blank=True, null=True)
    report_json_version = models.PositiveSmallIntegerField(blank=True, null=True)

    objects = DeferredJSONReportManager()

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
        COMPLETE_WITH_ERRORS = "COMPLETE_WITH_ERRORS", "Complete With Errors"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT)
    #: TreeNode which is the root into which this Deposit is being made.
    #: Referenced TreeNode must be either type COLLECTION or FOLDER
    parent_node = models.ForeignKey("TreeNode", on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    state = models.CharField(
        choices=State.choices, default=State.REGISTERED, max_length=50
    )

    registered_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)
    hashed_at = models.DateTimeField(blank=True, null=True)
    replicated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        reg_dt = self.registered_at.strftime("%Y-%m-%d %H:%M:%S")
        return f"Deposit-{self.organization_id}-{self.collection_id}-{reg_dt}"

    def make_deposit_report(self):
        deposit_stats = TreeNode.objects.filter(depositfile__deposit=self).aggregate(
            total_size=Coalesce(Sum("size"), 0), file_count=Coalesce(Count("*"), 0)
        )
        collection_root = self.collection.tree_node
        collection_stats = TreeNode.objects.filter(
            path__descendant=collection_root.path
        ).aggregate(
            collection_total_size=Coalesce(Sum("size"), 0),
            collection_file_count=Coalesce(Count("*"), 0),
        )
        report = Report(
            collection=self.collection,
            report_type=Report.ReportType.DEPOSIT,
            started_at=self.registered_at,
            ended_at=self.hashed_at,  # TODO: should this be replicated_at?
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
        self.send_deposit_report_email()

    def send_deposit_report_email(self):
        deposit_report_link = f"https://{settings.CURRENT_HOST}/vault/deposit/{self.id}"
        collections_link = f"https://{settings.CURRENT_HOST}/vault/collections"
        message = f"""
Hello {self.user.username}

Your deposit to {self.collection.name} is now complete:
View deposit report {deposit_report_link}
View all collections {collections_link}

Please feel free to contact our product team at vault@archive.org if you are experiencing any issues.

All the best,

Vault team
        """
        send_mail(
            "Vault - Deposit Complete",
            message,
            "vault@archive.org",
            [self.user.email],
            fail_silently=False,
        )


class DepositFile(models.Model):
    class State(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        UPLOADED = "UPLOADED", "Uploaded"
        HASHED = "HASHED", "Hashed"
        REPLICATED = "REPLICATED", "Replicated"
        ERROR = "ERROR", "Error"

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


class DeletionAwareTreeNodeManager(models.Manager):
    """TreeNode model manager which hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)


class TreeNode(models.Model):
    class Type(models.TextChoices):
        # a downloadable file
        FILE = "FILE", "File"
        # folder node other than collection node
        FOLDER = "FOLDER", "Folder"
        # top level directory of a collection
        COLLECTION = "COLLECTION", "Collection"
        # top level directory of an entire organization
        ORGANIZATION = "ORGANIZATION", "Organization"

    # node types which may not be deleted
    undeletable_types = (
        Type.COLLECTION,
        Type.ORGANIZATION,
    )

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

    #: For FILE: the size of the underlying content in bytes.
    #: For FOLDER, COLLECTION, ORGANIZATION: the sum of the size of all nodes
    #: in the subtree.
    size = models.PositiveBigIntegerField(blank=True, default=0, null=True)
    #: For FOLDER, COLLECTION, ORGANIZATION: the count of all FILEs in the
    #: subtree. For FILEs: 1; this is set automatically by trigger. See
    #: PLPGSQL function: ``_do_treenode_set_new_file_count``
    file_count = models.PositiveBigIntegerField(blank=True, default=0, null=False)
    file_type = models.CharField(max_length=255, blank=True, null=True)
    # TODO (mwilson): expand/remove char limit:
    # https://webarchive.jira.com/browse/WT-1167
    pbox_path = models.CharField(max_length=255, blank=True, null=True)

    uploaded_at = models.DateTimeField(
        blank=True, null=True
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
    #: True when this TreeNode is deleted
    deleted = models.BooleanField(blank=True, default=False, null=False)

    objects = DeletionAwareTreeNodeManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("parent", "name"), name="vault_treenode_parent_and_name"
            ),
        ]

    @property
    def content_url(self) -> typing.Optional[str]:
        """Generates a URL for downloading the content of this *TreeNode*.

        Returns ``None`` if this *TreeNode* is not of *node_type* *FILE*., or
        if *pbox_path* is ``None`` or describes an invalid path.
        """

        if self.node_type != TreeNode.Type.FILE:
            return None

        if self.pbox_path is None:
            return None

        try:
            return get_presigned_url(
                self.pbox_path,
                settings.PETABOX_SERVICE_NAME,
                settings.PETABOX_SECRET,
                settings.PETABOX_URL_SIGNATURE_EXPIRATION_SECS,
            )
        except InvalidPetaboxPath:
            logger.warning(
                "TreeNode id=%d has an invalid pbox_path=%s",
                self.id,
                self.pbox_path,
            )
            return None

    def delete(self, using=None, keep_parents=False):
        """Marks this *TreeNode* and all children as deleted, but doesn't
        actually delete the record.

        Neither related records nor the underlying content are physically
        deleted.

        :py:attr:`.deleted` will not reflect the new deletion status after this
        function returns, thus a call to :py:meth`.TreeNode.refresh_from_db`
        may be desirable.

        Parameters *using* and *keep_parents* are included for API
        compatibility with Django's *Model.delete()*.

        :raises: :py:class:`.TreeNodeException` when attempting to delete an
            undeletable TreeNode type
        """
        if self.deleted:
            logger.warning("deletion of already deleted TreeNode id=%d", self.id)
            return

        if self.node_type in self.undeletable_types:
            raise TreeNodeException(
                f"unable to delete TreeNode of type {self.node_type}",
            )

        TreeNode.objects.using(using).filter(path__descendant=self.path).update(
            deleted=True, deleted_at=utils.utcnow()
        )

    def hard_delete(self):
        """Physically deletes this :py:class:`.TreeNode` row."""
        logger.warning("hard deletion of TreeNode id=%d", self.id)
        super().delete()

    def get_ancestor(
        self,
        _type: typing.Union["TreeNode.Type", str],
    ) -> typing.Optional["TreeNode"]:
        """Returns the nearests ancestor to this :py:class:`Treenode` of type
        *_type*. Where no ancestor node of the given type exists, `None` is
        returned.
        """
        return (
            TreeNode.objects.filter(
                path__ancestor=self.path,
                node_type=_type,
            )
            .order_by("-path")
            .first()
        )

    def get_collection(self) -> Collection:
        """Gets the :py:class:`.Collection` associated with the
        `COLLECTION`-type ancestor of this :py:class:`.TreeNode`, or raise
        :py:exc:`.Collection.DoesNotExist`.
        """
        return Collection.objects.get(
            tree_node__path__ancestor=self.path,
        )

    @classmethod
    def get_owned_by(cls, pk: int, user_id: int) -> "TreeNode":
        """Gets the :py:class:`.TreeNode` identified by *pk* which is
        ultimately owned by the :py:class:`.Organization` to which the
        :py:class:`.User` identified by *user_id* belongs.

        :param pk: id of target :py:class:`.TreeNode` to return
        :param user_id: id of :py:class:`.User` designating the
            :py:class:`.Organization` owning the target :py:class:`.TreeNode`

        :return: target :py:class:`.TreeNode`

        :raises: :py:exc:`.TreeNode.DoesNotExist` when no such
            :py:class:`.TreeNode` exists
        """
        org_node = cls.objects.get(organization__user__id=user_id)
        return cls.objects.get(
            pk=pk,
            path__descendant=org_node.path,
        )


###############################################################################
# Signal Handlers
###############################################################################


@receiver(post_save, sender=Organization)
def create_organization_handler(
    sender,  # pylint: disable=unused-argument
    **kwargs,
):
    """Automatically create a TreeNode for new Organizations if necessary."""
    if kwargs["created"]:
        org = kwargs["instance"]
        if not org.tree_node:
            org_node = TreeNode.objects.create(
                node_type=TreeNode.Type.ORGANIZATION, name=org.name
            )
            org.tree_node = org_node
            org.save()


@receiver(post_save, sender=Collection)
def create_collection_handler(
    sender,  # pylint: disable=unused-argument
    **kwargs,
):
    """Automatically create corresponding ORGANIZATION and COLLECTION-type TreeNodes
    for new Collections if necessary."""
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


@receiver(post_save, sender=Collection)
def collection_update_postsave_handler(
    sender,  # pylint: disable=unused-argument
    **kwargs,
):
    """Propagate name changes to the associated TreeNode."""
    if kwargs["created"]:
        return
    collection = kwargs["instance"]
    node = collection.tree_node
    if node and node.name != collection.name:
        node.name = collection.name
        node.save()


# Define the valid TreeNode child -> parent node_type hierarchy.
TREE_NODE_TYPE_VALID_PARENT_TYPES_MAP = {
    TreeNode.Type.ORGANIZATION: set(),
    TreeNode.Type.COLLECTION: {TreeNode.Type.ORGANIZATION},
    TreeNode.Type.FOLDER: {TreeNode.Type.COLLECTION, TreeNode.Type.FOLDER},
    TreeNode.Type.FILE: {TreeNode.Type.COLLECTION, TreeNode.Type.FOLDER},
}


# Define a TreeNode.Type.* -> Model map for types that have an associated model.
TREE_NODE_TYPE_MODEL_MAP = {
    TreeNode.Type.ORGANIZATION: Organization,
    TreeNode.Type.COLLECTION: Collection,
}


@receiver(pre_save, sender=TreeNode)
def treenode_presave_handler(
    sender,  # pylint: disable=unused-argument
    **kwargs,
):
    """Enforce that the TreeNode type is a valid child of the specified parent and that
    the name value for ORGANIZATION and COLLECTION-type nodes does not exceed the max
    length of the name field on the associated model."""
    node = kwargs["instance"]
    # Raise a FieldError if the parent type is invalid.
    parent_type = node.parent and node.parent.node_type
    valid_parent_types = TREE_NODE_TYPE_VALID_PARENT_TYPES_MAP[node.node_type]
    if (parent_type is None and valid_parent_types) or (
        parent_type is not None and parent_type not in valid_parent_types
    ):
        raise FieldError(
            f"Valid parents for node of type ({node.node_type}) are: "
            f"{valid_parent_types}, but specified parent is of type: "
            f"{parent_type}"
        )
    # Raise a FieldError if the name length exceeds the max of the associated model for
    # ORGANIZATION and COLLECTION-type nodes.
    model = TREE_NODE_TYPE_MODEL_MAP.get(node.node_type)
    if model and len(node.name) > model.name.field.max_length:
        raise FieldError(
            f"Can not set 'name' of length ({len(node.name)}) for node of "
            f"type ({node.node_type}) because the "
            f"({model.__name__}) model has a max 'name' length of "
            f"({model.name.field.max_length})."
        )


@receiver(post_save, sender=TreeNode)
def treenode_update_postsave_handler(
    sender,  # pylint: disable=unused-argument
    **kwargs,
):
    """Propagate name changes for COLLECTION-type nodes to the associated Collection."""
    if kwargs["created"]:
        return
    node = kwargs["instance"]
    if node.node_type != TreeNode.Type.COLLECTION:
        return
    collection = Collection.objects.get(tree_node=node)
    if collection.name != node.name:
        # Note that TreeNode.name.max_lenth > Collection.name.max_length, but logic
        # in treenode_presave_handler() prevents us from having to deal with that here.
        collection.name = node.name
        collection.save()
