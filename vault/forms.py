# pylint: disable=too-many-instance-attributes

from dataclasses import dataclass

from django.core.files import File
from django import forms
from django.forms import CheckboxSelectMultiple

from vault import models


class CreateCollectionForm(forms.Form):
    name = forms.CharField(label="Collection Name", max_length=255)


class EditCollectionSettingsForm(forms.Form):
    target_replication = forms.ChoiceField(
        choices=models.ReplicationFactor.choices, label="Replication"
    )
    fixity_frequency = forms.ChoiceField(choices=models.FixityFrequency.choices)
    target_geolocations = forms.ModelMultipleChoiceField(
        models.Geolocation.objects.all().order_by("-name"),
        widget=CheckboxSelectMultiple,
        label="Geolocations",
    )


class FileFieldForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=None, empty_label="Select Collection for Deposit"
    )

    file_field = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "multiple": True,
            }
        ),
        label="Files",
    )

    dir_field = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "webkitdirectory": True,
                "multiple": True,
            }
        ),
        label="Directory",
    )

    # Store user inputs - Protected from Django sanitization
    #
    #  See JS file: vault/static/js/preserve-directory-info.js
    #
    #  directories: Full paths to html5 directory uploaded files
    #  shasums: Client calculated sha256sums
    #  collname: Client selected collection name (:FIXME: must be validated)
    #
    directories = forms.CharField(widget=forms.HiddenInput())
    shasums = forms.CharField(widget=forms.HiddenInput())
    sizes = forms.CharField(widget=forms.HiddenInput())
    comment = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collection"].queryset = queryset


@dataclass
class FlowChunkGet:
    """Represent a flow.js file chunk object"""

    deposit_id: int
    file_identifier: str
    file_name: str
    file_relative_path: str
    number: int
    size: int
    file_total_size: int
    file_total_chunks: int
    target_chunk_size: int


@dataclass
class FlowChunkPost(FlowChunkGet):
    file: File


class FlowChunkGetForm(forms.Form):
    depositId = forms.IntegerField()
    flowIdentifier = forms.CharField()
    flowFilename = forms.CharField()
    flowRelativePath = forms.CharField()
    flowChunkNumber = forms.IntegerField()
    flowChunkSize = forms.IntegerField()
    flowCurrentChunkSize = forms.IntegerField()
    flowTotalSize = forms.IntegerField()
    flowTotalChunks = forms.IntegerField()

    def flow_chunk(self) -> FlowChunkGet:
        return FlowChunkGet(
            deposit_id=self.cleaned_data["depositId"],
            file_identifier=self.cleaned_data["flowIdentifier"],
            file_name=self.cleaned_data["flowFilename"],
            file_relative_path=self.cleaned_data["flowRelativePath"],
            number=self.cleaned_data["flowChunkNumber"],
            size=self.cleaned_data["flowCurrentChunkSize"],
            file_total_size=self.cleaned_data["flowTotalSize"],
            file_total_chunks=self.cleaned_data["flowTotalChunks"],
            target_chunk_size=self.cleaned_data["flowChunkSize"],
        )


class FlowChunkPostForm(FlowChunkGetForm):
    file = forms.FileField(allow_empty_file=True)

    def flow_chunk(self) -> FlowChunkPost:
        return FlowChunkPost(
            deposit_id=self.cleaned_data["depositId"],
            file=self.cleaned_data["file"],
            file_identifier=self.cleaned_data["flowIdentifier"],
            file_name=self.cleaned_data["flowFilename"],
            file_relative_path=self.cleaned_data["flowRelativePath"],
            number=self.cleaned_data["flowChunkNumber"],
            size=self.cleaned_data["flowCurrentChunkSize"],
            file_total_size=self.cleaned_data["flowTotalSize"],
            file_total_chunks=self.cleaned_data["flowTotalChunks"],
            target_chunk_size=self.cleaned_data["flowChunkSize"],
        )


class RegisterDepositForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=None, empty_label="Select Collection for Deposit"
    )

    def __init__(self, *args, **kwargs):
        collections = None
        if "collections" in kwargs:
            collections = kwargs.pop("collections")
        super().__init__(*args, **kwargs)
        if collections:
            self.fields["collection"].queryset = collections


class RegisterDepositFileForm(forms.Form):
    flow_identifier = forms.CharField()
    name = forms.CharField()
    relative_path = forms.CharField()
    size = forms.IntegerField()
    type = forms.CharField(required=False)
    pre_deposit_modified_at = forms.DateTimeField(required=False)
