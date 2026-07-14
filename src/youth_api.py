"""HTTP client for the Ontong Youth Center Open API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import httpx

from .config import Settings


class YouthCenterApiError(Exception):
    """Raised when the upstream Youth Center API cannot be queried."""


@dataclass(frozen=True)
class YouthPolicyClient:
    """Small synchronous HTTP client supporting both Youth Center API formats."""

    settings: Settings

    @property
    def uses_new_api(self) -> bool:
        path = urlparse(self.settings.youth_center_api_url).path.lower()
        return "/go/ythip/getplcy" in path

    def request(self, params: Mapping[str, Any]) -> dict[str, Any]:
        if not self.settings.open_api_key:
            raise YouthCenterApiError(
                "Youth Center API key is not set. Configure OPEN_API_KEY "
                "(or YOUTH_CENTER_API_KEY) in the deployed container environment."
            )

        key_name = "apiKeyNm" if self.uses_new_api else "openApiVlak"
        query = {
            key_name: self.settings.open_api_key,
            **_without_empty_values(params),
        }

        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = client.get(self.settings.youth_center_api_url, params=query)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = _safe_response_preview(exc.response)
            raise YouthCenterApiError(
                "Youth Center API returned "
                f"HTTP {exc.response.status_code} from "
                f"{self.settings.youth_center_api_url}. Response: {body}"
            ) from exc
        except httpx.RequestError as exc:
            raise YouthCenterApiError(
                "Youth Center API request failed for "
                f"{self.settings.youth_center_api_url}: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise YouthCenterApiError(
                "Youth Center API returned a non-JSON response "
                f"(HTTP {response.status_code}, "
                f"content-type={response.headers.get('content-type', 'unknown')}). "
                f"Response: {_safe_response_preview(response)}"
            ) from exc

        if not isinstance(payload, dict):
            raise YouthCenterApiError(
                "Youth Center API returned an unexpected JSON shape: "
                f"{type(payload).__name__}"
            )

        api_error = _extract_api_error(payload)
        if api_error:
            raise YouthCenterApiError(f"Youth Center API rejected the request: {api_error}")

        return payload

    def search_policies(
        self,
        *,
        keyword: Optional[str] = None,
        policy_name: Optional[str] = None,
        description_keyword: Optional[str] = None,
        region_code: Optional[str] = None,
        category_major: Optional[str] = None,
        category_middle: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)

        if self.uses_new_api:
            return self.request(
                {
                    "pageNum": page,
                    "pageSize": page_size,
                    "pageType": 1,
                    "rtnType": "json",
                    "plcyKywdNm": keyword,
                    "plcyNm": policy_name,
                    "plcyExplnCn": description_keyword,
                    "rgnCd": region_code,
                    "plcyTypeCd": category_major,
                    "wlfareTyCd": category_middle,
                }
            )

        # Legacy OPEN API documented at /opi/youthPlcyList.do
        query_text = policy_name or description_keyword
        return self.request(
            {
                "pageIndex": page,
                "display": page_size,
                "query": query_text,
                "keyword": keyword,
                "bizTycdSel": category_major,
                "srchPolyBizSecd": region_code,
            }
        )

    def get_policy_detail(self, policy_id: str) -> dict[str, Any]:
        if self.uses_new_api:
            payload = self.request(
                {
                    "pageNum": 1,
                    "pageSize": 10,
                    "pageType": 1,
                    "rtnType": "json",
                    "plcyNo": policy_id,
                }
            )
        else:
            payload = self.request(
                {
                    "pageIndex": 1,
                    "display": 10,
                    "srchPolicyId": policy_id,
                }
            )

        items = _extract_items(payload)
        for item in items:
            if str(item.get("plcyNo", "")).strip() == policy_id:
                return dict(item)
        if len(items) == 1:
            return dict(items[0])
        return {}


def _without_empty_values(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


def _safe_response_preview(response: httpx.Response, limit: int = 500) -> str:
    try:
        text = response.text
    except Exception:
        return "<unreadable response body>"
    text = " ".join(text.split())
    return text[:limit] if text else "<empty body>"


def _extract_api_error(payload: Mapping[str, Any]) -> Optional[str]:
    """Extract common HTTP-200 API error payloads without treating empty results as errors."""

    candidates: list[Mapping[str, Any]] = [payload]
    for key in ("result", "response", "header"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)
            header = value.get("header")
            if isinstance(header, Mapping):
                candidates.append(header)

    for candidate in candidates:
        code = _first_present(
            candidate,
            "resultCode",
            "resultCd",
            "errorCode",
            "errCd",
            "code",
        )
        message = _first_present(
            candidate,
            "resultMessage",
            "resultMsg",
            "errorMessage",
            "errMsg",
            "message",
        )
        if code is None and message is None:
            continue

        normalized_code = str(code).strip().lower() if code is not None else ""
        # Common success values. A message alone is only considered an error when it
        # clearly indicates failure, so normal metadata does not become an exception.
        if normalized_code in {"", "0", "00", "0000", "success", "ok", "200"}:
            if message and any(
                token in str(message).lower()
                for token in ("error", "fail", "invalid", "denied", "오류", "실패", "유효하지")
            ):
                return str(message)
            continue
        return f"code={code}, message={message or 'no message'}"
    return None


def _first_present(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
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
        items = _as_item_list(candidate)
        if items:
            return items
    if "plcyNo" in payload:
        return [payload]
    return []


def _as_item_list(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if "plcyNo" in value:
            return [value]
        for key in ("item", "items", "list", "data", "result", "youthPolicyList"):
            nested_items = _as_item_list(value.get(key))
            if nested_items:
                return nested_items
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, Mapping)]
    return []
