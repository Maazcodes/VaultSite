-- This file exists only for reference; it's not used by migrations or expected
-- to be runnable.

-------------------------------------------------------------------------------
-- Trigger Functions ----------------------------------------------------------
-------------------------------------------------------------------------------

-- function to calculate the path of any given treenode
CREATE OR REPLACE FUNCTION _update_treenode_path() RETURNS TRIGGER AS
$$
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path = NEW.id::text::ltree;
    ELSE
        SELECT path || NEW.id::text::ltree
          FROM vault_treenode
         WHERE id = NEW.parent_id
          INTO NEW.path;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _reject_null_treenode_path() RETURNS TRIGGER AS
$$
BEGIN
    IF NEW.path IS NULL THEN
        RAISE EXCEPTION 'path may not be updated to NULL';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- function to update the path of the descendants of a treenode
CREATE OR REPLACE FUNCTION _update_descendants_treenode_path() RETURNS TRIGGER AS
$$
BEGIN
    UPDATE vault_treenode
       SET path = NEW.path || subpath(vault_treenode.path, nlevel(OLD.path))
     WHERE vault_treenode.path <@ OLD.path AND id != NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- performs TreeNode file accounting on INSERT
CREATE OR REPLACE FUNCTION _do_treenode_insert_file_accounting() RETURNS TRIGGER AS
$$
BEGIN
    UPDATE vault_treenode
    SET
        file_count = file_count + 1,
        size = COALESCE(size, 0) + COALESCE(NEW.size, 0)
    WHERE
        path @> (
            SELECT path
            FROM vault_treenode
            WHERE id = NEW.parent_id
        );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- performs TreeNode file accounting on hard DELETE
CREATE OR REPLACE FUNCTION _do_treenode_delete_file_accounting() RETURNS TRIGGER AS
$$
DECLARE
    size_delta int;
BEGIN
    IF OLD.node_type != 'FILE' THEN
        size_delta = 0;
    ELSE
        size_delta = COALESCE(OLD.size, 0);
    END IF;

    UPDATE vault_treenode
    SET
        file_count = file_count - 1,
        size = COALESCE(size, 0) - size_delta
    WHERE
        path @> OLD.path
    AND
        path != OLD.path;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- performs TreeNode file accounting on UPDATE
CREATE OR REPLACE FUNCTION _do_treenode_update_file_accounting() RETURNS TRIGGER AS
$$
DECLARE
    file_count_delta int;
    size_delta int;
BEGIN
    IF pg_trigger_depth() > 1 THEN
        -- prevent trigger recursion
        RETURN NULL;
    END IF;

    IF OLD.deleted != NEW.deleted THEN
        -- case: soft un/delete
        IF NEW.deleted THEN
            size_delta = -1 * COALESCE(NEW.size, 0);
            file_count_delta = -1;
        ELSE
            size_delta = 1 * COALESCE(NEW.size, 0);
            file_count_delta = 1;
        END IF;

        -- Only propagate size changes to ancestors for FILE node deletions.
        -- This is necessary to avoid double-counting sizes which exist not
        -- only for FILE nodes, but for all non-FILE ancestors.
        if NEW.node_type != 'FILE' THEN
            size_delta = 0;
        END IF;

        UPDATE vault_treenode
        SET
            file_count = file_count + file_count_delta,
            size = COALESCE(size, 0) + size_delta
        WHERE
            path @> NEW.path
        AND
            path != NEW.path;

    ELSIF OLD.parent_id != NEW.parent_id THEN
        -- case: move

        IF NEW.node_type = 'FOLDER' THEN
            -- case: +1 for FOLDER nodes because parents' file_count includes
            -- folders because the behavior of
            -- _do_treenode_insert_file_accounting() increments ancestors'
            -- file_count on creation of all children, regardless of node_type
            file_count_delta = OLD.file_count + 1;
        ELSE
            file_count_delta = OLD.file_count;
        END IF;

        -- decrement old ancestors
        UPDATE vault_treenode AS self
        SET
            file_count = self.file_count - file_count_delta,
            size = COALESCE(self.size, 0) - COALESCE(OLD.size, 0)
        FROM
            vault_treenode as old_parent
        WHERE
            old_parent.id = OLD.parent_id
        AND
            self.path @> old_parent.path
        AND
            self.id != OLD.id;

        -- increment new ancestors
        UPDATE vault_treenode AS self
        SET
            file_count = self.file_count + file_count_delta,
            size = COALESCE(self.size, 0) + COALESCE(NEW.size, 0)
        FROM
            vault_treenode as new_parent
        WHERE
            new_parent.id = NEW.parent_id
        AND
            self.path @> new_parent.path
        AND
            self.id != NEW.id;

    ELSIF OLD.size != NEW.size THEN
        -- case: size change
        IF NEW.node_type != 'FILE' THEN
            RAISE EXCEPTION 'size of non-FILE nodes may not be explicitly modified';
        END IF;

        UPDATE vault_treenode
        SET
            size = COALESCE(size, 0) - COALESCE(OLD.size, 0) + COALESCE(NEW.size, 0)
        WHERE
            path @> NEW.path
        AND
            path != NEW.path;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- ensures new FILE TreeNodes have file_count = 1
