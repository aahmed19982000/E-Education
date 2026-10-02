from django import forms

from .models import EnrollmentRequest


class ApplyForm(forms.ModelForm):
    class Meta:
        model = EnrollmentRequest
        fields = ["full_name", "email", "phone", "mode", "preferred_times", "notes"]
        widgets = {
            "mode": forms.RadioSelect,
            "preferred_times": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs["class"] = "field"
