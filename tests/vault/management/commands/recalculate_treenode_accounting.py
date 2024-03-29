import pytest

from vault.management.commands.recalculate_treenode_accounting import (
    _calculate_parent_sizes,
    _get_exhausted_parents,
    _is_parent_of,
    _walk_treenodes,
)


ROWS = [
    (1, None, "1", 0, "ORGANIZATION"),
    (10066, 1, "1.10066", 0, "COLLECTION"),
    (17305, 10066, "1.10066.17305", 0, "FOLDER"),
    (17306, 17305, "1.10066.17305.17306", 0, "FOLDER"),
    (17307, 17306, "1.10066.17305.17306.17307", 10, "FILE"),
    (17308, 17306, "1.10066.17305.17306.17308", 0, "FOLDER"),
    (17309, 17308, "1.10066.17305.17306.17308.17309", 7, "FILE"),
    (17310, 17305, "1.10066.17305.17310", 3, "FILE"),
    (10278, 1, "1.10278", 9, "FILE"),
    (2, None, "2", 0, "FOLDER"),
    (4, None, "4", 0, "FOLDER"),
    (5, 4, "4.5", 420, "FILE"),
]


def test_walk_treenodes():
    expected = [
        (1, None, "1", 0, [], "ORGANIZATION", False),
        (10066, 1, "1.10066", 0, [], "COLLECTION", False),
        (17305, 10066, "1.10066.17305", 0, [], "FOLDER", False),
        (17306, 17305, "1.10066.17305.17306", 0, [], "FOLDER", False),
        (17307, 17306, "1.10066.17305.17306.17307", 10, [], "FILE", False),
        (17308, 17306, "1.10066.17305.17306.17308", 0, [], "FOLDER", False),
        (
            17309,
            17308,
            "1.10066.17305.17306.17308.17309",
            7,
            [17308, 17306],
            "FILE",
            False,
        ),
        (17310, 17305, "1.10066.17305.17310", 3, [17305, 10066], "FILE", False),
        (10278, 1, "1.10278", 9, [1], "FILE", False),
        (2, None, "2", 0, [], "FOLDER", True),
        (4, None, "4", 0, [], "FOLDER", False),
        (5, 4, "4.5", 420, [4], "FILE", False),
    ]

    actual = list(_walk_treenodes(ROWS))
    assert expected == actual


@pytest.mark.parametrize(
    "rows,expected",
    [
        (
            [
                (1, None, "1", 0, "FOLDER"),
                (2, None, "2", 0, "FOLDER"),
            ],
            [
                (1, None, "1", 0, [], "FOLDER", True),
                (2, None, "2", 0, [], "FOLDER", True),
            ],
        ),
        (
            [
                (1, None, "1", 0, "FOLDER"),
                (2, None, "1.2", 0, "FILE"),
            ],
            [
                (1, None, "1", 0, [], "FOLDER", False),
                (2, None, "1.2", 0, [1], "FILE", False),
            ],
        ),
    ],
)
def test_walk_treenodes_is_empty(rows, expected):
    """_walk_treenodes produces correct results for is_empty"""
    actual = list(_walk_treenodes(rows))
    assert expected == actual


def test_get_exhausted_parents():
    path1 = "1.10066.17305.17306.17308.17309"
    path2 = "1.10066.17305.17310"

    expected = [17308, 17306]
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = "1.10066.17305.17310"
    path2 = "1.10066.17305.17306.17308.17309"
    expected = []
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = "1.10066.17305.17310"
    path2 = "1.10066.17305.17310"
    expected = []
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = ""
    path2 = ""
    expected = []
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = "1"
    path2 = "1"
    expected = []
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = "1.10066.17305.17310"
    path2 = "2.10278"
    expected = [17305, 10066, 1]
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual

    path1 = "4.5"
    path2 = None
    expected = [4]
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual


def test_get_exhausted_parents__empty_folder():
    path1 = "1.2"
    path2 = "3"
    expected = [1]
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual


def test_get_exhausted_parents__disjoint():
    path1 = "2"
    path2 = "3"
    expected = []
    actual = _get_exhausted_parents(path1, path2)
    assert expected == actual


def test_calculate_parent_sizes_success():
    expected = [
        (17308, 7, 1, 7),
        (17306, 17, 3, 7),
        (17305, 20, 5, 8),
        (10066, 20, 6, 8),
        (1, 29, 8, 9),
        (2, 0, 0, 10),
        (4, 420, 1, 12),
    ]
    actual = list(_calculate_parent_sizes(ROWS))
    assert expected == actual


def test_calculate_parent_sizes_empty():
    rows = []
    assert [] == list(_calculate_parent_sizes(rows))


def test_calculate_parent_sizes_tiny():
    rows = [
        (1, None, "1", 0, "FOLDER"),
        (2, 1, "1.2", 420, "FILE"),
    ]
    expected = [
        (1, 420, 1, 2),
    ]
    actual = list(_calculate_parent_sizes(rows))
    assert expected == actual


def test_calculate_parent_sizes_empty_parent():
    rows = [
        (1, None, "1", 0, "FOLDER"),
        (2, None, "2", 0, "FOLDER"),
    ]
    expected = [
        (1, 0, 0, 1),
        (2, 0, 0, 2),
    ]
    actual = list(_calculate_parent_sizes(rows))
    assert expected == actual


def test_test():
    rows = [
        (1, None, "1", 0, "FOLDER"),
        (2, 1, "1.2", 0, "FOLDER"),
        (3, None, "3", 0, "FOLDER"),
    ]
    expected = [
        (2, 0, 0, 2),
        (1, 0, 0, 2),
        (3, 0, 0, 3),
    ]
    actual = list(_calculate_parent_sizes(rows))
    assert expected == actual


@pytest.mark.parametrize(
    "path1,path2,expected",
    [
        ("1", "1.2", True),
        ("1", "1.2.3", False),
        ("1.2", "1.2.3", True),
        ("1.2", "1.3.3", False),
        ("1", "2", False),
        ("1", None, False),
        ("1", "1", False),
        ("1.2", "1", False),
    ],
)
def test_is_parent_of(path1: str, path2: str, expected: bool):
    """_is_parent_of basic correctness"""
    actual = _is_parent_of(path1, path2)
    assert expected == actual
