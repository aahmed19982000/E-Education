"""Keep audio files on disk in step with the database.

Handled here (not in views) so it also covers the Django admin, queryset
deletes and the seed command: deleting a question deletes its clip, and
replacing or removing a clip deletes the old file. Files are only removed
once the transaction commits, so a rolled-back save never loses audio.
"""
from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Question


def _delete_file_on_commit(storage, name):
    if name:
        transaction.on_commit(lambda: storage.delete(name))


@receiver(post_delete, sender=Question)
def delete_audio_with_question(sender, instance, **kwargs):
    if instance.audio_file:
        _delete_file_on_commit(instance.audio_file.storage, instance.audio_file.name)


@receiver(pre_save, sender=Question)
def delete_replaced_audio(sender, instance, **kwargs):
    if not instance.pk:
        return
    old_name = Question.objects.filter(pk=instance.pk).values_list("audio_file", flat=True).first()
    if old_name and old_name != instance.audio_file.name:
        _delete_file_on_commit(instance.audio_file.storage, old_name)
