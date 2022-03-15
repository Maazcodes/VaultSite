from itertools import zip_longest
import time
from typing import List, Iterable, Tuple, Optional

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.transaction import set_autocommit, commit, rollback
from more_itertools import peekable
from tqdm import tqdm

from vault.models import TreeNode

InputRow = Tuple[int, int, str, int, str]
WalkedRow = Tuple[int, Optional[int], str, int, List[int], str]
CalculatedRow = Tuple[int, int, int, int]


class Command(BaseCommand):
    help = "Recursively recalculates TreeNode size and file_count values"

    def add_arguments(self, parser):
        parser.add_argument(
            "--root-id",
            dest="root_id",
            type=int,
            help=(
                "Root TreeNode to which to constrain recursive recalculation. "
                "If omitted, all TreeNodes will be recalculated."
            ),
        )
        parser.add_argument(
            "--no-dry-run",
            dest="dry_run",
            action="store_false",
            help=(
                "Actually modify data. The default is dry-run, which is "
                "guaranteed to be read-only."
            ),
        )

    def handle(self, *args, **options):
        start = time.perf_counter()
        root_id = options["root_id"]
        dry_run = options["dry_run"]

        # implicitly starts a transaction
        # see: https://docs.djangoproject.com/en/4.0/topics/db/transactions/#transactions
        set_autocommit(False)

        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE "vault_treenode" DISABLE TRIGGER ALL;')

        try:
            if root_id is not None:
                qs = TreeNode.objects.filter(pk=root_id)
            else:
                qs = TreeNode.objects.all()
            num_rows = qs.count()

            with tqdm(total=num_rows) as pbar:
                rows = qs.order_by("path").values_list(
                    "id", "parent_id", "path", "size", "node_type"
                )

                for node_id, size, file_count, rows_seen in _calculate_parent_sizes(
                    rows
                ):
                    pbar.update(rows_seen)
                    TreeNode.objects.filter(pk=node_id).update(
                        size=size, file_count=file_count
                    )

            if not dry_run:
                commit()
                self.stdout.write("Changes committed.")
            else:
                rollback()
                self.stdout.write("Changes rolled back because this is a dry run.")
        finally:
            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE "vault_treenode" ENABLE TRIGGER ALL;')

        end = time.perf_counter()
        self.stdout.write(f"Elapsed time: {end - start}s")


def _calculate_parent_sizes(rows: Iterable[InputRow]) -> Iterable[CalculatedRow]:
    """Yields (node_id, subtree_size, subtree_file_count, rows_seen) for each
    non-leaf node encountered in *rows*. *rows* must be sorted by *path*,
    ascending, which, by the behavior of LTREE comparisons, results in a
    depth-first traversal.

    *rows_seen* is a monotonically-increasing count of the number of TreeNodes
    observed at the point at which stats about a given non-leaf node are
    yielded; it can be compared against the size of *rows* to compute progress.
    """
    # stack of non-FILE (aka "container") parent nodes into which sizes are
    # accumulated
    parents_stack = []

    max_rows_seen = 0
    for rows_seen, walked_row in enumerate(_walk_treenodes(rows), 1):
        max_rows_seen = max(max_rows_seen, rows_seen)
        (_id, parent_id, _, size, exhausted_parents, node_type) = walked_row

        if node_type != "FILE":
            # container nodes go on the stack
            size_empty = 0
            file_count_empty = 0
            parents_stack.append([_id, size_empty, file_count_empty])
            continue

        if parent_id is None:
            continue

        # parents atop the stack with non-matching ids indicate empty container
        # nodes; pop and record them
        while len(parents_stack) > 0:
            [top_parent_id, top_parent_size, top_parent_file_count] = parents_stack[-1]
            if top_parent_id == parent_id:
                # case: no empty container nodes atop the stack
                break

            parents_stack.pop()
            yield (top_parent_id, top_parent_size, top_parent_file_count, rows_seen)

        assert parents_stack[-1][0] == parent_id
        parents_stack[-1][1] += size  # add cur nodes size to its parent
        parents_stack[-1][2] += 1  # file count

        # foreach parent whose children have all been seen, record their
        # ultimate sizes
        for epid in exhausted_parents:
            assert parents_stack[-1][0] == epid
            [parent_id, parent_size, parent_file_count] = parents_stack.pop()
            yield (parent_id, parent_size, parent_file_count, rows_seen)

            # record parents' final size to its parent
            if len(parents_stack) > 0:
                parents_stack[-1][1] += parent_size
                count_the_container = 1
                parents_stack[-1][2] += parent_file_count + count_the_container

    # drain and record left-over parents
    for [parent_id, parent_size, parent_file_count] in parents_stack[::-1]:
        yield (parent_id, parent_size, parent_file_count, max_rows_seen)


def _get_exhausted_parents(path1: str, path2: Optional[str]) -> List[int]:
    """Returns nonleaf node ids present in *path1* not found in *path2* in
    reverse order.

    If **path2** is ``None`` then returns the non-leaf path components in **path**
    """
    ids1 = path1.split(".")[:-1]

    if path2 is None:
        return [int(a) for a in ids1][::-1]

    ids2 = path2.split(".")
    return [int(a) for (a, b) in zip_longest(ids1, ids2) if a and a != b][::-1]


def _walk_treenodes(rows: Iterable[InputRow]) -> Iterable[WalkedRow]:
    """Iterator which walks *rows*, returning facts about each row. *rows*
    should be an iterable of ``tuple``, with each containing:

    * id
    * parent_id
    * path
    * size
    * node_type

    The iterator yields tuples containing:

    * id
    * parent_id
    * path
    * size
    * exhausted_parents: ``list`` of ids of parent nodes whose children have
      all been walked
    * node_type
    """
    _rows = peekable(rows)
    for (_id, parent_id, path, size, node_type) in _rows:
        size = size if size is not None else 0
        next_path = _rows.peek(None)[2] if _rows.peek(None) else None
        yield (
            _id,
            parent_id,
            path,
            size,
            _get_exhausted_parents(path, next_path),
            node_type,
        )
