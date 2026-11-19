import os
import io
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

import database
from database import engine, get_db
import models
from models import (
    Review,
    AlertConfig,
    Theme,
    ReviewResponse,
    ReviewStatusUpdate,
    AlertConfigResponse,
    AlertConfigUpdate,
    TestAlertRequest,
    AnalyticsSummary,
    AnalyticsTimelinePoint,
    ThemeResponse,
    ThemeCreate,
    ThemeUpdate,
    ThemeEscalateResponse,
)
import nlp
import seed_data

# Initialize DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FeedPulse API",
    description="Multi-Channel App Review & Feedback Triage Dashboard Backend",
    version="1.0.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_THEMES_METADATA = [
    {
        "name": "Login Crash",
        "description": "Authentication failures, crashes on launch, session termination, biometric login issues",
        "owner_team": "Auth Squad",
        "jira_component_id": "AUTH-CRASH",
    },
    {
        "name": "Billing & Payments",
        "description": "In-app purchases, subscriptions, double charges, refunds, receipts",
        "owner_team": "Finance Squad",
        "jira_component_id": "FIN-BILLING",
    },
    {
        "name": "Performance & Lag",
        "description": "Frame drops, latency, memory leaks, thermal throttling, loading spinners",
        "owner_team": "Core Platform",
        "jira_component_id": "PLAT-PERF",
    },
    {
        "name": "UI/UX",
        "description": "Layout confusion, gesture navigation, contrast, readability, visual styling",
        "owner_team": "Design Squad",
        "jira_component_id": "UIUX-EXP",
    },
    {
        "name": "General",
        "description": "General feedback, mixed commentary, and unclassified feedback",
        "owner_team": "Customer Support",
        "jira_component_id": "CS-GENERAL",
    },
]


def init_default_themes(db: Session):
    for item in DEFAULT_THEMES_METADATA:
        theme = db.query(Theme).filter(Theme.name == item["name"]).first()
        if not theme:
            theme = Theme(
                name=item["name"],
                description=item["description"],
                owner_team=item["owner_team"],
                jira_component_id=item["jira_component_id"],
            )
            db.add(theme)
    db.commit()


