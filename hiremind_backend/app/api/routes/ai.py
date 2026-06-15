from fastapi import APIRouter, Depends, HTTPException
import concurrent.futures
import logging
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import Assessment, AssessmentAttempt, CandidateAnswer, CodeSubmission, Question
from app.schemas.schemas import GenerateQuestionsRequest, EvaluateRequest
from app.services import ai_service

router = APIRouter(prefix="/api/ai", tags=["AI"])
logger = logging.getLogger(__name__)


def recommendation_from_score(score: float | int | None) -> str:
    try:
        value = float(score or 0)
    except Exception:
        value = 0.0
    if value >= 85:
        return "strong_hire"
    if value >= 70:
        return "hire"
    if value >= 50:
        return "borderline"
    return "no_hire"


@router.post("/generate-questions")
def generate_questions(
    payload: GenerateQuestionsRequest,
    assessment_id: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("recruiter", "admin")),
):
    """
    Generate questions via GPT-4o and optionally save them to an assessment.
    """
    all_questions = []
    # Parallelize generation across requested question types to reduce wall-clock latency.
    # Use per-type counts if provided in `payload.counts`, otherwise fallback to `payload.count`.
    # sanitize counts: only honor counts for requested types and coerce to ints
    raw_counts = payload.counts or {}
    counts_map: dict = {}
    for k, v in (raw_counts.items() if isinstance(raw_counts, dict) else []):
        if k in payload.types:
            try:
                iv = int(v)
            except Exception:
                continue
            if iv < 0:
                iv = 0
            counts_map[k] = min(iv, 200)  # cap per-type to sane maximum

    max_workers = min(4, max(1, len(payload.types)))
    fut_map: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for q_type in payload.types:
            per_type_count = counts_map.get(q_type, int(getattr(payload, "count", 1)))
            try:
                per_type_count = int(per_type_count)
            except Exception:
                per_type_count = 1
            per_type_count = max(0, min(per_type_count, 200))
            fut = ex.submit(
                ai_service.generate_questions,
                payload.role,
                payload.skills,
                payload.difficulty,
                q_type,
                per_type_count,
                payload.job_description,
                payload.experience_level,
            )
            fut_map[fut] = q_type

        for fut in concurrent.futures.as_completed(list(fut_map.keys())):
            q_type = fut_map.get(fut)
            try:
                questions = fut.result()
                # Ensure each returned question has the expected type (fallback to q_type)
                for q in questions:
                    if not q.get("type") or q.get("type") != q_type:
                        q["type"] = q_type
                all_questions.extend(questions)
            except Exception as e:
                logger.exception("AI generation task failed for type=%s: %s", q_type, e)
                raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")

    # Optionally persist to assessment
    if assessment_id:
        a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not a:
            raise HTTPException(status_code=404, detail="Assessment not found")

        saved = []
        for i, q in enumerate(all_questions):
            question = Question(
                assessment_id=a.id,
                type=q.get("type", "mcq"),
                difficulty=q.get("difficulty", payload.difficulty),
                prompt=q.get("prompt", ""),
                options=q.get("options"),
                correct_answer=str(q.get("correct_answer", "")),
                test_cases=q.get("test_cases"),
                points=q.get("points", 10),
                order=i,
            )
            db.add(question)
            saved.append(question)
        db.commit()

        return {
            "generated": len(all_questions),
            "saved_to_assessment": assessment_id,
            "questions": [
                {
                    "id": str(q.id),
                    "type": q.type,
                    "difficulty": q.difficulty,
                    "prompt": q.prompt[:100] + "..." if len(q.prompt) > 100 else q.prompt,
                }
                for q in saved
            ],
        }

    return {"generated": len(all_questions), "questions": all_questions}


