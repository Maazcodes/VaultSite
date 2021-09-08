-- make sure we cannot have a path where one of the ancestor is the row itself
-- (this would cause an infinite recursion)
ALTER TABLE vault_treenode
        ADD CONSTRAINT check_no_recursion
            CHECK(index(path, id::text::ltree) = (nlevel(path) - 1));
