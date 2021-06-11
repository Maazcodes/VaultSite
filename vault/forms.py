from django import forms


class CollectionForm(forms.Form):
    name = forms.CharField(label='Collection Name', max_length=255)


class FileFieldForm(forms.Form):
    collection = forms.ModelChoiceField(queryset=None)

    file_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'multiple': True, }))

    dir_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'webkitdirectory':True, 'multiple': True, }))

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
    collname    = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = queryset
