-- used when we get descendants or ancestors
CREATE INDEX vault_treenode_path_gist
          ON vault_treenode
       USING GIST(path);
