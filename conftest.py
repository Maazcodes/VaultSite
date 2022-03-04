import json

from pytest import fixture

from django.conf import settings
from model_bakery import baker

from vault.models import (
    Collection,
    Geolocation,
    Organization,
    Plan,
    Report,
    TreeNode,
    User,
)


###############################################################################
# Factory Fixtures
###############################################################################


@fixture
def make_collection():
    return lambda **kwargs: baker.make(Collection, **kwargs)


@fixture
def make_geolocation():
    return lambda **kwargs: baker.make(Geolocation, **kwargs)


@fixture
def make_plan(geolocation):
    def maker(**kwargs):
        plan = baker.make(Plan, price_per_terabyte=0, **kwargs)
        plan.default_geolocations.set([geolocation])
        plan.save()
        return plan

    return maker


@fixture
def make_treenode():
    def maker(parent, node_type="FILE", **kwargs):
        # Enforce valid-length default names for ORGANIZATION and COLLECTION-type node.
        model = {"ORGANIZATION": Organization, "COLLECTION": Collection}.get(node_type)
        if model and "name" not in kwargs:
            kwargs["name"] = baker.prepare(model).name
        return baker.make(TreeNode, parent=parent, node_type=node_type, **kwargs)

    return maker


@fixture
def make_organization(make_plan):
    def maker(**kwargs):
        if "plan" not in kwargs:
            kwargs["plan"] = make_plan()
        organization = baker.make(Organization, **kwargs)
        # Assert that a TreeNode is automatically created.
        assert isinstance(organization.tree_node, TreeNode)
        return organization

    return maker


@fixture
def fixity_report_json_body():
    return """
{
    "collectionName" : "1_Parent",
    "startTime" : "2022-03-05T20:39:51.986Z",
    "endTime" : "2022-03-05T20:40:00.394Z",
    "fileCount" : 5,
    "totalSize" : 671366,
    "errorCount" : 0,
    "files" : [
        {
            "filename" : "Image3.png",
            "id" : "treeNode-10286",
            "depositTime" : "2021-11-15T08:12:18.358Z",
            "checkTime" : "2022-03-05T20:39:51.986Z",
            "size" : 172346,
            "success" : true,
            "canonicalChecksums" : [
                "md5:a9fafff10a78d9595c65b83f6128fd90",
                "sha1:5c24e50d12d95964ac733ef829cd7e17d6ae6ac5",
                "sha256:10957d6ef7b791d65894760bddcc86526e8aff91bdc3913ea95d4c70382e0562"
            ],
            "sources" : [
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior",
                    "time" : "2021-11-15T08:12:18.358Z"
                },
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior"
                },
                {
                    "source" : "PBOX",
                    "region" : "us-west-1",
                    "type" : "generated",
                    "location" : "https://archive.org/serve/DPS-VAULT-QA-1-20211115-00001/Deposit:172/Image3.png"
                }
            ]
        },
        {
            "filename" : "Parent/Child/GrandChild/Image6.png",
            "id" : "treeNode-10285",
            "depositTime" : "2021-11-15T14:27:49.587Z",
            "checkTime" : "2022-03-05T20:39:52.103Z",
            "size" : 254775,
            "success" : true,
            "canonicalChecksums" : [
                "md5:31958cfed58b6448f3c91128ed477fdf",
                "sha1:7e047f8f72ac75822f382e442bd81abc56bae287",
                "sha256:848c3b5047a4af53987de6e289c7b04825cce08d70b61d0ea47439492874a3f7"
            ],
            "sources" : [
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior",
                    "time" : "2021-11-15T14:27:49.587Z"
                },
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior"
                },
                {
                    "source" : "PBOX",
                    "region" : "us-west-1",
                    "type" : "generated",
                    "location" : "https://archive.org/serve/DPS-VAULT-QA-1-20211115-00001/Deposit:161/Parent/Child/GrandChild/Image6.png"
                }
            ]
        },
        {
            "filename" : "Parent/Child/Image4.png",
            "id" : "treeNode-10282",
            "depositTime" : "2021-11-15T14:27:49.583Z",
            "checkTime" : "2022-03-05T20:39:52.733Z",
            "size" : 41768,
            "success" : true,
            "canonicalChecksums" : [
                "md5:1e5588c89eeea88ebb6d21aa8b632c76",
                "sha1:7ba73fa5fcc1cb578e3ad0ef8b50eab27a0e2d9b",
                "sha256:bb2173f973c59f78c153737e8b66b708acd88ef8e33c59780f085832b47662b9"
            ],
            "sources" : [
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior",
                    "time" : "2021-11-15T14:27:49.583Z"
                },
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior"
                },
                {
                    "source" : "PBOX",
                    "region" : "us-west-1",
                    "type" : "generated",
                    "location" : "https://archive.org/serve/DPS-VAULT-QA-1-20211115-00001/Deposit:161/Parent/Child/Image4.png"
                }
            ]
        },
        {
            "filename" : "Parent/Image125.png",
            "id" : "treeNode-10280",
            "depositTime" : "2021-11-15T14:27:49.084Z",
            "checkTime" : "2022-03-05T20:39:53.419Z",
            "size" : 30131,
            "success" : true,
            "canonicalChecksums" : [
                "md5:bbcfff9e9af70d1bbf0e551a0141b7eb",
                "sha1:57210cc44f2de7983b255f05bd4292d584b4cda9",
                "sha256:2c5406dea32af691fc20e229907a73c703ff3248018814f890a6db220e97ccab"
            ],
            "sources" : [
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior",
                    "time" : "2021-11-15T14:27:49.084Z"
                },
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior"
                },
                {
                    "source" : "PBOX",
                    "region" : "us-west-1",
                    "type" : "generated",
                    "location" : "https://archive.org/serve/DPS-VAULT-QA-1-20211115-00001/Deposit:161/Parent/Image125.png"
                }
            ]
        },
        {
            "filename" : "Parent/Image3.png",
            "id" : "treeNode-10283",
            "depositTime" : "2021-11-15T14:27:49.161Z",
            "checkTime" : "2022-03-05T20:39:52.208Z",
            "size" : 172346,
            "success" : true,
            "canonicalChecksums" : [
                "md5:a9fafff10a78d9595c65b83f6128fd90",
                "sha1:5c24e50d12d95964ac733ef829cd7e17d6ae6ac5",
                "sha256:10957d6ef7b791d65894760bddcc86526e8aff91bdc3913ea95d4c70382e0562"
            ],
            "sources" : [
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior",
                    "time" : "2021-11-15T14:27:49.161Z"
                },
                {
                    "source" : "VAULT",
                    "region" : "us-west-2",
                    "type" : "prior"
                },
                {
                    "source" : "PBOX",
                    "region" : "us-west-1",
                    "type" : "generated",
                    "location" : "https://archive.org/serve/DPS-VAULT-QA-1-20211115-00001/Deposit:161/Parent/Image3.png"
                }
            ]
        }
    ]
}
    """