def get_or_create_alert_config(db: Session) -> AlertConfig:
    config = db.query(AlertConfig).first()
    if not config:
        default_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
        default_threshold = float(os.getenv("NEGATIVE_THRESHOLD_PCT", "30.0"))
        config = AlertConfig(
            slack_webhook_url=default_webhook,
            negative_threshold_pct=default_threshold,
            is_enabled=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# ---------------------------------------------------------
# INGESTION & SEEDING ROUTES
# ---------------------------------------------------------

@app.post("/api/reviews/seed", summary="Populate database with 65+ realistic multi-channel mock reviews")
async def seed_reviews(db: Session = Depends(get_db)):
    # Delete existing reviews to provide clean state or replenish
    db.query(Review).delete()
    db.commit()

    raw_items = seed_data.generate_seed_reviews()
    created_reviews: List[Review] = []

    negative_count = 0
    for item in raw_items:
        rating_val = item.get("rating")
        nlp_res = nlp.analyze_review_content(item["content"], rating=rating_val)
        if nlp_res["sentiment_label"] == "Negative":
            negative_count += 1

        review_obj = Review(
            source=item["source"],
            author=item["author"],
            rating=rating_val,
            content=item["content"],
            created_at=item["created_at"],
            sentiment_score=nlp_res["sentiment_score"],
            sentiment_label=nlp_res["sentiment_label"],
            category_theme=nlp_res["category_theme"],
            status=item["status"],
        )
        created_reviews.append(review_obj)

    db.bulk_save_objects(created_reviews)
    db.commit()

    # Check alert spike condition
    total = len(created_reviews)
    neg_pct = (negative_count / total * 100) if total > 0 else 0
    config = get_or_create_alert_config(db)

    alert_triggered = False
    alert_result = None

    if config.is_enabled and neg_pct >= config.negative_threshold_pct:
        alert_triggered = True
        sample_quote = created_reviews[0].content if created_reviews else "No feedback content"
        alert_result = await nlp.dispatch_slack_alert(
            webhook_url=config.slack_webhook_url,
            title="Spike in Negative App Reviews Detected!",
            message=f"Negative feedback spike alert triggered during dataset ingestion. *{neg_pct:.1f}%* of reviews were flagged as Negative (Threshold: *{config.negative_threshold_pct:.1f}%*).",
            metrics={
                "Total Ingested": str(total),
                "Negative Reviews": f"{negative_count} ({neg_pct:.1f}%)",
                "Alert Threshold": f"{config.negative_threshold_pct:.1f}%",
                "Primary Spike Channel": "Multi-Channel Seed",
            },
            sample_review=sample_quote,
        )

    return {
        "message": f"Successfully seeded {total} reviews.",
        "total_seeded": total,
        "negative_percentage": round(neg_pct, 1),
        "alert_triggered": alert_triggered,
        "alert_details": alert_result,
    }


@app.post("/api/reviews/upload", summary="Upload CSV file of user feedback")
async def upload_reviews_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a CSV file.",
        )

    contents = await file.read()
    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse CSV file: {str(exc)}",
        )

    required_cols = {"content"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain at least a 'content' column. Found columns: {list(df.columns)}",
        )

    valid_sources = {"App Store", "Google Play", "Reddit", "Discord"}
    added_reviews = []
    negative_count = 0

    for _, row in df.iterrows():
        content_text = str(row.get("content", "")).strip()
        if not content_text or content_text.lower() == "nan":
            continue

        raw_source = str(row.get("source", "App Store")).strip()
        source = raw_source if raw_source in valid_sources else "App Store"
        author = str(row.get("author", "Anonymous User")).strip()
        if not author or author.lower() == "nan":
            author = "Anonymous User"

        raw_rating = row.get("rating")
        rating = None
        if pd.notna(raw_rating):
            try:
                rating = int(float(raw_rating))
                rating = max(1, min(5, rating))
            except (ValueError, TypeError):
                rating = None

        nlp_res = nlp.analyze_review_content(content_text, rating=rating)
        if nlp_res["sentiment_label"] == "Negative":
            negative_count += 1

        review_obj = Review(
            source=source,
            author=author,
            rating=rating,
            content=content_text,
            created_at=datetime.utcnow(),
            sentiment_score=nlp_res["sentiment_score"],
            sentiment_label=nlp_res["sentiment_label"],
            category_theme=nlp_res["category_theme"],
            status="New",
        )
        added_reviews.append(review_obj)

    if added_reviews:
        db.bulk_save_objects(added_reviews)
        db.commit()

    total = len(added_reviews)
    neg_pct = (negative_count / total * 100) if total > 0 else 0
    config = get_or_create_alert_config(db)

    alert_triggered = False
    alert_result = None

    if config.is_enabled and total > 0 and neg_pct >= config.negative_threshold_pct:
        alert_triggered = True
        sample_quote = added_reviews[0].content if added_reviews else "No feedback"
        alert_result = await nlp.dispatch_slack_alert(
            webhook_url=config.slack_webhook_url,
            title="Spike in Negative Reviews (CSV Ingestion Batch)!",
            message=f"Negative feedback spike alert triggered during CSV upload. *{neg_pct:.1f}%* of newly uploaded reviews were flagged as Negative (Threshold: *{config.negative_threshold_pct:.1f}%*).",
            metrics={
                "Batch Size": str(total),
                "Negative Reviews": f"{negative_count} ({neg_pct:.1f}%)",
                "Alert Threshold": f"{config.negative_threshold_pct:.1f}%",
                "File Ingested": file.filename,
            },
            sample_review=sample_quote,
        )

    return {
        "message": f"Successfully ingested {total} reviews from CSV.",
        "total_ingested": total,
        "negative_percentage": round(neg_pct, 1),
        "alert_triggered": alert_triggered,
        "alert_details": alert_result,
    }


# ---------------------------------------------------------
# REVIEWS & TRIAGE ROUTES
# ---------------------------------------------------------

