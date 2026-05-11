from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Supports ORDER BY score DESC used in get_top_jobs
        Index("ix_jobs_score", "score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Unique natural key — ON CONFLICT DO NOTHING uses this index
    link: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)

    # AI scoring — null until first scored; cached permanently after that
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    saved_by: Mapped[list["SavedJob"]] = relationship(back_populates="job")

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} score={self.score}>"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    level: Mapped[str] = mapped_column(String(50), nullable=False, default="junior")

    applications: Mapped[list["Application"]] = relationship(back_populates="user")
    saved_jobs: Mapped[list["SavedJob"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<UserProfile id={self.id} telegram_id={self.telegram_id} level={self.level!r}>"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["UserProfile"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")

    def __repr__(self) -> str:
        return f"<Application id={self.id} user_id={self.user_id} job_id={self.job_id}>"


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        # Prevents saving the same job twice; also handles race conditions via DB constraint
        UniqueConstraint("user_id", "job_id", name="uq_saved_jobs_user_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["UserProfile"] = relationship(back_populates="saved_jobs")
    job: Mapped["Job"] = relationship(back_populates="saved_by")

    def __repr__(self) -> str:
        return f"<SavedJob id={self.id} user_id={self.user_id} job_id={self.job_id}>"
