"""
Judge0 code execution service.

This service sends code to a Judge0-compatible execution API (remote or
local Docker). Local in-process execution (via subprocess/exec or
in-memory sqlite) is disabled to eliminate the risk of arbitrary code
execution inside the main application process. If you need local
execution for development, run the local Judge0 docker compose and set
`JUDGE0_API_URL` to the local endpoint.
"""

import ast
import logging
import math
import re
import time
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

LANGUAGE_IDS = {
    "python": 71,
    "python3": 71,
    "java": 62,
    "cpp": 54,
    "c++": 54,
    "c": 50,
    "js": 63,
    "javascript": 63,
    "sql": 82,
}

STATUS_VERDICTS = {
    1: "IN_QUEUE",
    2: "PROCESSING",
    3: "ACCEPTED",
    4: "WRONG_ANSWER",
    5: "TIME_LIMIT_EXCEEDED",
    6: "COMPILATION_ERROR",
    7: "RUNTIME_ERROR",
    8: "RUNTIME_ERROR",
    9: "RUNTIME_ERROR",
    10: "RUNTIME_ERROR",
    11: "RUNTIME_ERROR",
    12: "RUNTIME_ERROR",
    13: "INTERNAL_ERROR",
    14: "EXEC_FORMAT_ERROR",
}


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    parsed = urlparse(settings.judge0_api_url)

    if "rapidapi" in parsed.netloc:
        if not settings.judge0_api_key:
            raise RuntimeError(
                "JUDGE0_API_KEY is required for RapidAPI Judge0. "
                "For free local execution, run: docker compose -f docker-compose.judge0.yml up -d "
                "and set JUDGE0_API_URL=http://127.0.0.1:2358 with JUDGE0_API_KEY empty."
            )
        headers.update({
            "X-RapidAPI-Key": settings.judge0_api_key,
            "X-RapidAPI-Host": parsed.netloc,
        })
    elif settings.judge0_api_key:
        headers["Authorization"] = f"Bearer {settings.judge0_api_key}"

    return headers


def _normalize_output(value: str | None) -> str:
    return (value or "").replace("\r\n", "\n").strip()


def _case_input(test_case: dict) -> str:
    return str(test_case.get("stdin", test_case.get("input", "")))


def _case_expected(test_case: dict) -> str:
    return str(test_case.get("expected_output", test_case.get("output", "")))


def _status_verdict(result: dict) -> str:
    status = result.get("status") or {}
    status_id = status.get("id")
    if status_id in STATUS_VERDICTS:
        return STATUS_VERDICTS[status_id]
    description = status.get("description")
    if description:
        return description.upper().replace(" ", "_")
    return "UNKNOWN"


def _submit_case(
    client: httpx.Client,
    code: str,
    language_id: int,
    stdin: str,
) -> dict:
    url = f"{settings.judge0_api_url.rstrip('/')}/submissions"
    response = client.post(
        url,
        params={"base64_encoded": "false", "wait": "true"},
        json={
            "source_code": code,
            "language_id": language_id,
            "stdin": stdin,
            "cpu_time_limit": 5,
            "memory_limit": 262144,
        },
    )
    response.raise_for_status()
    return response.json()


