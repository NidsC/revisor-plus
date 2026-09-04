"""Patch the Revisor Plus Django project to enable the school_onboarding drop-in app.

Run from the repository root with the same Python/venv used for the project:
    python install_school_onboarding.py

The script only edits settings + root urls. It writes .before_school_onboarding
backup files before changing anything.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()


def find_main_py() -> Path:
    direct = ROOT / "main.py"
    if direct.exists():
        return direct
    candidates = [
        p for p in ROOT.glob("*/*main.py")
        if ".venv" not in p.parts and "venv" not in p.parts
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit("Could not uniquely find main.py. Put this script next to main.py and run it again.")


def settings_path_from_entrypoint(main_py: Path) -> Path:
    text = main_py.read_text(encoding="utf-8")
    match = re.search(r"DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)", text)
    if not match:
        match = re.search(r"DJANGO_SETTINGS_MODULE['\"]\]\s*=\s*['\"]([^'\"]+)", text)
    if not match:
        match = re.search(r"setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)", text)
    if not match:
        raise SystemExit("Could not read DJANGO_SETTINGS_MODULE from main.py.")
    module = match.group(1)
    candidate = main_py.parent.joinpath(*module.split(".")).with_suffix(".py")
    if candidate.exists():
        return candidate
    raise SystemExit(f"Settings file not found for {module}: {candidate}")


def urls_path_from_settings(settings_path: Path, project_root: Path) -> Path:
    text = settings_path.read_text(encoding="utf-8")
    match = re.search(r"ROOT_URLCONF\s*=\s*['\"]([^'\"]+)['\"]", text)
    if match:
        candidate = project_root.joinpath(*match.group(1).split(".")).with_suffix(".py")
        if candidate.exists():
            return candidate
    nearby = settings_path.parent / "urls.py"
    if nearby.exists():
        return nearby
    raise SystemExit("Could not find the root urls.py from ROOT_URLCONF.")


def backup(path: Path):
    backup_path = path.with_name(path.name + ".before_school_onboarding")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def insert_into_list(text: str, list_name: str, entry: str, after_contains: str | None = None) -> str:
    if entry in text:
        return text
    match = re.search(rf"(^\s*{re.escape(list_name)}\s*=\s*\[)", text, flags=re.M)
    if not match:
        raise ValueError(f"Could not find {list_name} = [...] in settings.py")

    start = match.end()
    depth = 1
    i = start
    in_string = None
    escape = False
    while i < len(text):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
        else:
            if char in "'\"":
                in_string = char
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        i += 1
    else:
        raise ValueError(f"Could not find end of {list_name}")

    block = text[start:end]
    indent_match = re.search(r"\n(\s+)[^\s]", block)
    indent = indent_match.group(1) if indent_match else "    "
    line = f"\n{indent}'{entry}',"

    if after_contains and after_contains in block:
        line_match = re.search(rf"^.*{re.escape(after_contains)}.*$", block, flags=re.M)
        if line_match:
            insert_at = start + line_match.end()
            return text[:insert_at] + line + text[insert_at:]

    return text[:end] + line + "\n" + text[end:]


def patch_settings(path: Path):
    backup(path)
    text = path.read_text(encoding="utf-8")
    text = insert_into_list(text, "INSTALLED_APPS", "school_onboarding")
    text = insert_into_list(
        text,
        "MIDDLEWARE",
        "school_onboarding.middleware.SchoolOnboardingMiddleware",
        after_contains="django.contrib.auth.middleware.AuthenticationMiddleware",
    )
    path.write_text(text, encoding="utf-8")


def patch_urls(path: Path):
    backup(path)
    text = path.read_text(encoding="utf-8")
    if 'include("school_onboarding.urls")' in text or "include('school_onboarding.urls')" in text:
        return

    # Make sure include is imported from django.urls.
    django_urls = re.search(r"from\s+django\.urls\s+import\s+([^\n]+)", text)
    if django_urls:
        imports = [item.strip() for item in django_urls.group(1).split(",")]
        if "include" not in imports:
            imports.insert(0, "include")
            replacement = "from django.urls import " + ", ".join(dict.fromkeys(imports))
            text = text[:django_urls.start()] + replacement + text[django_urls.end():]
    else:
        text = "from django.urls import include, path\n" + text

    match = re.search(r"(^\s*urlpatterns\s*=\s*\[)", text, flags=re.M)
    if not match:
        raise ValueError("Could not find urlpatterns = [...] in root urls.py")
    insert_at = match.end()
    text = text[:insert_at] + '\n    path("school-onboarding/", include("school_onboarding.urls")),' + text[insert_at:]
    path.write_text(text, encoding="utf-8")


def main():
    main_py = find_main_py()
    project_root = main_py.parent
    settings_path = settings_path_from_entrypoint(main_py)
    urls_path = urls_path_from_settings(settings_path, project_root)

    app_here = project_root / "school_onboarding"
    source_app = ROOT / "school_onboarding"
    if not app_here.exists() and source_app.exists() and source_app.resolve() != app_here.resolve():
        shutil.copytree(source_app, app_here)
    elif not app_here.exists():
        raise SystemExit("school_onboarding folder is missing. Drag it next to main.py first.")

    print(f"Project root: {project_root}")
    print(f"Settings:     {settings_path}")
    print(f"Root URLs:    {urls_path}")
    patch_settings(settings_path)
    patch_urls(urls_path)
    print("\nPatched settings.py and urls.py. Backups were created beside both files.")

    print("\nRunning Django checks + migration...")
    commands = [
        [sys.executable, str(main_py), "check"],
        [sys.executable, str(main_py), "migrate", "school_onboarding"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=project_root)
        if result.returncode != 0:
            print("\nThe files are installed, but a Django command failed.")
            print("Activate your project venv, then run:")
            print(f"  {sys.executable} {main_py.name} check")
            print(f"  {sys.executable} {main_py.name} migrate school_onboarding")
            return result.returncode

    print("\nSchool onboarding installed successfully.")
    print("Next: download the GIAS 'Establishment fields' CSV and run:")
    print(f"  {sys.executable} {main_py.name} import_gias_schools path/to/edubasealldata.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
