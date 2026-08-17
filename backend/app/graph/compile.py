from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.core.logging import log_event
from app.graph.nodes.calculate import calculate_node
from app.graph.nodes.halt import halt_node
from app.graph.nodes.parse import semantic_parser_node
from app.graph.nodes.publish import save_to_database_node
from app.graph.nodes.vision import vision_extractor_node
from app.graph.state import AgentState

_GRAPH = None
_CHECKPOINTER = None


def build_checkpointer():
    settings = get_settings()
    if settings.redis_url:
        try:
            from langgraph.checkpoint.redis import RedisSaver

            saver = RedisSaver.from_conn_string(settings.redis_url)
            saver.setup()
            log_event("checkpointer_ready", backend="redis")
            return saver
        except Exception as exc:  # noqa: BLE001
            log_event("redis_checkpointer_unavailable", error=str(exc))
    log_event("checkpointer_ready", backend="memory")
    return MemorySaver()


def route_after_vision(state: AgentState) -> str:
    rules = state.get("extracted_rules") or {}
    if rules.get("status") == "ok":
        return "semantic_parser"
    if int(state.get("vision_failures") or 0) >= 2 or state.get("halt_reason"):
        return "halt"
    return "vision_extractor"


def route_after_parse(state: AgentState) -> str:
    parsed = state.get("parsed_actions") or {}
    if parsed.get("status") == "ok" and state.get("dynamic_roster"):
        return "calculate"
    return "halt"


def route_after_calculate(state: AgentState) -> str:
    metrics = state.get("calculated_percentages") or {}
    if metrics.get("status") == "ok":
        return "save_to_database"
    return "halt"


def build_graph(checkpointer: Any | None = None):
    builder = StateGraph(AgentState)
    builder.add_node("vision_extractor", vision_extractor_node)
    builder.add_node("semantic_parser", semantic_parser_node)
    builder.add_node("calculate", calculate_node)
    builder.add_node("save_to_database", save_to_database_node)
    builder.add_node("halt", halt_node)

    builder.add_edge(START, "vision_extractor")
    builder.add_conditional_edges("vision_extractor", route_after_vision)
    builder.add_conditional_edges("semantic_parser", route_after_parse)
    builder.add_conditional_edges("calculate", route_after_calculate)
    builder.add_edge("save_to_database", END)
    builder.add_edge("halt", END)

    return builder.compile(
        checkpointer=checkpointer or build_checkpointer(),
        interrupt_before=["save_to_database"],
    )


def get_graph():
    global _GRAPH, _CHECKPOINTER
    if _GRAPH is None:
        _CHECKPOINTER = build_checkpointer()
        _GRAPH = build_graph(_CHECKPOINTER)
    return _GRAPH


def reset_graph_cache() -> None:
    global _GRAPH, _CHECKPOINTER
    _GRAPH = None
    _CHECKPOINTER = None
