import html
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


def _squash(text):
    """Drop all whitespace: the hand-converted pages wrap tags and lines differently from the
    Markdown, and a tag stripped between a word and its punctuation leaves a stray space."""
    return re.sub(r"\s+", "", text)


def _first_sentences(path):
    """First sentence of every prose paragraph of a Markdown document."""
    with open(path, encoding="utf-8") as f:
        paragraphs = re.split(r"\n\s*\n", f.read())
    sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para or not (para[0].isalpha() or para[0] == "*"):
            continue
        para = re.sub(r"\s+", " ", para.replace("**", ""))
        end = para.find(". ")
        sentence = para[: end + 1] if end != -1 else para
        if len(sentence) > 40:
            sentences.append(sentence)
    return sentences


class LegalPageTests(TestCase):
    def test_legal_pages_carry_the_resolved_documents(self):
        for name, doc in (("privacy", "docs/legal/privacy-policy.md"), ("terms", "docs/legal/terms-of-service.md")):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", content)).split())
                needles = {
                    "privacy": ("Version 1.0", "18 November 2026"),
                    "terms": ("Version 1.1", "19 November 2026", "£14.99 per month, per pupil"),
                }
                for needle in needles[name] + ("RevisorPlus", "revisorplus@gmail.com"):
                    self.assertIn(needle, text)
                if name == "terms":
                    self.assertNotIn("29.99", text)
                for banned in ("[CHECK", "DRAFT", "Solicitor note", "TODO", "**"):
                    self.assertNotIn(banned, content)
                sentences = _first_sentences(settings.BASE_DIR / doc)
                self.assertGreaterEqual(len(sentences), 12)
                squashed = _squash(text)
                for sentence in sentences:
                    self.assertIn(_squash(sentence), squashed, sentence)

    def test_landing_and_login_link_to_both_pages(self):
        for url in ("/", reverse("account_login")):
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertIn('href="/privacy/"', content)
                self.assertIn('href="/terms/"', content)
