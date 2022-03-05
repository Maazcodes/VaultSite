from django.core.exceptions import FieldError

from freezegun import freeze_time
from model_bakery.baker import prepare
from pytest import (
    fixture,
    mark,
    raises,
)

from vault.models import (
    Collection,
    Organization,
    Report,
    TreeNode,
    TreeNodeException,
)
from vault import utils


###############################################################################
# Constants
###############################################################################


TREE_NODE_TYPES = {"ORGANIZATION", "COLLECTION", "FOLDER", "FILE"}


###############################################################################
# Tests
###############################################################################


def assert_tree_node_types_is_valid():
    """Check that our local TREE_NODE_TYPES matches the names in TreeNode.Type"""
    assert TREE_NODE_TYPES == set(TreeNode.Type.values)


class TestTreeNode:
    @mark.django_db
    @mark.parametrize(
        "node_type,valid_parent_types,num_invalid_types",
        (
            ("ORGANIZATION", set(), 4),
            ("COLLECTION", {"ORGANIZATION"}, 3),
            ("FOLDER", {"COLLECTION", "FOLDER"}, 2),
            ("FILE", {"COLLECTION", "FOLDER"}, 2),
        ),
    )
    def test_type_hierarchy_enforcement(
        self,
        make_treenode,
        treenode_stack,
        node_type,
        valid_parent_types,
        num_invalid_types,
    ):
        """Check that the valid TreeNode type hierarchy is enforced."""
        # Check that a node is successfully created when a valid parent is specified.
        # Save a node for the subsequent invalid-parent update test.
        node = None
        if not valid_parent_types:
            node = make_treenode(node_type=node_type, parent=None)
        else:
            for parent_type in valid_parent_types:
                node = make_treenode(
                    node_type=node_type, parent=treenode_stack[parent_type]
                )

        # Check that specifying a parent with an invalid type is not allowed.
        invalid_parent_types = TREE_NODE_TYPES - valid_parent_types
        assert len(invalid_parent_types) == num_invalid_types
        for invalid_parent_type in invalid_parent_types:
            # Test on creation.
            with raises(FieldError):
                make_treenode(
                    node_type=node_type, parent=treenode_stack[invalid_parent_type]
                )
            # Test on update.
            with raises(FieldError):
                node.parent = treenode_stack[invalid_parent_type]
                node.save()

    @freeze_time("2022-01-01")
    @mark.django_db
    def test_content_url__success(
        self,
        make_treenode,
        treenode_stack,
    ):
        """TreeNode.content_url successfully generates pbox url"""
        treenode = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FILE",
            pbox_path="foo/bar",
        )
        assert treenode.pbox_path is not None
        assert (
            treenode.content_url
            == "https://archive.org/download/foo/bar?dps-vault-foo=1640997000-901322cdff274c82a9f7e30a8859c355"
        )

    @mark.django_db
    def test_content_url__none_when_node_type_not_file(
        self,
        make_treenode,
        treenode_stack,
    ):
        """TreeNode.content_url returns no URL when node_type is not file"""
        treenode = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FOLDER",
        )
        assert treenode.node_type == "FOLDER"
        assert treenode.content_url is None

    @mark.django_db
    def test_content_url__none_when_pbox_path_none(
        self,
        make_treenode,
        treenode_stack,
    ):
        """TreeNode.content_url returns no URL when pbox_path not defined"""
        treenode = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FILE",
        )
        assert treenode.pbox_path is None
        assert treenode.content_url is None

    @mark.django_db
    def test_content_url__none_when_pbox_path_invalid(
        self,
        make_treenode,
        treenode_stack,
    ):
        """TreeNode.content_url returns no URL when pbox_path is invalid"""
        treenode = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FILE",
            pbox_path="INVALID-BECAUSE-NO-SLASHES",
        )
        assert "/" not in treenode.pbox_path
        assert treenode.content_url is None

    @mark.django_db
    def test_delete__success(
        self,
        treenode_stack,
    ):
        """TreeNode.delete basic correctness"""
        # Given: an undeleted treenode
        file_node = treenode_stack["FILE"]
        assert file_node.deleted is False
        assert file_node.deleted_at is None

        # When: it's deleted
        file_node.delete()
        file_node.refresh_from_db()

        # Then: it's actually marked as deleted
        assert file_node.deleted is True
        assert file_node.deleted_at is not None

    @freeze_time("2022-01-01")
    @mark.django_db
    def test_delete__success_recursive(
        self,
        treenode_stack,
    ):
        """TreeNode.delete successfully recursively deletes nodes"""
        # Given: undeleted folder and nested file node
        now = utils.utcnow()
        folder_node = treenode_stack["FOLDER"]
        file_node = treenode_stack["FILE"]
        assert folder_node.deleted is False
        assert folder_node.deleted_at is None
        assert file_node.deleted is False
        assert file_node.deleted_at is None

        # When: the folder is deleted
        folder_node.delete()
        folder_node.refresh_from_db()
        file_node.refresh_from_db()

        # Then: both folder and file are deleted
        assert folder_node.deleted
        assert folder_node.deleted_at == now
        assert file_node.deleted
        assert file_node.deleted_at == now

    @mark.django_db
    def test_delete__success_already_deleted(
        self,
        make_treenode,
        treenode_stack,
    ):
        """TreeNode.delete is a noop for already deleted rows"""
        # Given: an already deleted treenode
        now = utils.utcnow()
        treenode = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FILE",
            deleted=True,
            deleted_at=now,
        )
        treenode.refresh_from_db()
        assert treenode.deleted
        assert treenode.deleted_at == now

        # When: we try to delete it again
        treenode.delete()
        treenode.refresh_from_db()

        # Then: it's still deleted
        assert treenode.deleted
        assert treenode.deleted_at == now

    @mark.django_db
    def test_delete__fail_deleting_organization_and_collection(
        self,
        treenode_stack,
    ):
        """TreeNode.delete raises on delete of organization and collection treenodes"""
        # Given: org and col-type nodes
        org_node = treenode_stack["ORGANIZATION"]
        col_node = treenode_stack["COLLECTION"]

        # When: we try to delete either, Then: they both raise
        with raises(TreeNodeException):
            org_node.delete()
        with raises(TreeNodeException):
            col_node.delete()

    @mark.django_db
    def test_hard_delete__success(
        self,
        treenode_stack,
    ):
        """TreeNode.hard_delete correctness"""
        # Given: an undeleted node
        file_node = treenode_stack["FILE"]
        file_node_id = file_node.id

        # When: it's hard deleted
        file_node.hard_delete()

        # Then: it's physically removed from the db
        with raises(TreeNode.DoesNotExist):
            TreeNode.objects.get(pk=file_node_id)

    @mark.django_db
    def test_deletion_aware_tree_node_manager__hides_soft_deleted_nodes(
        self,
        treenode_stack,
    ):
        """DeletionAwareTreeNodeManager makes soft-deleted objects invisible"""
        # Given: an undeleted node
        file_node = treenode_stack["FILE"]
        file_node_id = file_node.id

        # When: it's soft deleted
        file_node.delete()
        file_node.refresh_from_db()

        # Then: it's invisible from the default query manager...
        with raises(TreeNode.DoesNotExist):
            TreeNode.objects.get(pk=file_node_id)

        # ... but it's not actually gone
        file_node.refresh_from_db()
        file_node.deleted = False
        file_node.save()
        TreeNode.objects.get(pk=file_node_id)


