"""Question packs, the taxonomy, and the stdlib-only tools that check them.

This is a package only so that `catalog/passages.py` can import
`elevenplus_data.passage_lines` — the passage-wrapping rules have to be the
same object for the renderer and for the validator, or a `line_ref` the
validator approves points at a different line than the pupil sees.

It is NOT a Django app and must not be added to INSTALLED_APPS. The tools in
here (`validate_questions.py`, `taxonomy_lookup.py`, `preview_questions.py`)
are run as scripts by contributors who have no virtualenv, so nothing in this
package may import Django at module level.
"""
