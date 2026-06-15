"""
AI Service — wraps OpenAI GPT-4o for:
  1. Question generation
  2. Candidate evaluation / scoring
"""
import json
import logging
import re
from typing import List, Optional
from openai import OpenAI
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


# ── Question Generation ───────────────────────────────────────────────────────

QUESTION_GEN_SYSTEM = """You are an expert technical interviewer at a top tech company.
Generate high-quality assessment questions in strict JSON format only.
No markdown, no extra text — pure JSON array."""

QUESTION_GEN_TEMPLATE = """Generate {count} {type} questions for a {role} role.
Skills required: {skills}
Difficulty: {difficulty}

Return a JSON array of objects. Each object must have:
- "type": "{type}"
- "difficulty": "{difficulty}"
- "prompt": <question text>
- "options": <array of 4 strings for MCQ, null for others>
- "correct_answer": <correct option index 0-3 for MCQ, reference solution for coding/sql>
- "test_cases": <array of {{"input": "...", "expected_output": "..."}} for coding, null for MCQ>
- "points": <integer 10-30>

For coding questions, write a clear problem statement with input/output format.
For SQL questions, include the table schema in the prompt.
For MCQ, all 4 options must be plausible."""

QUESTION_GEN_TEMPLATE_CODING = """Generate {count} coding questions for a {role} role.
Skills required: {skills}
Difficulty: {difficulty}

Return a JSON array of objects. Each object must have:
- "type": "coding"
- "difficulty": "{difficulty}"
- "prompt": <question text>
- "options": null
- "correct_answer": <simple Python reference solution>
- "test_cases": []
- "points": <integer 10-30>

For coding questions:
- Make each problem a simple, self-contained Python function challenge.
- Include the exact function name and signature candidates should implement.
- Do not ask for FastAPI, REST endpoints, databases, files, web APIs, language model APIs, network calls, packages, or external services.
- Do not require stdin/stdout parsing.
- Prefer easy topics such as strings, lists, dictionaries, math, sorting, and validation."""

# A more constrained template for aptitude questions (quant, logical, verbal)
QUESTION_GEN_TEMPLATE_APTITUDE = """Generate {count} aptitude questions (quantitative, logical reasoning, or verbal) suitable for placement tests.
Produce only non-coding multiple-choice questions (MCQ) with exactly 4 options. Do NOT generate programming or coding problems.
For each question return an object with these fields only:
- "type": "aptitude"
- "difficulty": "{difficulty}"
- "prompt": <question text>
- "options": <array of 4 strings>  # four plausible answer choices
- "correct_answer": <index 0-3>   # index into options array
- "points": <integer 5-25>

Return a JSON array of objects only."""


def _looks_like_sql_question(prompt: str) -> bool:
    return bool(
        re.search(
            r"\b(SQL|PostgreSQL|CREATE\s+TABLE|SELECT\b|JOIN\b|GROUP\s+BY|ORDER\s+BY)\b",
            prompt or "",
            flags=re.IGNORECASE,
        )
    )


def _temperature_fastapi_cases(prompt: str) -> list[dict] | None:
    text = (prompt or "").lower()
    if "celsius" not in text or "fahrenheit" not in text:
        return None
    return [
        {"input": "celsius=0", "expected_output": "{'fahrenheit': 32.0}"},
        {"input": "celsius=100", "expected_output": "{'fahrenheit': 212.0}"},
        {"input": "celsius=-40", "expected_output": "{'fahrenheit': -40.0}"},
    ]


def _language_model_api_cases(prompt: str) -> list[dict] | None:
    text = (prompt or "").lower()
    if "generate_text" not in text and "language model api" not in text:
        return None
    return [
        {
            "input": "prompt='Write a product tagline', max_tokens=12",
            "expected_output": "Generated text for tagline",
        },
        {
            "input": "prompt='Summarize this paragraph', max_tokens=20",
            "expected_output": "Generated summary text",
        },
    ]


def _top_employees_sql_cases(prompt: str) -> list[dict] | None:
    text = prompt or ""
    if not (
        re.search(r"CREATE\s+TABLE\s+employees", text, flags=re.IGNORECASE)
        and re.search(r"top\s+three|top\s+3", text, flags=re.IGNORECASE)
        and re.search(r"department", text, flags=re.IGNORECASE)
    ):
        return None

    return [
        {
            "input": (
                "employees table with data: "
                "[(1, 'Ana', 'Engineering', 120000), (2, 'Ben', 'Engineering', 110000), "
                "(3, 'Cara', 'Engineering', 105000), (4, 'Dan', 'Engineering', 90000), "
                "(5, 'Eli', 'HR', 95000), (6, 'Fay', 'HR', 90000), "
                "(7, 'Gus', 'HR', 85000), (8, 'Hana', 'Sales', 100000)]"
            ),
            "expected_output": (
                "Ana Engineering 120000\nBen Engineering 110000\nCara Engineering 105000\n"
                "Eli HR 95000\nFay HR 90000\nGus HR 85000\nHana Sales 100000"
            ),
        }
    ]


