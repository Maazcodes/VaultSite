from django import forms
from django.forms import CheckboxSelectMultiple

from vault import models


class CreateCollectionForm(forms.Form):
    name = forms.CharField(label='Collection Name', max_length=255)


class EditCollectionSettingsForm(forms.Form):
    target_replication  = forms.ChoiceField(choices=models.ReplicationFactor.choices, label="Replication")
    fixity_frequency    = forms.ChoiceField(choices=models.FixityFrequency.choices)
    target_geolocations = forms.ModelMultipleChoiceField(models.Geolocation.objects.all().order_by("-name"), widget=CheckboxSelectMultiple, label="Geolocations")


class FileFieldForm(forms.Form):
    collection = forms.ModelChoiceField(queryset=None, empty_label='Select Collection for Deposit')

    file_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'multiple': True, }), label='Files')

    dir_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'webkitdirectory':True, 'multiple': True, }), label='Directory')

    # Store user inputs - Protected from Django sanitization
    #
    #  See JS file: vault/static/js/preserve-directory-info.js
    #
    #  directories: Full paths to html5 directory uploaded files
    #  shasums: Client calculated sha256sums
    #  collname: Client selected collection name (:FIXME: must be validated)
    #
    directories = forms.CharField(widget=forms.HiddenInput())
    shasums     = forms.CharField(widget=forms.HiddenInput())
    sizes       = forms.CharField(widget=forms.HiddenInput())
    comment     = forms.CharField(widget=forms.HiddenInput())


    def __init__(self, queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = queryset
