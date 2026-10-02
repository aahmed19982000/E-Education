from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import models

from accounts.models import Profile
from articles.models import Article
from courses.models import Attendance, Cohort, CohortSlot, EnrollmentRequest, Course, Enrollment, Lesson, LessonAttachment
from team.models import VIDEO_MAX_MB, TeamMember, TeamReview
from quiz.audio import AudioDecodeError, compress_audio
from quiz.models import AUDIO_MAX_MB, MAX_OPTIONS, MIN_OPTIONS, Category, Question, QuizSettings


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


class TeamMemberForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = [
            "is_owner", "order",
            "name_ar", "name_en",
            "role_ar", "role_en",
            "specialties_ar", "specialties_en",
            "bio_ar", "bio_en",
            "youtube_url", "photo",
        ]
        widgets = {
            "specialties_ar": forms.HiddenInput(),
            "specialties_en": forms.HiddenInput(),
            "name_ar": forms.TextInput(attrs={"placeholder": "مثال: محمد عزت"}),
            "name_en": forms.TextInput(attrs={"placeholder": "Example: Mohamed Ezzat"}),
            "role_ar": forms.TextInput(attrs={"placeholder": "مثال: مدرس لغة إنجليزية"}),
            "role_en": forms.TextInput(attrs={"placeholder": "Example: English Teacher"}),
            "bio_ar": forms.Textarea(attrs={"rows": 6}),
            "bio_en": forms.Textarea(attrs={"rows": 6}),
            "youtube_url": forms.URLInput(attrs={"placeholder": "https://www.youtube.com/watch?v=..."}),
        }
        labels = {
            "is_owner": "المالك والمدير", "order": "الترتيب",
            "name_ar": "الاسم (عربي)", "name_en": "الاسم (إنجليزي)",
            "role_ar": "المسمى الوظيفي (عربي)", "role_en": "المسمى الوظيفي (إنجليزي)",
            "specialties_ar": "التخصصات (عربي)", "specialties_en": "التخصصات (إنجليزي)",
            "bio_ar": "نبذة تعريفية (عربي)", "bio_en": "نبذة تعريفية (إنجليزي)",
            "youtube_url": "رابط فيديو يوتيوب", "photo": "الصورة الشخصية",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class TeamReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TeamReview
        fields = ["student_name", "rating", "text", "youtube_url", "video_file", "order"]
        widgets = {
            "rating": forms.Select(choices=[(i, "★" * i) for i in range(5, 0, -1)]),
            "text": forms.Textarea(attrs={"rows": 4}),
            "youtube_url": forms.URLInput(attrs={"placeholder": "https://www.youtube.com/watch?v=..."}),
        }
        labels = {
            "student_name": "اسم الطالب", "rating": "التقييم", "text": "نص التقييم",
            "youtube_url": "رابط فيديو يوتيوب", "video_file": "أو ارفع ملف فيديو", "order": "الترتيب",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_video_file(self):
        video = self.cleaned_data.get("video_file")
        if video and hasattr(video, "size") and video.size > VIDEO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"حجم الفيديو أكبر من {VIDEO_MAX_MB} ميجابايت. استخدم رابط يوتيوب للفيديوهات الكبيرة.")
        return video


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
    position = forms.ChoiceField(
        label="مكان السؤال في الاختبار", required=False,
        error_messages={"invalid_choice": "هذا المكان لم يعد موجودًا، اختر مكانًا آخر."},
    )

    class Meta:
        model = Question
        fields = [
            "category", "points", "time_limit_seconds",
            "passage_ar", "passage_en",
            "audio_file", "audio_label_ar", "audio_label_en",
            "text_ar", "text_en",
        ]
        widgets = {
            "passage_ar": forms.Textarea(attrs={"rows": 4}),
            "passage_en": forms.Textarea(attrs={"rows": 4}),
            "text_ar": forms.Textarea(attrs={"rows": 2}),
            "text_en": forms.Textarea(attrs={"rows": 2}),
            "audio_file": forms.FileInput(attrs={"accept": "audio/*"}),
            "points": forms.NumberInput(attrs={"step": "0.5", "min": "0"}),
            "time_limit_seconds": forms.NumberInput(attrs={"step": "5", "min": "0"}),
        }
        labels = {
            "points": "درجة السؤال",
            "time_limit_seconds": "وقت هذا السؤال (بالثواني)",
            "category": "التصنيف",
            "passage_ar": "نص القراءة", "passage_en": "نص القراءة (إنجليزي)",
            "audio_file": "المقطع الصوتي",
            "audio_label_ar": "وصف المقطع", "audio_label_en": "وصف المقطع (إنجليزي)",
            "text_ar": "نص السؤال", "text_en": "نص السؤال (إنجليزي)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_position()
        self.fields["category"].empty_label = "اختر التصنيف…"
        self.fields["category"].error_messages["required"] = "اختر تصنيفًا للسؤال أو أضف تصنيفًا جديدًا."
        self.quiz_settings = QuizSettings.load()
        default_time = self.quiz_settings.question_time_seconds
        self.fields["time_limit_seconds"].help_text = (
            f"اتركه فارغًا لاستخدام الوقت الافتراضي ({default_time} ثانية)، أو 0 لإلغاء الوقت لهذا السؤال."
            if default_time else "اتركه فارغًا ليكون السؤال بدون وقت."
        )
        if not self.quiz_settings.is_per_question:
            # Whole-test grading splits marks equally, so a per-question value would be ignored.
            del self.fields["points"]
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
        self.initial_options = [
            (options_ar[i] if i < len(options_ar) else "", options_en[i] if i < len(options_en) else "")
            for i in range(max(len(options_ar), 4))
        ]
        self._style_fields()

    def _init_position(self):
        """Position dropdown: "at the start" or "after question N" for every other question."""
        # Number by the real quiz position (what the questions list shows), skipping this question.
        ordered = list(Question.objects.order_by("order", "pk"))
        others = [q for q in ordered if q.pk != self.instance.pk]
        choices = [("start", "في بداية الاختبار")]
        for number, q in enumerate(ordered, start=1):
            if q.pk == self.instance.pk:
                continue
            text = q.text_ar if len(q.text_ar) <= 60 else q.text_ar[:60] + "…"
            choices.append((str(q.pk), f"بعد السؤال {number}: {text}"))
        self.fields["position"].choices = choices

        if self.instance.pk:
            before = [q for q in others if (q.order, q.pk) < (self.instance.order, self.instance.pk)]
            self.fields["position"].initial = str(before[-1].pk) if before else "start"
        else:
            self.fields["position"].initial = str(others[-1].pk) if others else "start"

    def _place(self, instance):
        """Put `instance` at the chosen position and renumber the whole quiz 1..n."""
        position = self.cleaned_data.get("position")
        others = list(Question.objects.exclude(pk=instance.pk).order_by("order", "pk"))
        if position == "start":
            index = 0
        elif position:
            index = next((i + 1 for i, q in enumerate(others) if str(q.pk) == position), len(others))
        else:
            return
        others.insert(index, instance)
        changed = []
        for number, q in enumerate(others, start=1):
            if q.order != number:
                q.order = number
                changed.append(q)
        Question.objects.bulk_update(changed, ["order"])

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
        if not audio or "audio_file" not in self.files:
            return audio  # nothing new uploaded
        if audio.size > AUDIO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"حجم الملف أكبر من {AUDIO_MAX_MB} ميجابايت.")
        try:
            return compress_audio(audio)
        except AudioDecodeError:
            raise forms.ValidationError("تعذّرت قراءة الملف. تأكد أنه مقطع صوتي سليم.")

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
        # Clear whatever doesn't belong to the chosen type so hidden fields never leak into the quiz.
        if kind != Question.KIND_READING:
            instance.passage_ar = instance.passage_en = ""
        if kind != Question.KIND_LISTENING or (self.remove_audio and not self.files.get("audio_file")):
            instance.audio_file = ""
        if kind != Question.KIND_LISTENING:
            instance.audio_label_ar = instance.audio_label_en = ""

        if not instance.pk:
            last = Question.objects.aggregate(m=models.Max("order"))["m"]
            instance.order = (last or 0) + 1  # default: end of the quiz
        instance.options_ar = data["options_ar"]
        instance.options_en = data["options_en"]
        instance.correct_index = data["correct_index"]
        if commit:
            instance.save()
            self._place(instance)
        return instance


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name_ar", "name_en"]
        labels = {"name_ar": "اسم التصنيف", "name_en": "الاسم بالإنجليزية (اختياري)"}
        error_messages = {"name_ar": {"unique": "يوجد تصنيف بهذا الاسم بالفعل."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_name_ar(self):
        return " ".join(self.cleaned_data["name_ar"].split())

    def clean_name_en(self):
        return " ".join(self.cleaned_data["name_en"].split())


class QuizSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = QuizSettings
        fields = ["grading_mode", "total_marks", "exam_time_minutes", "question_time_seconds"]
        widgets = {
            "grading_mode": forms.RadioSelect,
            "total_marks": forms.NumberInput(attrs={"step": "1", "min": "1"}),
            "exam_time_minutes": forms.NumberInput(attrs={"step": "1", "min": "0"}),
            "question_time_seconds": forms.NumberInput(attrs={"step": "5", "min": "0"}),
        }
        labels = {
            "grading_mode": "نظام الدرجات",
            "total_marks": "الدرجة الكلية للاختبار",
            "exam_time_minutes": "مدة الاختبار كله (بالدقائق)",
            "question_time_seconds": "الوقت الافتراضي لكل سؤال (بالثواني)",
        }
        help_texts = {
            "exam_time_minutes": "0 = بدون وقت. عند انتهاء الوقت يُنهى الاختبار وتظهر النتيجة.",
            "question_time_seconds": "0 = بدون وقت. عند انتهاء وقت السؤال يُقفل وينتقل الطالب للسؤال التالي. يمكن تغييره لسؤال معيّن من صفحة السؤال.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


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


class CourseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title_ar", "title_en", "description_ar", "description_en", "audience",
                  "offers_group", "offers_private", "price_group", "price_private", "is_published"]
        widgets = {
            "description_ar": forms.Textarea(attrs={"rows": 4}),
            "description_en": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "title_ar": "اسم الكورس (عربي)", "title_en": "اسم الكورس (إنجليزي — اختياري)",
            "description_ar": "الوصف (عربي)", "description_en": "الوصف (إنجليزي — اختياري)",
            "audience": "نوع الكورس", "offers_group": "متاح جروب", "offers_private": "متاح خصوصي",
            "price_group": "سعر الجروب (ج.م)", "price_private": "سعر الخصوصي (ج.م)",
            "is_published": "منشور على الموقع",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("offers_group") and not cleaned.get("offers_private"):
            raise forms.ValidationError("اختر جروب أو خصوصي على الأقل.")
        return cleaned


class CohortForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name", "mode", "teacher", "start_date", "weeks"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {"name": "اسم المجموعة (اختياري)", "mode": "النوع", "teacher": "المدرس",
                  "start_date": "تاريخ بداية الجلسات", "weeks": "عدد الأسابيع"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class SlotForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CohortSlot
        fields = ["weekday", "start_time", "duration_minutes"]
        widgets = {"start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}
        labels = {"weekday": "اليوم", "start_time": "الوقت", "duration_minutes": "المدة (دقيقة)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


SlotFormSet = forms.inlineformset_factory(Cohort, CohortSlot, form=SlotForm, extra=2, can_delete=True)


class LessonForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title_ar", "title_en", "starts_at", "duration_minutes", "zoom_url", "recording_url",
                  "notes_ar", "notes_en"]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "notes_ar": forms.Textarea(attrs={"rows": 3}),
            "notes_en": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title_ar": "عنوان الجلسة (عربي)", "title_en": "عنوان الجلسة (إنجليزي)",
            "starts_at": "موعد الجلسة", "duration_minutes": "المدة (دقيقة)",
            "zoom_url": "رابط Zoom", "recording_url": "رابط التسجيل",
            "notes_ar": "ملاحظات (عربي)", "notes_en": "ملاحظات (إنجليزي)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        self._style_fields()


class AttachmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LessonAttachment
        fields = ["kind", "title", "file"]
        labels = {"kind": "النوع", "title": "العنوان", "file": "الملف"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


AttachmentFormSet = forms.inlineformset_factory(Lesson, LessonAttachment, form=AttachmentForm, extra=1, can_delete=True)


class EnrollForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label="البريد الإلكتروني للطالب")

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise forms.ValidationError("لا يوجد طالب مسجل بهذا البريد.")
        self.user = user
        return email

    def save(self):
        enrollment, created = Enrollment.objects.get_or_create(user=self.user, course=self.course)
        if not created and not enrollment.is_active:
            enrollment.status = Enrollment.STATUS_ACTIVE
            enrollment.save(update_fields=["status"])
        return enrollment, created


class RequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EnrollmentRequest
        fields = ["status", "payment_status", "assigned_teacher", "admin_notes"]
        widgets = {"admin_notes": forms.Textarea(attrs={"rows": 4})}
        labels = {"status": "الحالة", "payment_status": "الدفع", "assigned_teacher": "المدرس المختار",
                  "admin_notes": "ملاحظات الإدارة"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
