import random
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quiz.models import Category, Question
from quiz.placement_test import questions as test

AUDIO_DIR = Path(test.__file__).resolve().parent


class Command(BaseCommand):
    help = "Load the 30-question English placement test (A1–C2), including its listening clips."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace", action="store_true",
            help="Delete all existing quiz questions (and their audio) first. Required if any exist.",
        )

    def handle(self, *args, replace=False, **options):
        existing = Question.objects.count()
        if existing and not replace:
            raise CommandError(
                f"There are already {existing} questions. Run with --replace to delete them and load the placement test."
            )

        with transaction.atomic():
            if existing:
                Question.objects.all().delete()  # quiz.signals removes their audio files on commit

            categories = {
                key: Category.objects.get_or_create(name_ar=ar, defaults={"name_en": en})[0]
                for key, (ar, en) in test.CATEGORIES.items()
            }
            # Spread the correct answer evenly over the four positions, in a shuffled
            # but fixed order (same seed = same test every time it's loaded).
            rng = random.Random(2026)
            slots = [i % 4 for i in range(len(test.QUESTIONS))]
            rng.shuffle(slots)
            for order, (item, slot) in enumerate(zip(test.QUESTIONS, slots), start=1):
                correct, *wrong = item["options"]
                rng.shuffle(wrong)
                options = wrong[:slot] + [correct] + wrong[slot:]
                question = Question(
                    order=order,
                    category=categories[item["kind"]],
                    text_ar=item["text_ar"],
                    text_en=item.get("text_en", ""),
                    passage_ar=item.get("passage", ""),
                    options_ar=options,
                    options_en=[],
                    correct_index=options.index(correct),
                    points=Decimal(test.POINTS[item["level"]]),
                    time_limit_seconds=item.get("seconds"),
                )
                clip = item.get("audio")
                if clip:
                    question.audio_label_ar = clip["label_ar"]
                    question.audio_label_en = clip["label_en"]
                    with open(AUDIO_DIR / clip["file"], "rb") as fh:
                        question.audio_file.save(clip["file"], File(fh), save=False)
                question.save()

        levels = {}
        for item in test.QUESTIONS:
            levels[item["level"]] = levels.get(item["level"], 0) + 1
        summary = ", ".join(f"{lvl}: {n}" for lvl, n in sorted(levels.items()))
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(test.QUESTIONS)} placement test questions ({summary})."))
