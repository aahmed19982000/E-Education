import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0012_course_levels"),
        ("exams", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="exam", name="one_level_exam_per_cohort"),
        migrations.AddField(
            model_name="exam", name="level",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="exams", to="courses.courselevel"),
        ),
        migrations.AddField(
            model_name="exam", name="number",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="submission", name="cohort",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="exam_submissions", to="courses.cohort"),
        ),
    ]
