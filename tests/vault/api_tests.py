import json
from django.urls import reverse
from model_bakery import baker
import pytest
from vault import api
from vault.models import Collection, DepositFile, File, Organization, Report, TreeNode


@pytest.mark.django_db
@pytest.mark.parametrize("coll_count", [0, 3])
def test_api_collections(rf, coll_count):
    user = baker.make("vault.User", _fill_optional=["organization"])
    if coll_count > 0:
        baker.make("Collection", organization=user.organization, _quantity=coll_count)
    assert len(Organization.objects.all()) == 1
    assert len(Collection.objects.all()) == coll_count

    request = rf.get(reverse("api_collections"))
    request.user = user
    response = api.collections(request)
    assert response.status_code == 200
    colls = json.loads(response.content)["collections"]
    assert len(colls) == coll_count


@pytest.mark.django_db
def test_api_reports(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    collection = baker.make("Collection", organization=user.organization)
    deposit = baker.make(
        "Deposit", user=user, organization=user.organization, collection=collection
    )
    files = baker.make("DepositFile", deposit=deposit, _quantity=5)
    old_deposit_report = baker.make(
        "Report", collection=collection, report_type=Report.ReportType.DEPOSIT
    )
    fixity_report = baker.make(
        "Report", collection=collection, report_type=Report.ReportType.FIXITY
    )
    assert len(Organization.objects.all()) == 1
    assert len(Collection.objects.all()) == 1
    assert len(TreeNode.objects.all()) == 2
    request = rf.get(f"/api/reports")
    request.user = user
    response = api.reports(request)
    assert response.status_code == 200
    reports = json.loads(response.content)["reports"]
    assert len(reports) == 3


@pytest.mark.django_db
class TestWarningDepositApi:
    """
    Test cases for warning deposit api
    API path: api/warning_deposit
    """

    def test_with_file_in_db(self, rf):
        """
        Input:
            Deposit Files in Collection: 3
            Deposit Files in specific path: 3
            Files created in database collection: 3
            Files created in database specific path: 3

        Expected Output:
            Matched files in collection: 3
            Matched files in specific path: 3
        """
        file_count = 3
        self.all_checks(file_count, rf)

    def test_without_file_in_db(self, rf):
        """
        Input:
            Deposit Files in Collection: 3
            Deposit Files in specific path: 3
            Files created in database collection: 0
            Files created in database specific path: 0

        Expected Output:
            Matched files in collection: 0
            Matched files in specific path: 0
        """
        file_count = 0
        self.all_checks(file_count, rf)

    def all_checks(self, file_count, rf):
        user, collection, parent_folder, child_folder = self.create_path()
        files = []
        deposit_files_list = [
            "Image1.png",
            "File2.txt",
            "File3.pdf",
            "Image4.jpg",
            "Song5.mp4",
        ]
        deposit = baker.make(
            "Deposit", user=user, organization=user.organization, collection=collection
        )
        file_relative_path = ""
        # deposit files in collection
        files = self.create_deposit_files(
            deposit, files, file_relative_path, deposit_files_list
        )
        # deposit files in path
        file_relative_path = parent_folder.name + "/" + child_folder.name + "/"
        files = self.create_deposit_files(
            deposit, files, file_relative_path, deposit_files_list
        )
        payload = {
            "collection_id": collection.id,
            "files": files,
            "total_size": sum([file["size"] for file in files]),
        }
        self.create_files_in_db(collection.tree_node, deposit_files_list, file_count)
        # create file in path
        self.create_files_in_db(child_folder, deposit_files_list, file_count)
        assert len(Organization.objects.all()) == 1
        assert len(Collection.objects.all()) == 1
        assert len(TreeNode.objects.all()) == 4 + (file_count * 2)
        assert len(DepositFile.objects.all()) == 10
        request = rf.post(
            reverse("api_warning_deposit"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.user = user
        response = api.warning_deposit(request)
        # check the number of matched files in collection
        matched_file = json.loads(response.content)["objects"]
        assert len(matched_file) == file_count
        # check the matched path and number of matched files in that path
        matched_path = json.loads(response.content)["relative_path"]
        assert len(matched_path) == file_count
        assert response.status_code == 200

    def create_deposit_files(
        self, deposit, files, file_relative_path, deposit_files_list
    ):
        for file in deposit_files_list:
            deposit_file = baker.make(
                "DepositFile",
                deposit=deposit,
                name=file,
                relative_path=file_relative_path + file,
            )
            file_dict = {
                "name": deposit_file.name,
                "relative_path": deposit_file.relative_path,
                "size": deposit_file.size,
            }
            files.append(file_dict)
        return files

    def create_files_in_db(self, parent, deposit_files_list, file_count):
        files_in_db = deposit_files_list[:file_count]
        for file in files_in_db:
            baker.make("TreeNode", node_type="FILE", parent=parent, name=file)
        return files_in_db

    def create_path(self):
        user = baker.make("vault.User", _fill_optional=["organization"])
        collection = baker.make(
            "Collection", organization=user.organization, name="Test 1"
        )
        parent_folder = baker.make(
            "TreeNode", node_type="FOLDER", parent=collection.tree_node, name="parent"
        )
        child_folder = baker.make(
            "TreeNode", node_type="FOLDER", parent=parent_folder, name="child"
        )
        return (user, collection, parent_folder, child_folder)