@fixture
def make_fixity_report(fixity_report_json_body):
    report_type = Report.ReportType.FIXITY
    report_json = json.loads(fixity_report_json_body)
    return lambda **kwargs: baker.make(
        Report, report_type=report_type, report_json=report_json, **kwargs
    )


@fixture
def make_super_user(make_organization):
    return lambda: baker.make(
        User, organization=make_organization(), is_staff=True, is_superuser=True
    )


@fixture
def make_staff_user(make_organization):
    return lambda: baker.make(User, organization=make_organization(), is_staff=True)


@fixture
def make_user(make_organization):
    def maker(organization=None):
        organization = organization or make_organization()
        return baker.make(User, organization=organization)

    return maker


###############################################################################
# Normal Fixtures
###############################################################################


@fixture
def geolocation(make_geolocation):
    return make_geolocation()


@fixture
def plan(make_plan):
    return make_plan()


@fixture
def organization(make_organization):
    return make_organization()


@fixture
def super_user(make_super_user):
    return make_super_user()


@fixture
def staff_user(make_staff_user):
    return make_staff_user()


@fixture
def user(make_user):
    return make_user()


@fixture
def treenode_stack(make_treenode, make_collection, make_organization):
    """Return a complete valid TreeNode type hierarchy dict keyed by type name."""
    organization = make_organization()
    organization.refresh_from_db()
    organization_node = organization.tree_node
    organization_node.refresh_from_db()
    collection = make_collection()
    collection.refresh_from_db()
    collection_node = collection.tree_node
    collection_node.refresh_from_db()
    folder_node = make_treenode(node_type="FOLDER", parent=collection_node)
    folder_node.refresh_from_db()
    file_node = make_treenode(node_type="FILE", parent=folder_node)
    file_node.refresh_from_db()
    return {
        "ORGANIZATION": organization_node,
        "COLLECTION": collection_node,
        "FOLDER": folder_node,
        "FILE": file_node,
    }
