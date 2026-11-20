"""
FeedPulse Time-Based Negative Review Anomaly Detection Engine
-----------------------------------------------------------
Implements statistical Z-score anomaly detection over sliding 1-hour time windows
using stored review timestamps.

Calculation:
    Z = (current_count - historical_mean) / historical_standard_deviation

Handles:
- Insufficient historical data (< 3 historical windows or small sample size)
- Zero standard deviation (historical variance = 0)
- Empty time windows (0 negative reviews)
- Invalid or missing timestamps
- Repeated alert generation for the same anomaly window
- Timezone consistency (strict UTC)
- Small datasets where statistical conclusions are unreliable
"""

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

import nlp
from config import settings
from models import Review, AlertConfig, AnomalyReport

logger = logging.getLogger("feedpulse.anomaly")

# In-memory registry to prevent duplicate alerts for the same anomaly window
_dispatched_alert_signatures: Set[str] = set()


def reset_dispatched_alerts() -> None:
    """Clears dispatched alert cache (useful for automated testing)."""
    global _dispatched_alert_signatures
    _dispatched_alert_signatures.clear()


def parse_review_timestamp(raw_dt: Any) -> Optional[datetime]:
    """
    Safely parses or normalizes review timestamps to naive UTC datetime.
    Returns None if timestamp is missing or malformed.
    """
    if raw_dt is None:
        return None
    if isinstance(raw_dt, datetime):
        # Normalize timezone aware to naive UTC
        if raw_dt.tzinfo is not None:
            return raw_dt.astimezone(timezone.utc).replace(tzinfo=None)
        return raw_dt
    if isinstance(raw_dt, str):
        cleaned = raw_dt.strip()
        if not cleaned:
            return None
        try:
            iso_candidate = cleaned.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_candidate)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, TypeError):
            pass
        # Try common datetime string formats
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt
            except ValueError:
                continue
    return None


def calculate_z_score(
    current_count: int,
    historical_counts: List[int],
    threshold: float = 2.5,
    min_spike_volume: int = 2,
) -> Tuple[bool, Optional[float], Optional[float], Optional[float], str, str]:
    """
    Computes statistical Z-score for the current count against historical counts.

    Returns:
        (is_anomaly, z_score, historical_mean, historical_std, severity, reason)
    """
    h_len = len(historical_counts)
    if h_len < 3:
        return (
            False,
            None,
            None,
            None,
            "NORMAL",
            f"Insufficient historical data: {h_len} historical windows available (minimum 3 required).",
        )

    # Calculate Mean
    mean = sum(historical_counts) / h_len

    # Calculate Sample Variance and Standard Deviation
    variance = sum((c - mean) ** 2 for c in historical_counts) / (h_len - 1)
    std = math.sqrt(variance)

    # Edge Case: Zero Standard Deviation (All historical counts are identical)
    if std == 0.0:
        if current_count <= round(mean):
            return (
                False,
                0.0,
                round(mean, 2),
                0.0,
                "NORMAL",
                "Current negative review volume is consistent with flat historical baseline.",
            )
        else:
            diff = current_count - mean
            if diff >= 3:
                # Significant volume surge over a flat zero-variance baseline
                return (
                    True,
                    999.0,
                    round(mean, 2),
                    0.0,
                    "CRITICAL",
                    f"Anomalous spike of {current_count} negative reviews detected above flat zero-variance baseline.",
                )
            else:
                return (
                    False,
                    None,
                    round(mean, 2),
                    0.0,
                    "NORMAL",
                    "Small volume increase with zero historical variance; statistically inconclusive.",
                )

    # Calculate standard Z-Score
    z = (current_count - mean) / std
    z_rounded = round(z, 2)

    if z >= threshold and current_count >= min_spike_volume:
        severity = "CRITICAL" if z >= (threshold + 1.0) else "HIGH"
        return (
            True,
            z_rounded,
            round(mean, 2),
            round(std, 2),
            severity,
            f"Statistical anomaly detected: Current volume ({current_count}) exceeds baseline (mean={mean:.2f}, std={std:.2f}) with Z-score {z_rounded:.2f} >= threshold {threshold:.1f}.",
        )
    else:
        return (
            False,
            z_rounded,
            round(mean, 2),
            round(std, 2),
            "NORMAL",
            f"Z-score {z_rounded:.2f} is within normal baseline threshold ({threshold:.1f}).",
        )


