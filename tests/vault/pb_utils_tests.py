from freezegun import freeze_time
import pytest

from vault import pb_utils


class TestGetPresignedURL:
    def test_rejects_omitted_filename(self):
        """get_presigned_url raises exception when pbox_item_slash_filename omits filename"""
        item = "item"
        petabox_secret = bytes("petabox_secret", "ascii")
        service_name = "service_name"
        with pytest.raises(ValueError):
            pb_utils.get_presigned_url(f"{item}", service_name, petabox_secret)

    @freeze_time("2022-01-01")
    def test_basic_correctness(self):
        """get_presigned_url produces correct presigned urls"""
        item = "item_name"
        filename = "file_name"
        petabox_secret = bytes("petabox_secret", "ascii")
        service_name = "service_name"

        expected = "https://archive.org/download/item_name/file_name?service_name-item_name=1640995260-0e942acb1627129511260601143ba76d"
        actual = pb_utils.get_presigned_url(
            f"{item}/{filename}", service_name, petabox_secret
        )

        assert expected == actual

    @freeze_time("2022-01-01")
    def test_nested_directory(self):
        """get_presigned_url success when filename contains a directory"""
        item = "item_name"
        filename = "directory/file_name"
        petabox_secret = bytes("petabox_secret", "ascii")
        service_name = "service_name"
        expected = "https://archive.org/download/item_name/directory/file_name?service_name-item_name=1640995260-0e942acb1627129511260601143ba76d"
        actual = pb_utils.get_presigned_url(
            f"{item}/{filename}", service_name, petabox_secret
        )
        assert expected == actual
