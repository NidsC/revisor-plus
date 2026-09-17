from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a role. Email is the login identifier."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TUTOR = "tutor", "Tutor"
        ADMIN = "admin", "Admin"
        PARENT = "parent", "Parent"

    email = models.EmailField("email address", unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=150, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        limit_choices_to={"role": "parent"},
    )

    def __str__(self):
        return self.full_name or self.email or self.username

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_tutor(self):
        return self.role == self.Role.TUTOR

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT
