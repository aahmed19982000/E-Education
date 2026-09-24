import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from quiz.models import Question

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class QuestionFormTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "admin@example.com", "pass12345!")
        self.client.force_login(self.admin)

    def post(self, data, url=None, files=None):
        payload = {
            "kind": "standard",
            "tag_ar": "قواعد",
            "text_ar": "She ___ to school.",
            "option_ar": ["goes", "go", "", "going"],
            "option_en": ["", "", "", ""],
            "correct_index": "3",
            **data,
            **(files or {}),
        }
        return self.client.post(url or reverse("dashboard:question_create"), payload)

    def audio(self, name="clip.mp3"):
        return SimpleUploadedFile(name, b"ID3fake-audio", content_type="audio/mpeg")

    def test_standard_question_skips_blank_options_and_keeps_correct_answer(self):
        resp = self.post({})
        self.assertRedirects(resp, reverse("dashboard:questions_list"))
        q = Question.objects.get()
        self.assertEqual(q.options_ar, ["goes", "go", "going"])
        self.assertEqual(q.options_ar[q.correct_index], "going")
        self.assertEqual(q.options_en, [])
        self.assertEqual(q.order, 1)

    def test_order_auto_increments(self):
        self.post({})
        self.post({})
        self.assertEqual(list(Question.objects.values_list("order", flat=True)), [1, 2])

    def test_correct_answer_must_be_a_filled_option(self):
        resp = self.post({"correct_index": "2"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.exists())

    def test_needs_two_options(self):
        resp = self.post({"option_ar": ["only", "", "", ""], "correct_index": "0"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.exists())

    def test_listening_requires_audio(self):
        resp = self.post({"kind": "listening"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.exists())

    def test_listening_with_audio_upload(self):
        resp = self.post({"kind": "listening", "audio_label_ar": "محادثة"}, files={"audio_file": self.audio()})
        self.assertEqual(resp.status_code, 302)
        q = Question.objects.get()
        self.assertTrue(q.audio_file.name.startswith("quiz/audio/"))
        self.assertEqual(q.kind, Question.KIND_LISTENING)
        self.assertTrue(q.localized("ar")["audio_url"])

    def test_rejects_non_audio_file(self):
        bad = SimpleUploadedFile("notes.pdf", b"%PDF", content_type="application/pdf")
        resp = self.post({"kind": "listening"}, files={"audio_file": bad})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.exists())

    def test_switching_type_clears_audio_and_deletes_file(self):
        self.post({"kind": "listening"}, files={"audio_file": self.audio()})
        q = Question.objects.get()
        storage, name = q.audio_file.storage, q.audio_file.name
        self.post({"kind": "standard"}, url=reverse("dashboard:question_edit", args=[q.pk]))
        q.refresh_from_db()
        self.assertFalse(q.audio_file)
        self.assertFalse(storage.exists(name))

    def test_edit_keeps_existing_audio_when_no_new_file(self):
        self.post({"kind": "listening"}, files={"audio_file": self.audio()})
        q = Question.objects.get()
        name = q.audio_file.name
        resp = self.post({"kind": "listening", "text_ar": "edited"}, url=reverse("dashboard:question_edit", args=[q.pk]))
        self.assertEqual(resp.status_code, 302)
        q.refresh_from_db()
        self.assertEqual(q.audio_file.name, name)
        self.assertEqual(q.text_ar, "edited")

    def test_save_and_add_another_redirects_to_create(self):
        resp = self.post({"save_add_another": "1"})
        self.assertRedirects(resp, reverse("dashboard:question_create"))

    def test_english_falls_back_to_arabic(self):
        self.post({"option_en": ["", "Go", "", ""]})
        q = Question.objects.get()
        en = q.localized("en")
        self.assertEqual(en["text"], "She ___ to school.")
        self.assertEqual(en["options"], ["goes", "Go", "going"])