def _normalize_generated_question(item: dict, requested_type: str, difficulty: str) -> dict:
    if not isinstance(item, dict):
        return item

    prompt = str(item.get("prompt") or "")
    inferred_type = "sql" if requested_type == "coding" and _looks_like_sql_question(prompt) else requested_type
    item["type"] = inferred_type
    item.setdefault("difficulty", difficulty)

    if inferred_type == "coding":
        item["options"] = None
        item["test_cases"] = []

    if inferred_type == "sql":
        item["options"] = None
        cases = item.get("test_cases")
        if not isinstance(cases, list) or not cases:
            fallback = _top_employees_sql_cases(prompt)
            item["test_cases"] = fallback or []
        else:
            item["test_cases"] = cases

    if inferred_type in {"mcq", "aptitude"}:
        item["test_cases"] = None

    return item


def _fallback_question(question_type: str, difficulty: str, index: int) -> dict:
    n = index + 1
    if question_type == "aptitude":
        return {
            "type": "aptitude",
            "difficulty": difficulty,
            "prompt": f"A train covers 60 km in 1.5 hours. What is its average speed? (Question {n})",
            "options": ["40 km/h", "45 km/h", "60 km/h", "90 km/h"],
            "correct_answer": 0,
            "test_cases": None,
            "points": 10,
        }
    if question_type == "mcq":
        return {
            "type": "mcq",
            "difficulty": difficulty,
            "prompt": f"Which Python data structure stores key-value pairs? (Question {n})",
            "options": ["List", "Tuple", "Dictionary", "Set"],
            "correct_answer": 2,
            "test_cases": None,
            "points": 10,
        }
    if question_type == "sql":
        return {
            "type": "sql",
            "difficulty": difficulty,
            "prompt": (
                f"Given a table employees(id INT, name VARCHAR(100), department VARCHAR(100), "
                f"salary INT), write a SQL query to list employee names in descending salary order. "
                f"(Question {n})"
            ),
            "options": None,
            "correct_answer": "SELECT name FROM employees ORDER BY salary DESC;",
            "test_cases": [],
            "points": 10,
        }
    return {
        "type": "coding",
        "difficulty": difficulty,
        "prompt": (
            f"Write a Python function sum_numbers(numbers: list[int]) -> int that returns "
            f"the sum of all integers in the list. (Question {n})"
        ),
        "options": None,
        "correct_answer": "def sum_numbers(numbers: list[int]) -> int:\n    return sum(numbers)",
        "test_cases": [],
        "points": 10,
    }


def _ensure_question_count(data: list[dict], question_type: str, difficulty: str, count: int) -> list[dict]:
    requested = max(0, int(count or 0))
    normalized = [
        _normalize_generated_question(item, question_type, difficulty)
        for item in data
        if isinstance(item, dict)
    ]
    normalized = [item for item in normalized if item.get("type") == question_type]
    while len(normalized) < requested:
        normalized.append(_fallback_question(question_type, difficulty, len(normalized)))
    return normalized[:requested]


