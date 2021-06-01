from django import forms


class CollectionForm(forms.Form):
    name = forms.CharField(label='Collection Name', max_length=255)


class BasicFileUploadForm(forms.Form):
    collection = forms.ModelChoiceField(queryset=None)
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    def __init__(self, queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = queryset