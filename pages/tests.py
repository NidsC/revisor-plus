import html
import re

from django.conf import settings
from django.test import TestCase, override_settings
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
                    "privacy": ("Version 1.2", "19 November 2026"),
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


META_ON = dict(META_PIXEL_ID="123", META_CAPI_TOKEN="x", META_ENABLED=True, META_GRAPH_VERSION="v27.0")


@override_settings(**META_ON)
class ConsentTests(TestCase):
    def test_the_consent_page_renders_with_the_current_choice(self):
        response = self.client.get(reverse("consent"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cookies on RevisorPlus")
        self.assertContains(response, "You have not made a choice yet.")
        self.assertContains(response, 'value="yes"')
        self.assertContains(response, 'value="no"')
        self.client.cookies["rp_consent"] = "no"
        self.assertContains(self.client.get(reverse("consent")), "advertising cookies rejected")

    def test_posting_a_choice_sets_the_cookie_and_redirects_to_a_safe_next_only(self):
        for choice in ("yes", "no"):
            with self.subTest(choice=choice):
                response = self.client.post(reverse("consent"), {"choice": choice, "next": "/offer/X/?a=1"})
                self.assertRedirects(response, "/offer/X/?a=1", fetch_redirect_response=False)
                cookie = response.cookies["rp_consent"]
                self.assertEqual(cookie.value, choice)
                self.assertEqual(cookie["max-age"], 180 * 24 * 3600)
                self.assertEqual(cookie["samesite"], "Lax")
                self.assertFalse(cookie["httponly"])
        for unsafe in ("https://evil.example/", "//evil.example/", ""):
            with self.subTest(next=unsafe):
                response = self.client.post(reverse("consent"), {"choice": "yes", "next": unsafe})
                self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_the_cookie_is_secure_when_debug_is_off(self):
        with override_settings(DEBUG=False):
            response = self.client.post(reverse("consent"), {"choice": "yes"})
        self.assertTrue(response.cookies["rp_consent"]["secure"])

    def test_an_invalid_choice_sets_nothing(self):
        response = self.client.post(reverse("consent"), {"choice": "maybe"})
        self.assertNotIn("rp_consent", response.cookies)

    def test_the_consent_post_needs_a_csrf_token(self):
        from django.test import Client

        response = Client(enforce_csrf_checks=True).post(reverse("consent"), {"choice": "yes"})
        self.assertEqual(response.status_code, 403)

    def test_the_banner_shows_on_the_landing_and_offer_pages_only_without_a_cookie(self):
        offer = self._offer_page_patches()
        self.addCleanup(offer)
        for url in ("/", reverse("offer_landing", args=["FIRSTMONTH499"])):
            with self.subTest(url=url):
                page = self.client.get(url).content.decode()
                self.assertIn('class="rp-consent"', page)
                self.assertIn('name="choice" value="no"', page)
                self.assertLess(page.index('value="no"'), page.index('value="yes"'))
                self.assertIn('href="/privacy/#s12"', page)
                self.assertNotIn("fbq(", page)
        for cookie in ("yes", "no"):
            self.client.cookies["rp_consent"] = cookie
            self.assertNotIn('class="rp-consent"', self.client.get("/").content.decode())

    def test_there_is_no_banner_without_a_pixel_id(self):
        with override_settings(META_PIXEL_ID="", META_CAPI_TOKEN="", META_ENABLED=False):
            self.assertNotIn('class="rp-consent"', self.client.get("/").content.decode())

    def test_the_pixel_snippet_appears_only_with_yes(self):
        for cookie, expected in ((None, False), ("no", False), ("yes", True)):
            with self.subTest(cookie=cookie):
                client = self.client_class()
                if cookie:
                    client.cookies["rp_consent"] = cookie
                page = client.get("/").content.decode()
                self.assertEqual("fbq('track', 'PageView')" in page, expected)
                if expected:
                    self.assertIn("connect.facebook.net/en_US/fbevents.js", page)
                    self.assertIn('id="rp-meta-pixel-id"', page)

    def test_the_footers_link_to_the_cookie_choices(self):
        for url in ("/", reverse("account_login")):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'href="/consent/">Cookie choices</a>')

    def test_no_pixel_markup_on_login_family_or_pupil_pages_under_any_cookie_state(self):
        from accounts.models import User

        parent = User.objects.create_user(username="par", email="par@example.test", password="x" * 12, role="parent")
        pupil = User(username="pup", full_name="Pup", role="student", parent=parent)
        pupil.set_password("y" * 12)
        pupil.save()
        for cookie in (None, "no", "yes"):
            for who, url in ((None, reverse("account_login")), (parent, reverse("family:home")),
                             (pupil, reverse("practice:dashboard"))):
                with self.subTest(cookie=cookie, url=url):
                    client = self.client_class()
                    if cookie:
                        client.cookies["rp_consent"] = cookie
                    if who:
                        client.force_login(who)
                    page = client.get(url).content.decode()
                    self.assertNotIn("fbq(", page)
                    self.assertNotIn("fbevents.js", page)
                    self.assertNotIn('class="rp-consent"', page)

    def _offer_page_patches(self):
        from unittest import mock

        promo = {"id": "promo_x", "code": "FIRSTMONTH499", "restrictions": {"first_time_transaction": True},
                 "promotion": {"type": "coupon", "coupon": {"amount_off": 1000, "currency": "gbp",
                                                            "duration": "once", "redeem_by": None}}}
        patches = [
            mock.patch("billing.offers.stripe.PromotionCode.list", return_value={"data": [promo]}),
            mock.patch("billing.funnel.stripe_ready", return_value=True),
        ]
        for patch in patches:
            patch.start()

        def stop():
            for patch in patches:
                patch.stop()
        return stop
