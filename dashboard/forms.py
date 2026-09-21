from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from accounts.models import Profile
from articles.models import Article
from levels.models import Level
from quiz.models import Question


class StyledFormMixin:
    """Adds the site's `.field` CSS class to every widget automatically."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            css = widget.attrs.get("class", "")
            widget.attrs["class"] = (css + " field").strip()


class DashboardLoginForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label="البريد الإلكتروني")
    password = forms.CharField(widget=forms.PasswordInput, label="كلمة المرور")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class LevelForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Level
        fields = [
            "code", "order",
            "name_ar", "name_en",
            "description_ar", "description_en",
            "duration_ar", "duration_en",
            "price_group", "price_private",
        ]
        widgets = {
            "description_ar": forms.Textarea(attrs={"rows": 3}),
            "description_en": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "code": "الرمز", "order": "الترتيب",
            "name_ar": "الاسم (عربي)", "name_en": "الاسم (إنجليزي)",
            "description_ar": "الوصف (عربي)", "description_en": "الوصف (إنجليزي)",
            "duration_ar": "المدة (عربي)", "duration_en": "المدة (إنجليزي)",
            "price_group": "سعر الجروب", "price_private": "سعر الخصوصي",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ArticleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            "order", "category_ar", "category_en",
            "title_ar", "title_en",
            "excerpt_ar", "excerpt_en",
            "body_ar", "body_en",
            "read_time_ar", "read_time_en",
        ]
        widgets = {
            "excerpt_ar": forms.Textarea(attrs={"rows": 3}),
            "excerpt_en": forms.Textarea(attrs={"rows": 3}),
            "body_ar": forms.Textarea(attrs={"rows": 8}),
            "body_en": forms.Textarea(attrs={"rows": 8}),
        }
        labels = {
            "order": "الترتيب",
            "category_ar": "التصنيف (عربي)", "category_en": "التصنيف (إنجليزي)",
            "title_ar": "العنوان (عربي)", "title_en": "العنوان (إنجليزي)",
            "excerpt_ar": "مقتطف (عربي)", "excerpt_en": "مقتطف (إنجليزي)",
            "body_ar": "نص المقال (عربي)", "body_en": "نص المقال (إنجليزي)",
            "read_time_ar": "مدة القراءة (عربي)", "read_time_en": "مدة القراءة (إنجليزي)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class QuestionForm(StyledFormMixin, forms.ModelForm):
    option1_ar = forms.CharField(label="الاختيار 1 (عربي)")
    option2_ar = forms.CharField(label="الاختيار 2 (عربي)")
    option3_ar = forms.CharField(label="الاختيار 3 (عربي)")
    option4_ar = forms.CharField(label="الاختيار 4 (عربي)")
    option1_en = forms.CharField(label="Option 1 (English)")
    option2_en = forms.CharField(label="Option 2 (English)")
    option3_en = forms.CharField(label="Option 3 (English)")
    option4_en = forms.CharField(label="Option 4 (English)")
    correct_index = forms.ChoiceField(
        label="الإجابة الصحيحة",
        choices=[(0, "الاختيار 1"), (1, "الاختيار 2"), (2, "الاختيار 3"), (3, "الاختيار 4")],
    )

    class Meta:
        model = Question
        fields = [
            "order", "tag_ar", "tag_en",
            "passage_ar", "passage_en",
            "audio_label_ar", "audio_label_en",
            "text_ar", "text_en",
        ]
        widgets = {
            "passage_ar": forms.Textarea(attrs={"rows": 3}),
            "passage_en": forms.Textarea(attrs={"rows": 3}),
            "text_ar": forms.Textarea(attrs={"rows": 2}),
            "text_en": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "order": "الترتيب",
            "tag_ar": "الوسم (عربي)", "tag_en": "الوسم (إنجليزي)",
            "passage_ar": "نص القراءة (عربي)", "passage_en": "نص القراءة (إنجليزي)",
            "audio_label_ar": "تسمية الاستماع (عربي)", "audio_label_en": "تسمية الاستماع (إنجليزي)",
            "text_ar": "نص السؤال (عربي)", "text_en": "نص السؤال (إنجليزي)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            options_ar = self.instance.options_ar or ["", "", "", ""]
            options_en = self.instance.options_en or ["", "", "", ""]
            for i in range(4):
                self.fields[f"option{i + 1}_ar"].initial = options_ar[i] if i < len(options_ar) else ""
                self.fields[f"option{i + 1}_en"].initial = options_en[i] if i < len(options_en) else ""
            self.fields["correct_index"].initial = self.instance.correct_index
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.options_ar = [self.cleaned_data[f"option{i + 1}_ar"] for i in range(4)]
        instance.options_en = [self.cleaned_data[f"option{i + 1}_en"] for i in range(4)]
        instance.correct_index = int(self.cleaned_data["correct_index"])
        if commit:
            instance.save()
        return instance


class StaffUserCreateForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(max_length=150, label="الاسم الكامل")
    email = forms.EmailField(label="البريد الإلكتروني")
    password = forms.CharField(widget=forms.PasswordInput, label="كلمة المرور")
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, label="الصلاحية")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مسجّل بالفعل.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password"):
            temp_user = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("full_name", ""),
            )
            try:
                validate_password(cleaned["password"], user=temp_user)
            except forms.ValidationError as exc:
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
            is_staff=True,
        )
        user.profile.role = self.cleaned_data["role"]
        user.profile.save()
        return user


class StaffUserEditForm(StyledFormMixin, forms.Form):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, label="الصلاحية")
    is_active = forms.BooleanField(label="الحساب مفعّل", required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None and self.initial.get("role") is None:
            self.fields["role"].initial = getattr(user.profile, "role", "")
            self.fields["is_active"].initial = user.is_active
        self._style_fields()

    def save(self):
        self.user.is_active = self.cleaned_data["is_active"]
        self.user.save(update_fields=["is_active"])
        self.user.profile.role = self.cleaned_data["role"]
        self.user.profile.save(update_fields=["role"])
        return self.user
