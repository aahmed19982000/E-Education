import io
import math
import shutil
import struct
import tempfile
import wave

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from levels.models import Level
from quiz.models import Category, Question

MEDIA_ROOT = tempfile.mkdtemp()


def make_wav(seconds=3, rate=44100):
    """A real stereo 16-bit WAV (a 440 Hz tone), big enough for compression to matter."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        frame = b"".join(
            struct.pack("<hh", s, s)
            for s in (int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(rate))
        )
        w.writeframes(frame * seconds)
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class QuestionFormTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "admin@example.com", "pass12345!")
        self.client.force_login(self.admin)
        self.category = Category.objects.create(name_ar="قواعد", name_en="Grammar")

    def post(self, data, url=None, files=None):
        payload = {
            "kind": "standard",
            "category": str(self.category.pk),
            "text_ar": "She ___ to school.",
            "option_ar": ["goes", "go", "", "going"],
            "option_en": ["", "", "", ""],
            "correct_index": "3",
            **data,
            **(files or {}),
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url or reverse("dashboard:question_create"), payload)

    def audio(self, name="clip.wav"):
        return SimpleUploadedFile(name, make_wav(), content_type="audio/wav")

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

    def texts(self):
        return list(Question.objects.values_list("text_ar", flat=True))

    def test_position_at_start_shifts_others(self):
        self.post({"text_ar": "A"})
        self.post({"text_ar": "B"})
        self.post({"text_ar": "C", "position": "start"})
        self.assertEqual(self.texts(), ["C", "A", "B"])
        self.assertEqual(list(Question.objects.values_list("order", flat=True)), [1, 2, 3])

    def test_position_after_a_question(self):
        self.post({"text_ar": "A"})
        self.post({"text_ar": "B"})
        a = Question.objects.get(text_ar="A")
        self.post({"text_ar": "C", "position": str(a.pk)})
        self.assertEqual(self.texts(), ["A", "C", "B"])

    def test_edit_can_move_question(self):
        for t in "ABC":
            self.post({"text_ar": t})
        c = Question.objects.get(text_ar="C")
        self.post({"text_ar": "C", "position": "start"}, url=reverse("dashboard:question_edit", args=[c.pk]))
        self.assertEqual(self.texts(), ["C", "A", "B"])

    def test_edit_form_preselects_current_position(self):
        for t in "ABC":
            self.post({"text_ar": t})
        a, b = Question.objects.get(text_ar="A"), Question.objects.get(text_ar="B")
        resp = self.client.get(reverse("dashboard:question_edit", args=[b.pk]))
        self.assertEqual(resp.context["form"]["position"].value(), str(a.pk))
        resp = self.client.get(reverse("dashboard:question_create"))
        self.assertEqual(resp.context["form"]["position"].value(), str(Question.objects.get(text_ar="C").pk))

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

    def test_audio_is_compressed_to_small_mp3(self):
        upload = self.audio()
        original_size = upload.size
        self.post({"kind": "listening"}, files={"audio_file": upload})
        q = Question.objects.get()
        self.assertTrue(q.audio_file.name.endswith(".mp3"))
        self.assertLess(q.audio_file.size, original_size / 10)

    def test_corrupt_audio_is_rejected(self):
        bad = SimpleUploadedFile("clip.mp3", b"not really audio", content_type="audio/mpeg")
        resp = self.post({"kind": "listening"}, files={"audio_file": bad})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("audio_file", resp.context["form"].errors)
        self.assertFalse(Question.objects.exists())

    def test_deleting_question_deletes_audio_file(self):
        self.post({"kind": "listening"}, files={"audio_file": self.audio()})
        q = Question.objects.get()
        storage, name = q.audio_file.storage, q.audio_file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("dashboard:question_delete", args=[q.pk]))
        self.assertFalse(Question.objects.exists())
        self.assertFalse(storage.exists(name))

    def test_bulk_delete_also_deletes_audio_files(self):
        self.post({"kind": "listening"}, files={"audio_file": self.audio()})
        q = Question.objects.get()
        storage, name = q.audio_file.storage, q.audio_file.name
        with self.captureOnCommitCallbacks(execute=True):
            Question.objects.all().delete()  # e.g. Django admin bulk action / seed command
        self.assertFalse(storage.exists(name))

    def test_replacing_audio_deletes_old_file(self):
        self.post({"kind": "listening"}, files={"audio_file": self.audio("first.wav")})
        q = Question.objects.get()
        storage, old = q.audio_file.storage, q.audio_file.name
        self.post({"kind": "listening"}, url=reverse("dashboard:question_edit", args=[q.pk]),
                  files={"audio_file": self.audio("second.wav")})
        q.refresh_from_db()
        self.assertNotEqual(q.audio_file.name, old)
        self.assertTrue(storage.exists(q.audio_file.name))
        self.assertFalse(storage.exists(old))

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


class QuestionReorderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "admin@example.com", "pass12345!")
        self.client.force_login(self.admin)
        cat = Category.objects.create(name_ar="قواعد")
        self.q = [
            Question.objects.create(order=i, category=cat, text_ar=f"q{i}", options_ar=["a", "b"], correct_index=0)
            for i in (1, 2, 3)
        ]
        self.url = reverse("dashboard:questions_reorder")

    def test_reorder_saves_new_positions(self):
        a, b, c = self.q
        resp = self.client.post(self.url, {"ids": [c.pk, a.pk, b.pk]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(Question.objects.values_list("text_ar", flat=True)), ["q3", "q1", "q2"])
        self.assertEqual(list(Question.objects.values_list("order", flat=True)), [1, 2, 3])

    def test_rejects_stale_or_partial_list(self):
        a, b, _ = self.q
        resp = self.client.post(self.url, {"ids": [b.pk, a.pk]})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(list(Question.objects.values_list("text_ar", flat=True)), ["q1", "q2", "q3"])

    def test_rejects_get(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(self.url, {"ids": [q.pk for q in self.q]})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(list(Question.objects.values_list("text_ar", flat=True)), ["q1", "q2", "q3"])


class CategoryManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "admin@example.com", "pass12345!")
        self.client.force_login(self.admin)

    def test_quick_add_from_question_form(self):
        resp = self.client.post(reverse("dashboard:category_quick_add"), {"name_ar": "  محادثة  ", "name_en": "Speaking"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        category = Category.objects.get(pk=data["id"])
        self.assertEqual(category.name_ar, "محادثة")
        self.assertEqual(category.name_en, "Speaking")

    def test_quick_add_rejects_duplicates_and_blank(self):
        Category.objects.create(name_ar="محادثة")
        resp = self.client.post(reverse("dashboard:category_quick_add"), {"name_ar": "محادثة"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("بالفعل", resp.json()["error"])
        resp = self.client.post(reverse("dashboard:category_quick_add"), {"name_ar": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Category.objects.count(), 1)

    def test_create_and_rename_category(self):
        self.client.post(reverse("dashboard:category_create"), {"name_ar": "استماع", "name_en": ""})
        c = Category.objects.get()
        self.client.post(reverse("dashboard:category_edit", args=[c.pk]), {"name_ar": "استماع", "name_en": "Listening"})
        c.refresh_from_db()
        self.assertEqual(c.name_en, "Listening")

    def test_cannot_delete_category_in_use(self):
        c = Category.objects.create(name_ar="قواعد")
        Question.objects.create(order=1, category=c, text_ar="q", options_ar=["a", "b"], correct_index=0)
        resp = self.client.post(reverse("dashboard:category_delete", args=[c.pk]))
        self.assertRedirects(resp, reverse("dashboard:categories_list"))
        self.assertTrue(Category.objects.filter(pk=c.pk).exists())

    def test_delete_unused_category(self):
        c = Category.objects.create(name_ar="قديم")
        self.client.post(reverse("dashboard:category_delete", args=[c.pk]))
        self.assertFalse(Category.objects.exists())

    def test_question_requires_category(self):
        resp = self.client.post(reverse("dashboard:question_create"), {
            "kind": "standard", "text_ar": "q", "option_ar": ["a", "b"], "option_en": ["", ""], "correct_index": "0",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("category", resp.context["form"].errors)


class PlacementSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com", "admin@example.com", "pass12345!")
        self.client.force_login(self.admin)
        self.levels = [
            Level.objects.create(
                code=code, order=i, name_ar=code, name_en=code, description_ar="-", description_en="-",
                duration_ar="-", duration_en="-", price_group=1, price_private=1,
            )
            for i, code in enumerate(["A1", "A2", "B1"], start=1)
        ]
        self.url = reverse("dashboard:quiz_placement")

    def data(self, *values):
        return {f"min_{lvl.pk}": v for lvl, v in zip(self.levels, values)}

    def mins(self):
        return list(Level.objects.order_by("order").values_list("test_min_percent", flat=True))

    def test_saves_thresholds_and_blank_excludes_level(self):
        resp = self.client.post(self.url, self.data("0", "", "60"))
        self.assertRedirects(resp, self.url)
        self.assertEqual(self.mins(), [0, None, 60])

    def test_first_included_level_must_start_at_zero(self):
        resp = self.client.post(self.url, self.data("10", "40", "70"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["form"].non_field_errors())
        self.assertEqual(self.mins(), [None, None, None])

    def test_thresholds_must_increase(self):
        resp = self.client.post(self.url, self.data("0", "50", "50"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f"min_{self.levels[2].pk}", resp.context["form"].errors)

    def test_rejects_out_of_range(self):
        resp = self.client.post(self.url, self.data("0", "50", "150"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.mins(), [None, None, None])

    def test_needs_at_least_one_level(self):
        resp = self.client.post(self.url, self.data("", "", ""))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["form"].non_field_errors())
