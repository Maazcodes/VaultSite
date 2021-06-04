from django import forms


class CollectionForm(forms.Form):
    name = forms.CharField(label='Collection Name', max_length=255)


class FileFieldForm(forms.Form):
    collection = forms.ModelChoiceField(queryset=None)
    
    file_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'multiple': True, }))
    
    dir_field = forms.FileField(required=False, widget=forms.ClearableFileInput(
        attrs={ 'webkitdirectory':True, 'multiple': True, }))

    def __init__(self, queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = queryset
