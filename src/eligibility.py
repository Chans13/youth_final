"""Preliminary policy eligibility checks."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional


DISCLAIMER = (
    "이 결과는 온통청년 API의 공개 조건과 사용자가 입력한 정보를 단순 비교한 예비 판단입니다. "
    "최종 신청 가능 여부는 반드시 정책 공고문과 담당 기관을 통해 확인해야 합니다."
)


def evaluate_policy_eligibility(
    detail: Mapping[str, Any],
    *,
    birth_date: Optional[str] = None,
    age: Optional[int] = None,
    residence_region_code: Optional[str] = None,
    income_level: Optional[int] = None,
    monthly_income: Optional[int] = None,
    marriage_status: Optional[str] = None,
    job_code: Optional[str] = None,
    school_code: Optional[str] = None,
    major_code: Optional[str] = None,
    special_condition_code: Optional[str] = None,
) -> dict[str, Any]:
    """Compare user-provided conditions against normalized policy detail."""

    basic = _dict(detail.get("basic"))
    eligibility = _dict(detail.get("eligibility"))
    condition_codes = _dict(detail.get("condition_codes"))
    period = _dict(detail.get("period"))

    computed_age = age if age is not None else age_from_birth_date(birth_date)
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    missing: list[str] = []

    min_age = _to_int(eligibility.get("min_age"))
    max_age = _to_int(eligibility.get("max_age"))
    if min_age is not None or max_age is not None:
        if computed_age is None:
            missing.append("age 또는 birth_date")
        elif min_age is not None and computed_age < min_age:
            unmatched.append(_condition("age", computed_age, f"{min_age}세 이상"))
        elif max_age is not None and computed_age > max_age:
            unmatched.append(_condition("age", computed_age, f"{max_age}세 이하"))
        else:
            matched.append(_condition("age", computed_age, _age_label(min_age, max_age)))
    elif eligibility.get("age"):
        uncertain.append(_condition("age", computed_age, eligibility.get("age")))

    _compare_code(
        "residence_region_code",
        residence_region_code,
        eligibility.get("residence") or basic.get("region_code"),
        matched,
        unmatched,
        uncertain,
        missing,
        allow_prefix=True,
    )
    _compare_numeric_or_text(
        "income_level",
        income_level,
        condition_codes.get("income_level") or eligibility.get("income"),
        matched,
        unmatched,
        uncertain,
        missing,
    )
    _compare_text_presence(
        "monthly_income",
        monthly_income,
        eligibility.get("income"),
        matched,
        uncertain,
        missing,
    )
    _compare_code(
        "marriage_status",
        marriage_status,
        condition_codes.get("marriage_status") or eligibility.get("marriage"),
        matched,
        unmatched,
        uncertain,
        missing,
    )
    _compare_code(
        "job_code",
        job_code,
        condition_codes.get("job_code") or eligibility.get("job"),
        matched,
        unmatched,
        uncertain,
        missing,
    )
    _compare_code(
        "school_code",
        school_code,
        condition_codes.get("school_code") or eligibility.get("education"),
        matched,
        unmatched,
        uncertain,
        missing,
    )
    _compare_code(
        "major_code",
        major_code,
        condition_codes.get("major_code") or eligibility.get("major"),
        matched,
        unmatched,
        uncertain,
        missing,
    )
    _compare_code(
        "special_condition_code",
        special_condition_code,
        condition_codes.get("special_condition_code") or eligibility.get("special_conditions"),
        matched,
        unmatched,
        uncertain,
        missing,
    )

    if unmatched:
        status = "not_eligible"
        summary = "입력 조건 중 정책 조건과 명확히 맞지 않는 항목이 있습니다."
    elif not matched and (missing or uncertain):
        status = "insufficient_information"
        summary = "판단에 필요한 사용자 정보가 부족하거나 정책 조건이 텍스트로만 제공됩니다."
    elif uncertain or missing:
        status = "needs_review"
        summary = "일부 조건은 담당 기관 또는 공고문 확인이 필요합니다."
    else:
        status = "likely_eligible"
        summary = "입력된 조건 기준으로는 신청 가능성이 있어 보입니다."

    return {
        "policy_id": detail.get("policy_id"),
        "policy_title": basic.get("title"),
        "eligibility_status": status,
        "summary": summary,
        "matched_conditions": matched,
        "unmatched_conditions": unmatched,
        "uncertain_conditions": uncertain,
        "missing_user_information": missing,
        "important_policy_conditions": {
            "eligibility": eligibility,
            "condition_codes": condition_codes,
            "period": period,
        },
        "disclaimer": DISCLAIMER,
    }


def age_from_birth_date(value: Optional[str], today: Optional[date] = None) -> Optional[int]:
    if not value:
        return None
    today = today or date.today()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            born = datetime.strptime(value, fmt).date()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            continue
    return None


def build_checklist(
    detail: Mapping[str, Any],
    eligibility_result: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    basic = _dict(detail.get("basic"))
    application = _dict(detail.get("application"))
    period = _dict(detail.get("period"))
    eligibility = _dict(detail.get("eligibility"))
    institution = _dict(detail.get("institution"))

    checklist = [
        _check("신청 기간 확인", period.get("application_period"), "period"),
        _check("지원 내용 확인", basic.get("support_content"), "support"),
        _check("신청 자격 확인", eligibility, "eligibility"),
        _check("신청 방법 확인", application.get("method"), "application"),
        _check("제출 서류 준비", application.get("required_documents"), "documents"),
        _check("유의사항 확인", application.get("notes"), "notes"),
    ]

    warnings: list[str] = []
    if not period.get("application_period"):
        warnings.append("API 응답에 신청 기간 정보가 없으므로 공고문 확인이 필요합니다.")
    if not application.get("required_documents"):
        warnings.append("제출 서류 정보가 비어 있습니다. 신청 전 담당 기관에 확인하세요.")
    if eligibility_result:
        status = eligibility_result.get("eligibility_status")
        if status in ("not_eligible", "needs_review", "insufficient_information"):
            warnings.append(str(eligibility_result.get("summary")))

    return {
        "policy_id": detail.get("policy_id"),
        "policy_title": basic.get("title"),
        "application_summary": {
            "period": period.get("application_period"),
            "method": application.get("method"),
            "required_documents": application.get("required_documents"),
        },
        "checklist": checklist,
        "warnings": [warning for warning in warnings if warning],
        "contact": {
            "institution": institution.get("supervising_institution"),
            "department": institution.get("department"),
            "phone": institution.get("contact"),
        },
        "links": detail.get("links") or {},
    }


def _compare_code(
    name: str,
    user_value: Optional[str],
    policy_value: Any,
    matched: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    uncertain: list[dict[str, Any]],
    missing: list[str],
    *,
    allow_prefix: bool = False,
) -> None:
    if not policy_value:
        return
    policy_text = str(policy_value)
    if _looks_like_free_text(policy_text):
        uncertain.append(_condition(name, user_value, policy_text))
        return
    if user_value in (None, ""):
        missing.append(name)
        return
    user_text = str(user_value)
    policy_tokens = _tokens(policy_text)
    if user_text in policy_tokens or (allow_prefix and any(user_text.startswith(token) for token in policy_tokens)):
        matched.append(_condition(name, user_value, policy_text))
    else:
        unmatched.append(_condition(name, user_value, policy_text))


def _compare_numeric_or_text(
    name: str,
    user_value: Optional[int],
    policy_value: Any,
    matched: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    uncertain: list[dict[str, Any]],
    missing: list[str],
) -> None:
    if not policy_value:
        return
    policy_number = _to_int(policy_value)
    if user_value is None:
        missing.append(name)
        return
    if policy_number is None:
        uncertain.append(_condition(name, user_value, policy_value))
    elif user_value <= policy_number:
        matched.append(_condition(name, user_value, policy_value))
    else:
        unmatched.append(_condition(name, user_value, policy_value))


def _compare_text_presence(
    name: str,
    user_value: Optional[int],
    policy_text: Any,
    matched: list[dict[str, Any]],
    uncertain: list[dict[str, Any]],
    missing: list[str],
) -> None:
    if not policy_text:
        return
    if user_value is None:
        missing.append(name)
    else:
        uncertain.append(_condition(name, user_value, policy_text))


def _check(title: str, source: Any, category: str) -> dict[str, Any]:
    return {
        "category": category,
        "title": title,
        "status": "todo",
        "detail": source or "API 응답에 상세 정보가 없습니다. 공고문 또는 담당 기관 확인이 필요합니다.",
    }


def _condition(name: str, user_value: Any, policy_value: Any) -> dict[str, Any]:
    return {"condition": name, "user_value": user_value, "policy_value": policy_value}


def _tokens(value: str) -> set[str]:
    separators = [",", "|", "/", " ", ";"]
    normalized = value
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    return {token.strip() for token in normalized.split(",") if token.strip()}


def _looks_like_free_text(value: str) -> bool:
    return any(ch in value for ch in "가나다라마바사아자차카타파하") or len(value) > 20


def _age_label(min_age: Optional[int], max_age: Optional[int]) -> str:
    if min_age is not None and max_age is not None:
        return f"{min_age}세 이상 {max_age}세 이하"
    if min_age is not None:
        return f"{min_age}세 이상"
    if max_age is not None:
        return f"{max_age}세 이하"
    return "연령 조건"


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None