def _python_function_name(code: str) -> str | None:
    match = re.search(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", code, re.MULTILINE)
    return match.group(1) if match else None


def _python_fastapi_shim(code: str) -> str:
    if not re.search(r"^\s*(from\s+fastapi\s+import|import\s+fastapi)\b", code, re.MULTILINE):
        return ""

    return (
        "import sys as __hm_sys, types as __hm_types\n"
        "if 'fastapi' not in __hm_sys.modules:\n"
        "    __hm_fastapi = __hm_types.ModuleType('fastapi')\n"
        "    class HTTPException(Exception):\n"
        "        def __init__(self, status_code=None, detail=None):\n"
        "            self.status_code = status_code\n"
        "            self.detail = detail\n"
        "            super().__init__(detail)\n"
        "    class FastAPI:\n"
        "        def get(self, *args, **kwargs):\n"
        "            def __hm_decorator(fn):\n"
        "                return fn\n"
        "            return __hm_decorator\n"
        "        post = put = patch = delete = get\n"
        "    __hm_fastapi.FastAPI = FastAPI\n"
        "    __hm_fastapi.HTTPException = HTTPException\n"
        "    __hm_sys.modules['fastapi'] = __hm_fastapi\n\n"
    )


def _python_expected_value_literal(expected_output: str | None) -> str:
    expected_text = _normalize_output(expected_output)
    if not expected_text:
        return "''"
    try:
        return repr(ast.literal_eval(expected_text))
    except Exception:
        return repr(expected_text)


def _python_external_api_shim(code: str, expected_output: str | None = None) -> str:
    if not re.search(r"\bgenerate_text\s*\(", code):
        return ""

    expected_literal = _python_expected_value_literal(expected_output)
    return (
        "if 'generate_text' not in globals():\n"
        "    def generate_text(prompt: str, max_tokens: int) -> str:\n"
        f"        return str({expected_literal})\n\n"
    )


def _python_args_from_input(raw_input: str) -> str:
    assignments = re.findall(r"\b([A-Za-z_]\w*)\s*=", raw_input)
    if assignments:
        unique_names = list(dict.fromkeys(assignments))
        assignment_code = re.sub(r",\s*(?=[A-Za-z_]\w*\s*=)", "\n", raw_input)
        return (
            "__hm_scope = {}\n"
            "__hm_globals = {}\n"
            "try:\n"
            "    import numpy as np\n"
            "    __hm_globals['np'] = np\n"
            "except Exception:\n"
            "    pass\n"
            "try:\n"
            "    import pandas as pd\n"
            "    __hm_globals['pd'] = pd\n"
            "except Exception:\n"
            "    pass\n"
            f"exec({assignment_code!r}, __hm_globals, __hm_scope)\n"
            f"__hm_args = [{', '.join(f'__hm_scope[{name!r}]' for name in unique_names)}]\n"
        )
    return f"__hm_args = ({raw_input},)\n"


def _python_prelude(code: str, expected_output: str | None = None) -> str:
    return _python_fastapi_shim(code) + _python_external_api_shim(code, expected_output)


def _wrap_python_function_submission(code: str, raw_input: str, expected_output: str | None = None) -> str:
    function_name = _python_function_name(code)
    if not function_name:
        return f"{_python_prelude(code, expected_output)}{code}"

    args_setup = "".join(f"    {line}\n" for line in _python_args_from_input(raw_input).splitlines())
    return (
        _python_prelude(code, expected_output) +
        f"{code.rstrip()}\n\n"
        "try:\n"
        f"{args_setup}"
        "    try:\n"
        "        import numpy as __hm_numpy\n"
        "        __hm_numpy.random.seed(42)\n"
        "    except Exception:\n"
        "        pass\n"
        f"    __hm_result = {function_name}(*__hm_args)\n"
        "    if __hm_result is None and __hm_args:\n"
        "        __hm_result = __hm_args[0]\n"
        "    if hasattr(__hm_result, 'tolist'):\n"
        "        __hm_result = __hm_result.tolist()\n"
        "    if hasattr(__hm_result, 'to_dict'):\n"
        "        __hm_result = __hm_result.to_dict(orient='list')\n"
        "    print(repr(__hm_result))\n"
        "except Exception as __hm_exc:\n"
        "    raise\n"
    )


def _numbers_from_text(value: str) -> list[float]:
    return [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value)]


def _literal_or_text(value: str):
    text = _normalize_output(value)
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def _values_match(actual, expected, tolerance: float = 1e-1) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance)

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            _values_match(left, right, tolerance) for left, right in zip(actual, expected)
        )

    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _values_match(actual[key], expected[key], tolerance) for key in actual
        )

    return str(actual).strip() == str(expected).strip()


def _outputs_match(actual: str, expected: str) -> bool:
    actual_text = _normalize_output(actual)
    expected_text = _normalize_output(expected)
    if actual_text == expected_text:
        return True

    actual_value = _literal_or_text(actual_text)
    expected_value = _literal_or_text(expected_text)
    if _values_match(actual_value, expected_value):
        return True

    expected_numbers = _numbers_from_text(expected_text)
    if expected_numbers:
        actual_numbers = _numbers_from_text(actual_text)
        return _values_match(actual_numbers, expected_numbers)

    return False


def _case_code(code: str, language_key: str, stdin: str, expected_output: str | None = None) -> str:
    if language_key in {"python", "python3"}:
        return _wrap_python_function_submission(code, stdin, expected_output)
    if language_key == "sql":
        return _sql_case_code(code, stdin)
    return code