def detect_negative_review_anomalies(
    reviews: List[Review],
    eval_time: Optional[datetime] = None,
    threshold: Optional[float] = None,
    window_hours: int = 1,
    baseline_hours: int = 24,
    alert_config: Optional[AlertConfig] = None,
    dispatch_slack: bool = False,
) -> AnomalyReport:
    """
    Evaluates stored reviews for negative sentiment anomalies over a sliding 1-hour window.
    """
    effective_threshold = (
        threshold
        if threshold is not None
        else getattr(settings, "Z_SCORE_THRESHOLD", 2.5)
    )

    # Filter reviews with valid timestamps
    valid_reviews: List[Tuple[Review, datetime]] = []
    for r in reviews:
        parsed_dt = parse_review_timestamp(r.created_at)
        if parsed_dt is not None:
            valid_reviews.append((r, parsed_dt))

    if not valid_reviews:
        return AnomalyReport(
            is_anomaly=False,
            z_score=None,
            threshold=effective_threshold,
            current_negative_count=0,
            current_total_count=0,
            historical_mean=None,
            historical_std=None,
            historical_windows_count=0,
            has_sufficient_data=False,
            triggering_theme=None,
            representative_review=None,
            time_window="Last 1 Hour",
            severity="NORMAL",
            reason="No reviews with valid timestamps available for anomaly detection.",
            alert_triggered=False,
        )

    # Determine evaluation end time
    if eval_time is None:
        eval_time = max(dt for _, dt in valid_reviews)
    else:
        eval_time = parse_review_timestamp(eval_time) or max(dt for _, dt in valid_reviews)

    window_delta = timedelta(hours=window_hours)
    current_window_start = eval_time - window_delta
    current_window_end = eval_time

    # Separate current window reviews from historical
    current_reviews: List[Review] = []
    historical_reviews: List[Tuple[Review, datetime]] = []

    baseline_start = eval_time - timedelta(hours=baseline_hours + window_hours)

    for rev, dt in valid_reviews:
        if current_window_start <= dt <= current_window_end:
            current_reviews.append(rev)
        elif baseline_start <= dt < current_window_start:
            historical_reviews.append((rev, dt))

    # Current window counts
    current_total = len(current_reviews)
    current_neg_reviews = [r for r in current_reviews if r.sentiment_label == "Negative"]
    current_negative_count = len(current_neg_reviews)

    # Partition historical window into 1-hour slots
    historical_counts: List[int] = []
    num_windows = max(3, baseline_hours)

    for i in range(num_windows):
        w_start = current_window_start - timedelta(hours=i + 1)
        w_end = current_window_start - timedelta(hours=i)
        count_in_w = sum(1 for _, dt in historical_reviews if w_start <= dt < w_end)
        historical_counts.append(count_in_w)

    # Data sufficiency check
    has_sufficient_data = len(valid_reviews) >= 3 and len(historical_reviews) >= 2

    if not has_sufficient_data:
        return AnomalyReport(
            is_anomaly=False,
            z_score=None,
            threshold=effective_threshold,
            current_negative_count=current_negative_count,
            current_total_count=current_total,
            historical_mean=None,
            historical_std=None,
            historical_windows_count=len(historical_counts),
            has_sufficient_data=False,
            triggering_theme=None,
            representative_review=None,
            time_window=f"{current_window_start.strftime('%H:%M')} - {current_window_end.strftime('%H:%M UTC')}",
            severity="NORMAL",
            reason="Insufficient historical data to establish a reliable baseline (requires at least 3 reviews and prior windows).",
            alert_triggered=False,
        )

    # Compute Z-score
    is_anomaly, z_score, hist_mean, hist_std, severity, reason = calculate_z_score(
        current_count=current_negative_count,
        historical_counts=historical_counts,
        threshold=effective_threshold,
    )

    # Identify triggering theme in current negative reviews
    triggering_theme: Optional[str] = None
    representative_review: Optional[str] = None

    if current_neg_reviews:
        theme_counts: Dict[str, int] = {}
        for r in current_neg_reviews:
            theme_counts[r.category_theme] = theme_counts.get(r.category_theme, 0) + 1
        triggering_theme = max(theme_counts.keys(), key=lambda k: theme_counts[k])

        # Pick most critical negative review from triggering theme (lowest sentiment score)
        theme_negatives = [r for r in current_neg_reviews if r.category_theme == triggering_theme]
        target_pool = theme_negatives if theme_negatives else current_neg_reviews
        sorted_by_polarity = sorted(target_pool, key=lambda r: (r.sentiment_score, -(r.id or 0)))
        representative_review = sorted_by_polarity[0].content

    # Duplicate alert prevention key
    window_key = f"{current_window_start.strftime('%Y%m%d%H%M')}_{triggering_theme or 'General'}_{current_negative_count}_{effective_threshold}"

    alert_dispatched = False
    alert_details = None

    if is_anomaly and dispatch_slack and alert_config and alert_config.is_enabled:
        if window_key not in _dispatched_alert_signatures:
            _dispatched_alert_signatures.add(window_key)
            alert_dispatched = True

            # Prepare Slack alert
            title = f"Time-Series Anomaly: Surge in {triggering_theme or 'Negative Reviews'}"
            message = (
                f"Statistical anomaly detector flagged a negative feedback surge! "
                f"*{current_negative_count}* negative reviews in the last hour "
                f"(Z-Score: *{z_score}*, Baseline Mean: *{hist_mean}*, Threshold: *{effective_threshold}*)."
            )
            import asyncio
            try:
                alert_details = asyncio.run(
                    nlp.dispatch_slack_alert(
                        webhook_url=alert_config.slack_webhook_url,
                        title=title,
                        message=message,
                        sample_review=representative_review,
                        alert_type="Time-Series Anomaly (Z-Score)",
                        severity=severity,
                        theme=triggering_theme,
                        affected_reviews=current_negative_count,
                        negative_pct=round((current_negative_count / current_total * 100), 1) if current_total > 0 else 100.0,
                        time_window=f"{current_window_start.strftime('%Y-%m-%d %H:%M')} to {current_window_end.strftime('%H:%M UTC')}",
                    )
                )
            except Exception as e:
                logger.error(f"Failed to dispatch anomaly Slack alert: {e}")
        else:
            reason += " (Alert already dispatched for this anomaly window)."

    return AnomalyReport(
        is_anomaly=is_anomaly,
        z_score=z_score,
        threshold=effective_threshold,
        current_negative_count=current_negative_count,
        current_total_count=current_total,
        historical_mean=hist_mean,
        historical_std=hist_std,
        historical_windows_count=len(historical_counts),
        has_sufficient_data=has_sufficient_data,
        triggering_theme=triggering_theme,
        representative_review=representative_review,
        time_window=f"{current_window_start.strftime('%Y-%m-%d %H:%M')} - {current_window_end.strftime('%H:%M UTC')}",
        severity=severity,
        reason=reason,
        alert_triggered=alert_dispatched,
        alert_details=alert_details,
    )
