from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import AssessmentAttempt, User
from app.schemas.schemas import ReportResponse

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/{candidate_id}", response_model=ReportResponse)
def get_report(
    candidate_id: UUID,
    format: str = "json",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Fetch the latest evaluated attempt report for a candidate.
    Recruiters can see any candidate; candidates can only see their own.
    """
    if current_user.role == "candidate" and str(current_user.id) != str(candidate_id):
        raise HTTPException(status_code=403, detail="Access denied")

    attempt = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.candidate_id == candidate_id,
            AssessmentAttempt.status == "evaluated",
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="No evaluated report found for this candidate")

    if format == "pdf":
        pdf_bytes = _generate_pdf(attempt, db)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=report_{candidate_id}.pdf"
            },
        )

    return ReportResponse(
        candidate_id=attempt.candidate_id,
        attempt_id=attempt.id,
        total_score=attempt.total_score,
        technical_score=attempt.technical_score,
        behavioral_score=attempt.behavioral_score,
        evaluation_report=attempt.evaluation_report,
        proctoring_summary=attempt.proctoring_summary,
        submitted_at=attempt.submitted_at,
    )


def _generate_pdf(attempt: AssessmentAttempt, db: Session) -> bytes:
    """Generate a PDF report using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    accent = HexColor("#00d4ff")
    dark = HexColor("#060b14")

    elements = []

    # Title
    title_style = ParagraphStyle("title", fontSize=22, textColor=accent,
                                  spaceAfter=6, fontName="Helvetica-Bold")
    elements.append(Paragraph("SmartSkale HireMind AI — Candidate Report", title_style))
    elements.append(Spacer(1, 0.4*cm))

    candidate = db.query(User).filter(User.id == attempt.candidate_id).first()
    sub_style = ParagraphStyle("sub", fontSize=11, textColor=HexColor("#6b8299"), spaceAfter=12)
    elements.append(Paragraph(f"Candidate: {candidate.name if candidate else str(attempt.candidate_id)}", sub_style))
    elements.append(Paragraph(f"Submitted: {attempt.submitted_at.strftime('%Y-%m-%d %H:%M UTC') if attempt.submitted_at else 'N/A'}", sub_style))
    elements.append(Spacer(1, 0.5*cm))

    # Score table
    score_data = [
        ["Metric", "Score"],
        ["Total Score", f"{attempt.total_score:.1f}/100" if attempt.total_score else "N/A"],
        ["Technical Score", f"{attempt.technical_score:.1f}/100" if attempt.technical_score else "N/A"],
        ["Behavioral Score", f"{attempt.behavioral_score:.1f}/100" if attempt.behavioral_score else "N/A"],
    ]
    table = Table(score_data, colWidths=[8*cm, 6*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f5f5f5"), HexColor("#ffffff")]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*cm))

    # AI Summary
    if attempt.evaluation_report:
        report = attempt.evaluation_report
        h2 = ParagraphStyle("h2", fontSize=13, fontName="Helvetica-Bold",
                             textColor=dark, spaceAfter=6, spaceBefore=12)
        body = ParagraphStyle("body", fontSize=10, textColor=HexColor("#333333"),
                               spaceAfter=4, leading=15)

        elements.append(Paragraph("AI Evaluation Summary", h2))
        elements.append(Paragraph(report.get("summary", ""), body))

        elements.append(Paragraph("Recommendation", h2))
        rec = report.get("recommendation", "N/A").replace("_", " ").upper()
        elements.append(Paragraph(rec, ParagraphStyle("rec", fontSize=14,
                                                       fontName="Helvetica-Bold",
                                                       textColor=accent)))

        if report.get("strengths"):
            elements.append(Paragraph("Strengths", h2))
            for s in report["strengths"]:
                elements.append(Paragraph(f"• {s}", body))

        if report.get("improvements"):
            elements.append(Paragraph("Areas for Improvement", h2))
            for s in report["improvements"]:
                elements.append(Paragraph(f"• {s}", body))

    doc.build(elements)
    return buf.getvalue()
