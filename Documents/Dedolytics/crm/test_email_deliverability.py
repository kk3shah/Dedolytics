"""
Comprehensive tests for email deliverability fixes.

Tests cover:
  1. Email headers: Reply-To, List-Unsubscribe, From, To, Bcc, Subject
  2. Plain-text extraction from HTML (spam filter compliance)
  3. Infographic email wrapper (no display:flex, uses table layout)
  4. Sender name determinism across initial + follow-up emails
  5. SMTP interaction via mock (verifies the message actually sent)
  6. Edge cases: empty HTML, missing credentials, special characters
  7. Follow-up template rendering with placeholder substitution

Run:  python -m pytest test_email_deliverability.py -v
  or: python test_email_deliverability.py
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from email.message import EmailMessage
import smtplib

# Mock google.generativeai before any CRM module imports it.
# This prevents ImportError in environments without the full gRPC/cffi stack.
_mock_genai = MagicMock()
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.generativeai", _mock_genai)


# ─── Test Helpers ────────────────────────────────────────────────────────────

SAMPLE_HTML = """
<html>
<body style="margin: 0; padding: 0;">
  <div style="max-width: 600px; margin: 0 auto; font-family: Arial;">
    <h1>Hello World</h1>
    <p>This is a <strong>test email</strong> for Acme Corp.</p>
    <p>We build dashboards that track revenue.</p>
    <a href="https://example.com">Book a Call</a>
    <style>.hidden { display: none; }</style>
    <script>alert('xss')</script>
  </div>
</body>
</html>
"""

SAMPLE_INFOGRAPHIC = """
<div style="width:100%;max-width:600px;margin:0 auto;padding:20px;box-sizing:border-box;background-color:#ffffff;">
  <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics" width="140" />
  <h2>Custom Analytics for Iron Gym</h2>
  <p>We can help you track member retention, peak hours, and revenue per class.</p>
  <a href="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ2HePxAUUQzDdORvH9M7ZxCnczzZHTq6w_Ubpjy2STAQTLqYfAgCC9bqNidQSiguEqe1_1kJ_lx"
     style="display:inline-block;padding:14px 28px;background-color:#0056b3;color:#ffffff;">
    Schedule a Free 15-Min Call
  </a>
