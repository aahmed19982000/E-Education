from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("هذا البريد الإلكتروني مسجّل بالفعل / This email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password2") and cleaned["password"] != cleaned["password2"]:
            self.add_error("password2", "كلمتا المرور غير متطابقتين / Passwords do not match.")
        if cleaned.get("password"):
            temp_user = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("full_name", ""),
            )
            try:
                validate_password(cleaned["password"], user=temp_user)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        full_name = self.cleaned_data["full_name"].strip()
        first_name, _, last_name = full_name.partition(" ")
        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password"],
            first_name=first_name,
            last_name=last_name,
        )
        user.profile.phone = self.cleaned_data.get("phone", "")
        user.profile.save()
        return user


class EmailLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
