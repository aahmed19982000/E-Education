import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [("exams", "0003_exam_level_data")]

    operations = [
        migrations.RemoveField(model_name="exam", name="cohort"),
        migrations.RemoveField(model_name="exam", name="lesson"),
        migrations.AlterField(
            model_name="exam", name="level",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams",
                                    to="courses.courselevel"),
        ),
        migrations.AlterModelOptions(name="exam", options={"ordering": ["level", "kind", "number"]}),
        migrations.AddConstraint(
            model_name="exam",
            constraint=models.UniqueConstraint(condition=Q(kind="session"), fields=("level", "number"),
                                               name="one_session_exam_per_level_number"),
        ),
        migrations.AddConstraint(
            model_name="exam",
            constraint=models.UniqueConstraint(condition=Q(kind="level"), fields=("level",),
                                               name="one_final_exam_per_level"),
        ),
    ]
