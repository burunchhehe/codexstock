from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


JSON_MEDIA_TYPES = frozenset({"application/json", "application/problem+json"})


@dataclass(frozen=True)
class RequestRejection:
    status: int
    error: str
    message: str

    def as_payload(self) -> dict[str, object]:
        return {"ok": False, "error": self.error, "message": self.message, "request_blocked": True, "real_order_allowed": False}


def _header(headers: Mapping[str, str], name: str) -> str:
    return str(headers.get(name, "") or "").strip()


def _origin_matches_host(origin: str, host: str) -> bool:
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower().rstrip(".") == host.lower().rstrip(".")


def validate_local_api_write(path: str, headers: Mapping[str, str], *, body_length: int) -> RequestRejection | None:
    if not path.startswith("/api/"):
        return None
    content_type = _header(headers, "Content-Type").split(";", 1)[0].strip().lower()
    if body_length > 0 and content_type not in JSON_MEDIA_TYPES:
        return RequestRejection(415, "json_content_type_required", "로컬 API 변경 요청은 application/json 형식만 허용합니다.")
    if path.startswith("/api/mobile/"):
        return None
    if _header(headers, "Sec-Fetch-Site").lower() in {"cross-site", "none"}:
        return RequestRejection(403, "cross_site_request_blocked", "다른 웹사이트에서 보낸 로컬 API 변경 요청을 차단했습니다.")
    origin = _header(headers, "Origin")
    host = _header(headers, "Host")
    if origin and (not host or not _origin_matches_host(origin, host)):
        return RequestRejection(403, "origin_not_allowed", "코덱스스톡 화면과 출처가 다른 변경 요청을 차단했습니다.")
    return None
