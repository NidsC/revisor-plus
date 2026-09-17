import os

from django.db import migrations


def reset_unparented_pupils(apps, schema_editor):
    """Live data is demo-only as of 2026-09-16 (owner decision); this cascades
    those pupils' sessions, attempts, assignments and tutor links, and
    seed_demo recreates the demo family on the next build."""
    User = apps.get_model("accounts", "User")
    unparented = User.objects.filter(role="student", parent__isnull=True)
    count = unparented.count()
    if count == 0:
        return
    if os.environ.get("CONFIRM_PUPIL_RESET") != "1":
        raise RuntimeError(
            f"{count} unparented pupils would be deleted with their attempts; "
            "back up first (./backup.sh) then rerun migrate with "
            "CONFIRM_PUPIL_RESET=1"
        )
    unparented.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_parent_alter_user_email_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(reset_unparented_pupils, noop_reverse),
    ]
