from django import forms


class NewEntryForm(forms.Form):
    title = forms.CharField(
        label="Page Title",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Title"})
    )
    content = forms.CharField(
        label="Markdown Content",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 10})
    )

    def clean_title(self):
        return self.cleaned_data["title"].strip()


class EditEntryForm(forms.Form):
    content = forms.CharField(
        label="Markdown Content",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 10})
    )

