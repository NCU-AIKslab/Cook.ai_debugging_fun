import json
import asyncio
from .driver import build_driver_code
from .models import CaseResult, CaseStatus
from .sandbox_runner import run_in_sandbox, safe_check

async def run_judge(problem, user_code: str):
    """Main judging pipeline."""

    # Forbidden check BEFORE any testcase
    try:
        safe_check(user_code)
    except ValueError as e:
        return [
            CaseResult(
                case_id=1,
                status=CaseStatus.RE,
                input="", 
                expected="",
                actual="",
                error=str(e),
            )
        ]

    timeout_sec = max(problem.time_limit_ms / 1000.0, 1.0)
    results = []

    for idx, tc in enumerate(problem.test_cases, start=1):

        injected = build_driver_code(
            user_code=user_code,
            input_val=tc.input,
            judge_type=problem.judge_type,
            entry_point=problem.entry_point,
        )
        # Run sandbox
        try:
            outcome = await run_in_sandbox(injected, timeout_sec)
        except RuntimeError as e:
            # sandbox unavailable → system error
            return [
                CaseResult(
                    case_id=idx,
                    status=CaseStatus.RE,
                    input=str(tc.input),
                    expected="",
                    actual="",
                    error=str(e),
                )
            ]

        # Timeout
        if outcome.status == "timeout":
            results.append(
                CaseResult(
                    case_id=idx,
                    status=CaseStatus.TLE,
                    input=str(tc.input),
                    expected=str(tc.expected),
                    actual="",
                    error="Time Limit Exceeded",
                )
            )
            break

        # Runtime Error
        if outcome.status != "ok":
            results.append(
                CaseResult(
                    case_id=idx,
                    status=CaseStatus.RE,
                    input=str(tc.input),
                    expected=str(tc.expected),
                    actual=outcome.stdout.strip(),
                    error=outcome.error_text,
                )
            )
            break

        # Compare AC / WA
        expected_str = (
            tc.expected.strip()
            if isinstance(tc.expected, str)
            else json.dumps(tc.expected)
        )
        actual_str = outcome.stdout.strip()

        status = CaseStatus.AC if actual_str == expected_str else CaseStatus.WA

        results.append(
            CaseResult(
                case_id=idx,
                status=status,
                input=str(tc.input),
                expected=expected_str,
                actual=actual_str,
                error="",
            )
        )

    return results


def compute_verdict(results, total_cases):
    """Compute final verdict from case results."""
    if not results:
        return "System Error"

    # Priority order
    for st, label in [
        (CaseStatus.TLE, "Time Limit Exceeded"),
        (CaseStatus.RE, "Runtime Error"),
        (CaseStatus.WA, "Wrong Answer"),
    ]:
        if any(r.status == st for r in results):
            return label

    if len(results) == total_cases and all(r.status == CaseStatus.AC for r in results):
        return "Accepted"

    return "Judged"