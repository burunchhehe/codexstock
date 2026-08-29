from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar


SYNTHETIC_WARNING_KO = (
    "이 결과는 코덱스스톡이 생성한 합성 가격을 사용한 연구·화면 점검용 결과입니다. "
    "실제 시장 성과나 실주문 근거로 사용할 수 없습니다."
)


def attach_data_contract(payload: dict[str, Any], *, data_mode: str, source: str, real_order_allowed: bool, warning: str = "") -> dict[str, Any]:
    payload["data_mode"] = data_mode
    payload["source"] = source
    payload["real_order_allowed"] = bool(real_order_allowed)
    payload["simulated"] = data_mode in {"synthetic", "simulated", "paper"}
    if warning:
        payload["data_warning"] = warning
    return payload


def attach_synthetic_contract(payload: dict[str, Any], *, source: str = "native_deterministic_generator") -> dict[str, Any]:
    return attach_data_contract(payload, data_mode="synthetic", source=source, real_order_allowed=False, warning=SYNTHETIC_WARNING_KO)


F = TypeVar("F", bound=Callable[..., object])


def synthetic_result(source: str) -> Callable[[F], F]:
    def decorate(function: F) -> F:
        @wraps(function)
        def wrapped(*args: object, **kwargs: object) -> object:
            result = function(*args, **kwargs)
            if isinstance(result, dict):
                return attach_synthetic_contract(result, source=source)
            return result
        return wrapped  # type: ignore[return-value]
    return decorate