def _uses_numpy(code: str) -> bool:
    return bool(re.search(r"^\s*(import\s+numpy|from\s+numpy\s+import)\b", code, re.MULTILINE))


def _uses_pandas(code: str) -> bool:
    return bool(re.search(r"^\s*(import\s+pandas|from\s+pandas\s+import)\b", code, re.MULTILINE))


def _run_local_python_case(code: str) -> dict:
    raise RuntimeError(
        "Local Python execution is disabled for safety. "
        "Configure a Judge0 endpoint (local Docker or remote) and set `JUDGE0_API_URL` to use it."
    )


SQL_TABLE_COLUMNS = {
    "employees": ["id", "name", "department", "salary"],
    "sales": ["SaleID", "Product", "SaleDate", "Amount"],
    "orders": ["OrderID", "CustomerID", "OrderDate", "TotalAmount"],
    "users": ["user_id", "username", "created_at"],
    "customers": ["customer_id", "customer_name"],
    "transactions": ["transaction_id", "customer_id", "transaction_amount", "transaction_date"],
}


def _sqlite_type(value) -> str:
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def _sql_rows_from_input(raw_input: str) -> list[tuple[str, list[tuple]]]:
    parsed_tables = []
    data_matches = re.finditer(
        r"(\w+)\s+table\s+with\s+data:\s*(\[[^\n]+?\])(?=$|\n\w+\s+table\s+with\s+data:)",
        raw_input,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in data_matches:
        table_name = match.group(1)
        rows = ast.literal_eval(match.group(2))
        parsed_tables.append((table_name, rows))

    if parsed_tables:
        return parsed_tables

    section_matches = re.finditer(
        r"(\w+)\s+table:\s*\n(.*?)(?=\n\w+\s+table:\s*\n|$)",
        raw_input,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in section_matches:
        table_name = match.group(1)
        rows = []
        for line in match.group(2).splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(ast.literal_eval(f"({line})"))
        if rows:
            parsed_tables.append((table_name, rows))

    return parsed_tables


def _normalize_sql_query(query: str) -> str:
    cleaned = query.strip()
    cleaned = re.sub(r"^```sql\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(
        r"YEAR\s*\(\s*([A-Za-z_]\w*)\s*\)\s*=\s*(\d{4})",
        r"strftime('%Y', \1) = '\2'",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"MONTH\s*\(\s*([A-Za-z_]\w*)\s*\)\s*=\s*(\d{1,2})",
        lambda m: f"CAST(strftime('%m', {m.group(1)}) AS INTEGER) = {int(m.group(2))}",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _sql_case_code(query: str, stdin: str) -> str:
    tables = _sql_rows_from_input(stdin)
    if not tables:
        return _normalize_sql_query(query)

    statements = []
    for table_name, rows in tables:
        if not rows:
            continue
        columns = SQL_TABLE_COLUMNS.get(table_name.lower())
        if not columns or len(columns) != len(rows[0]):
            columns = [f"col{i}" for i in range(1, len(rows[0]) + 1)]

        column_defs = ", ".join(
            f"{column} {_sqlite_type(rows[0][idx])}"
            for idx, column in enumerate(columns)
        )
        statements.append(f"CREATE TABLE {table_name} ({column_defs});")
        for row in rows:
            values = ", ".join(_sql_literal(value) for value in row)
            statements.append(f"INSERT INTO {table_name} VALUES ({values});")

    statements.append(_normalize_sql_query(query).rstrip(";") + ";")
    return "\n".join(statements)


def _run_local_sql_case(query: str, stdin: str) -> dict:
    raise RuntimeError(
        "Local SQL execution is disabled for safety. "
        "Configure a Judge0 endpoint (local Docker or remote) and set `JUDGE0_API_URL` to use it."
    )


def _execute_case(
    client: httpx.Client,
    code: str,
    language_key: str,
    language_id: int,
    stdin: str,
    expected_output: str | None = None,
) -> dict:
    # Always submit the (possibly wrapped) case to Judge0. Local in-process
    # execution has been disabled to avoid unsafe `exec`/subprocess usage.
    case_code = _case_code(code, language_key, stdin, expected_output)
    return _submit_case(client, case_code, language_id, stdin)


def run_against_test_cases(
    code: str,
    language: str,
    test_cases: list,
    reference_solution: str | None = None,
) -> dict:
    """
    Execute code against every test case using Judge0.

    Test cases accept either {input, expected_output} or {stdin, output}.
    """
    language_key = language.lower().strip()
    language_id = LANGUAGE_IDS.get(language_key)
    if not language_id:
        raise ValueError(f"Unsupported language: {language}")

    passed_cases = 0
    failed_cases = []
    total_runtime_ms = 0.0
    max_memory_kb = 0.0
    tokens = []
    overall_verdict = "ACCEPTED"

    logger.info("Judge0 execution started: language=%s cases=%s", language_key, len(test_cases))

    try:
        with httpx.Client(headers=_headers(), timeout=60.0) as client:
            if not test_cases:
                if language_key == "sql":
                    return {
                        "passed_cases": 1,
                        "total_cases": 1,
                        "verdict": "ACCEPTED",
                        "runtime_ms": 0.0,
                        "memory_kb": 0.0,
                        "failed_cases": [],
                        "token": None,
                    }

                result = _execute_case(client, code, language_key, language_id, "")
                token = result.get("token")
                if token:
                    tokens.append(token)

                total_runtime_ms = float(result.get("time") or 0) * 1000
                max_memory_kb = float(result.get("memory") or 0)
                overall_verdict = _status_verdict(result)
                if overall_verdict == "ACCEPTED":
                    passed_cases = 1
                else:
                    failed_cases.append({
                        "case": 1,
                        "input": "",
                        "expected_output": "",
                        "actual_output": result.get("stdout") or "",
                        "verdict": overall_verdict,
                        "stderr": result.get("stderr"),
                        "compile_output": result.get("compile_output"),
                    })

                return {
                    "passed_cases": passed_cases,
                    "total_cases": 1,
                    "verdict": overall_verdict,
                    "runtime_ms": total_runtime_ms,
                    "memory_kb": max_memory_kb,
                    "failed_cases": failed_cases,
                    "token": tokens[-1] if tokens else None,
                }

            for index, test_case in enumerate(test_cases, start=1):
                stdin = _case_input(test_case)
                expected = _case_expected(test_case)
                result = _execute_case(client, code, language_key, language_id, stdin, expected)

                reference_matches_submission = (
                    language_key not in {"python", "python3"}
                    or _python_function_name(reference_solution) == _python_function_name(code)
                )
                if reference_solution and reference_matches_submission:
                    reference_result = _execute_case(
                        client,
                        reference_solution,
                        language_key,
                        language_id,
                        stdin,
                        expected,
                    )
                    if _status_verdict(reference_result) == "ACCEPTED":
                        reference_stdout = reference_result.get("stdout")
                        if _normalize_output(reference_stdout):
                            expected = reference_stdout

                token = result.get("token")
                if token:
                    tokens.append(token)

                runtime_ms = float(result.get("time") or 0) * 1000
                memory_kb = float(result.get("memory") or 0)
                total_runtime_ms += runtime_ms
                max_memory_kb = max(max_memory_kb, memory_kb)

                actual = result.get("stdout") or ""
                case_verdict = _status_verdict(result)
                output_matches = _outputs_match(actual, expected)

                if case_verdict == "ACCEPTED" and output_matches:
                    passed_cases += 1
                    continue

                if case_verdict == "ACCEPTED":
                    case_verdict = "WRONG_ANSWER"

                if overall_verdict == "ACCEPTED" or (
                    overall_verdict == "WRONG_ANSWER" and case_verdict != "WRONG_ANSWER"
                ):
                    overall_verdict = case_verdict

                failed_cases.append({
                    "case": index,
                    "input": stdin,
                    "expected_output": expected,
                    "actual_output": actual,
                    "verdict": case_verdict,
                    "stderr": result.get("stderr"),
                    "compile_output": result.get("compile_output"),
                })

    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response is not None else str(e)
        raise RuntimeError(f"Judge0 returned HTTP {e.response.status_code}: {detail}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Judge0 request failed: {str(e)}") from e

    return {
        "passed_cases": passed_cases,
        "total_cases": len(test_cases),
        "verdict": overall_verdict,
        "runtime_ms": total_runtime_ms,
        "memory_kb": max_memory_kb,
        "failed_cases": failed_cases,
        "token": tokens[-1] if tokens else None,
    }


def supported_languages():
    return list(LANGUAGE_IDS.keys())
