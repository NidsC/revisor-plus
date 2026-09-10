from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def find_project_root():
    # This drop-in is designed to be extracted directly beside main.py.
    if (ROOT / "main.py").exists():
        return ROOT

    matches = list(ROOT.glob("**/main.py"))
    if len(matches) == 1:
        return matches[0].parent

    raise SystemExit(
        "Could not uniquely find main.py. Extract this ZIP into the RevisorPlus "
        "folder that contains main.py, then run this file again."
    )


def find_base_template(project):
    preferred = [
        project / "templates" / "base.html",
        project / "templates" / "layout.html",
    ]
    for path in preferred:
        if path.exists():
            return path

    candidates = []
    for path in project.glob("**/*.html"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if "</head>" in text and "</body>" in text and "RevisorPlus" in text:
            candidates.append(path)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SystemExit("Could not find the main base HTML template.")

    raise SystemExit(
        "Found several possible base templates:\n" +
        "\n".join(str(path) for path in candidates[:10])
    )


def copy_assets_if_needed(project):
    source = ROOT / "static" / "student_portals"
    destination = project / "static" / "student_portals"
    destination.mkdir(parents=True, exist_ok=True)

    installed = []
    skipped = []

    for name in ("portals.css", "portals.js"):
        src = source / name
        dst = destination / name

        if not src.exists():
            raise SystemExit(f"Missing packaged asset: {src}")

        # IMPORTANT: when the ZIP is extracted directly into the project,
        # src and dst are the same file. The previous installer tried to
        # copy a file onto itself on Windows, which caused WinError 32.
        if src.resolve() == dst.resolve():
            skipped.append(name)
            continue

        shutil.copy2(src, dst)
        installed.append(name)

    return installed, skipped


def inject_assets(base):
    text = base.read_text(encoding="utf-8")

    css_tag = '  <link rel="stylesheet" href="/static/student_portals/portals.css?v=2">'
    js_tag = '  <script src="/static/student_portals/portals.js?v=2" defer></script>'

    changed = False

    if "/static/student_portals/portals.css" not in text:
        if "</head>" not in text:
            raise SystemExit(f"{base} has no </head> tag.")
        text = text.replace("</head>", css_tag + "\n</head>", 1)
        changed = True

    if "/static/student_portals/portals.js" not in text:
        if "</body>" not in text:
            raise SystemExit(f"{base} has no </body> tag.")
        text = text.replace("</body>", js_tag + "\n</body>", 1)
        changed = True

    if changed:
        backup = base.with_suffix(base.suffix + ".before_student_portals")
        if not backup.exists():
            shutil.copy2(base, backup)
        base.write_text(text, encoding="utf-8")

    return changed


def main():
    project = find_project_root()
    base = find_base_template(project)

    installed, skipped = copy_assets_if_needed(project)
    changed = inject_assets(base)

    print()
    print("RevisorPlus Practice + Mock portals are ready.")
    print(f"Project:       {project}")
    print(f"Base template: {base}")
    print()

    if skipped:
        print("Static assets were already in the correct drag-and-drop location:")
        for name in skipped:
            print(f"  - {name}")

    if installed:
        print("Copied static assets:")
        for name in installed:
            print(f"  - {name}")

    if changed:
        print("Base template linked to the portal CSS/JS.")
        print("Backup created beside it: base.html.before_student_portals")
    else:
        print("Base template already links to the portal CSS/JS.")

    print()
    print("No database, migrations, question-bank logic, or mock-generation logic were changed.")
    print("Refresh the browser with Ctrl + F5.")


if __name__ == "__main__":
    main()
