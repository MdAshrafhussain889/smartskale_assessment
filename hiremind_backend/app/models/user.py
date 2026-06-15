import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Float,
    ForeignKey, Text, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy import Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255))
    role = Column(SAEnum("candidate", "recruiter", "admin", name="user_role"), nullable=False)
    google_id = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    assessments = relationship("Assessment", back_populates="recruiter",
                               foreign_keys="Assessment.recruiter_id")
    attempts = relationship("AssessmentAttempt", back_populates="candidate",
                            foreign_keys="AssessmentAttempt.candidate_id")


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    types = Column(JSON, default=list)          # ["mcq","coding","sql"]
    duration_minutes = Column(Integer, default=60)
    proctoring_enabled = Column(Boolean, default=True)
    adaptive = Column(Boolean, default=False)
    status = Column(SAEnum("draft", "active", "archived", name="assessment_status"), default="draft")
    created_at = Column(DateTime(timezone=True), default=now_utc)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    pass_score = Column(Integer, default=70)
    proctoring_options = Column(JSON, nullable=True)
    section_cutoffs = Column(JSON, nullable=True)  # e.g. {"mcq":60, "coding":70}

    recruiter = relationship("User", back_populates="assessments",
                             foreign_keys=[recruiter_id])
    questions = relationship("Question", back_populates="assessment", cascade="all, delete-orphan")
    attempts = relationship("AssessmentAttempt", back_populates="assessment")


class Question(Base):
    __tablename__ = "questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    type = Column(SAEnum("mcq", "coding", "sql", "aptitude", name="question_type"), nullable=False)
    difficulty = Column(SAEnum("easy", "medium", "hard", name="difficulty_level"), default="medium")
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=True)         # For MCQ
    correct_answer = Column(Text, nullable=True)  # MCQ index or reference answer
    test_cases = Column(JSON, nullable=True)      # For coding: [{input, expected_output}]
    points = Column(Integer, default=10)
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    assessment = relationship("Assessment", back_populates="questions")
    answers = relationship("CandidateAnswer", back_populates="question", cascade="all, delete-orphan")


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=now_utc)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(SAEnum("in_progress", "submitted", "evaluated", name="attempt_status"), default="in_progress")
    total_score = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    behavioral_score = Column(Float, nullable=True)
    evaluation_report = Column(JSON, nullable=True)
    proctoring_summary = Column(JSON, nullable=True)
    passed = Column(Boolean, nullable=True)

    assessment = relationship("Assessment", back_populates="attempts")
    candidate = relationship("User", back_populates="attempts", foreign_keys=[candidate_id])
    submissions = relationship("CodeSubmission", back_populates="attempt", cascade="all, delete-orphan")
    answers = relationship("CandidateAnswer", back_populates="attempt", cascade="all, delete-orphan")
    proctor_events = relationship("ProctorEvent", back_populates="attempt", cascade="all, delete-orphan")


class CodeSubmission(Base):
    __tablename__ = "code_submissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    language = Column(String(50), nullable=False)
    code = Column(Text, nullable=False)
    verdict = Column(String(50), nullable=True)   # ACCEPTED / WRONG_ANSWER / TLE / etc.
    passed_cases = Column(Integer, default=0)
    total_cases = Column(Integer, default=0)
    runtime_ms = Column(Float, nullable=True)
    memory_kb = Column(Float, nullable=True)
    judge0_token = Column(String(255), nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=now_utc)

    attempt = relationship("AssessmentAttempt", back_populates="submissions")


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_candidate_answer_attempt_question"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    answer_index = Column(Integer, nullable=True)
    answer_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    attempt = relationship("AssessmentAttempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")


class ProctorEvent(Base):
    __tablename__ = "proctor_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id"), nullable=False)
    event_type = Column(
        SAEnum("tab_switch", "face_missing", "fullscreen_exit", "multi_face",
               "copy_paste", "other", name="proctor_event_type"),
        nullable=False
    )
    timestamp = Column(DateTime(timezone=True), default=now_utc)
    frame_snapshot_url = Column(String(500), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)

    attempt = relationship("AssessmentAttempt", back_populates="proctor_events")
