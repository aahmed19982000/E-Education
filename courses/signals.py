from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EnrollmentRequest


@receiver(post_save, sender=EnrollmentRequest)
def notify_payment(sender, instance, **kwargs):
    """Whatever marks a request paid (dashboard or gateway), the student is thanked once."""
    if instance.is_paid:
        from core import notify
        notify.payment_received(instance)
