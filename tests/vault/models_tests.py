from django.core.exceptions import FieldError
from django.db.transaction import atomic
import django.db

from freezegun import freeze_time
from pytest import (
    mark,
    raises,
)

from vault.models import (
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

    @mark.django_db
    def test_get_owned_by__basic_success(self, make_user, make_treenode):
        """Treenode.get_owned_by basic correctness"""
        # Given: a treenode hierarchy owned by a user
        user = make_user()
        org = user.organization
        org_node = make_treenode(parent=None, node_type="ORGANIZATION")
        org.tree_node = org_node
        org.save()
        coll_node = make_treenode(parent=org_node, node_type="COLLECTION")

        # When: we ask for a node owned by the given user
        actual = TreeNode.get_owned_by(coll_node.id, user_id=user.id)

        # Then: the correct node is returned
        assert actual == coll_node

    @mark.django_db
    def test_get_owned_by__rejects_unauthorized(self, make_user, make_treenode):
        """Treenode.get_owned_by raises when given user doesn't own TreeNode"""
        # Given: a treenode hierarchy NOT owned by a given user
        bogus_user = make_user()
        user = make_user()
        org = user.organization
        org_node = make_treenode(parent=None, node_type="ORGANIZATION")
        org.tree_node = org_node
        org.save()
        coll_node = make_treenode(parent=org_node, node_type="COLLECTION")

        # When: we ask for a node NOT owned by the given user
        # Then: an exception is raised
        with raises(TreeNode.DoesNotExist):
            TreeNode.get_owned_by(coll_node.id, user_id=bogus_user.id)

    @mark.django_db
    def test_get_ancestor__basic_success(self, treenode_stack):
        # Given: a simple treenode hierarchy
        file_node = treenode_stack["FILE"]
        collection_node = treenode_stack["COLLECTION"]

        # When: the collection-type parent of a file is requested
        actual = file_node.get_ancestor(TreeNode.Type.COLLECTION)

        # Then: the correct collection is returned
        assert actual == collection_node

    @mark.django_db
    def test_get_ancestor__nested_folders(self, treenode_stack, make_treenode):
        # Given: a nested folder hierarchy
        folder1 = treenode_stack["FOLDER"]
        folder2 = make_treenode(parent=folder1, node_type="FOLDER")
        folder2.refresh_from_db()
        file2 = make_treenode(parent=folder2, node_type="FILE")
        file2.refresh_from_db()

        # When: the folder-type parent of a file in a nested folder hierarchy
        # is requested
        actual = file2.get_ancestor(TreeNode.Type.FOLDER)

        # Then: the closest folder ancestor to the file is returned
        assert actual == folder2

    @mark.django_db
    def test_get_ancestor__nonexistent_ancestor_type(self, treenode_stack):
        # Given: a collection node as part of a treenode hierarchy
        collection_node = treenode_stack["COLLECTION"]

        # When: an folder-type ancestor of the collection is requested
        actual = collection_node.get_ancestor("FOLDER")

        # Then: no TreeNode is returned
        assert actual is None

    @mark.django_db
    def test_get_collection(self, make_collection, make_treenode):
        # Given: a a collection and treenode hierarchy
        collection = make_collection()
        collection_node = collection.tree_node
        folder_node = make_treenode(parent=collection_node)
        folder_node.refresh_from_db()

        # When: the collection of a folder-type treenode is requested
        actual = folder_node.get_collection()

        # Then: the correct collection is returned
        assert collection == actual


class TestTreeNodeAccountingTriggers:
    """Test case for create/update/delete file accounting triggers"""

    @mark.django_db
    def test_creation_basic_success(self, treenode_stack):
        """New TreeNode hierarchy is created with correct size and file_count"""
        # only a file count of 2 because collection and org aren't counted
        # by the file accounting triggers
        assert treenode_stack["ORGANIZATION"].file_count == 2
        assert treenode_stack["COLLECTION"].file_count == 2
        assert treenode_stack["FOLDER"].file_count == 1
        assert treenode_stack["FILE"].file_count == 1

        assert treenode_stack["ORGANIZATION"].size == 420
        assert treenode_stack["COLLECTION"].size == 420
        assert treenode_stack["FOLDER"].size == 420
        assert treenode_stack["FILE"].size == 420

    @mark.django_db
    def test_creation_complex_hierarchy(self, treenode_stack, make_treenode):
        """complex TreeNode hierarchy is created correctly"""
        # Given: a treenode hierarchy
        assert treenode_stack["FOLDER"].file_count == 1
        assert treenode_stack["FILE"].file_count == 1
        assert treenode_stack["FOLDER"].size == 420
        assert treenode_stack["FILE"].size == 420
        folder = treenode_stack["FOLDER"]

        # When: a new folder and file are added
        folder2 = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FOLDER",
        )
        make_treenode(
            parent=folder2,
            node_type="FILE",
            size=42,
        )

        # Then: the hierarchy reflects the new nodes
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder2.size == 42
        assert folder2.file_count == 1
        assert folder.size == 462
        assert folder.file_count == 3

    @mark.django_db
    def test_deletion_basic_success(self, treenode_stack):
        """TreeNode deletion triggers updates to ancestors' size and file_count"""
        # only a file count of 2 because collection and org aren't counted
        # by the file accounting triggers
        assert treenode_stack["ORGANIZATION"].file_count == 2
        assert treenode_stack["ORGANIZATION"].size == 420

        treenode_stack["FILE"].hard_delete()

        treenode_stack["ORGANIZATION"].refresh_from_db()
        assert treenode_stack["ORGANIZATION"].file_count == 1
        assert treenode_stack["ORGANIZATION"].size == 0

    @mark.django_db
    def test_deletion_nested_folders(self, treenode_stack, make_treenode):
        """TreeNode hard deletion independent of other files"""
        # folder
        # └── folder2
        #     └── file2
        folder = treenode_stack["FOLDER"]
        folder2 = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FOLDER",
        )
        file2 = make_treenode(
            parent=folder2,
            node_type="FILE",
            size=7,
        )
        file2.refresh_from_db()
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder2.file_count == 1
        assert folder2.size == 7
        assert folder.file_count == 3
        assert folder.size == 427

        folder2.hard_delete()
        with raises(TreeNode.DoesNotExist):
            file2.refresh_from_db()

        folder.refresh_from_db()
        assert folder.size == 420
        assert folder.file_count == 1

    @mark.django_db
    def test_deletion_nested_correctness(self, treenode_stack, make_treenode):
        """TreeNode hard deletion independent of other files"""
        # Given: a complex file hierarchy
        # folder
        # ├── file
        # └── folder2
        #     └── file2
        file = treenode_stack["FILE"]
        folder = treenode_stack["FOLDER"]
        folder2 = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FOLDER",
        )
        file2 = make_treenode(
            parent=folder2,
            node_type="FILE",
            size=42,
        )
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder2.size == 42
        assert folder2.file_count == 1
        assert folder.size == 462
        assert folder.file_count == 3

        # When: a file in the hierarchy is removed
        # folder
        # ├── XXXX
        # └── folder2
        #     └── file2
        file.hard_delete()
        folder.refresh_from_db()
        folder2.refresh_from_db()
        file2.refresh_from_db()

        # Then: its direct parent is updated
        assert folder.size == 42
        assert folder.file_count == 2
        # ... and so is its distant ancestor
        assert folder2.size == 42
        assert folder2.file_count == 1
        # ... but its cousin file isn't affected
        assert file2.size == 42

    @mark.django_db
    def test_soft_delete_success(self, treenode_stack):
        """TreeNode soft deletion produces correct accounting"""
        # Given: a node hierarchy
        folder = treenode_stack["FOLDER"]
        file = treenode_stack["FILE"]
        assert folder.file_count == 1
        assert folder.size == 420

        # When: a file is soft-deleted
        file.delete()
        file.refresh_from_db()
        assert file.deleted

        # Then: the accounting changes propagate to the ancestor
        folder.refresh_from_db()
        assert folder.size == 0
        assert folder.file_count == 0

    @mark.django_db
    def test_soft_delete_one_file_among_multiple(
        self,
        treenode_stack,
        make_treenode,
    ):
        """TreeNode soft deletion doesn't affect sibling files"""
        # Given: a node hierarchy with two files
        # folder
        # ├── file
        # └── file2
        folder = treenode_stack["FOLDER"]
        file = treenode_stack["FILE"]
        file2 = make_treenode(parent=folder, node_type="FILE", size=42)
        folder.refresh_from_db()
        assert folder.file_count == 2
        assert folder.size == 462

        # When: one file is deleted
        # folder
        # ├── XXXX
        # └── file2
        file.delete()
        file.refresh_from_db()
        assert file.deleted

        # Then: ancestor accounting is correct and sibling file is unaffected
        folder.refresh_from_db()
        file2.refresh_from_db()
        assert folder.size == 42
        assert folder.file_count == 1
        assert file2.size == 42

    @mark.django_db
    def test_soft_delete_folder(
        self,
        treenode_stack,
        make_treenode,
    ):
        """TreeNode folder soft deletion produces correct accounting"""
        # Given: a complex file hierarchy
        # folder
        # ├── file
        # └── folder2
        #     └── file2
        file = treenode_stack["FILE"]
        folder = treenode_stack["FOLDER"]
        folder2 = make_treenode(
            parent=treenode_stack["FOLDER"],
            node_type="FOLDER",
        )
        file2 = make_treenode(
            parent=folder2,
            node_type="FILE",
            size=42,
        )
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder2.size == 42
        assert folder2.file_count == 1
        assert folder.size == 462
        assert folder.file_count == 3

        # When: a nested folder is deleted
        # folder
        # ├── file
        # └── XXXXXXX
        #     └── file2
        folder2.delete()
        folder2.refresh_from_db()
        assert folder2.deleted

        # Then: ancestral accounting is correct...
        folder.refresh_from_db()
        file.refresh_from_db()
        assert folder.size == 420
        assert folder.file_count == 1

        # ...changes recurse to descendant...
        file2.refresh_from_db()
        assert file2.deleted
        assert (
            file2.size == 42
        ), "size of recursively soft-deleted file shouldn't change"

        # ...and file sibling to deleted folder is unaffected
        file.refresh_from_db()
        assert not file.deleted
        assert file.size == 420

    @mark.django_db
    def test_move_file(self, treenode_stack, make_treenode):
        """TreeNode file move produces correct accounting"""
        # Given: a complex node hierarchy
        # folder
        # ├── file
        # └── folder2
        folder = treenode_stack["FOLDER"]
        file = treenode_stack["FILE"]
        folder2 = make_treenode(
            parent=folder,
            node_type="FOLDER",
        )
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert file.size == 420
        assert folder.size == 420
        assert folder.file_count == 2
        assert folder2.file_count == 0

        # When: file is moved between folders
        # folder
        # └── folder2
        #     └── file
        file.parent = folder2
        file.save()
        file.refresh_from_db()
        assert file.parent_id == folder2.id

        # Then:  old and new parent folder have correct accounting
        folder.refresh_from_db()
        folder2.refresh_from_db()
        assert file.size == 420
        assert file.file_count == 1
        assert folder.file_count == 2
        assert folder.size == 420
        assert folder2.size == 420
        assert folder2.file_count == 1

        # When: the file is moved back to its original folder
        # folder
        # ├── file
        # └── folder2
        file.parent = folder
        file.save()
        file.refresh_from_db()
        assert file.parent_id == folder.id

        # Then: all accounting is back to where we began
        folder.refresh_from_db()
        folder2.refresh_from_db()
        assert file.size == 420
        assert file.file_count == 1
        assert folder.file_count == 2
        assert folder.size == 420
        assert folder2.size == 0
        assert folder2.file_count == 0

    @mark.django_db
    def test_move_folder(self, treenode_stack, make_treenode):
        """TreeNode folder move produces correct accounting"""
        # Given: a nested node hierarchy
        # folder
        # └── folder2
        #     └── folder3
        #         └── file2
        folder = treenode_stack["FOLDER"]
        folder2 = make_treenode(
            parent=folder,
            node_type="FOLDER",
        )
        folder3 = make_treenode(
            parent=folder2,
            node_type="FOLDER",
        )
        file2 = make_treenode(
            parent=folder3,
            node_type="FILE",
            size=7,
        )
        file2.refresh_from_db()
        folder3.refresh_from_db()
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder.size == 427
        assert folder.file_count == 4
        assert folder2.size == 7
        assert folder2.file_count == 2
        assert folder3.size == 7
        assert folder3.file_count == 1
        assert file2.size == 7

        # When: folder is moved
        # folder
        # ├── folder2
        # └── folder3
        #     └── file2
        folder3.parent = folder
        folder3.save()

        # Then: all accounting is correct
        folder.refresh_from_db()
        folder2.refresh_from_db()
        folder3.refresh_from_db()
        file2.refresh_from_db()
        assert folder.size == 427
        assert folder.file_count == 4
        assert folder2.size == 0
        assert folder2.file_count == 0
        assert folder3.size == 7
        assert folder3.file_count == 1
        assert file2.size == 7

    @mark.django_db
    def test_move_only_folder(self, treenode_stack, make_treenode):
        """Treenode empty folder move produces correct accounting"""
        # Given: a nested node hierarchy
        # folder
        # └── folder2
        #     └── folder3
        folder = treenode_stack["FOLDER"]
        folder2 = make_treenode(
            parent=folder,
            node_type="FOLDER",
        )
        folder3 = make_treenode(
            parent=folder2,
            node_type="FOLDER",
        )
        folder3.refresh_from_db()
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder.size == 420
        assert folder.file_count == 3
        assert folder2.size == 0
        assert folder2.file_count == 1
        assert folder3.size == 0
        assert folder3.file_count == 0

        # When: an empty folder is moved
        # folder
        # ├── folder2
        # └── folder3
        folder3.parent = folder
        folder3.save()

        # Then: all accounting is correct
        folder3.refresh_from_db()
        folder2.refresh_from_db()
        folder.refresh_from_db()
        assert folder.size == 420
        assert folder.file_count == 3
        assert folder2.size == 0
        assert folder2.file_count == 0
        assert folder3.size == 0
        assert folder3.file_count == 0

    @mark.django_db
    def test_size_change(self, treenode_stack):
        """Treenode file size change produces correct results"""
        # Given: a file in a folder
        folder = treenode_stack["FOLDER"]
        file = treenode_stack["FILE"]
        assert file.size == 420
        assert folder.size == 420
        assert folder.file_count == 1

        # When: the size of the file changes
        file.size = 7
        file.save()

        # Then: the size change is reflected on the parent folder
        folder.refresh_from_db()
        assert folder.size == 7
        assert folder.file_count == 1

    @mark.django_db
    def test_reject_folder_size_change(self, treenode_stack):
        """Treenode file size change is rejected on non-FILEs"""
        # Given: a folder
        folder = treenode_stack["FOLDER"]
        assert folder.size == 420

        # When: a size change is attempted on the folder
        # Then: the change is rejected...
        with atomic():
            # note: atomic() tx block required for isolation because pg
            # exceptions foul the current transaction
            with raises(django.db.InternalError) as e:
                folder.size = 7
                folder.save()
            assert "size of non-FILE nodes may not be explicitly modified" in str(e)

        # ...and the folder size is unchanged
        folder.refresh_from_db()
        assert folder.size == 420

    @mark.django_db
    def test_reject_multiple_managed_attr_changes(self, treenode_stack, make_treenode):
        """Treenode rejects changes to more than one managed attribute"""
        # Managed attributes: `deleted`, `parent_id`, `size`

        # Given: a TreeNode
        collection = treenode_stack["COLLECTION"]
        file = treenode_stack["FILE"]
        folder2 = make_treenode(parent=collection, node_type="FOLDER")

        # When: two managed attributes change
        file.size = 42
        file.deleted = True

        # Then: the change is rejected by trigger
        with atomic():
            with raises(django.db.InternalError):
                file.save()

        # RESET
        file.refresh_from_db()
        assert file.size == 420

        # When: two other managed attributes change
        file.size = 42
        file.parent = folder2

        # Then: the change is rejected by trigger
        with atomic():
            with raises(django.db.InternalError):
                file.save()

        # RESET
        file.refresh_from_db()
        assert file.size == 420

        # When: three managed attributes change
        file.size = 42
        file.deleted = True
        file.parent = folder2

        # Then: the change is rejected by trigger
        with atomic():
            with raises(django.db.InternalError):
                file.save()

    @mark.django_db
    def test_accept_no_managed_attr_changes(self, treenode_stack):
        """Treenode tolerates change to zero managed attributes"""
        # Managed attributes: `deleted`, `parent_id`, `size`

        # Given: a TreeNode FILE
        file = treenode_stack["FILE"]

        # When: a non-managed attribute changes
        file.comment = "foobarbaz"

        # Then: the change is accepted by postgres
        file.save()

    @mark.django_db
    def test_no_soft_then_hard_deletion_double_counting(self, treenode_stack):
        """Treenode soft then hard deletes don't double apply accounting"""
        # Given: a treenode hierarchy
        file = treenode_stack["FILE"]
        folder = treenode_stack["FOLDER"]
        assert file.size == 420
        assert folder.size == 420
        assert folder.file_count == 1

        # When: the file is soft-deleted
        file.deleted = True
        file.save()

        # Then: the ancestors' size and file_count accounting is correct
        folder.refresh_from_db()
        assert folder.size == 0
        assert folder.file_count == 0

        # When: the file is then hard-deleted
        file.hard_delete()

        # Then: the ancestor's size and file_count accounting is still correct,
        # i.e., the deletion of size and/or file_count hasn't been
        # double-counted
        folder.refresh_from_db()
        assert folder.size == 0
        assert folder.file_count == 0

    @mark.django_db
    def test_soft_deleted_inserts_dont_affect_ancestors(
        self,
        treenode_stack,
        make_treenode,
    ):
        """New soft-deleted TreeNodes don't affect ancestors' accounting"""
        # Given: a treenode hierarchy
        file = treenode_stack["FILE"]
        folder = treenode_stack["FOLDER"]
        assert file.size == 420
        assert folder.size == 420
        assert folder.file_count == 1

        # When: a TreeNode is added as soft deleted
        deleted_file = make_treenode(
            parent=folder,
            node_type="FILE",
            deleted=True,
            size=42,
        )
        assert deleted_file.deleted
        assert deleted_file.size == 42

        # Then: folder accounting is unchanged by the insertion of a
        # soft-deleted file node
        folder.refresh_from_db()
        assert folder.size == 420
        assert folder.file_count == 1


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
