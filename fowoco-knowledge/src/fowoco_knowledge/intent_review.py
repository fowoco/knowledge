from __future__ import annotations

import re
from typing import Any

BOUNDARY_PATTERNS = {
    "PAYROLL_ACCOUNT": re.compile(r"급여\s*계좌|급여계좌|통장\s*사본|계좌\s*(개설|변경|등록|정보)"),
    "LEAVE_BOUNDARY": re.compile(r"휴가|연차|병가"),
    "COMPLETED_STATUS": re.compile(
        r"완료|처리됨|끝났|끝남|이미\s*(답변|처리|첨부|제출)|"
        r"별도\s*지시\s*없|변경\s*없|그대로\s*유지|자동\s*반영"
    ),
    "EXTERNAL_EXECUTION": re.compile(
        r"접수|신고|출입국|고용센터|기관|홈페이지|"
        r"자동\s*(제출|접수|처리|신고)|신청\s*(해|진행|접수)|"
        r"제출\s*(해|완료|처리)"
    ),
}

BOUNDARY_FLAG_ORDER = [
    "PAYROLL_ACCOUNT",
    "LEAVE_BOUNDARY",
    "COMPLETED_STATUS",
    "EXTERNAL_EXECUTION",
    "LONG_EVIDENCE",
]

HIGH_PRIORITY_FLAGS = {
    "PAYROLL_ACCOUNT",
    "COMPLETED_STATUS",
    "EXTERNAL_EXECUTION",
}

LONG_EVIDENCE_MIN_CHARS = 24


def select_boundary_flags(case: dict[str, Any]) -> list[str]:
    hr_input = case["hr_input"]
    flags = [flag for flag, pattern in BOUNDARY_PATTERNS.items() if pattern.search(hr_input)]
    if any(
        isinstance(item.get("evidence"), str) and len(item["evidence"]) >= LONG_EVIDENCE_MIN_CHARS
        for item in case["intents"]
    ):
        flags.append("LONG_EVIDENCE")
    return [flag for flag in BOUNDARY_FLAG_ORDER if flag in flags]


def review_priority(flags: list[str]) -> str:
    return "HIGH" if HIGH_PRIORITY_FLAGS.intersection(flags) else "MEDIUM"


def review_case_id(source_record_id: int) -> str:
    return f"INT-RVW-{source_record_id:04d}"
