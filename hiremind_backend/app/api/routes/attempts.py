from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import Assessment, AssessmentAttempt, CandidateAnswer, Question
from app.schemas.schemas import MCQAnswersSubmitRequest, MCQAnswerOut

router = APIRouter(prefix="/api/attempts", tags=["Attempts"])


def recommendation_from_score(score: float | int | None) -> str | None:
    if score is None:
        return None
    try:
        value = float(score)
    except Exception:
        return None
    if value >= 85:
        return "strong_hire"
    if value >= 70:
        return "hire"
    if value >= 50:
        return "borderline"
    return "no_hire"


@router.post("/start/{assessment_id}", status_code=201)
def start_attempt(
    assessment_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Start a new assessment attempt for the authenticated candidate."""
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.status == "active",
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Active assessment not found")

    # Disallow multiple attempts: if any attempt exists for this candidate+assessment, block start
    existing_any = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.candidate_id == current_user.id,
    ).first()
    if existing_any:
        raise HTTPException(status_code=400, detail="Candidate already has an attempt for this assessment")

    attempt = AssessmentAttempt(
        assessment_id=assessment_id,
        candidate_id=current_user.id,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": str(attempt.id),
        "assessment_id": str(assessment_id),
        "duration_minutes": assessment.duration_minutes,
        "proctoring_enabled": assessment.proctoring_enabled,
        "status": "in_progress",
        "started_at": attempt.started_at.isoformat(),
    }


@router.post("/{attempt_id}/submit")
def submit_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark an attempt as submitted."""
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == attempt_id,
        AssessmentAttempt.candidate_id == current_user.id,
        AssessmentAttempt.status == "in_progress",
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="In-progress attempt not found")

    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "attempt_id": str(attempt.id),
        "status": "submitted",
        "submitted_at": attempt.submitted_at.isoformat(),
    }


@router.post("/{attempt_id}/answers", response_model=list[MCQAnswerOut])
def submit_mcq_answers(
    attempt_id: UUID,
    payload: MCQAnswersSubmitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create or update MCQ/aptitude answers for an in-progress attempt."""
    if not payload.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required")

    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == attempt_id,
        AssessmentAttempt.candidate_id == current_user.id,
        AssessmentAttempt.status == "in_progress",
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="In-progress attempt not found")

    saved_answers = []
    for item in payload.answers:
        if item.answer_index is None and item.answer_text is None:
            raise HTTPException(
                status_code=400,
                detail=f"Answer is required for question {item.question_id}",
            )

        question = db.query(Question).filter(
            Question.id == item.question_id,
            Question.assessment_id == attempt.assessment_id,
        ).first()
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {item.question_id} not found")

        if question.type not in ("mcq", "aptitude"):
            raise HTTPException(
                status_code=400,
                detail=f"Question {item.question_id} is not an MCQ/aptitude question",
            )

        if (
            item.answer_index is not None
            and question.options
            and not 0 <= item.answer_index < len(question.options)
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Answer index out of range for question {item.question_id}",
            )

        is_correct = None
        if question.correct_answer is not None:
            try:
                is_correct = item.answer_index == int(question.correct_answer)
            except ValueError:
                if item.answer_text is not None:
                    is_correct = item.answer_text.strip().lower() == question.correct_answer.strip().lower()

        answer = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == attempt.id,
            CandidateAnswer.question_id == question.id,
        ).first()

        if answer:
            answer.answer_index = item.answer_index
            answer.answer_text = item.answer_text
            answer.is_correct = is_correct
            answer.submitted_at = datetime.now(timezone.utc)
        else:
            answer = CandidateAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                answer_index=item.answer_index,
                answer_text=item.answer_text,
                is_correct=is_correct,
            )
            db.add(answer)

        saved_answers.append(answer)

    db.commit()
    for answer in saved_answers:
        db.refresh(answer)

    return saved_answers


@router.get("/my")
def my_attempts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all attempts for the current candidate."""
    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.candidate_id == current_user.id)
        .order_by(AssessmentAttempt.started_at.desc())
        .all()
    )
    return [
        {
            "attempt_id": str(a.id),
            "assessment_id": str(a.assessment_id),
            "status": a.status,
            "total_score": a.total_score,
            "passed": a.passed,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
        for a in attempts
    ]


@router.get("/recruiter/all")
def all_attempts(
    assessment_id: UUID = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("recruiter", "admin")),
):
    """List all attempts — recruiter view."""
    from app.models.user import User
    query = (
        db.query(AssessmentAttempt)
        .join(Assessment, AssessmentAttempt.assessment_id == Assessment.id)
    )
    if current_user.role != "admin":
        query = query.filter(Assessment.recruiter_id == current_user.id)
    if assessment_id:
        query = query.filter(AssessmentAttempt.assessment_id == assessment_id)
    attempts = query.order_by(AssessmentAttempt.submitted_at.desc()).all()

    result = []
    for a in attempts:
        candidate = db.query(User).filter(User.id == a.candidate_id).first()
        score_recommendation = recommendation_from_score(a.total_score)
        result.append({
            "attempt_id": str(a.id),
            "assessment_id": str(a.assessment_id),
            "candidate_id": str(a.candidate_id),
            "candidate_name": candidate.name if candidate else "Unknown",
            "candidate_email": candidate.email if candidate else "Unknown",
            "status": a.status,
            "total_score": a.total_score,
            "passed": a.passed,
            "recommendation": score_recommendation or (a.evaluation_report or {}).get("recommendation"),
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        })
    return result
