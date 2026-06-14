"""Smoke tests for the aceData site.

Covers public page rendering, authentication flows (including the custom
username-or-email backend), the account page, the checkout landing page, and
the Stripe webhook's purchase-recording logic.
"""
import hashlib
import hmac
import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomUser, Purchase


PUBLIC_PAGES = [
    "home", "pricing", "services",
    "contacts", "about", "privacy", "terms-of-use", "signup",
    "login", "password_reset_custom", "password_reset_sent",
    "checkout", "success", "cancel",
]


class PublicPageTests(TestCase):
    def test_public_pages_return_200(self):
        for name in PUBLIC_PAGES:
            with self.subTest(page=name):
                resp = self.client.get(reverse(name))
                self.assertEqual(resp.status_code, 200, f"{name} did not return 200")


class AuthFlowTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        resp = self.client.post(reverse("signup"), {
            "username": "datafan",
            "email": "datafan@example.com",
            "password1": "Sup3rStr0ngPwd!",
            "password2": "Sup3rStr0ngPwd!",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        self.assertTrue(CustomUser.objects.filter(username="datafan").exists())

    def test_login_with_username_and_with_email(self):
        CustomUser.objects.create_user(
            username="ace", email="ace@example.com", password="Sup3rStr0ngPwd!"
        )
        # Username
        self.assertTrue(self.client.login(username="ace", password="Sup3rStr0ngPwd!"))
        self.client.logout()
        # Email (custom backend allows email in the username field)
        self.assertTrue(
            self.client.login(username="ace@example.com", password="Sup3rStr0ngPwd!")
        )

    def test_bad_credentials_return_none_not_error(self):
        """The backend must return None (not raise) for unknown/wrong creds."""
        CustomUser.objects.create_user(
            username="ace", email="ace@example.com", password="Sup3rStr0ngPwd!"
        )
        self.assertFalse(self.client.login(username="nope", password="whatever"))
        self.assertFalse(self.client.login(username="ace", password="wrong-password"))

    def test_logout_via_post(self):
        """The UI logs out via POST (the supported method across Django versions)."""
        user = CustomUser.objects.create_user(
            username="ace", email="ace@example.com", password="Sup3rStr0ngPwd!"
        )
        self.client.force_login(user)
        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
        # Session is no longer authenticated.
        self.assertNotIn("_auth_user_id", self.client.session)


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="ace", email="ace@example.com", password="Sup3rStr0ngPwd!"
        )
        self.client.force_login(self.user)

    def test_weak_new_password_is_rejected(self):
        self.client.post(reverse("change_password"), {
            "old_password": "Sup3rStr0ngPwd!",
            "changed_password": "123",
        })
        self.user.refresh_from_db()
        # Old password still works; the weak one was not applied.
        self.assertTrue(self.user.check_password("Sup3rStr0ngPwd!"))

    def test_strong_new_password_applies_and_keeps_session(self):
        resp = self.client.post(reverse("change_password"), {
            "old_password": "Sup3rStr0ngPwd!",
            "changed_password": "An0therStr0ng!Pwd",
        })
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("An0therStr0ng!Pwd"))
        # Session stays valid after the hash change (no silent logout).
        self.assertIn("_auth_user_id", self.client.session)


class AccountPageTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="ace", email="ace@example.com", password="Sup3rStr0ngPwd!"
        )

    def test_account_requires_login(self):
        resp = self.client.get(reverse("account"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_account_shows_purchase_history(self):
        Purchase.objects.create(user_name="ace", item_name="Tier 2", amount_paid="99.00")
        self.client.force_login(self.user)
        resp = self.client.get(reverse("account"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tier 2")


def _stripe_signed_headers(payload: str, secret: str):
    """Build a valid Stripe-Signature header for a payload."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}".encode()
    signature = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    return {"HTTP_STRIPE_SIGNATURE": f"t={timestamp},v1={signature}"}


class ContactTests(TestCase):
    def test_contact_post_sends_email_and_redirects(self):
        from django.core import mail
        resp = self.client.post(reverse("contacts"), {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company": "Acme",
            "message": "I need a data warehouse.",
        })
        self.assertRedirects(resp, reverse("contacts"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Jane Doe", mail.outbox[0].body)

    def test_contact_post_requires_fields(self):
        from django.core import mail
        resp = self.client.post(reverse("contacts"), {"name": "", "email": "", "message": ""})
        self.assertRedirects(resp, reverse("contacts"))
        self.assertEqual(len(mail.outbox), 0)


class CheckoutAccessTests(TestCase):
    def test_paid_tiers_require_login(self):
        for name in ("tier2", "tier3"):
            with self.subTest(tier=name):
                resp = self.client.post(reverse(name))
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/login", resp["Location"])


class WebhookSecurityTests(TestCase):
    def test_webhook_without_secret_is_refused(self):
        """With no signing secret configured, unsigned events are refused."""
        from . import views
        self.addCleanup(setattr, views, "endpoint_secret", views.endpoint_secret)
        views.endpoint_secret = ""
        resp = self.client.post(
            reverse("webhook"), data="{}", content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Purchase.objects.count(), 0)


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
class WebhookTests(TestCase):
    def test_completed_checkout_records_and_links_purchase(self):
        # endpoint_secret is read at import time, so patch the view module too.
        from . import views
        self.addCleanup(setattr, views, "endpoint_secret", views.endpoint_secret)
        views.endpoint_secret = "whsec_test_secret"

        buyer = CustomUser.objects.create_user(
            username="ace", email="buyer@example.com", password="Sup3rStr0ngPwd!"
        )

        event = {
            "id": "evt_test_123",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {"object": {
                "created": int(time.time()),
                "customer_details": {"email": "buyer@example.com", "name": "Buyer"},
                "metadata": {
                    "my_client": "ace",
                    "user_id": str(buyer.pk),
                    "product_name": "Build",
                    "price": "149.00",
                },
            }},
        }
        payload = json.dumps(event)
        headers = _stripe_signed_headers(payload, "whsec_test_secret")
        resp = self.client.post(
            reverse("webhook"), data=payload,
            content_type="application/json", **headers
        )
        self.assertEqual(resp.status_code, 200)
        purchase = Purchase.objects.get(item_name="Build")
        # The purchase is linked to the buyer's account via the FK.
        self.assertEqual(purchase.user_id, buyer.pk)
        self.assertEqual(purchase.user_name, "ace")
        self.assertEqual(purchase.event_id, "evt_test_123")

    def test_duplicate_event_does_not_create_second_purchase(self):
        """A retried (identical) Stripe event must not duplicate the purchase."""
        from . import views
        self.addCleanup(setattr, views, "endpoint_secret", views.endpoint_secret)
        views.endpoint_secret = "whsec_test_secret"

        event = {
            "id": "evt_dup_456",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {"object": {
                "created": int(time.time()),
                "customer_details": {"email": "buyer@example.com", "name": "Buyer"},
                "metadata": {"product_name": "Build", "price": "149.00"},
            }},
        }
        payload = json.dumps(event)

        def deliver():
            headers = _stripe_signed_headers(payload, "whsec_test_secret")
            return self.client.post(
                reverse("webhook"), data=payload,
                content_type="application/json", **headers
            )

        self.assertEqual(deliver().status_code, 200)
        self.assertEqual(deliver().status_code, 200)  # Stripe retry
        self.assertEqual(Purchase.objects.filter(event_id="evt_dup_456").count(), 1)