class TestReport:
    """Tests for the Report model"""

    @mark.django_db
    def test_fixity_report_json_is_deferred(
        self, django_assert_num_queries, make_fixity_report
    ):
        """Check DeferredJSONReportManager defers loading of the report_json field until
        it is explicitly called."""
        report = make_fixity_report()
        with django_assert_num_queries(1):
            # Django runs one query to fetch the report...
            rep = Report.objects.get(pk=report.pk)
            # ...and no further query is needed to read the report_type field value.
            str(rep.report_type)
        with django_assert_num_queries(2):
            # Django runs one query to fetch the report...
            rep = Report.objects.get(pk=report.pk)
            # ...and a second query to fetch the report_json field value.
            str(rep.report_json)


@mark.django_db
def test_collection_name_change_triggers_treenode_name_update(make_collection):
    """Check that updating a Collection's name field will automatically update the name
    field of its associated TreeNode."""
    # Create a collection.
    collection = make_collection()
    node = collection.tree_node
    node.refresh_from_db()
    assert node.name == collection.name

    # Rename the Collection.
    new_name = collection.name[::-1]  # reverse
    assert new_name != collection.name
    collection.name = new_name
    collection.save()

    # Verify that the TreeNode name has also been updated.
    node.refresh_from_db()
    assert node.name == collection.name == new_name


@mark.django_db
def test_collection_type_treenode_name_change_triggers_collection_name_update(
    make_collection,
):
    """Check that updating a COLLECTION-type TreeNode's name field will automatically
    update the name field of its associated Collection."""
    # Create a collection.
    # Note that a TreeNode with name=collection.name is automatically created by the
    # Collection post_save signal handler.
    collection = make_collection()
    node = collection.tree_node
    node.refresh_from_db()
    assert collection.name == node.name

    # Rename the node.
    new_name = node.name[::-1]  # reverse
    assert new_name != node.name
    node.name = new_name
    node.save()

    # Verify that the Collection name has also been updated.
    collection.refresh_from_db()
    assert collection.name == node.name == new_name

    # Check that attempting to set a TreeNode.name value that exceeds the max
    # Collection.name length raises a FieldError.
    node.name += "!"
    with raises(FieldError) as e:
        node.save()


@mark.django_db
def test_organization_type_treenode_name_length_cannot_exceed_organization_name_length(
    treenode_stack,
):
    """Check that attempting to set an ORGANIZATION-type TreeNode name value to a length
    that exceeds the max length of the Organization.name field raises a FieldError."""
    node = treenode_stack["ORGANIZATION"]
    node.name += "!"
    with raises(FieldError):
        node.save()