@app.get("/api/reviews", response_model=List[ReviewResponse], summary="Get reviews with filters")
def get_reviews(
    source: Optional[str] = Query(None, description="App Store, Google Play, Reddit, Discord"),
    sentiment: Optional[str] = Query(None, description="Positive, Neutral, Negative"),
    theme: Optional[str] = Query(None, description="Login Crash, Billing & Payments, etc."),
    status: Optional[str] = Query(None, description="New, Investigating, Escalated, Resolved"),
    search: Optional[str] = Query(None, description="Keyword search in content or author"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(Review)

    if source and source.strip() and source.lower() != "all":
        query = query.filter(Review.source == source.strip())
    if sentiment and sentiment.strip() and sentiment.lower() != "all":
        query = query.filter(Review.sentiment_label == sentiment.strip())
    if theme and theme.strip() and theme.lower() != "all":
        query = query.filter(Review.category_theme == theme.strip())
    if status and status.strip() and status.lower() != "all":
        query = query.filter(Review.status == status.strip())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((Review.content.ilike(term)) | (Review.author.ilike(term)))

    return query.order_by(desc(Review.created_at)).limit(limit).all()


@app.patch("/api/reviews/{review_id}/status", response_model=ReviewResponse, summary="Update review Kanban status")
def update_review_status(
    review_id: int,
    payload: ReviewStatusUpdate,
    db: Session = Depends(get_db),
):
    allowed_statuses = ["New", "Investigating", "Escalated", "Resolved"]
    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Must be one of {allowed_statuses}",
        )

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.status = payload.status
    db.commit()
    db.refresh(review)
    return review


@app.delete("/api/reviews/{review_id}", summary="Delete single review")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
    return {"message": f"Review {review_id} deleted"}


@app.delete("/api/reviews", summary="Clear all reviews")
def clear_all_reviews(db: Session = Depends(get_db)):
    count = db.query(Review).delete()
    db.commit()
    return {"message": f"Cleared {count} reviews"}


# ---------------------------------------------------------
# THEMES & WORKFLOW ROUTES
# ---------------------------------------------------------

@app.get("/api/themes", response_model=List[ThemeResponse], summary="List all themes with review metrics")
def list_themes(db: Session = Depends(get_db)):
    init_default_themes(db)
    themes = db.query(Theme).all()

    res = []
    for t in themes:
        rev_count = db.query(func.count(Review.id)).filter(Review.category_theme == t.name).scalar() or 0
        neg_count = (
            db.query(func.count(Review.id))
            .filter(Review.category_theme == t.name, Review.sentiment_label == "Negative")
            .scalar()
            or 0
        )
        esc_count = (
            db.query(func.count(Review.id))
            .filter(Review.category_theme == t.name, Review.status == "Escalated")
            .scalar()
            or 0
        )

        res.append(
            ThemeResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                owner_team=t.owner_team,
                jira_component_id=t.jira_component_id,
                created_at=t.created_at,
                review_count=rev_count,
                negative_count=neg_count,
                escalated_count=esc_count,
            )
        )
    return res


@app.get("/api/themes/{theme_id}", response_model=ThemeResponse, summary="Get single theme details")
def get_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    rev_count = db.query(func.count(Review.id)).filter(Review.category_theme == theme.name).scalar() or 0
    neg_count = (
        db.query(func.count(Review.id))
        .filter(Review.category_theme == theme.name, Review.sentiment_label == "Negative")
        .scalar()
        or 0
    )
    esc_count = (
        db.query(func.count(Review.id))
        .filter(Review.category_theme == theme.name, Review.status == "Escalated")
        .scalar()
        or 0
    )

    return ThemeResponse(
        id=theme.id,
        name=theme.name,
        description=theme.description,
        owner_team=theme.owner_team,
        jira_component_id=theme.jira_component_id,
        created_at=theme.created_at,
        review_count=rev_count,
        negative_count=neg_count,
        escalated_count=esc_count,
    )