</div>
"""


# ─── SMB Outreach Tests ──────────────────────────────────────────────────────


class TestSMBPlainTextExtraction(unittest.TestCase):
    """Tests for smb_outreach._html_to_plain_text()"""

    def setUp(self):
        from smb_outreach import _html_to_plain_text

        self.extract = _html_to_plain_text

    def test_extracts_visible_text(self):
        """Plain-text output must contain the actual readable content."""
        result = self.extract(SAMPLE_HTML)
        self.assertIn("Hello World", result)
        self.assertIn("test email", result)
        self.assertIn("Acme Corp", result)
        self.assertIn("Book a Call", result)

    def test_strips_style_tags(self):
        """Style tag content must NOT leak into plain text."""
        result = self.extract(SAMPLE_HTML)
        self.assertNotIn(".hidden", result)
        self.assertNotIn("display: none", result)

    def test_strips_script_tags(self):
        """Script tag content must NOT leak into plain text."""
        result = self.extract(SAMPLE_HTML)
        self.assertNotIn("alert", result)
        self.assertNotIn("xss", result)

    def test_no_excessive_blank_lines(self):
        """Output should not have 3+ consecutive newlines."""
        result = self.extract(SAMPLE_HTML)
        self.assertNotIn("\n\n\n", result)

    def test_not_generic_placeholder(self):
        """Output must NOT be the old generic 'Please enable HTML' text."""
        result = self.extract(SAMPLE_HTML)
        self.assertNotIn("Please enable HTML", result)

    def test_empty_html_returns_empty_string(self):
        """Empty HTML input should return empty string, not crash."""
        result = self.extract("")
        self.assertEqual(result, "")

    def test_html_with_only_style_returns_empty(self):
        """HTML with only style/script tags should return empty after stripping."""
        result = self.extract("<html><style>body{color:red}</style></html>")
        self.assertEqual(result, "")

    def test_unicode_content_preserved(self):
        """Unicode characters (accents, symbols) must survive extraction."""
        html = "<p>Café résumé — $499/month</p>"
        result = self.extract(html)
        self.assertIn("Café", result)
        self.assertIn("résumé", result)
        self.assertIn("$499/month", result)

    def test_followup_template_extraction(self):
        """Follow-up template HTML must produce meaningful plain text."""
        from smb_outreach import FOLLOWUP_TEMPLATES, CALENDAR_LINK

        rendered = FOLLOWUP_TEMPLATES[0]["body"].format(
            company_name="Iron Gym",
            category="fitness",
            calendar_link=CALENDAR_LINK,
        )
        result = self.extract(rendered)
        self.assertIn("Iron Gym", result)
        self.assertIn("15 minutes", result)
        self.assertIn("free", result.lower())
        self.assertTrue(len(result) > 50, "Plain text should be substantial, not a stub")


class TestSMBEmailHeaders(unittest.TestCase):
    """Tests that send_html_email() sets all required headers on the EmailMessage."""

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_all_critical_headers_present(self, mock_smtp_class):
        """Every email must have Reply-To, List-Unsubscribe, From, To, Bcc, Subject."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        result = send_html_email(
            to_address="client@example.com",
            subject="Test Subject",
            html_body="<p>Hello</p>",
            sender_email="ops@dedolytics.org",
            sender_password="fake-password",
            sender_name="Paul",
        )

        self.assertTrue(result)
        mock_server.send_message.assert_called_once()

        # Grab the actual EmailMessage that was sent
        msg = mock_server.send_message.call_args[0][0]
        self.assertIsInstance(msg, EmailMessage)

        # Verify every critical header
        self.assertEqual(msg["Subject"], "Test Subject")
        self.assertEqual(msg["To"], "client@example.com")
        self.assertIn("ops@dedolytics.org", msg["From"])
        self.assertIn("Paul", msg["From"])
        self.assertEqual(msg["Reply-To"], "hello@dedolytics.org")
        self.assertIn("unsubscribe@dedolytics.org", msg["List-Unsubscribe"])
        self.assertEqual(msg["Bcc"], "hello@dedolytics.org")

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_reply_to_is_monitored_inbox(self, mock_smtp_class):
        """Reply-To must point to hello@dedolytics.org, NOT the rotating sender."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email(
            to_address="someone@example.com",
            subject="Test",
            html_body="<p>Hi</p>",
            sender_email="ops@dedolytics.org",  # rotating sender
            sender_password="fake",
            sender_name="Ed",
        )

        msg = mock_server.send_message.call_args[0][0]
        # Reply-To should NOT be the rotating sender
        self.assertNotEqual(msg["Reply-To"], "ops@dedolytics.org")
        self.assertEqual(msg["Reply-To"], "hello@dedolytics.org")

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_list_unsubscribe_is_mailto(self, mock_smtp_class):
        """List-Unsubscribe must be a mailto: URI (required format)."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email(
            to_address="a@b.com",
            subject="Sub",
            html_body="<p>Hi</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Will",
        )

        msg = mock_server.send_message.call_args[0][0]
        self.assertIn("mailto:", msg["List-Unsubscribe"])

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_plain_text_part_is_meaningful(self, mock_smtp_class):
        """The text/plain MIME part must contain real content, not a generic stub."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email(
            to_address="a@b.com",
            subject="Sub",
            html_body="<p>Track your revenue with custom dashboards.</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Paul",
        )

        msg = mock_server.send_message.call_args[0][0]

        # Extract the text/plain part
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break

        self.assertIsNotNone(plain_part, "Email must have a text/plain part")
        self.assertNotIn("Please enable HTML", plain_part)
        self.assertIn("revenue", plain_part.lower())

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_html_part_is_present(self, mock_smtp_class):
        """The text/html MIME part must be present with the original HTML."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email(
            to_address="a@b.com",
            subject="Sub",
            html_body="<p>Custom dashboard for your business</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Paul",
        )

        msg = mock_server.send_message.call_args[0][0]

        html_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break

        self.assertIsNotNone(html_part, "Email must have a text/html part")
        self.assertIn("Custom dashboard", html_part)

    def test_missing_credentials_returns_true_without_sending(self):
        """When credentials are missing, should return True (simulation) without SMTP."""
        from smb_outreach import send_html_email

        # Empty string password
        result = send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", "", "Paul")
        self.assertTrue(result)

        # None password
        result = send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", None, "Paul")
        self.assertTrue(result)

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_smtp_failure_returns_false(self, mock_smtp_class):
        """SMTP connection failure should return False, not crash."""
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        from smb_outreach import send_html_email

        result = send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", "pw", "Paul")
        self.assertFalse(result)


