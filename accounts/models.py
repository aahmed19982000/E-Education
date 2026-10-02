from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    ROLE_MANAGER = "manager"
    ROLE_CONTENT_STAFF = "content_staff"
    ROLE_SUPPORT = "support"
    ROLE_TEACHER = "teacher"
    # Two member categories: administrators (several permission levels) and teachers.
    ADMIN_ROLE_CHOICES = [
        (ROLE_MANAGER, "مدير"),
        (ROLE_CONTENT_STAFF, "مشرف المحتوى"),
        (ROLE_SUPPORT, "مسؤول خدمة العملاء"),
    ]
    TEACHER_ROLE_CHOICES = [(ROLE_TEACHER, "مدرّس")]
    ROLE_CHOICES = ADMIN_ROLE_CHOICES + TEACHER_ROLE_CHOICES
    ROLE_GROUPS = [("الإداريون", ADMIN_ROLE_CHOICES), ("المدرّسون", TEACHER_ROLE_CHOICES)]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"
