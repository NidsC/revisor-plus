from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("urn", models.CharField(db_index=True, max_length=16, unique=True)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("postcode", models.CharField(blank=True, db_index=True, max_length=12)),
                ("town", models.CharField(blank=True, db_index=True, max_length=120)),
                ("county", models.CharField(blank=True, max_length=120)),
                ("establishment_type", models.CharField(blank=True, max_length=160)),
                ("admissions_policy", models.CharField(blank=True, max_length=120)),
                ("gender", models.CharField(blank=True, max_length=80)),
                ("phase", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(blank=True, max_length=100)),
                ("statutory_low_age", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("statutory_high_age", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("easting", models.IntegerField(blank=True, db_index=True, null=True)),
                ("northing", models.IntegerField(blank=True, db_index=True, null=True)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SchoolOnboardingState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("skipped_at", models.DateTimeField(blank=True, null=True)),
                ("last_postcode", models.CharField(blank=True, max_length=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="school_onboarding_state", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="StudentTargetSchool",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_targets", to="school_onboarding.school")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="school_onboarding_targets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="school",
            index=models.Index(fields=["status", "phase"], name="school_onbo_status_58a8ea_idx"),
        ),
        migrations.AddIndex(
            model_name="school",
            index=models.Index(fields=["easting", "northing"], name="school_onbo_easting_f84783_idx"),
        ),
        migrations.AddConstraint(
            model_name="studenttargetschool",
            constraint=models.UniqueConstraint(fields=("user", "school"), name="unique_student_target_school"),
        ),
    ]
