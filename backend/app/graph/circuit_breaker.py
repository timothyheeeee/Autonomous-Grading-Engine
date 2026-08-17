from app.config import get_settings
from app.core.logging import log_event
from app.graph.state import AgentState


class CircuitBreakerTripped(RuntimeError):
    pass


def check_circuit_breaker(state: AgentState) -> str | None:
    settings = get_settings()
    failures = int(state.get("failed_attempts") or 0)
    tokens = int(state.get("token_usage") or 0)
    if failures >= settings.max_tool_failures:
        reason = (
            f"Self-correction loop terminated after {failures} failed tool attempts "
            f"(limit={settings.max_tool_failures})."
        )
        log_event("circuit_breaker", reason=reason, kind="tool_failures", failures=failures)
        return reason
    if tokens >= settings.max_graph_tokens:
        reason = (
            f"Token circuit breaker tripped at {tokens} tokens "
            f"(limit={settings.max_graph_tokens})."
        )
        log_event("circuit_breaker", reason=reason, kind="token_limit", tokens=tokens)
        return reason
    return None
