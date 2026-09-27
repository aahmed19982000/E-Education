import django.db.models.deletion
from django.db import migrations, models


def tags_to_categories(apps, schema_editor):
    Category = apps.get_model("quiz", "Category")
    Question = apps.get_model("quiz", "Question")
    for q in Question.objects.all():
        name_ar = q.tag_ar.strip() or "عام"
        category, created = Category.objects.get_or_create(name_ar=name_ar, defaults={"name_en": q.tag_en.strip()})
        if not created and not category.name_en and q.tag_en.strip():
            category.name_en = q.tag_en.strip()
            category.save(update_fields=["name_en"])
        q.category = category
        q.save(update_fields=["category"])


def categories_to_tags(apps, schema_editor):
    Question = apps.get_model("quiz", "Question")
    for q in Question.objects.select_related("category"):
        q.tag_ar, q.tag_en = q.category.name_ar, q.category.name_en
        q.save(update_fields=["tag_ar", "tag_en"])


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0003_grading"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_ar", models.CharField(max_length=100, unique=True)),
                ("name_en", models.CharField(blank=True, help_text="Optional; falls back to Arabic", max_length=100)),
            ],
            options={"ordering": ["name_ar"], "verbose_name_plural": "Categories"},
        ),
        migrations.AddField(
            model_name="question",
            name="category",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="questions", to="quiz.category"),
        ),
        # Tags become optional so the reverse migration can refill them.
        migrations.AlterField(model_name="question", name="tag_ar", field=models.CharField(blank=True, max_length=100)),
        migrations.RunPython(tags_to_categories, categories_to_tags),
        migrations.RemoveField(model_name="question", name="tag_ar"),
        migrations.RemoveField(model_name="question", name="tag_en"),
        migrations.AlterField(
            model_name="question",
            name="category",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questions", to="quiz.category"),
        ),
    ]
