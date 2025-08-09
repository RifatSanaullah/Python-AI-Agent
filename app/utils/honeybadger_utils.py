from typing import Any, Dict, Optional, Union

try:
    # Honeybadger client (configured in app startup)
    from honeybadger import honeybadger as hb
except Exception:  # pragma: no cover - defensive import
    hb = None  # type: ignore


def notify_honeybadger(
    error_or_message: Union[BaseException, str],
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Safely send an error/message to Honeybadger.

    - No-ops if Honeybadger is unavailable or misconfigured
    - Never raises (safe in hot paths like audio loops)
    """
    try:
        if hb is None:
            return
        payload_context = context or {}
        hb.notify(error_or_message, context=payload_context)
    except Exception:
        # Never let reporting crash runtime
        return


