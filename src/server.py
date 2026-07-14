"""FastMCP tool definitions for Youth Center policy access."""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .eligibility import build_checklist, evaluate_policy_eligibility
from .normalizer import normalize_policy_detail, normalize_search_response
from .youth_api import YouthCenterApiError, YouthPolicyClient


settings = get_settings()
mcp = FastMCP(
    "youth-policy-mcp",
    json_response=True,
    stateless_http=True,
    host=settings.host,
    port=settings.port,
)
mcp.settings.streamable_http_path = "/mcp"


def _client() -> YouthPolicyClient:
    return YouthPolicyClient(settings)


def _error(message: str, code: str = "youth_center_api_error") -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _detail_or_error(policy_id: str) -> dict[str, Any]:
    try:
        payload = _client().get_policy_detail(policy_id)
        detail = normalize_policy_detail(payload)
        if not detail:
            return _error(f"Policy not found: {policy_id}", "not_found")
        return detail
    except YouthCenterApiError as exc:
        return _error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive MCP boundary
        return _error(f"Unexpected server error: {exc}", "unexpected_error")


@mcp.tool()
def search_youth_policies(
    keyword: Optional[str] = None,
    policy_name: Optional[str] = None,
    description_keyword: Optional[str] = None,
    region_code: Optional[str] = None,
    category_major: Optional[str] = None,
    category_middle: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Search Youth Center policies through the official youthPlcyList API."""

    query = {
        "keyword": keyword,
        "policy_name": policy_name,
        "description_keyword": description_keyword,
        "region_code": region_code,
        "category_major": category_major,
        "category_middle": category_middle,
        "page": page,
        "page_size": page_size,
    }
    try:
        payload = _client().search_policies(
            keyword=keyword,
            policy_name=policy_name,
            description_keyword=description_keyword,
            region_code=region_code,
            category_major=category_major,
            category_middle=category_middle,
            page=page,
            page_size=page_size,
        )
        return normalize_search_response(payload, query)
    except YouthCenterApiError as exc:
        return _error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive MCP boundary
        return _error(f"Unexpected server error: {exc}", "unexpected_error")


@mcp.tool()
def get_youth_policy_detail(policy_id: str) -> dict[str, Any]:
    """Find a policy detail by policy number."""

    return _detail_or_error(policy_id)


@mcp.tool()
def check_policy_eligibility(
    policy_id: str,
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
    """Pre-check likely eligibility by comparing user conditions with policy detail."""

    detail = _detail_or_error(policy_id)
    if "error" in detail:
        return detail
    return evaluate_policy_eligibility(
        detail,
        birth_date=birth_date,
        age=age,
        residence_region_code=residence_region_code,
        income_level=income_level,
        monthly_income=monthly_income,
        marriage_status=marriage_status,
        job_code=job_code,
        school_code=school_code,
        major_code=major_code,
        special_condition_code=special_condition_code,
    )


@mcp.tool()
def compare_youth_policies(
    policy_ids: list[str],
    focus: Optional[list[str]] = None,
    age: Optional[int] = None,
    residence_region_code: Optional[str] = None,
    income_level: Optional[int] = None,
) -> dict[str, Any]:
    """Compare several Youth Center policies by key application dimensions."""

    rows: list[dict[str, Any]] = []
    differences: list[str] = []
    focus_set = set(focus or [])

    for policy_id in policy_ids:
        detail = _detail_or_error(policy_id)
        if "error" in detail:
            rows.append({"policy_id": policy_id, "error": detail["error"]})
            continue

        basic = detail.get("basic", {})
        application = detail.get("application", {})
        institution = detail.get("institution", {})
        period = detail.get("period", {})
        eligibility = evaluate_policy_eligibility(
            detail,
            age=age,
            residence_region_code=residence_region_code,
            income_level=income_level,
        )
        row = {
            "policy_id": detail.get("policy_id"),
            "title": basic.get("title"),
            "support_content": basic.get("support_content"),
            "application_period": period.get("application_period"),
            "eligibility": detail.get("eligibility"),
            "eligibility_status": eligibility.get("eligibility_status"),
            "application_method": application.get("method"),
            "required_documents": application.get("required_documents"),
            "institution": institution,
        }
        if focus_set:
            row = {key: value for key, value in row.items() if key in focus_set or key in {"policy_id", "title"}}
        rows.append(row)

    _add_difference(differences, rows, "support_content", "지원 내용이 정책별로 다릅니다.")
    _add_difference(differences, rows, "application_period", "신청 기간이 정책별로 다릅니다.")
    _add_difference(differences, rows, "eligibility_status", "입력 조건 기준 예비 적합성이 다릅니다.")

    eligible_titles = [
        row.get("title") for row in rows if row.get("eligibility_status") == "likely_eligible"
    ]
    if eligible_titles:
        recommendation = f"입력 조건 기준으로는 {', '.join(str(title) for title in eligible_titles)} 정책을 우선 검토하세요."
    else:
        recommendation = "조건 정보가 부족하거나 검토가 필요한 항목이 있습니다. 신청 기간과 자격 조건을 먼저 확인하세요."

    return {
        "compared_policy_count": len([row for row in rows if "error" not in row]),
        "comparison_table": rows,
        "key_differences": differences,
        "recommendation": recommendation,
    }


@mcp.tool()
def build_policy_application_checklist(
    policy_id: str,
    include_user_specific_checks: bool = False,
    age: Optional[int] = None,
    residence_region_code: Optional[str] = None,
    income_level: Optional[int] = None,
    monthly_income: Optional[int] = None,
    job_code: Optional[str] = None,
    school_code: Optional[str] = None,
) -> dict[str, Any]:
    """Build an application preparation checklist for one policy."""

    detail = _detail_or_error(policy_id)
    if "error" in detail:
        return detail

    eligibility_result = None
    if include_user_specific_checks:
        eligibility_result = evaluate_policy_eligibility(
            detail,
            age=age,
            residence_region_code=residence_region_code,
            income_level=income_level,
            monthly_income=monthly_income,
            job_code=job_code,
            school_code=school_code,
        )
    return build_checklist(detail, eligibility_result)


def run() -> None:
    """Run the FastMCP server."""

    mcp.run(transport=settings.transport)


def _add_difference(
    differences: list[str],
    rows: list[dict[str, Any]],
    key: str,
    message: str,
) -> None:
    values = {str(row.get(key)) for row in rows if row.get(key) not in (None, "", {})}
    if len(values) > 1:
        differences.append(message)
