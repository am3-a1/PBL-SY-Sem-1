"""
FeedPulse Offline NLP Pipeline
-------------------------------
Architectural Note & Limitations:
This module provides a fast, 100% offline sentiment analysis and theme classification
pipeline suitable for local deployments and student portfolios.
- Sentiment scoring is powered by VADER (Valence Aware Dictionary and sEntiment Reasoner),
  a rule-based lexicon analyzer, augmented with hybrid star-rating weighting.
- Theme classification combines domain keyword regex matching with TF-IDF cosine similarity
  against anchor category descriptions.
- It is NOT a deep neural network or large language model (LLM). Sarcasm without low star ratings,
  highly domain-specific jargon, or mixed-topic reviews may have lower confidence.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import httpx
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import validate_slack_webhook_url

logger = logging.getLogger("feedpulse.nlp")
logging.basicConfig(level=logging.INFO)

analyzer = SentimentIntensityAnalyzer()

THEMES = [
    "Login Crash",
    "Billing & Payments",
    "Performance & Lag",
    "UI/UX",
    "General",
]

# Anchor profiles for TF-IDF cosine similarity matching
THEME_DESCRIPTIONS = {
    "Login Crash": (
        "login crash crash on startup cannot log in sign in authentication fail "
        "password reset otp verification face id touch id 2fa freeze black screen "
        "force closes immediately booted out boot loop app keeps crashing when opening"
    ),
    "Billing & Payments": (
        "billing payment credit card charge charged overcharged refund subscription "
        "cancel subscription renewal renew receipt money stolen double charge price increase "
        "in app purchase paywall restore purchases invoice payment gateway declined"
    ),
    "Performance & Lag": (
        "slow lag laggy stutter frame drops sluggish battery drain overheating phone hot "
        "high memory ram usage latency delay slow response takes forever loading infinite spinner "
        "unresponsive freezing device gets warm high cpu"
    ),
    "UI/UX": (
        "user interface ui ux design layout dark mode font size button confusing cluttered "
        "navigation hard to find gesture swipe ugly color contrast cramped view readability "
        "unintuitive awkward layout bad update visual redesign"
    ),
    "General": (
        "app software service support feedback general update feature request compliment review "
        "good job great app okay normal fine standard functionality"
    ),
}

# Domain keyword regex weights
THEME_KEYWORDS = {
    "Login Crash": [
        r"\b(login|log-in|log in|logging in)\b",
        r"\b(sign in|signing in|signin)\b",
        r"\b(crash|crashes|crashing|crashed)\b",
        r"\b(freeze|freezes|freezing|frozen)\b",
        r"\b(black screen|force close|force closed|bootloop)\b",
        r"\b(password|otp|2fa|face id|touch id|auth|authentication)\b",
    ],
    "Billing & Payments": [
        r"\b(bill|billing|billed)\b",
        r"\b(charge|charges|charged|overcharged)\b",
        r"\b(payment|payments|pay)\b",
        r"\b(refund|refunds|refunded)\b",
        r"\b(subscription|subscriptions|subscribe|unsubscribed)\b",
        r"\b(credit card|debit card|in-app purchase|iap|paywall)\b",
        r"\b(renewal|renew|receipt|invoice|stolen money)\b",
    ],
    "Performance & Lag": [
        r"\b(lag|laggy|lagging)\b",
        r"\b(slow|sluggish|slowly)\b",
        r"\b(battery drain|battery life|drains battery)\b",
        r"\b(overheat|overheating|phone gets hot|warm)\b",
        r"\b(stutter|stuttering|frame rate|fps)\b",
        r"\b(latency|delay|takes forever|unresponsive)\b",
        r"\b(ram|memory leak|cpu usage)\b",
    ],
    "UI/UX": [
        r"\b(ui|ux|user interface|interface)\b",
        r"\b(design|layout|redesign)\b",
        r"\b(dark mode|light mode|theme)\b",
        r"\b(font|readability|text size)\b",
        r"\b(navigation|gesture|button|menu|sidebar)\b",
        r"\b(cluttered|cramped|unintuitive|confusing|ugly)\b",
    ],
}

# Pre-train lightweight TF-IDF model on anchor descriptions
theme_names_ordered = list(THEME_DESCRIPTIONS.keys())
theme_corpus = [THEME_DESCRIPTIONS[t] for t in theme_names_ordered]
tfidf_vectorizer = TfidfVectorizer(stop_words="english")
theme_vectors = tfidf_vectorizer.fit_transform(theme_corpus)


def clean_review_text(text: Optional[str]) -> str:
    """Sanitizes text by stripping whitespace and removing excessive non-printable chars."""
    if not text:
        return ""
    text_str = str(text).strip()
    if text_str.lower() in ("nan", "null", "none"):
        return ""
    return text_str


def analyze_sentiment(text: str) -> Tuple[float, str]:
    """
    Computes VADER compound polarity score (-1.0 to 1.0) and assigns label.
    >= 0.05: Positive
    <= -0.05: Negative
    Else: Neutral
    """
    cleaned = clean_review_text(text)
    if not cleaned:
        return 0.0, "Neutral"

    scores = analyzer.polarity_scores(cleaned)
    compound = round(scores["compound"], 4)

    if compound >= 0.05:
        label = "Positive"
    elif compound <= -0.05:
        label = "Negative"
    else:
        label = "Neutral"

    return compound, label


def apply_rating_weight(
    sentiment_score: float,
    sentiment_label: str,
    rating: Optional[int],
) -> Tuple[float, str]:
    """
    Applies a hybrid weighting model combining star rating (1-5) and VADER text sentiment.
    - Rating 1-2: Strictly Negative, capping score to <= -0.30 (or <= -0.50 for 1-star).
    - Rating 3: Weighted towards Neutral.
    - Rating 4-5: Weighted towards Positive, overriding minor complaints or sarcasm.
    """
    if rating is None:
        return sentiment_score, sentiment_label

    try:
        r = int(rating)
    except (ValueError, TypeError):
        return sentiment_score, sentiment_label

    if r <= 1:
        # Strongly negative (1-star review, handles polite sarcasm)
        if sentiment_score >= 0.0:
            adjusted = -0.60 - round(min(0.35, sentiment_score * 0.4), 4)
        else:
            adjusted = min(-0.50, sentiment_score)
        adjusted = max(-1.0, min(-0.50, round(adjusted, 4)))
        return adjusted, "Negative"

    elif r == 2:
        # Clearly negative (2-star review)
        if sentiment_score >= 0.0:
            adjusted = -0.35 - round(min(0.25, sentiment_score * 0.3), 4)
        else:
            adjusted = min(-0.30, sentiment_score)
        adjusted = max(-1.0, min(-0.30, round(adjusted, 4)))
        return adjusted, "Negative"

    elif r == 3:
        # Neutral center (3-star review)
        if abs(sentiment_score) <= 0.40:
            adjusted = round(sentiment_score * 0.25, 4)
            return adjusted, "Neutral"
        elif sentiment_score > 0.40:
            if sentiment_score >= 0.65:
                return round(sentiment_score * 0.7, 4), "Positive"
            return round(sentiment_score * 0.3, 4), "Neutral"
        else:
            if sentiment_score <= -0.65:
                return round(sentiment_score * 0.7, 4), "Negative"
            return round(sentiment_score * 0.3, 4), "Neutral"

    elif r == 4:
        # Mostly positive (4-star review)
        if sentiment_score <= -0.35:
            adjusted = round(sentiment_score * 0.4, 4)
            label = "Negative" if adjusted <= -0.20 else "Neutral"
            return adjusted, label
        elif sentiment_score < 0.05:
            adjusted = max(0.15, round(sentiment_score + 0.30, 4))
            return min(1.0, adjusted), "Positive"
        else:
            adjusted = max(sentiment_score, 0.25)
            return min(1.0, round(adjusted, 4)), "Positive"

    elif r >= 5:
        # Strongly positive (5-star review)
        if sentiment_score < 0.30:
            adjusted = max(0.40, round(0.50 + sentiment_score * 0.3, 4))
        else:
            adjusted = max(sentiment_score, 0.50)
        adjusted = max(0.30, min(1.0, round(adjusted, 4)))
        return adjusted, "Positive"

    return sentiment_score, sentiment_label


def classify_theme(text: str) -> Tuple[str, float]:
    """
    Combines direct keyword hits with TF-IDF cosine similarity against anchor themes.
    Returns:
        (category_theme, confidence_score) where confidence is between 0.0 and 1.0.
    """
    cleaned = clean_review_text(text)
    if not cleaned:
        return "General", 0.5

    lower_text = cleaned.lower()

    # Step 1: Check direct keyword regex matches with scores
    keyword_scores = {theme: 0.0 for theme in THEMES}
    has_keyword_match = False
    for theme, patterns in THEME_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, lower_text):
                keyword_scores[theme] += 2.0
                has_keyword_match = True

    # Step 2: TF-IDF similarity score
    tfidf_max_sim = 0.0
    try:
        review_vec = tfidf_vectorizer.transform([cleaned])
        similarities = cosine_similarity(review_vec, theme_vectors)[0]
        for idx, theme_name in enumerate(theme_names_ordered):
            sim = float(similarities[idx])
            keyword_scores[theme_name] += sim * 2.5
            if sim > tfidf_max_sim:
                tfidf_max_sim = sim
    except Exception as e:
        logger.warning(f"TF-IDF similarity failed: {e}")

    # Determine best theme
    best_theme = max(keyword_scores.keys(), key=lambda k: keyword_scores[k])
    best_score = keyword_scores[best_theme]

    if best_score > 0.8:
        # Calculate normalized confidence
        confidence = min(0.98, max(0.55, (best_score / 4.5) * 0.8 + 0.2))
        return best_theme, round(confidence, 2)

    return "General", 0.50


def analyze_review_content(content: str, rating: Optional[int] = None) -> Dict[str, Any]:
    """
    Full pipeline for a single review: sentiment scoring, rating weighting,
    and theme classification with confidence score.
    """
    sentiment_score, sentiment_label = analyze_sentiment(content)
    if rating is not None:
        sentiment_score, sentiment_label = apply_rating_weight(sentiment_score, sentiment_label, rating)
    theme, confidence = classify_theme(content)
    return {
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "category_theme": theme,
        "theme_confidence": confidence,
    }


def build_slack_blocks(
    title: str,
    message: str,
    metrics: Optional[Dict[str, Any]] = None,
    sample_review: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Builds a Slack Block Kit JSON payload.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 {title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": message,
            },
        },
    ]

    if metrics:
        fields = []
        for key, val in metrics.items():
            fields.append({"type": "mrkdwn", "text": f"*{key}:*\\n{val}"})
        blocks.append({"type": "section", "fields": fields})

    if sample_review:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"> *Critical User Quote:*\\n> \\\"{sample_review}\\\"",
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "FeedPulse Automated Feedback Triage System • Local NLP Sentinel",
                }
            ],
        }
    )

    return {"text": f"FeedPulse Alert: {title}", "blocks": blocks}


async def dispatch_slack_alert(
    webhook_url: Optional[str],
    title: str,
    message: str,
    metrics: Optional[Dict[str, Any]] = None,
    sample_review: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends payload to Slack Incoming Webhook, or runs in sandbox mode if no valid webhook URL.
    Enforces strict URL parsing, HTTPS scheme, hooks.slack.com host, and path validation.
    """
    payload = build_slack_blocks(title, message, metrics, sample_review)

    # Sandbox mode if no webhook URL provided or URL is invalid
    if not webhook_url or not webhook_url.strip() or not validate_slack_webhook_url(webhook_url):
        logger.info(f"[SANDBOX SLACK ALERT] Triggered in sandbox simulation: {title}")
        return {
            "status": "sandbox_success",
            "is_sandbox": True,
            "message": "Slack alert simulated successfully (Sandbox Mode - No active or valid Slack webhook provided).",
            "payload": payload,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url.strip(), json=payload)
            if response.status_code == 200:
                logger.info(f"Slack notification successfully dispatched for: {title}")
                return {
                    "status": "delivered",
                    "is_sandbox": False,
                    "message": "Slack notification successfully posted to channel.",
                    "payload": payload,
                }
            else:
                logger.warning(f"Slack API returned status {response.status_code}")
                return {
                    "status": "error",
                    "is_sandbox": False,
                    "message": f"Slack API returned status {response.status_code}: {response.text[:200]}",
                    "payload": payload,
                }
    except Exception as exc:
        logger.error(f"Failed to post to Slack webhook: {type(exc).__name__}")
        return {
            "status": "error",
            "is_sandbox": False,
            "message": f"Network exception when posting to Slack: {str(exc)[:200]}",
            "payload": payload,
        }
