from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import models

from accounts.models import Profile
from articles.models import Article
from levels.models import Level
from quiz.models import AUDIO_MAX_MB, MAX_OPTIONS, MIN_OPTIONS, Question


class StyledFormMixin:
    """Adds the site's `.field` CSS class to every widget automatically."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.HiddenInput)):
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
    """One form for every question type. Options are rendered as rows
    (Arabic + optional English + a "correct" radio) instead of 8 loose fields,
    and the English translation is optional (the quiz falls back to Arabic)."""

    kind = forms.ChoiceField(
        label="نوع السؤال",
        choices=[
            (Question.KIND_STANDARD, "سؤال عادي"),
            (Question.KIND_READING, "قراءة (مع نص)"),
            (Question.KIND_LISTENING, "استماع (مع مقطع صوتي)"),
        ],
        initial=Question.KIND_STANDARD,
        widget=forms.RadioSelect,
    )
    correct_index = forms.IntegerField(min_value=0, max_value=MAX_OPTIONS - 1, widget=forms.HiddenInput, required=False)

    class Meta:
        model = Question
        fields = [
            "order", "tag_ar", "tag_en",
            "passage_ar", "passage_en",
            "audio_file", "audio_label_ar", "audio_label_en",
            "text_ar", "text_en",
        ]
        widgets = {
            "passage_ar": forms.Textarea(attrs={"rows": 4}),
            "passage_en": forms.Textarea(attrs={"rows": 4}),
            "text_ar": forms.Textarea(attrs={"rows": 2}),
            "text_en": forms.Textarea(attrs={"rows": 2}),
            "tag_ar": forms.TextInput(attrs={"list": "tag-suggestions", "autocomplete": "off"}),
            "audio_file": forms.FileInput(attrs={"accept": "audio/*"}),
        }
        labels = {
            "order": "الترتيب",
            "tag_ar": "التصنيف", "tag_en": "التصنيف (إنجليزي)",
            "passage_ar": "نص القراءة", "passage_en": "نص القراءة (إنجليزي)",
            "audio_file": "المقطع الصوتي",
            "audio_label_ar": "وصف المقطع", "audio_label_en": "وصف المقطع (إنجليزي)",
            "text_ar": "نص السؤال", "text_en": "نص السؤال (إنجليزي)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].required = False
        self.fields["order"].help_text = "اتركه فارغًا ليُضاف في آخر الاختبار."
        self.remove_audio = False

        instance = self.instance
        if instance.pk:
            self.fields["kind"].initial = instance.kind
            self.fields["correct_index"].initial = instance.correct_index
            options_ar = list(instance.options_ar or [])
            options_en = list(instance.options_en or [])
        else:
            options_ar, options_en = [], []
            self.fields["correct_index"].initial = 0
            self.initial["order"] = None  # blank = append to the end
        self.initial_options = [
            (options_ar[i] if i < len(options_ar) else "", options_en[i] if i < len(options_en) else "")
            for i in range(max(len(options_ar), 4))
        ]
        self._style_fields()

    def option_rows(self):
        """Rows for the template: submitted values on a re-render, else the saved ones."""
        if self.is_bound:
            ar = self.data.getlist("option_ar")
            en = self.data.getlist("option_en")
            rows = [(ar[i], en[i] if i < len(en) else "") for i in range(len(ar))]
        else:
            rows = self.initial_options
        while len(rows) < MIN_OPTIONS:
            rows.append(("", ""))
        return [{"index": i, "ar": a, "en": e} for i, (a, e) in enumerate(rows[:MAX_OPTIONS])]

    def clean_audio_file(self):
        audio = self.cleaned_data.get("audio_file")
        if audio and hasattr(audio, "size") and audio.size > AUDIO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"حجم الملف أكبر من {AUDIO_MAX_MB} ميجابايت.")
        return audio

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")

        # Options: drop blank rows, keep the "correct" pointer aligned with what's left.
        ar = [v.strip() for v in self.data.getlist("option_ar")][:MAX_OPTIONS]
        en = [v.strip() for v in self.data.getlist("option_en")][:MAX_OPTIONS]
        correct = cleaned.get("correct_index")
        options_ar, options_en, new_correct = [], [], None
        for i, text in enumerate(ar):
            if not text:
                continue
            if i == correct:
                new_correct = len(options_ar)
            options_ar.append(text)
            options_en.append(en[i] if i < len(en) else "")
        if len(options_ar) < MIN_OPTIONS:
            self.add_error(None, f"أضف {MIN_OPTIONS} اختيارات على الأقل.")
        elif new_correct is None:
            self.add_error(None, "حدد الإجابة الصحيحة (يجب أن تكون اختيارًا غير فارغ).")
        cleaned["options_ar"] = options_ar
        cleaned["options_en"] = options_en if any(options_en) else []
        cleaned["correct_index"] = new_correct or 0

        # Type-specific requirements.
        self.remove_audio = self.data.get("remove_audio") == "1"
        if kind == Question.KIND_READING and not cleaned.get("passage_ar"):
            self.add_error("passage_ar", "أدخل نص القراءة.")
        if kind == Question.KIND_LISTENING:
            has_audio = cleaned.get("audio_file") or (self.instance.audio_file and not self.remove_audio)
            if not has_audio:
                self.add_error("audio_file", "ارفع مقطعًا صوتيًا أو سجّل واحدًا.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        data = self.cleaned_data
        kind = data["kind"]
        old_audio = None
        if self.instance.pk:
            old_audio = Question.objects.filter(pk=self.instance.pk).values_list("audio_file", flat=True).first()

        # Clear whatever doesn't belong to the chosen type so hidden fields never leak into the quiz.
        if kind != Question.KIND_READING:
            instance.passage_ar = instance.passage_en = ""
        if kind != Question.KIND_LISTENING or (self.remove_audio and not self.files.get("audio_file")):
            instance.audio_file = ""
        if kind != Question.KIND_LISTENING:
            instance.audio_label_ar = instance.audio_label_en = ""

        if data.get("order") is None:
            last = Question.objects.aggregate(m=models.Max("order"))["m"]
            instance.order = (last or 0) + 1
        instance.options_ar = data["options_ar"]
        instance.options_en = data["options_en"]
        instance.correct_index = data["correct_index"]
        if commit:
            instance.save()
            if old_audio and old_audio != instance.audio_file.name:
                instance.audio_file.storage.delete(old_audio)
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
