from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import Question, CodeSubmission, AssessmentAttempt
from app.schemas.schemas import CodeSubmitRequest, CodeSubmitResponse
from app.services import judge0_service

router = APIRouter(prefix="/api/code", tags=["Code Execution"])


@router.post("/submit", response_model=CodeSubmitResponse)
def submit_code(
    payload: CodeSubmitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Execute candidate code against test cases via Judge0."""
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == payload.attempt_id,
        AssessmentAttempt.candidate_id == current_user.id,
        AssessmentAttempt.status == "in_progress",
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="In-progress attempt not found")

    question = db.query(Question).filter(
        Question.id == payload.question_id,
        Question.assessment_id == attempt.assessment_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found for this attempt")

    test_cases = []

    try:
        result = judge0_service.run_against_test_cases(
            code=payload.code,
            language=payload.language,
            test_cases=test_cases,
            reference_solution=question.correct_answer,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Code execution failed: {str(e)}")

    # Persist submission
    submission = CodeSubmission(
        attempt_id=attempt.id,
        question_id=question.id,
        language=payload.language,
        code=payload.code,
        verdict=result["verdict"],
        passed_cases=result["passed_cases"],
        total_cases=result["total_cases"],
        runtime_ms=result.get("runtime_ms"),
        memory_kb=result.get("memory_kb"),
        judge0_token=result.get("token"),
    )
    db.add(submission)
    db.commit()

    return CodeSubmitResponse(
        passed_cases=result["passed_cases"],
        total_cases=result["total_cases"],
        verdict=result["verdict"],
        runtime_ms=result.get("runtime_ms"),
        memory_kb=result.get("memory_kb"),
        failed_cases=result.get("failed_cases", []),
    )


@router.get("/languages")
def supported_languages():
    return {
        "languages": list(judge0_service.LANGUAGE_IDS.keys()),
    }
