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
