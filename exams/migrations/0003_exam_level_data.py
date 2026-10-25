from django.db import migrations


def to_levels(apps, schema_editor):
    """Old exams belonged to one group. Give that group's course a first level (if the group has
    none), and move the exam up to (level, session number). A second group's exam with the same
    number is merged into the first: its handed-in answers move across, its questions are dropped."""
    Exam = apps.get_model("exams", "Exam")
    Submission = apps.get_model("exams", "Submission")
    CourseLevel = apps.get_model("courses", "CourseLevel")
    for exam in Exam.objects.select_related("cohort", "lesson").order_by("pk"):
        cohort = exam.cohort
        if cohort.level_id is None:
            level, _ = CourseLevel.objects.get_or_create(course_id=cohort.course_id, name_ar="المستوى الأول",
                                                         defaults={"name_en": "Level 1"})
            cohort.level_id = level.pk
            cohort.save(update_fields=["level"])
        number = exam.lesson.number if exam.lesson_id else None
        Submission.objects.filter(exam=exam).update(cohort=cohort)
        twin = Exam.objects.filter(level_id=cohort.level_id, kind=exam.kind, number=number).exclude(pk=exam.pk).first()
        if twin is not None:
            Submission.objects.filter(exam=exam).update(exam=twin)
            exam.delete()
            continue
        exam.level_id, exam.number = cohort.level_id, number
        exam.save(update_fields=["level", "number"])


class Migration(migrations.Migration):

    dependencies = [("exams", "0002_exam_level_fields")]

    operations = [migrations.RunPython(to_levels, migrations.RunPython.noop)]
