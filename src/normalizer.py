"""Normalize Youth Center API payloads into MCP-friendly objects."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional


SUMMARY_FIELD_MAP = {
    "policy_id": "plcyNo",
    "title": "plcyNm",
    "keywords": "plcyKywdNm",
    "summary": "plcyExplnCn",
    "category_major": "lclsfNm",
    "category_middle": "mclsfNm",
    "support_content": "plcySprtCn",
    "region_code": "zipCd",
    "application_period": "aplyYmd",
    "supervising_institution": "sprvsnInstCdNm",
    "last_modified_at": "lastMdfcnDt",
}


def normalize_search_response(
    payload: Mapping[str, Any], query: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert a policy list API response into the search tool output."""

    items = extract_items(payload)
    return {
        "query": dict(query),
        "count": extract_count(payload, items),
        "policies": [normalize_policy_summary(item) for item in items],
    }


def normalize_policy_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {name: _clean(item.get(source)) for name, source in SUMMARY_FIELD_MAP.items()}


def normalize_policy_detail(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a policy API row into grouped policy detail sections."""

    item = first_item(payload)
    if not item:
        return {}

    title = _clean(item.get("plcyNm"))
    policy_id = _clean(item.get("plcyNo"))
    return {
        "policy_id": policy_id,
        "basic": {
            "title": title,
            "keywords": _clean(item.get("plcyKywdNm")),
            "summary": _clean(item.get("plcyExplnCn")),
            "category_major": _clean(item.get("lclsfNm")),
            "category_middle": _clean(item.get("mclsfNm")),
            "support_content": _clean(item.get("plcySprtCn")),
            "region_code": _clean(item.get("zipCd")),
        },
        "institution": {
            "supervising_institution": _clean(item.get("sprvsnInstCdNm")),
            "operating_institution": _clean(
                first_present(item, "operInstCdNm", "operatingInstitution", "operInstNm")
            ),
            "contact": _clean(first_present(item, "inqTelNo", "picTelno", "cnsgNmor")),
            "department": _clean(first_present(item, "sprvsnInstPicNm", "picNm", "deptNm")),
        },
        "period": {
            "application_period": _clean(item.get("aplyYmd")),
            "business_period": _clean(first_present(item, "bizPrdCn", "plcyPrdCn")),
            "announcement_date": _clean(first_present(item, "ancmYmd", "pblancYmd")),
        },
        "application": {
            "method": _clean(first_present(item, "aplyMthdCn", "rqutProcCn")),
            "required_documents": _clean(first_present(item, "sbmsnDcmntCn", "pstnPaprCn")),
            "screening_method": _clean(first_present(item, "srngMthdCn", "jdgnPresCn")),
            "site": _clean(first_present(item, "aplyUrlAddr", "rqutUrla", "aplyUrl")),
            "notes": _clean(first_present(item, "etcMttrCn", "etctCn")),
        },
        "support_scale": {
            "scale": _clean(first_present(item, "sprtSclCnt", "sprtSclCn", "sprtTrgtMinAge")),
            "content": _clean(item.get("plcySprtCn")),
        },
        "eligibility": {
            "age": _clean(first_present(item, "ageInfo", "sprtTrgtAgeLmtYn", "ageLmtCn")),
            "min_age": _to_int(first_present(item, "sprtTrgtMinAge", "minAge")),
            "max_age": _to_int(first_present(item, "sprtTrgtMaxAge", "maxAge")),
            "residence": _clean(first_present(item, "zipCd", "prcpCn", "rsdRgnSeCd")),
            "income": _clean(first_present(item, "earnCndCn", "incomeCn", "earnEtcCn")),
            "education": _clean(first_present(item, "schoolCd", "accrRqisCn")),
            "major": _clean(first_present(item, "majrCd", "majrRqisCn")),
            "job": _clean(first_present(item, "jobCd", "empmSttsCn")),
            "marriage": _clean(first_present(item, "mrgSttsCd", "mrgSttsCn")),
            "special_conditions": _clean(first_present(item, "sBizCd", "splzRlmRqisCn")),
            "additional_conditions": _clean(first_present(item, "addAplyQlfcCndCn", "aditRscn")),
        },
        "condition_codes": {
            "job_code": _clean(first_present(item, "jobCd", "empmSttsCd")),
            "school_code": _clean(first_present(item, "schoolCd", "accrCd")),
            "major_code": _clean(first_present(item, "majrCd")),
            "marriage_status": _clean(first_present(item, "mrgSttsCd")),
            "special_condition_code": _clean(first_present(item, "sBizCd", "splzRlmCd")),
            "income_level": _clean(first_present(item, "earnMinAmt", "incomeLevel")),
        },
        "links": {
            "application_url": _clean(first_present(item, "aplyUrlAddr", "rqutUrla")),
            "reference_url": _clean(first_present(item, "refUrlAddr", "rfcSiteUrla1")),
        },
        "metadata": {
            "last_modified_at": _clean(item.get("lastMdfcnDt")),
            "raw_field_count": len(item),
        },
    }


def extract_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Find policy rows across common Youth Center response wrappers."""

    candidates: list[Any] = [
        payload.get("result"),
        payload.get("data"),
        payload.get("items"),
        payload.get("item"),
        payload.get("youthPolicyList"),
        payload.get("policyList"),
        payload.get("resultList"),
    ]

    for key in ("result", "data", "response", "body"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            candidates.extend(
                [
                    value.get("result"),
                    value.get("data"),
                    value.get("items"),
                    value.get("item"),
                    value.get("list"),
                    value.get("youthPolicyList"),
                    value.get("policyList"),
                    value.get("resultList"),
                ]
            )

    for candidate in candidates:
        normalized = _as_item_list(candidate)
        if normalized:
            return normalized
    if "plcyNo" in payload:
        return [payload]
    return []


def first_item(payload: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    items = extract_items(payload)
    return items[0] if items else None


def extract_count(payload: Mapping[str, Any], items: Iterable[Mapping[str, Any]]) -> int:
    sources: list[Mapping[str, Any]] = [payload]
    for wrapper_key in ("result", "data", "response", "body"):
        wrapper = payload.get(wrapper_key)
        if isinstance(wrapper, Mapping):
            sources.append(wrapper)
            for paging_key in ("pagging", "paging", "pagination", "page"):
                paging = wrapper.get(paging_key)
                if isinstance(paging, Mapping):
                    sources.append(paging)

    for source in sources:
        for key in ("totalCount", "totalCnt", "totCount", "count", "resultCnt", "totCnt"):
            value = source.get(key)
            if value is not None:
                count = _to_int(value)
                if count is not None:
                    return count
    return len(list(items))


def first_present(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_item_list(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if "plcyNo" in value:
            return [value]
        for key in ("item", "items", "list", "data", "result"):
            nested = value.get(key)
            nested_items = _as_item_list(nested)
            if nested_items:
                return nested_items
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, Mapping)]
    return []


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
