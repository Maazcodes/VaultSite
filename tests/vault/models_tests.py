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
    TreeNode,
)


###############################################################################
# Constants
###############################################################################


TREE_NODE_TYPES = {"ORGANIZATION", "COLLECTION", "FOLDER", "FILE"}


###############################################################################
# Fixtures
###############################################################################


@fixture
def treenode_stack(make_treenode):
    """Return a complete valid TreeNode type hierarchy dict keyed by type name."""
    # Set valid-length name values for ORGANIZATION and COLLECTION-type nodes.
    organization_node = make_treenode(
        node_type="ORGANIZATION", parent=None, name=prepare(Organization).name
    )
    collection_node = make_treenode(
        node_type="COLLECTION", parent=organization_node, name=prepare(Collection).name
    )
    folder_node = make_treenode(node_type="FOLDER", parent=collection_node)
    file_node = make_treenode(node_type="FILE", parent=folder_node)
    return {
        "ORGANIZATION": organization_node,
        "COLLECTION": collection_node,
        "FOLDER": folder_node,
        "FILE": file_node,
    }


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
def test_collection_name_change_triggers_treenode_name_update(make_collection):
    """Check that updating a Collection's name field will automatically update the name
    field of its associated TreeNode."""
    # Create a collection.
    collection = make_collection()
    node = collection.tree_node
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
