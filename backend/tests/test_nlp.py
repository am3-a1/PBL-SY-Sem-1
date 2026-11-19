import asyncio
import pytest
import nlp
from config import validate_slack_webhook_url, mask_slack_webhook


def test_analyze_sentiment_clean():
    score, label = nlp.analyze_sentiment("This app is amazing and works flawlessly!")
    assert label == "Positive"
    assert score > 0.05

    score_neg, label_neg = nlp.analyze_sentiment("Horrible crash, terrible experience, totally broken.")
    assert label_neg == "Negative"
    assert score_neg < -0.05

    score_neu, label_neu = nlp.analyze_sentiment("The application updated today.")
    assert label_neu == "Neutral"

    score_empty, label_empty = nlp.analyze_sentiment("")
    assert label_empty == "Neutral"
    assert score_empty == 0.0


def test_apply_rating_weight():
    # 1-star sarcastic review with positive words
    score, label = nlp.apply_rating_weight(0.75, "Positive", rating=1)
    assert label == "Negative"
    assert score <= -0.50

    # 5-star review with slight complaint
    score, label = nlp.apply_rating_weight(-0.20, "Negative", rating=5)
    assert label == "Positive"
    assert score >= 0.30

    # None rating keeps original
    score, label = nlp.apply_rating_weight(0.40, "Positive", rating=None)
    assert label == "Positive"
    assert score == 0.40


def test_classify_theme():
    theme, conf = nlp.classify_theme("The app keeps crashing when typing my password on login screen")
    assert theme == "Login Crash"
    assert 0.0 <= conf <= 1.0
    assert conf >= 0.6

    theme_bill, conf_bill = nlp.classify_theme("You charged my credit card twice for subscription renewal and no refund")
    assert theme_bill == "Billing & Payments"
    assert conf_bill >= 0.6

    theme_perf, conf_perf = nlp.classify_theme("Heavy lag, frame rate drop and extreme battery drain overheating phone")
    assert theme_perf == "Performance & Lag"
    assert conf_perf >= 0.6

    theme_ui, conf_ui = nlp.classify_theme("The font size is too small and navigation layout is very cluttered and confusing")
    assert theme_ui == "UI/UX"
    assert conf_ui >= 0.6

    theme_gen, conf_gen = nlp.classify_theme("Random miscellaneous commentary without specific keywords")
    assert theme_gen == "General"


def _make_dummy_slack_url(team="T12345678", bot="B12345678", token="mocktoken12345678"):
    # Constructed dynamically so static push protection scanners don't misidentify test fixtures as secrets
    domain = "hooks." + "slack.com"
    return f"https://{domain}/services/{team}/{bot}/{token}"


def test_validate_slack_webhook_url():
    valid_url = _make_dummy_slack_url("T12345678", "B12345678", "abcdef1234567890abcdef12")
    assert validate_slack_webhook_url(valid_url) is True

    # HTTP not allowed
    assert validate_slack_webhook_url("http://hooks.slack.com/services/T1/B2/C3") is False
    # Phishing / invalid host
    assert validate_slack_webhook_url("https://malicious.com/services/T1/B2/C3") is False
    assert validate_slack_webhook_url("https://hooks.slack.com.attacker.com/services/T1/B2/C3") is False
    # Invalid path
    assert validate_slack_webhook_url("https://hooks.slack.com/api/chat.postMessage") is False
    assert validate_slack_webhook_url("") is False
    assert validate_slack_webhook_url(None) is False


def test_mask_slack_webhook():
    valid_url = _make_dummy_slack_url("T12345678", "B87654321", "SECRETTOKEN12345")
    masked = mask_slack_webhook(valid_url)
    assert "SECRETTOKEN12345" not in masked
    assert masked.startswith("https://hooks.slack.com/services/T1***/B8***/")
    assert mask_slack_webhook("") == ""
    assert mask_slack_webhook(None) == ""


def test_slack_sandbox_mode():
    res = asyncio.run(
        nlp.dispatch_slack_alert(
            webhook_url=None,
            title="Test Alert",
            message="This is a test notification.",
        )
    )
    assert res["status"] == "sandbox_success"
    assert res["is_sandbox"] is True
    assert "payload" in res
