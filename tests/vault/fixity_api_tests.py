import json
from unittest.mock import patch

import pytest
from django.conf import settings

from vault import fixity_api
from vault import models


@pytest.mark.django_db
@patch("requests.get")
def test_postback(m_get, rf, make_collection, fixity_report_json_body):
    """postback view calls fixitter to fetch report and creates Report inst"""
    collection = make_collection()
    col_id = collection.id
    org_id = collection.organization.id
    token = "foobarbaz"
    api_key = settings.FIXITY_API_KEY
    fixity_report = json.loads(fixity_report_json_body)

    m_get.return_value.json.return_value = fixity_report

    body = {"reportUrl": "cool-report-url"}
    request = rf.post(
        f"/fixitter/postback/{org_id}/{col_id}/{token}?api_key={api_key}",
        data=json.dumps(body),
        content_type="application/json",
    )
    response = fixity_api.postback(request, org_id, col_id, token)
    assert response.status_code == 202

    m_get.assert_called_once_with(
        "cool-report-url",
        params={"apikey": "FIXITTER_API_KEY"},
    )

    all_reports = list(models.Report.objects.all())
    assert len(all_reports) == 1
    report = all_reports[0]
    assert report.collection_id == col_id
    assert report.report_type == models.Report.ReportType.FIXITY
    assert report.report_json == fixity_report
