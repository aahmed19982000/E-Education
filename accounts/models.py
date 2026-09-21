from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    ROLE_CONTENT_STAFF = "content_staff"
    ROLE_TEACHER = "teacher"
    ROLE_CHOICES = [
        (ROLE_CONTENT_STAFF, "موظف محتوى"),
        (ROLE_TEACHER, "مدرّس"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"