@app.patch("/api/themes/{theme_id}", response_model=ThemeResponse, summary="Update theme metadata")
def update_theme(theme_id: int, payload: ThemeUpdate, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    if payload.description is not None:
        theme.description = payload.description.strip()
    if payload.owner_team is not None:
        theme.owner_team = payload.owner_team.strip()
    if payload.jira_component_id is not None:
        theme.jira_component_id = payload.jira_component_id.strip()

    db.commit()
    db.refresh(theme)

    rev_count = db.query(func.count(Review.id)).filter(Review.category_theme == theme.name).scalar() or 0
    neg_count = (
        db.query(func.count(Review.id))
        .filter(Review.category_theme == theme.name, Review.sentiment_label == "Negative")
        .scalar()
        or 0
    )
    esc_count = (
        db.query(func.count(Review.id))
        .filter(Review.category_theme == theme.name, Review.status == "Escalated")
        .scalar()
        or 0
    )

    return ThemeResponse(
        id=theme.id,
        name=theme.name,
        description=theme.description,
        owner_team=theme.owner_team,
        jira_component_id=theme.jira_component_id,
        created_at=theme.created_at,
        review_count=rev_count,
        negative_count=neg_count,
        escalated_count=esc_count,
    )


@app.post("/api/themes/{theme_id}/escalate", response_model=ThemeEscalateResponse, summary="Bulk escalate all open reviews in this theme")
def bulk_escalate_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    open_reviews = (
        db.query(Review)
        .filter(Review.category_theme == theme.name, Review.status.in_(["New", "Investigating"]))
        .all()
    )

    escalated_count = len(open_reviews)
    for rev in open_reviews:
        rev.status = "Escalated"

    db.commit()
    return ThemeEscalateResponse(
        theme_name=theme.name,
        escalated_count=escalated_count,
        message=f"Successfully escalated {escalated_count} reviews in '{theme.name}' to Escalated.",
    )


# ---------------------------------------------------------
# ANALYTICS ENDPOINTS
# ---------------------------------------------------------

@app.get("/api/analytics/summary", response_model=AnalyticsSummary, summary="Get aggregate analytics")
def get_analytics_summary(db: Session = Depends(get_db)):
    reviews = db.query(Review).all()
    total = len(reviews)

    if total == 0:
        return AnalyticsSummary(
            total_reviews=0,
            avg_sentiment=0.0,
            sentiment_counts={"Positive": 0, "Neutral": 0, "Negative": 0},
            sentiment_percentages={"Positive": 0.0, "Neutral": 0.0, "Negative": 0.0},
            channel_counts={"App Store": 0, "Google Play": 0, "Reddit": 0, "Discord": 0},
            channel_sentiment={"App Store": 0.0, "Google Play": 0.0, "Reddit": 0.0, "Discord": 0.0},
            theme_counts={t: 0 for t in nlp.THEMES},
            status_counts={"New": 0, "Investigating": 0, "Escalated": 0, "Resolved": 0},
            critical_negative_count=0,
            churn_risk_index=0.0,
            sentiment_timeline=[],
        )

    total_sentiment = sum(r.sentiment_score for r in reviews)
    avg_sentiment = round(total_sentiment / total, 3)

    sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    status_counts = {"New": 0, "Investigating": 0, "Escalated": 0, "Resolved": 0}
    theme_counts = {t: 0 for t in nlp.THEMES}
    channel_counts = {"App Store": 0, "Google Play": 0, "Reddit": 0, "Discord": 0}
    channel_sentiment_sum = {"App Store": 0.0, "Google Play": 0.0, "Reddit": 0.0, "Discord": 0.0}

    critical_negative_count = 0
    severe_churn_factors = 0

    # Daily aggregation for timeline
    daily_groups: Dict[str, Dict[str, Any]] = {}

    for r in reviews:
        # Sentiment
        if r.sentiment_label in sentiment_counts:
            sentiment_counts[r.sentiment_label] += 1
        # Status
        if r.status in status_counts:
            status_counts[r.status] += 1
        # Theme
        theme_counts[r.category_theme] = theme_counts.get(r.category_theme, 0) + 1
        # Channel
        if r.source in channel_counts:
            channel_counts[r.source] += 1
            channel_sentiment_sum[r.source] += r.sentiment_score

        # Critical issues: rating <= 2 or Negative sentiment in New/Escalated
        is_critical = (r.rating is not None and r.rating <= 2) or (r.sentiment_label == "Negative")
        if is_critical and r.status in ["New", "Escalated"]:
            critical_negative_count += 1

        # Churn factor: critical login crashes or billing issues
        if r.category_theme in ["Login Crash", "Billing & Payments"] and r.sentiment_label == "Negative":
            severe_churn_factors += 1

        # Timeline grouping by date
        date_str = r.created_at.strftime("%Y-%m-%d")
        if date_str not in daily_groups:
            daily_groups[date_str] = {
                "total": 0,
                "sentiment_sum": 0.0,
                "negative": 0,
                "positive": 0,
            }
        daily_groups[date_str]["total"] += 1
        daily_groups[date_str]["sentiment_sum"] += r.sentiment_score
        if r.sentiment_label == "Negative":
            daily_groups[date_str]["negative"] += 1
        elif r.sentiment_label == "Positive":
            daily_groups[date_str]["positive"] += 1

    # Calculate channel sentiment averages
    channel_sentiment = {}
    for ch, count in channel_counts.items():
        channel_sentiment[ch] = round(channel_sentiment_sum[ch] / count, 3) if count > 0 else 0.0

    sentiment_percentages = {
        k: round((v / total) * 100, 1) for k, v in sentiment_counts.items()
    }

    # Churn Risk Index (0 - 100 scale)
    neg_pct = sentiment_percentages["Negative"]
    churn_score = (neg_pct * 0.6) + min(40.0, (severe_churn_factors / total * 100) * 1.2)
    churn_risk_index = round(min(100.0, max(0.0, churn_score)), 1)

    # Sort timeline chronological
    timeline = []
    for d in sorted(daily_groups.keys()):
        grp = daily_groups[d]
        timeline.append(
            AnalyticsTimelinePoint(
                date=d,
                avg_sentiment=round(grp["sentiment_sum"] / grp["total"], 3),
                total_reviews=grp["total"],
                negative_count=grp["negative"],
                positive_count=grp["positive"],
            )
        )

    return AnalyticsSummary(
        total_reviews=total,
        avg_sentiment=avg_sentiment,
        sentiment_counts=sentiment_counts,
        sentiment_percentages=sentiment_percentages,
        channel_counts=channel_counts,
        channel_sentiment=channel_sentiment,
        theme_counts=theme_counts,
        status_counts=status_counts,
        critical_negative_count=critical_negative_count,
        churn_risk_index=churn_risk_index,
        sentiment_timeline=timeline,
    )


# ---------------------------------------------------------
# ALERT CONFIGURATION & SLACK ENDPOINTS
# ---------------------------------------------------------

@app.get("/api/alerts/config", response_model=AlertConfigResponse, summary="Get alert configuration")
def get_alert_config(db: Session = Depends(get_db)):
    return get_or_create_alert_config(db)


@app.put("/api/alerts/config", response_model=AlertConfigResponse, summary="Update alert configuration")
def update_alert_config(payload: AlertConfigUpdate, db: Session = Depends(get_db)):
    config = get_or_create_alert_config(db)
    if payload.slack_webhook_url is not None:
        config.slack_webhook_url = payload.slack_webhook_url.strip()
    if payload.negative_threshold_pct is not None:
        config.negative_threshold_pct = max(1.0, min(100.0, payload.negative_threshold_pct))
    if payload.is_enabled is not None:
        config.is_enabled = payload.is_enabled

    db.commit()
    db.refresh(config)
    return config


@app.post("/api/alerts/test", summary="Send a test Slack notification")
async def send_test_alert(payload: TestAlertRequest, db: Session = Depends(get_db)):
    config = get_or_create_alert_config(db)
    target_url = payload.webhook_url if payload.webhook_url is not None else config.slack_webhook_url
    sample_quote = payload.sample_text or "The app crashes immediately after the splash screen when updating on iOS 17."

    result = await nlp.dispatch_slack_alert(
        webhook_url=target_url,
        title="Test Alert: FeedPulse Notification Sentinel",
        message="This is a test notification from *FeedPulse Feedback Triage System*. Outbound webhook integration is operational.",
        metrics={
            "Environment": "FeedPulse Local Production Sandbox",
            "Negative Threshold": f"{config.negative_threshold_pct:.1f}%",
            "Status": "Verified",
            "Time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        sample_review=sample_quote,
    )
    return result