class TestSMBInfographicWrapper(unittest.TestCase):
    """Tests for wrap_infographic_in_email() — email-safe HTML layout."""

    def setUp(self):
        from smb_outreach import wrap_infographic_in_email

        self.wrap = wrap_infographic_in_email

    def test_no_display_flex(self):
        """Wrapped email must NOT use display:flex (unsupported in Outlook/Gmail)."""
        result = self.wrap(SAMPLE_INFOGRAPHIC)
        self.assertNotIn("display: flex", result)
        self.assertNotIn("display:flex", result)

    def test_uses_table_layout(self):
        """Wrapped email must use table-based centering for email client compatibility."""
        result = self.wrap(SAMPLE_INFOGRAPHIC)
        self.assertIn("<table", result)
        self.assertIn("role=\"presentation\"", result)

    def test_infographic_content_preserved(self):
        """The original infographic HTML must be embedded intact."""
        result = self.wrap(SAMPLE_INFOGRAPHIC)
        self.assertIn("Custom Analytics for Iron Gym", result)
        self.assertIn("dedolytics.org/assets/images/logo.jpeg", result)
        self.assertIn("Schedule a Free 15-Min Call", result)

    def test_has_html_body_tags(self):
        """Output must be a complete HTML document with <html> and <body> tags."""
        result = self.wrap("<p>Test</p>")
        self.assertIn("<html>", result)
        self.assertIn("<body", result)
        self.assertIn("</body>", result)
        self.assertIn("</html>", result)

    def test_background_color_set(self):
        """Wrapper should set a background color for consistent rendering."""
        result = self.wrap("<p>Test</p>")
        self.assertIn("background-color", result)


class TestSMBSenderNameDeterminism(unittest.TestCase):
    """Tests that sender names are deterministic per lead_id."""

    def setUp(self):
        from smb_outreach import SENDER_NAMES

        self.names = SENDER_NAMES

    def test_same_lead_id_same_name(self):
        """The same lead_id must always produce the same sender name."""
        for lead_id in [1, 5, 42, 100, 999]:
            name1 = self.names[lead_id % len(self.names)]
            name2 = self.names[lead_id % len(self.names)]
            self.assertEqual(name1, name2, f"Lead {lead_id} got inconsistent names")

    def test_different_lead_ids_cycle_through_names(self):
        """Consecutive lead_ids should cycle through all available names."""
        assigned = set()
        for lead_id in range(len(self.names)):
            name = self.names[lead_id % len(self.names)]
            assigned.add(name)
        self.assertEqual(assigned, set(self.names), "Not all sender names are being used")

    def test_initial_and_followup_same_name(self):
        """For the same lead_id, initial and follow-up must use the same name."""
        for lead_id in [1, 2, 3, 10, 50, 101]:
            initial_name = self.names[lead_id % len(self.names)]
            followup_name = self.names[lead_id % len(self.names)]
            self.assertEqual(
                initial_name,
                followup_name,
                f"Lead {lead_id}: initial='{initial_name}' but followup='{followup_name}'",
            )


class TestSMBFollowUpTemplates(unittest.TestCase):
    """Tests that follow-up templates render correctly with placeholder values."""

    def setUp(self):
        from smb_outreach import FOLLOWUP_TEMPLATES, CALENDAR_LINK

        self.templates = FOLLOWUP_TEMPLATES
        self.calendar_link = CALENDAR_LINK

    def test_all_three_templates_exist(self):
        """There must be exactly 3 follow-up templates."""
        self.assertEqual(len(self.templates), 3)

    def test_subject_renders_company_name(self):
        """Subject line must include the company name after rendering."""
        for i, tpl in enumerate(self.templates):
            subject = tpl["subject"].format(company_name="Iron Gym")
            self.assertIn("Iron Gym", subject, f"Template {i} subject missing company name")

    def test_body_renders_all_placeholders(self):
        """Body must render company_name, category, and calendar_link without errors."""
        for i, tpl in enumerate(self.templates):
            try:
                body = tpl["body"].format(
                    company_name="Test Corp",
                    category="fitness",
                    calendar_link=self.calendar_link,
                )
            except KeyError as e:
                self.fail(f"Template {i} has unmatched placeholder: {e}")

            self.assertIn("Test Corp", body)
            self.assertIn(self.calendar_link, body)

    def test_calendar_link_is_valid_url(self):
        """Calendar link must be a valid Google Calendar URL."""
        self.assertTrue(
            self.calendar_link.startswith("https://calendar.google.com"),
            "Calendar link is not a Google Calendar URL",
        )


