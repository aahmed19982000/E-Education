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

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if course is not None:
            allowed = course.allowed_modes()
            self.fields["mode"].choices = [c for c in EnrollmentRequest.MODE_CHOICES if c[0] in allowed]
            self.fields["mode"].initial = allowed[0] if allowed else None
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs["class"] = "field"


class WorkshopBookingForm(forms.ModelForm):
    """Teachers' workshop booking; lands in the same admin requests list, marked as from a teacher."""

    class Meta:
        model = EnrollmentRequest
        fields = ["full_name", "email", "phone", "mode", "payment_method", "notes"]
        widgets = {"mode": forms.RadioSelect, "payment_method": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The workshop keeps its two plans; semi private is for student courses.
        self.fields["mode"].choices = [c for c in EnrollmentRequest.MODE_CHOICES
                                       if c[0] in (EnrollmentRequest.MODE_GROUP, EnrollmentRequest.MODE_PRIVATE)]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.kind = EnrollmentRequest.KIND_TEACHER
        if commit:
            obj.save()
        return obj
