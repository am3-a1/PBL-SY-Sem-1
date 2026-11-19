import os
import io
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
import pandas as pd
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Header,
    Security,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case, and_, or_

import database
from database import engine, get_db
import models
from models import (
    Review,
    AlertConfig,
    Theme,
    ReviewResponse,
    PaginatedReviewResponse,
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
    CsvImportSummary,
)
import nlp
import seed_data
from config import settings, validate_slack_webhook_url, mask_slack_webhook

# Setup application logger
logger = logging.getLogger("feedpulse.api")
logging.basicConfig(level=logging.INFO)

# Initialize DB tables with constraints
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FeedPulse API",
    description="Multi-Channel App Review & Feedback Triage Dashboard Backend",
    version="1.0.0",
)

# Hardened CORS configuration (rejects wildcards with credentials in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# LIGHTWEIGHT AUTHENTICATION & SECURITY DEPENDENCY
# ---------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
) -> bool:
    """
    Validates API key for destructive or mutating endpoints.
    Accepts:
      - X-API-Key header: <KEY>
      - Authorization header: Bearer <KEY>
    """
    provided_key = None
    if x_api_key:
        provided_key = x_api_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        provided_key = authorization.replace("Bearer ", "").strip()

    expected_key = settings.FEEDPULSE_API_KEY.strip()

    if not provided_key or provided_key != expected_key:
        logger.warning("Unauthorized access attempt to protected endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide a valid 'X-API-Key' or 'Authorization: Bearer <KEY>' header.",
        )
    return True


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
        config = AlertConfig(
            slack_webhook_url=settings.DEFAULT_SLACK_WEBHOOK_URL,
            negative_threshold_pct=settings.DEFAULT_NEGATIVE_THRESHOLD_PCT,
            is_enabled=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health", summary="Service health check")
@app.get("/api/health", summary="API health check")
def health_check(db: Session = Depends(get_db)):
    """Verifies service health, database connectivity, and configuration."""
    try:
        # Check DB connection
        db.execute(func.now() if not settings.DATABASE_URL.startswith("sqlite") else func.time())
        db_status = "connected"
    except Exception as exc:
        logger.error(f"Health check DB failure: {exc}")
        db_status = f"unhealthy: {type(exc).__name__}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------
# INGESTION & SEEDING ROUTES
# ---------------------------------------------------------

@app.post(
    "/api/reviews/seed",
    summary="Populate database with 65+ realistic multi-channel mock reviews",
    dependencies=[Depends(verify_api_key)],
)
async def seed_reviews(db: Session = Depends(get_db)):
    """
    Safely seeds mock reviews.
    Transactional: Prepares and scores reviews before replacing existing data.
    Protected by API key and production safeguard toggle.
    """
    if not settings.ALLOW_DEMO_SEEDING:
        logger.warning("Attempted to seed demo data when ALLOW_DEMO_SEEDING is disabled.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo data seeding is disabled in this environment.",
        )

    # Generate and analyze all seed items in memory first
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
            theme_confidence=nlp_res.get("theme_confidence", 1.0),
            status=item["status"],
        )
        created_reviews.append(review_obj)

    # Perform atomic database swap
    try:
        db.query(Review).delete()
        db.bulk_save_objects(created_reviews)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error during seeding: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist seed reviews. Existing data preserved.",
        )

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


