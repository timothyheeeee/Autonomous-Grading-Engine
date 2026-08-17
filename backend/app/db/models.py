from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    student_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    aliases_csv: Mapped[str] = mapped_column(String(1024), default="")
    unit_track: Mapped[str] = mapped_column(String(64), default="data_science")
    email: Mapped[str] = mapped_column(String(255))


class PublishedMetric(Base):
    __tablename__ = "published_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_name: Mapped[str] = mapped_column(String(255), index=True)
    criterion: Mapped[str] = mapped_column(String(255))
    percentage: Mapped[float] = mapped_column(Float)
    contribution_percentage: Mapped[float] = mapped_column(Float)
    overall_percentage: Mapped[float] = mapped_column(Float)
    source_row_ids: Mapped[str] = mapped_column(String(1024), default="")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    rubric_name: Mapped[str] = mapped_column(String(128))
    initiated_by: Mapped[str] = mapped_column(String(255))
    qualitative_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    traces: Mapped[list["TraceEvent"]] = relationship(back_populates="run")


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    node_name: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[PipelineRun] = relationship(back_populates="traces")
