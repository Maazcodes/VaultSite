from django.core.exceptions import FieldError

from pytest import (
    fixture,
    mark,
    raises,
)

from vault.models import TreeNode


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
    organization_node = make_treenode(node_type="ORGANIZATION", parent=None)
    collection_node = make_treenode(node_type="COLLECTION", parent=organization_node)
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


@mark.django_db
@mark.parametrize(
    "node_type,valid_parent_types,num_invalid_types",
    (
        ("ORGANIZATION", set(), 4),
        ("COLLECTION", {"ORGANIZATION"}, 3),
        ("FOLDER", {"COLLECTION", "FOLDER"}, 2),
        ("FILE", {"FOLDER"}, 3),
    ),
)
def test_valid_organization_parents(
    make_treenode, treenode_stack, node_type, valid_parent_types, num_invalid_types
):
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
