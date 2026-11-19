from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)  # 'App Store', 'Google Play', 'Reddit', 'Discord'
    author = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5, nullable
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    sentiment_score = Column(Float, nullable=False)  # -1.0 to 1.0
    sentiment_label = Column(String(20), nullable=False, index=True)  # 'Positive', 'Neutral', 'Negative'
    category_theme = Column(String(50), nullable=False, index=True)  # 'Login Crash', 'Billing & Payments', etc.
    status = Column(String(50), default="New", nullable=False, index=True)  # 'New', 'Investigating', 'Escalated', 'Resolved'


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    slack_webhook_url = Column(String(255), nullable=True)
    negative_threshold_pct = Column(Float, default=30.0, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)


class Theme(Base):
    __tablename__ = "themes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_team = Column(String(100), nullable=True)
    jira_component_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Schemas
class ReviewBase(BaseModel):
    source: str
    author: str
    rating: Optional[int] = None
    content: str


class ReviewCreate(ReviewBase):
    created_at: Optional[datetime] = None


class ReviewStatusUpdate(BaseModel):
    status: str


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    author: str
    rating: Optional[int] = None
    content: str
    created_at: datetime
    sentiment_score: float
    sentiment_label: str
    category_theme: str
    status: str


class AlertConfigBase(BaseModel):
    slack_webhook_url: Optional[str] = None
    negative_threshold_pct: float = 30.0
    is_enabled: bool = True


class AlertConfigResponse(AlertConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AlertConfigUpdate(BaseModel):
    slack_webhook_url: Optional[str] = None
    negative_threshold_pct: Optional[float] = None
    is_enabled: Optional[bool] = None


class TestAlertRequest(BaseModel):
    webhook_url: Optional[str] = None
    sample_text: Optional[str] = None


class AnalyticsTimelinePoint(BaseModel):
    date: str
    avg_sentiment: float
    total_reviews: int
    negative_count: int
    positive_count: int


class AnalyticsSummary(BaseModel):
    total_reviews: int
    avg_sentiment: float
    sentiment_counts: Dict[str, int]
    sentiment_percentages: Dict[str, float]
    channel_counts: Dict[str, int]
    channel_sentiment: Dict[str, float]
    theme_counts: Dict[str, int]
    status_counts: Dict[str, int]
    critical_negative_count: int
    churn_risk_index: float
    sentiment_timeline: List[AnalyticsTimelinePoint]


# Theme Schemas
class ThemeBase(BaseModel):
    name: str
    description: Optional[str] = None
    owner_team: Optional[str] = None
    jira_component_id: Optional[str] = None


class ThemeCreate(ThemeBase):
    pass


class ThemeUpdate(BaseModel):
    description: Optional[str] = None
    owner_team: Optional[str] = None
    jira_component_id: Optional[str] = None


class ThemeResponse(ThemeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    review_count: int = 0
    negative_count: int = 0
    escalated_count: int = 0


class ThemeEscalateResponse(BaseModel):
    theme_name: str
    escalated_count: int
    message: str