def generate_questions(
    role: str,
    skills: List[str],
    difficulty: str,
    question_type: str,
    count: int,
    job_description: Optional[str] = None,
    experience_level: Optional[str] = None,
) -> List[dict]:
    """Call GPT-4o to generate questions. Returns list of question dicts."""
    import time as _time
    start = _time.perf_counter()
    # Choose a prompt template depending on question_type to avoid inappropriate outputs
    if question_type == "aptitude":
        prompt = QUESTION_GEN_TEMPLATE_APTITUDE.format(
            count=count,
            role=role,
            skills=", ".join(skills),
            difficulty=difficulty,
        )
    elif question_type == "coding":
        prompt = QUESTION_GEN_TEMPLATE_CODING.format(
            count=count,
            role=role,
            skills=", ".join(skills),
            difficulty=difficulty,
        )
    else:
        prompt = QUESTION_GEN_TEMPLATE.format(
            count=count,
            type=question_type,
            role=role,
            skills=", ".join(skills),
            difficulty=difficulty,
        )
    parts = []
    if experience_level:
        parts.append(f"Experience level: {experience_level}")
    if job_description:
        parts.append("Job description:")
        parts.append(job_description)

    if parts:
        prompt = "\n\n".join(parts) + "\n\n" + prompt
    try:
        client = _client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": QUESTION_GEN_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        # GPT-4o with json_object may wrap in a key
        if isinstance(data, dict):
            for key in ("questions", "items", "data"):
                if key in data:
                    data = data[key]
                    break
            else:
                data = list(data.values())[0] if data else []
        elapsed = _time.perf_counter() - start
        logger.info("AI generate_questions: type=%s count=%s elapsed=%.2fs", question_type, count, elapsed)

        if not isinstance(data, list):
            data = []

        # Post-process: ensure aptitude items always have 4 options (some models may return short-answer by mistake)
        if question_type == "aptitude" and isinstance(data, list):
            fixed = []
            for item in data:
                try:
                    opts = item.get("options")
                    ca = item.get("correct_answer")
                    # valid if options is list of 4 and correct_answer is 0-3
                    if isinstance(opts, list) and len(opts) == 4 and isinstance(ca, int) and 0 <= ca <= 3:
                        fixed.append(item)
                        continue
                    # otherwise build a simple placeholder options array using the provided correct answer
                    correct_text = None
                    if isinstance(ca, int) and isinstance(opts, list) and opts:
                        # if ca is index but options incomplete, try to pad
                        correct_text = opts[ca] if 0 <= ca < len(opts) else None
                    if correct_text is None and isinstance(ca, str):
                        correct_text = ca

                    if not correct_text:
                        # fallback: use the prompt as basis
                        correct_text = "Answer"

                    # simple deterministic distractors
                    distractors = [f"{correct_text} (not A)", f"{correct_text} (not B)", f"{correct_text} (not C)"]
                    new_opts = [correct_text] + distractors
                    item["options"] = new_opts[:4]
                    item["correct_answer"] = 0
                    fixed.append(item)
                except Exception:
                    fixed.append(item)
            data = fixed

        data = _ensure_question_count(data, question_type, difficulty, count)

        return data if isinstance(data, list) else []
    except Exception as e:
        logger.exception("Question generation failed: %s", e)
        return _ensure_question_count([], question_type, difficulty, count)


# ── Candidate Evaluation ─────────────────────────────────────────────────────

EVAL_SYSTEM = """You are a fair, expert technical evaluator.
Evaluate candidate submissions objectively.
Respond ONLY with a JSON object — no markdown, no extra text."""

EVAL_TEMPLATE = """Evaluate the following candidate assessment submission.

Role: {role}
Assessment Type: {types}

CODE SUBMISSIONS:
{code_block}

MCQ ANSWERS:
{mcq_block}

PROCTORING SIGNALS:
{proctor_block}

Provide scores (0–100) and brief insights. Return JSON:
{{
  "technical_score": <0-100 float>,
  "code_quality_score": <0-100 float>,
  "mcq_score": <0-100 float>,
  "behavioral_score": <0-100 float>,
  "composite_score": <0-100 float>,
  "recommendation": "strong_hire" | "hire" | "borderline" | "no_hire",
  "strengths": ["...", "..."],
  "improvements": ["...", "..."],
  "code_feedback": [{{"question": "...", "feedback": "...", "score": 0-100}}],
  "risk_flags": ["..."],
  "summary": "<2-3 sentence professional summary>"
}}"""


def evaluate_candidate(
    role: str,
    types: List[str],
    code_submissions: List[dict],
    mcq_answers: List[dict],
    proctoring_data: Optional[dict] = None,
) -> dict:
    """
    Call GPT-4o to evaluate a candidate's full submission.
    Returns structured evaluation dict.
    """
    code_block = "\n\n".join(
        f"Q: {s.get('prompt', 'N/A')}\nLanguage: {s.get('language')}\n"
        f"Test Cases Passed: {s.get('passed_cases', '?')}/{s.get('total_cases', '?')}\n"
        f"Code:\n```\n{s.get('code', '')[:1500]}\n```"
        for s in code_submissions
    ) or "No code submissions."

    mcq_block = "\n".join(
        f"Q: {m.get('prompt', 'N/A')} | Answered: {m.get('answer_index')} "
        f"| Correct: {m.get('correct_index')} | {'✓' if m.get('is_correct') else '✗'}"
        for m in mcq_answers
    ) or "No MCQ answers."

    proctor_block = json.dumps(proctoring_data or {}, indent=2)

    prompt = EVAL_TEMPLATE.format(
        role=role,
        types=", ".join(types),
        code_block=code_block,
        mcq_block=mcq_block,
        proctor_block=proctor_block,
    )

    try:
        client = _client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EVAL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        raise


# ── Adaptive Difficulty ───────────────────────────────────────────────────────

def next_question_difficulty(current_score: float) -> str:
    """IRT-inspired adaptive difficulty selection."""
    if current_score >= 0.80:
        return "hard"
    elif current_score >= 0.50:
        return "medium"
    else:
        return "easy"
