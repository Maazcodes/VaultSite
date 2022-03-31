from django.http import Http404
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
import pytest

from vault import views
from vault.models import Collection, Organization, Report, TreeNode


@pytest.mark.django_db
def test_deposit_report(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    collection = baker.make("Collection", organization=user.organization)
    deposit = baker.make(
        "Deposit",
        user=user,
        organization=user.organization,
        collection=collection,
        parent_node_id=collection.tree_node.id,
    )
    files = baker.make("DepositFile", deposit=deposit, _quantity=5)
    request = rf.get(f"/deposit/{deposit.id}")
    request.user = user
    response = views.deposit_report(request, deposit.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_fixity_report_auth(rf, make_fixity_report):
    """A user should only be able to see Reports from their own Organization."""
    # Make two reports for two different orgs with two users.
    report_1 = make_fixity_report()
    report_2 = make_fixity_report()
    org_1 = report_1.collection.organization
    org_2 = report_2.collection.organization
    user_1 = baker.make("vault.User", organization=org_1)
    user_2 = baker.make("vault.User", organization=org_2)

    # Test a user can see their own organization's report:
    request = rf.get(f"/reports/fixity/{report_1.id}")
    request.user = user_1
    response = views.fixity_report(request, report_1.id)
    assert response.status_code == 200

    # Test a user may not see a different organization's report.
    request = rf.get(f"/reports/fixity/{report_1.id}")
    request.user = user_2
    with pytest.raises(Http404):
        views.fixity_report(request, report_1.id)


@pytest.mark.django_db
def test_collection(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    collection = baker.make("Collection", organization=user.organization)
    deposit = baker.make(
        "Deposit",
        user=user,
        organization=user.organization,
        collection=collection,
        parent_node_id=collection.tree_node.id,
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

    request = rf.get(f"/collection/{collection.id}")
    request.user = user
    response = views.collection(request, collection.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_deposit_compat(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])

    # method
    request = rf.get(f"/deposit/compat")
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 405, "do not allow GET"

    # incomplete request
    request = rf.post(f"/deposit/compat")
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 501, "missing client field"

    # incomplete request
    data = {"client": "DOAJ_CLI"}
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 400, "incomplete request"

    # create org and collection to send data to
    collection = baker.make("Collection", organization=user.organization)

    # incomplete request
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 400, "incomplete request"

    # complete but bogus hash
    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": 1,
        "sha256sum": "gotcha",
        "dir_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 409

    # missing file
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": "",
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 400, "missing file should fail"

    # bogus file data
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": "",
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "file_field": "...",
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 400, "should fail on bogus file data"

    # complete but bogus size; yields 200, since DOAJ does not supply size
    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": 1000,
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "dir_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 200, "complete request should be ok"

    # complete request, without size
    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "dir_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 200, "complete request should succeed, even w/o size"

    # complete request, with size
    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": 1,
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "dir_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 200, "complete request should succeed"

    # complete request, using "file_field" for file (like DOAJ supposedly does)
    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "client": "DOAJ_CLI",
        "collection": collection.id,
        "organization": collection.organization_id,
        "directories": "a.txt",
        "size": "",
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "file_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 200, "complete request should succeed"

    # script similar to what DOAJ might be doing
    # def upload_package(self, sha256sum):

    #     url = app.config.get("PRESERVATION_URL")
    #     username = app.config.get("PRESERVATION_USERNAME")
    #     password = app.config.get("PRESERVATION_PASSWD")
    #     collection_dict = app.config.get("PRESERVATION_COLLECTION")
    #     params = collection_dict[self.__owner]
    #     collection = params[0]
    #     collection_id = params[1]

    #     file_name = os.path.basename(self.tar_file)

    #     # payload for upload request
    #     payload = {
    #         'directories': file_name,
    #         'org': 'DOAJ',
    #         'client': 'DOAJ_CLI',
    #         'username': 'doaj_uploader',
    #         'size': '',
    #         'organization': '1',
    #         'orgname': 'DOAJ',
    #         'collection': collection_id,
    #         'collname': collection,
    #         'sha256sum': sha256sum
    #     }
    #     app.logger.info(payload)

    #     headers = {}
    #     # get the file to upload
    #     try:
    #         with open(self.tar_file, "rb") as f:
    #             files = {'file_field': (file_name, f)}
    #             response = requests.post(url, headers=headers, auth=(username, password), files=files, data=payload)
    #     except (IOError, Exception) as exp:
    #         app.logger.exception("Error opening the tar file")
    #         raise PreservationException("Error Uploading tar file to IA server")

    #     return response

    uploaded_file = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
    data = {
        "directories": "a.txt",
        "org": "DOAJ",
        "client": "DOAJ_CLI",
        "username": "doaj_uploader",
        "size": "",
        "organization": collection.organization_id,
        "orgname": "DOAJ",
        "collection": collection.id,
        "collname": collection.name,
        "sha256sum": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "file_field": uploaded_file,
    }
    request = rf.post(f"/deposit/compat", data=data)
    request.user = user
    response = views.deposit_compat(request)
    assert response.status_code == 200, "complete doaj-style request should succeed"