CREATE OR REPLACE FUNCTION _do_treenode_set_new_file_count() RETURNS TRIGGER AS
$$
BEGIN
    NEW.file_count = 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-------------------------------------------------------------------------------
-- Triggers -------------------------------------------------------------------
-------------------------------------------------------------------------------
-- calculate the path every time we insert a new treenode
DROP TRIGGER IF EXISTS treenode_path_insert_trg ON vault_treenode;
CREATE TRIGGER treenode_path_insert_trg
    BEFORE INSERT ON vault_treenode
    FOR EACH ROW
    EXECUTE PROCEDURE _update_treenode_path();

-- calculate the path when updating the parent or the code
DROP TRIGGER IF EXISTS treenode_path_update_trg ON vault_treenode;
CREATE TRIGGER treenode_path_update_trg
    BEFORE UPDATE ON vault_treenode
    FOR EACH ROW
    WHEN (OLD.parent_id IS DISTINCT FROM NEW.parent_id
        OR OLD.id IS DISTINCT FROM NEW.id)
    EXECUTE PROCEDURE _update_treenode_path();


-- if the path was updated, update the path of the descendants
DROP TRIGGER IF EXISTS treenode_path_after_trg ON vault_treenode;
CREATE TRIGGER treenode_path_after_trg
    AFTER UPDATE ON vault_treenode
    FOR EACH ROW
    WHEN (NEW.path IS DISTINCT FROM OLD.path)
    EXECUTE PROCEDURE _update_descendants_treenode_path();

-- assert modified rows can't set path to NULL
DROP TRIGGER IF EXISTS treenode_path_prevent_null_trg ON vault_treenode;
CREATE TRIGGER treenode_path_prevent_null_trg
    BEFORE UPDATE ON vault_treenode
    FOR EACH ROW
    WHEN (NEW.path IS NULL)
    EXECUTE PROCEDURE _reject_null_treenode_path();

-- do TreeNode accounting on INSERT
CREATE TRIGGER treenode_file_accounting_insert_trg
    AFTER INSERT ON vault_treenode
    FOR EACH ROW
    WHEN (NEW.node_type = 'FILE' OR NEW.node_type = 'FOLDER')
    EXECUTE PROCEDURE _do_treenode_insert_file_accounting();

-- do TreeNode accounting on UPDATE
CREATE TRIGGER treenode_file_accounting_update_trg
    AFTER UPDATE ON vault_treenode
    FOR EACH ROW
    WHEN (NEW.node_type = 'FILE' OR NEW.node_type = 'FOLDER')
    EXECUTE PROCEDURE _do_treenode_update_file_accounting();

-- do TreeNode accounting on DELETE
CREATE TRIGGER treenode_file_accounting_delete_trg
    AFTER DELETE ON vault_treenode
    FOR EACH ROW
    WHEN (OLD.node_type = 'FILE' OR OLD.node_type = 'FOLDER')
    EXECUTE PROCEDURE _do_treenode_delete_file_accounting();

-- ensure new FILE TreeNodes have file_count = 1
CREATE TRIGGER treenode_set_new_file_count
    BEFORE INSERT ON vault_treenode
    FOR EACH ROW
    WHEN (NEW.node_type = 'FILE')
    EXECUTE PROCEDURE _do_treenode_set_new_file_count();