@router.post("/evaluate")
def evaluate_candidate(
    payload: EvaluateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("recruiter", "admin")),
):
    """
    Evaluate a candidate's full attempt using GPT-4o.
    Stores evaluation report in the attempt record.
    """
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == payload.attempt_id
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    assessment = attempt.assessment
    if current_user.role == "recruiter" and assessment.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if attempt.status not in ("submitted", "evaluated"):
        raise HTTPException(status_code=400, detail="Attempt must be submitted before evaluation")

    # Enrich code submissions with question data
    enriched_code = []
    code_submissions = (
        db.query(CodeSubmission)
        .filter(CodeSubmission.attempt_id == attempt.id)
        .order_by(CodeSubmission.submitted_at.desc())
        .all()
    )
    latest_by_question = {}
    for sub in code_submissions:
        latest_by_question.setdefault(sub.question_id, sub)

    if latest_by_question:
        for sub in latest_by_question.values():
            q = db.query(Question).filter(Question.id == sub.question_id).first()
            enriched_code.append({
                "prompt": q.prompt if q else "N/A",
                "language": sub.language,
                "code": sub.code,
                "passed_cases": sub.passed_cases,
                "total_cases": sub.total_cases,
                "verdict": sub.verdict,
                "runtime_ms": sub.runtime_ms,
                "memory_kb": sub.memory_kb,
            })

    fallback_code_submissions = payload.code_submissions if not enriched_code else []
    for sub in fallback_code_submissions:
        q = db.query(Question).filter(Question.id == sub.get("question_id")).first()
        enriched_code.append({
            "prompt": q.prompt if q else "N/A",
            "language": sub.get("language"),
            "code": sub.get("code"),
            "passed_cases": sub.get("passed_cases", 0),
            "total_cases": sub.get("total_cases", 0),
            "verdict": sub.get("verdict"),
        })

    # Enrich MCQ answers
    enriched_mcq = []
    stored_answers = (
        db.query(CandidateAnswer)
        .filter(CandidateAnswer.attempt_id == attempt.id)
        .all()
    )

    if stored_answers:
        for ans in stored_answers:
            q = ans.question
            correct_idx = None
            if q and q.correct_answer is not None:
                try:
                    correct_idx = int(q.correct_answer)
                except ValueError:
                    pass
            enriched_mcq.append({
                "prompt": q.prompt if q else "N/A",
                "answer_index": ans.answer_index,
                "answer_text": ans.answer_text,
                "correct_index": correct_idx,
                "is_correct": ans.is_correct,
            })

    fallback_mcq_answers = payload.mcq_answers if not enriched_mcq else []
    for ans in fallback_mcq_answers:
        q = db.query(Question).filter(Question.id == ans.get("question_id")).first()
        correct_idx = None
        is_correct = False
        if q and q.correct_answer is not None:
            try:
                correct_idx = int(q.correct_answer)
                is_correct = ans.get("answer_index") == correct_idx
            except ValueError:
                pass
        enriched_mcq.append({
            "prompt": q.prompt if q else "N/A",
            "answer_index": ans.get("answer_index"),
            "correct_index": correct_idx,
            "is_correct": is_correct,
        })

    try:
        report = ai_service.evaluate_candidate(
            role=assessment.role,
            types=assessment.types or [],
            code_submissions=enriched_code,
            mcq_answers=enriched_mcq,
            proctoring_data=payload.proctoring_data,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI evaluation failed: {str(e)}")

    # Persist scores
    composite_score = report.get("composite_score")
    report["recommendation"] = recommendation_from_score(composite_score)
    attempt.evaluation_report = report
    attempt.total_score = composite_score
    attempt.technical_score = report.get("technical_score")
    attempt.behavioral_score = report.get("behavioral_score")
    attempt.status = "evaluated"
    # Determine pass/fail based on assessment.pass_score and optional section_cutoffs
    try:
        total_score = float(report.get("composite_score", 0) or 0)
        total_score = max(0.0, min(100.0, total_score))
        pass_threshold = float(assessment.pass_score or 0)
        overall_pass = total_score >= pass_threshold

        # If assessment has section_cutoffs configured, compute per-type percentages
        section_cutoffs = getattr(assessment, "section_cutoffs", None) or {}
        per_type_ok = True
        if section_cutoffs:
            # compute possible and earned per type
            qrs = db.query(Question).filter(Question.assessment_id == assessment.id).all()
            type_totals: dict = {}
            type_earned: dict = {}
            for q in qrs:
                t = q.type
                type_totals[t] = type_totals.get(t, 0) + (q.points or 0)
                type_earned.setdefault(t, 0)

            # MCQ answers
            answers = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt.id).all()
            for ans in answers:
                q = ans.question
                if not q:
                    continue
                if ans.is_correct:
                    type_earned[q.type] = type_earned.get(q.type, 0) + (q.points or 0)

            # Code submissions: proportional on passed_cases/total_cases
            # load submissions ordered by newest first so the first record per question is the latest
            submissions = (
                db.query(CodeSubmission)
                .filter(CodeSubmission.attempt_id == attempt.id)
                .order_by(CodeSubmission.submitted_at.desc())
                .all()
            )
            latest_sub: dict = {}
            for s in submissions:
                # keep the first (newest) submission seen per question
                latest_sub.setdefault(s.question_id, s)
            for q in qrs:
                if q.id in latest_sub:
                    s = latest_sub[q.id]
                    if s.total_cases and s.total_cases > 0:
                        ratio = float(s.passed_cases or 0) / float(s.total_cases)
                        type_earned[q.type] = type_earned.get(q.type, 0) + (q.points or 0) * ratio

            # Evaluate cutoffs
            for t, cutoff in (section_cutoffs or {}).items():
                possible = type_totals.get(t, 0)
                if possible <= 0:
                    continue
                earned = type_earned.get(t, 0)
                pct = (earned / possible) * 100.0 if possible else 0.0
                try:
                    req = float(cutoff)
                except Exception:
                    req = 0.0
                if pct < req:
                    per_type_ok = False
                    break

        attempt.passed = overall_pass and per_type_ok
    except Exception:
        attempt.passed = None
    if payload.proctoring_data:
        attempt.proctoring_summary = payload.proctoring_data
    db.commit()

    return {
        "attempt_id": str(attempt.id),
        "candidate_id": str(attempt.candidate_id),
        "evaluation_report": report,
    }


@router.post("/adaptive-difficulty")
def adaptive_difficulty(score: float):
    """Return next difficulty level based on running score."""
    return {"difficulty": ai_service.next_question_difficulty(score)}
