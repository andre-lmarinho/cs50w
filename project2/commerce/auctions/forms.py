from decimal import Decimal, InvalidOperation

from django import forms

from .models import Listing


class ListingForm(forms.ModelForm):
    category = forms.CharField(
        required=False,
        max_length=64,
        help_text="Optional category name.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Listing
        fields = ["title", "description", "starting_bid", "image_url"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "starting_bid": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01"}
            ),
            "image_url": forms.URLInput(attrs={"class": "form-control"}),
        }

    def clean_starting_bid(self):
        value = self.cleaned_data["starting_bid"]
        if value is not None and value <= 0:
            raise forms.ValidationError("Starting bid must be greater than zero.")
        return value


class BidForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Bid must be greater than zero.")
        return amount


class CommentForm(forms.Form):
    body = forms.CharField(
        label="Add Comment",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Leave a comment"}
        ),
    )