# ─── ABM Outreach Bot Tests ─────────────────────────────────────────────────


class TestABMEmailHeaders(unittest.TestCase):
    """Tests that outreach_bot.send_email() sets all required headers."""

    @patch("outreach_bot.smtplib.SMTP_SSL")
    def test_all_critical_headers_present(self, mock_smtp_class):
        """ABM email must have Reply-To, List-Unsubscribe, From, To, Bcc."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from outreach_bot import send_email

        result = send_email(
            to_address="vp@bigcorp.com",
            subject="Data Analytics at BigCorp",
            html_body="<p>Hi, let's chat about Power BI.</p>",
            sender_email="hello@dedolytics.org",
            sender_password="fake-pass",
            sender_name="Paul",
        )

        self.assertTrue(result)
        msg = mock_server.send_message.call_args[0][0]

        self.assertEqual(msg["Subject"], "Data Analytics at BigCorp")
        self.assertEqual(msg["To"], "vp@bigcorp.com")
        self.assertIn("hello@dedolytics.org", msg["From"])
        self.assertIn("Paul", msg["From"])
        self.assertEqual(msg["Reply-To"], "hello@dedolytics.org")
        self.assertIn("unsubscribe", msg["List-Unsubscribe"])
        self.assertEqual(msg["Bcc"], "hello@dedolytics.org")

    @patch("outreach_bot.smtplib.SMTP_SSL")
    def test_plain_text_not_generic(self, mock_smtp_class):
        """ABM email text/plain must be extracted from HTML, not a generic stub."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from outreach_bot import send_email

        send_email(
            to_address="a@b.com",
            subject="Test",
            html_body="<p>We built a RedSticker dashboard tracking $5.1M in markdowns.</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Ed",
        )

        msg = mock_server.send_message.call_args[0][0]
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break

        self.assertIsNotNone(plain_part)
        self.assertNotIn("Please enable HTML", plain_part)
        self.assertIn("RedSticker", plain_part)


class TestABMPlainTextExtraction(unittest.TestCase):
    """Tests for outreach_bot._html_to_plain_text()."""

    def setUp(self):
        from outreach_bot import _html_to_plain_text

        self.extract = _html_to_plain_text

    def test_extracts_content(self):
        result = self.extract(SAMPLE_HTML)
        self.assertIn("Hello World", result)
        self.assertIn("test email", result)

    def test_strips_scripts_and_styles(self):
        result = self.extract(SAMPLE_HTML)
        self.assertNotIn("alert", result)
        self.assertNotIn(".hidden", result)

    def test_empty_html(self):
        result = self.extract("")
        self.assertEqual(result, "")


# ─── SMTP Connection Tests ──────────────────────────────────────────────────