@app.post(
    "/api/reviews/upload",
    response_model=CsvImportSummary,
    summary="Upload CSV file of user feedback",
    dependencies=[Depends(verify_api_key)],
)
async def upload_reviews_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Hardened CSV upload pipeline with strict file size validation,
    encoding handling, column & value validation, and detailed summary reporting.
    """
    if not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid CSV file.",
        )

    # Read contents with streaming size limit check to prevent memory exhaustion
    contents = bytearray()
    chunk_size = 64 * 1024  # 64 KB
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        contents.extend(chunk)
        if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed upload size of {max_mb} MB.",
            )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # Multi-encoding decoding fallback
    decoded_str = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            decoded_str = contents.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if decoded_str is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode file encoding. Please ensure CSV is encoded in UTF-8 or ASCII.",
        )

    try:
        df = pd.read_csv(io.StringIO(decoded_str))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(exc)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contains headers but no data rows.",
        )

    if len(df) > settings.MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV file exceeds maximum row limit of {settings.MAX_UPLOAD_ROWS} rows (found {len(df)}).",
        )

    # Standardize column names (strip whitespace and lower for checking)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    if "content" not in col_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must contain at least a 'content' column. Found columns: {list(df.columns)}",
        )

    content_col = col_map["content"]
    source_col = col_map.get("source")
    author_col = col_map.get("author")
    rating_col = col_map.get("rating")

    valid_sources = {"App Store", "Google Play", "Reddit", "Discord"}
    added_reviews = []
    skipped_count = 0
    reasons = []
    negative_count = 0

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed accounting for header row

        # Content validation
        content_val = row.get(content_col)
        content_text = "" if pd.isna(content_val) else str(content_val).strip()

        if not content_text or content_text.lower() in ("nan", "null"):
            skipped_count += 1
            if len(reasons) < 10:
                reasons.append(f"Row {row_num}: Skipped empty review content.")
            continue

        if len(content_text) > settings.MAX_CONTENT_LENGTH:
            content_text = content_text[: settings.MAX_CONTENT_LENGTH]

        # Source validation (do NOT silently convert invalid sources)
        source = "App Store"
        if source_col and pd.notna(row.get(source_col)):
            raw_source = str(row[source_col]).strip()
            matched_source = next((s for s in valid_sources if s.lower() == raw_source.lower()), None)
            if matched_source:
                source = matched_source
            else:
                skipped_count += 1
                if len(reasons) < 10:
                    reasons.append(f"Row {row_num}: Skipped invalid source '{raw_source}'. Must be one of {sorted(list(valid_sources))}.")
                continue

        # Author validation
        author = "Anonymous User"
        if author_col and pd.notna(row.get(author_col)):
            raw_author = str(row[author_col]).strip()
            if raw_author and raw_author.lower() != "nan":
                author = raw_author[:100]

        # Rating validation (1-5 or null)
        rating = None
        if rating_col and pd.notna(row.get(rating_col)):
            try:
                r_val = int(float(row[rating_col]))
                if 1 <= r_val <= 5:
                    rating = r_val
                else:
                    rating = None
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
            theme_confidence=nlp_res.get("theme_confidence", 1.0),
            status="New",
        )
        added_reviews.append(review_obj)

    # Atomic persistence
    if added_reviews:
        try:
            db.bulk_save_objects(added_reviews)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to save CSV reviews to database: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database transaction failed during review insertion. Database rolled back cleanly.",
            )

    total_added = len(added_reviews)
    neg_pct = (negative_count / total_added * 100) if total_added > 0 else 0
    config = get_or_create_alert_config(db)

    alert_triggered = False
    alert_result = None

    if config.is_enabled and total_added > 0 and neg_pct >= config.negative_threshold_pct:
        alert_triggered = True
        sample_quote = added_reviews[0].content if added_reviews else "No feedback"
        alert_result = await nlp.dispatch_slack_alert(
            webhook_url=config.slack_webhook_url,
            title="Spike in Negative Reviews (CSV Ingestion Batch)!",
            message=f"Negative feedback spike alert triggered during CSV upload. *{neg_pct:.1f}%* of newly uploaded reviews were flagged as Negative (Threshold: *{config.negative_threshold_pct:.1f}%*).",
            metrics={
                "Batch Size": str(total_added),
                "Negative Reviews": f"{negative_count} ({neg_pct:.1f}%)",
                "Alert Threshold": f"{config.negative_threshold_pct:.1f}%",
                "File Ingested": file.filename,
            },
            sample_review=sample_quote,
        )

    return CsvImportSummary(
        message=f"Successfully imported {total_added} reviews ({skipped_count} skipped).",
        total_rows_processed=len(df),
        successful_imports=total_added,
        skipped_rows=skipped_count,
        failed_rows=0,
        reasons=reasons,
        alert_triggered=alert_triggered,
        alert_details=alert_result,
    )


# ---------------------------------------------------------
# REVIEWS & TRIAGE ROUTES
# ---------------------------------------------------------

@app.get(
    "/api/reviews",
    response_model=Union[PaginatedReviewResponse, List[ReviewResponse]],
    summary="Get reviews with filters and pagination",
)
def get_reviews(
    source: Optional[str] = Query(None, description="App Store, Google Play, Reddit, Discord"),
    sentiment: Optional[str] = Query(None, description="Positive, Neutral, Negative"),
    theme: Optional[str] = Query(None, description="Login Crash, Billing & Payments, etc."),
    status: Optional[str] = Query(None, description="New, Investigating, Escalated, Resolved"),
    search: Optional[str] = Query(None, description="Keyword search in content or author"),
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="Items per page"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Fallback limit for unpaginated queries"),
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

    # If pagination requested
    if page is not None:
        size = page_size or 50
        total_count = query.count()
        offset_val = (page - 1) * size
        items = query.order_by(desc(Review.created_at)).offset(offset_val).limit(size).all()
        total_pages = (total_count + size - 1) // size if size > 0 else 1
        return PaginatedReviewResponse(
            items=items,
            total=total_count,
            page=page,
            page_size=size,
            total_pages=total_pages,
        )

    # Unpaginated fallback (backward compatible with frontend default)
    max_limit = limit or 500
    return query.order_by(desc(Review.created_at)).limit(max_limit).all()


@app.patch(
    "/api/reviews/{review_id}/status",
    response_model=ReviewResponse,
    summary="Update review Kanban status",
    dependencies=[Depends(verify_api_key)],
)
def update_review_status(
    review_id: int,
    payload: ReviewStatusUpdate,
    db: Session = Depends(get_db),
):
    allowed_statuses = {"New", "Investigating", "Escalated", "Resolved"}
    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{payload.status}'. Must be one of {sorted(list(allowed_statuses))}",
        )

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    try:
        review.status = payload.status
        db.commit()
        db.refresh(review)
        return review
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to update status for review {review_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update review status.")


@app.delete(
    "/api/reviews/{review_id}",
    summary="Delete single review",
    dependencies=[Depends(verify_api_key)],
)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    try:
        db.delete(review)
        db.commit()
        return {"message": f"Review {review_id} deleted"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete review {review_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete review.")


@app.delete(
    "/api/reviews",
    summary="Clear all reviews",
    dependencies=[Depends(verify_api_key)],
)
def clear_all_reviews(db: Session = Depends(get_db)):
    try:
        count = db.query(Review).delete()
        db.commit()
        return {"message": f"Cleared {count} reviews"}
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to clear reviews: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to clear database.")


# ---------------------------------------------------------
# THEMES & WORKFLOW ROUTES
# ---------------------------------------------------------

@app.get("/api/themes", response_model=List[ThemeResponse], summary="List all themes with review metrics")
def list_themes(db: Session = Depends(get_db)):
    """
    Optimized: aggregates counts across themes in grouped database queries
    instead of repeated N*3 queries.
    """
    init_default_themes(db)
    themes = db.query(Theme).all()

    # Query 1: Total counts per theme
    total_counts = dict(
        db.query(Review.category_theme, func.count(Review.id))
        .group_by(Review.category_theme)
        .all()
    )

    # Query 2: Negative counts per theme
    negative_counts = dict(
        db.query(Review.category_theme, func.count(Review.id))
        .filter(Review.sentiment_label == "Negative")
        .group_by(Review.category_theme)
        .all()
    )

    # Query 3: Escalated counts per theme
    escalated_counts = dict(
        db.query(Review.category_theme, func.count(Review.id))
        .filter(Review.status == "Escalated")
        .group_by(Review.category_theme)
        .all()
    )

    res = []
    for t in themes:
        res.append(
            ThemeResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                owner_team=t.owner_team,
                jira_component_id=t.jira_component_id,
                created_at=t.created_at,
                review_count=total_counts.get(t.name, 0),
                negative_count=negative_counts.get(t.name, 0),
                escalated_count=escalated_counts.get(t.name, 0),
            )
        )
    return res


@app.get("/api/themes/{theme_id}", response_model=ThemeResponse, summary="Get single theme details")
def get_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found")

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


@app.patch(
    "/api/themes/{theme_id}",
    response_model=ThemeResponse,
    summary="Update theme metadata",
    dependencies=[Depends(verify_api_key)],
)
def update_theme(theme_id: int, payload: ThemeUpdate, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found")

    if payload.description is not None:
        theme.description = payload.description.strip()
    if payload.owner_team is not None:
        theme.owner_team = payload.owner_team.strip()
    if payload.jira_component_id is not None:
        theme.jira_component_id = payload.jira_component_id.strip()

    try:
        db.commit()
        db.refresh(theme)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to update theme {theme_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update theme.")

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


@app.post(
    "/api/themes/{theme_id}/escalate",
    response_model=ThemeEscalateResponse,
    summary="Bulk escalate all open reviews in this theme",
    dependencies=[Depends(verify_api_key)],
)
def bulk_escalate_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = db.query(Theme).filter(Theme.id == theme_id).first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found")

    try:
        updated_rows = (
            db.query(Review)
            .filter(
                Review.category_theme == theme.name,
                Review.status.in_(["New", "Investigating"]),
            )
            .update({"status": "Escalated"}, synchronize_session=False)
        )
        db.commit()
        return ThemeEscalateResponse(
            theme_name=theme.name,
            escalated_count=updated_rows,
            message=f"Successfully escalated {updated_rows} reviews in '{theme.name}' to Escalated.",
        )
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to bulk escalate theme {theme_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bulk escalation failed.")


# ---------------------------------------------------------
# DATABASE-SIDE ANALYTICS ENDPOINTS
# ---------------------------------------------------------

@app.get("/api/analytics/summary", response_model=AnalyticsSummary, summary="Get aggregate analytics")
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Optimized: Executes fully database-side aggregate queries (COUNT, AVG, GROUP BY)
    avoiding loading entire review tables into Python memory.
    """
    total = db.query(func.count(Review.id)).scalar() or 0

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

    # 1. Overall Average Sentiment
    avg_sentiment_val = db.query(func.avg(Review.sentiment_score)).scalar() or 0.0
    avg_sentiment = round(float(avg_sentiment_val), 3)

    # 2. Sentiment Counts
    sentiment_rows = (
        db.query(Review.sentiment_label, func.count(Review.id))
        .group_by(Review.sentiment_label)
        .all()
    )
    sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for label, count in sentiment_rows:
        if label in sentiment_counts:
            sentiment_counts[label] = count

    sentiment_percentages = {
        k: round((v / total) * 100, 1) for k, v in sentiment_counts.items()
    }

    # 3. Channel Counts & Average Sentiments
    channel_rows = (
        db.query(Review.source, func.count(Review.id), func.avg(Review.sentiment_score))
        .group_by(Review.source)
        .all()
    )
    channel_counts = {"App Store": 0, "Google Play": 0, "Reddit": 0, "Discord": 0}
    channel_sentiment = {"App Store": 0.0, "Google Play": 0.0, "Reddit": 0.0, "Discord": 0.0}
    for ch, count, avg_score in channel_rows:
        if ch in channel_counts:
            channel_counts[ch] = count
            channel_sentiment[ch] = round(float(avg_score or 0.0), 3)

    # 4. Status Counts
    status_rows = db.query(Review.status, func.count(Review.id)).group_by(Review.status).all()
    status_counts = {"New": 0, "Investigating": 0, "Escalated": 0, "Resolved": 0}
    for st, count in status_rows:
        if st in status_counts:
            status_counts[st] = count

    # 5. Theme Counts
    theme_rows = db.query(Review.category_theme, func.count(Review.id)).group_by(Review.category_theme).all()
    theme_counts = {t: 0 for t in nlp.THEMES}
    for th, count in theme_rows:
        theme_counts[th] = count

    # 6. Critical Negative Issues (rating <= 2 OR Negative sentiment, and status in New/Escalated)
    critical_negative_count = (
        db.query(func.count(Review.id))
        .filter(
            or_(
                and_(Review.rating.isnot(None), Review.rating <= 2),
                Review.sentiment_label == "Negative",
            ),
            Review.status.in_(["New", "Escalated"]),
        )
        .scalar()
        or 0
    )

    # 7. Severe Churn Factors (Login Crash or Billing & Payments with Negative sentiment)
    severe_churn_factors = (
        db.query(func.count(Review.id))
        .filter(
            Review.category_theme.in_(["Login Crash", "Billing & Payments"]),
            Review.sentiment_label == "Negative",
        )
        .scalar()
        or 0
    )

    neg_pct = sentiment_percentages["Negative"]
    churn_score = (neg_pct * 0.6) + min(40.0, (severe_churn_factors / total * 100) * 1.2)
    churn_risk_index = round(min(100.0, max(0.0, churn_score)), 1)

    # 8. Timeline Aggregation (Database-side date formatting)
    date_col = func.strftime("%Y-%m-%d", Review.created_at) if settings.DATABASE_URL.startswith("sqlite") else func.to_char(Review.created_at, "YYYY-MM-DD")
    timeline_rows = (
        db.query(
            date_col.label("day"),
            func.count(Review.id).label("total_day"),
            func.avg(Review.sentiment_score).label("avg_day_sentiment"),
            func.sum(case((Review.sentiment_label == "Negative", 1), else_=0)).label("neg_count"),
            func.sum(case((Review.sentiment_label == "Positive", 1), else_=0)).label("pos_count"),
        )
        .group_by("day")
        .order_by("day")
        .all()
    )

    timeline = []
    for day_str, total_day, avg_day_score, neg_c, pos_c in timeline_rows:
        if day_str:
            timeline.append(
                AnalyticsTimelinePoint(
                    date=day_str,
                    avg_sentiment=round(float(avg_day_score or 0.0), 3),
                    total_reviews=total_day or 0,
                    negative_count=int(neg_c or 0),
                    positive_count=int(pos_c or 0),
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
    config = get_or_create_alert_config(db)
    has_webhook = bool(config.slack_webhook_url and config.slack_webhook_url.strip())
    masked_url = mask_slack_webhook(config.slack_webhook_url) if has_webhook else ""
    return AlertConfigResponse(
        id=config.id,
        slack_webhook_url=masked_url,
        has_slack_webhook=has_webhook,
        negative_threshold_pct=config.negative_threshold_pct,
        is_enabled=config.is_enabled,
    )


@app.put(
    "/api/alerts/config",
    response_model=AlertConfigResponse,
    summary="Update alert configuration",
    dependencies=[Depends(verify_api_key)],
)
def update_alert_config(payload: AlertConfigUpdate, db: Session = Depends(get_db)):
    config = get_or_create_alert_config(db)

    if payload.slack_webhook_url is not None:
        url_input = payload.slack_webhook_url.strip()
        if not url_input:
            config.slack_webhook_url = ""
        elif "***" in url_input:
            pass
        elif not validate_slack_webhook_url(url_input):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack incoming webhook URL. Must be an https://hooks.slack.com/services/... URL.",
            )
        else:
            config.slack_webhook_url = url_input

    if payload.negative_threshold_pct is not None:
        config.negative_threshold_pct = max(1.0, min(100.0, payload.negative_threshold_pct))
    if payload.is_enabled is not None:
        config.is_enabled = payload.is_enabled

    try:
        db.commit()
        db.refresh(config)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to save alert configuration: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save alert configuration.")

    has_webhook = bool(config.slack_webhook_url and config.slack_webhook_url.strip())
    masked_url = mask_slack_webhook(config.slack_webhook_url) if has_webhook else ""
    return AlertConfigResponse(
        id=config.id,
        slack_webhook_url=masked_url,
        has_slack_webhook=has_webhook,
        negative_threshold_pct=config.negative_threshold_pct,
        is_enabled=config.is_enabled,
    )


@app.post(
    "/api/alerts/test",
    summary="Send a test Slack notification",
    dependencies=[Depends(verify_api_key)],
)
async def send_test_alert(payload: TestAlertRequest, db: Session = Depends(get_db)):
    config = get_or_create_alert_config(db)
    
    target_url = config.slack_webhook_url
    if payload.webhook_url is not None and payload.webhook_url.strip():
        provided = payload.webhook_url.strip()
        if "***" not in provided:
            if not validate_slack_webhook_url(provided):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Slack webhook URL format. Must be https://hooks.slack.com/services/...",
                )
            target_url = provided

    sample_quote = payload.sample_text or "The app crashes immediately after the splash screen when updating on iOS 17."

    result = await nlp.dispatch_slack_alert(
        webhook_url=target_url,
        title="Test Alert: FeedPulse Notification Sentinel",
        message="This is a test notification from *FeedPulse Feedback Triage System*. Outbound webhook integration is operational.",
        metrics={
            "Environment": settings.ENVIRONMENT.capitalize(),
            "Negative Threshold": f"{config.negative_threshold_pct:.1f}%",
            "Status": "Verified",
            "Time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        sample_review=sample_quote,
    )
    return result


# ---------------------------------------------------------
# PRODUCTION STATIC FRONTEND MOUNT
# ---------------------------------------------------------
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
    logger.info(f"Mounted production frontend from {dist_dir}")
