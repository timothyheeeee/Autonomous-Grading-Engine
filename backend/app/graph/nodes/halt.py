from typing import Any

from app.core.logging import log_event
from app.graph.state import AgentState


def halt_node(state: AgentState) -> dict[str, Any]:
    reason = state.get("halt_reason") or "unreadable_data"
    log_event(
        "graph_halted",
        reason=reason,
        vision_failures=state.get("vision_failures"),
        tokens=state.get("token_usage"),
    )
    return {
        "traces": [
            {
                "node": "halt",
                "payload": {"reason": reason},
                "ast": {"node_type": "Halt", "dump": "circuit_breaker(max_vision_failures=2)"},
            }
        ]
    }
