"""Optional LLM Guard-backed deep scanner for fetched docs."""

from __future__ import annotations

from typing import Any

_scanner: Any | None = None
_load_state = "not-loaded"
_load_error: str | None = None


def _set_failed(exc: BaseException) -> None:
    global _load_state, _load_error
    _load_state = "failed"
    _load_error = str(exc)
    print(f"WARNING: llm-guard model failed to load ({exc}); deep scan disabled")


def _get_scanner() -> Any | None:
    global _scanner, _load_state
    if _scanner is not None:
        return _scanner
    if _load_state in {"missing", "failed"}:
        return None

    try:
        from llm_guard.input_scanners import PromptInjection
        from llm_guard.input_scanners.prompt_injection import MatchType

        _scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
    except ModuleNotFoundError as exc:
        if exc.name == "llm_guard":
            _load_state = "missing"
        else:
            _set_failed(exc)
    except Exception as exc:
        _set_failed(exc)
    else:
        _load_state = "ready"
    return _scanner


def ensure_available() -> bool:
    """Initialize the scanner once and report whether it is usable."""
    return _get_scanner() is not None


def state() -> str:
    """Return the adapter load state for audit/reporting."""
    return _load_state


def load_error() -> str | None:
    """Return the adapter load error, when there is one."""
    return _load_error


def scan(text: str) -> list[str]:
    scanner = _get_scanner()
    if scanner is None:
        return []
    try:
        _sanitized, is_valid, risk_score = scanner.scan(text)
    except Exception as exc:
        print(f"WARNING: llm-guard scan failed ({exc}); treating as no extra findings")
        return []
    if is_valid:
        return []
    try:
        score = f"{float(risk_score):.2f}"
    except (TypeError, ValueError):
        score = str(risk_score)
    return [f"llm-guard-prompt-injection: risk={score}"]
