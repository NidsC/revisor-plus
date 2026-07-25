from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a role. Email is the login identifier."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TUTOR = "tutor", "Tutor"
        ADMIN = "admin", "Admin"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.full_name or self.email

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_tutor(self):
        return self.role == self.Role.TUTOR
