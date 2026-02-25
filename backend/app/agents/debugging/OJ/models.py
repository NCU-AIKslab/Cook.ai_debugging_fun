from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel

class CaseStatus(str, Enum):
    AC = "AC"
    WA = "WA"
    RE = "RE"
    TLE = "TLE"


@dataclass
class TestCase:
    input: Any
    expected: Any


@dataclass
class ProblemConfig:
    problem_id: str
    judge_type: str           # "stdio" or "function"
    entry_point: Optional[str]
    time_limit_ms: int
    test_cases: list
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None
    test_cases: list


@dataclass
class ExecutionOutcome:
    status: str              # ok / error / timeout / kernel_error
    stdout: str
    error_text: str


@dataclass
class CaseResult:
    case_id: int
    status: CaseStatus
    input: Any
    expected: str
    actual: str
    error: Optional[str] = None

    def as_dict(self):
        return {
            "case_id": self.case_id,
            "status": self.status.value,
            "input": self.input,
            "expected": self.expected,
            "actual": self.actual,
            "error": self.error,
        }

class CodePayload(BaseModel):
    problem_id: str
    student_id: str
    code: str
    is_teacher: bool = False