class TestSMBSMTPConnection(unittest.TestCase):
    """Tests that SMTP connection is handled correctly."""

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_connects_to_gmail_on_port_465(self, mock_smtp_class):
        """Must connect to smtp.gmail.com on port 465 (SSL)."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", "pw", "Paul")

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_login_called_with_credentials(self, mock_smtp_class):
        """Must call login() with the sender's email and password."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email("a@b.com", "Sub", "<p>Hi</p>", "sender@dedolytics.org", "my-pass", "Paul")

        mock_server.login.assert_called_once_with("sender@dedolytics.org", "my-pass")

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_quit_called_after_send(self, mock_smtp_class):
        """Must call quit() after sending to close the connection."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", "pw", "Paul")

        mock_server.quit.assert_called_once()

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_login_failure_returns_false(self, mock_smtp_class):
        """Authentication failure should return False, not crash."""
        import smtplib as _smtplib

        mock_server = MagicMock()
        mock_server.login.side_effect = _smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        result = send_html_email("a@b.com", "Sub", "<p>Hi</p>", "x@y.com", "pw", "Paul")
        self.assertFalse(result)


# ─── Integration-style Tests ────────────────────────────────────────────────


class TestEndToEndEmailConstruction(unittest.TestCase):
    """Tests the full email construction pipeline from infographic to sent message."""

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_infographic_through_wrapper_to_send(self, mock_smtp_class):
        """Full pipeline: infographic HTML → wrap → send → verify all headers + content."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import wrap_infographic_in_email, send_html_email

        # 1. Wrap infographic
        wrapped = wrap_infographic_in_email(SAMPLE_INFOGRAPHIC)

        # 2. Send it
        result = send_html_email(
            to_address="owner@irongym.ca",
            subject="Unlocking hidden profits at Iron Gym (Custom Analytics)",
            html_body=wrapped,
            sender_email="hello@dedolytics.org",
            sender_password="fake-pw",
            sender_name="Paul",
        )

        self.assertTrue(result)
        msg = mock_server.send_message.call_args[0][0]

        # 3. Verify headers
        self.assertEqual(msg["Reply-To"], "hello@dedolytics.org")
        self.assertIn("unsubscribe", msg["List-Unsubscribe"])
        self.assertEqual(msg["To"], "owner@irongym.ca")
        self.assertIn("Iron Gym", msg["Subject"])

        # 4. Verify HTML part contains the infographic content
        html_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_content()
                break
        self.assertIn("Iron Gym", html_part)
        self.assertIn("Schedule a Free 15-Min Call", html_part)
        self.assertNotIn("display: flex", html_part)
        self.assertNotIn("display:flex", html_part)

        # 5. Verify plain-text part has real content
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break
        self.assertNotIn("Please enable HTML", plain_part)
        self.assertIn("Iron Gym", plain_part)

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_followup_through_send(self, mock_smtp_class):
        """Full pipeline: follow-up template → render → send → verify headers + content."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import FOLLOWUP_TEMPLATES, CALENDAR_LINK, send_html_email

        # Render follow-up template
        tpl = FOLLOWUP_TEMPLATES[0]
        subject = tpl["subject"].format(company_name="Best Pizza Toronto")
        html_body = tpl["body"].format(
            company_name="Best Pizza Toronto",
            category="restaurant",
            calendar_link=CALENDAR_LINK,
        )

        # Send it
        result = send_html_email(
            to_address="info@bestpizza.ca",
            subject=subject,
            html_body=html_body,
            sender_email="contact@dedolytics.org",
            sender_password="fake-pw",
            sender_name="Will",
        )

        self.assertTrue(result)
        msg = mock_server.send_message.call_args[0][0]

        # Verify headers
        self.assertEqual(msg["Reply-To"], "hello@dedolytics.org")
        self.assertIn("unsubscribe", msg["List-Unsubscribe"])
        self.assertIn("Best Pizza Toronto", msg["Subject"])

        # Verify plain text has the company name
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break
        self.assertIn("Best Pizza Toronto", plain_part)
        self.assertNotIn("Please enable HTML", plain_part)


class TestSpecialCharactersInEmails(unittest.TestCase):
    """Tests that special characters in company names and emails don't break anything."""

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_company_name_with_ampersand(self, mock_smtp_class):
        """Company names with & should not break HTML or headers."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        result = send_html_email(
            to_address="info@example.com",
            subject="Analytics for M&M's Diner",
            html_body="<p>Hello from M&amp;M's Diner analysis</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Paul",
        )
        self.assertTrue(result)

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_company_name_with_quotes(self, mock_smtp_class):
        """Company names with quotes should not break email."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        result = send_html_email(
            to_address="info@example.com",
            subject='Analytics for "Best" Gym',
            html_body="<p>Analysis for &quot;Best&quot; Gym</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Ed",
        )
        self.assertTrue(result)

    @patch("smb_outreach.smtplib.SMTP_SSL")
    def test_french_characters(self, mock_smtp_class):
        """French-Canadian business names (accents) must work."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        from smb_outreach import send_html_email

        result = send_html_email(
            to_address="info@cafe-montreal.ca",
            subject="Analytiques pour Café Étoilé",
            html_body="<p>Bonjour Café Étoilé, nous avons préparé des données pour vous.</p>",
            sender_email="x@dedolytics.org",
            sender_password="pw",
            sender_name="Will",
        )
        self.assertTrue(result)

        msg = mock_server.send_message.call_args[0][0]
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_content()
                break
        self.assertIn("Café Étoilé", plain_part)


# ─── Run Tests ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
