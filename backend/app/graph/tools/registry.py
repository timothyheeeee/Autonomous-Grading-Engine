from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.core.rbac import can_execute_tools
from app.graph.tools.calculator import CalculateInput, calculate_normalized_percentages
from app.graph.tools.semantic import SemanticInput, extract_scored_actions


class ToolSpec(BaseModel):
    name: str
    description: str
    args_schema: type[BaseModel]
    mutating: bool
    ast_dump: dict[str, Any]
    source: str


def json_safe_ast(node: ast.AST) -> dict[str, Any]:
    return {"node_type": type(node).__name__, "dump": ast.dump(node, include_attributes=False)}


def _function_ast(fn: Callable[..., Any]) -> dict[str, Any]:
    return json_safe_ast(ast.parse(inspect.getsource(fn)))


def _build_registry() -> dict[str, tuple[ToolSpec, Callable[..., Any]]]:
    tools: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}

    def register(name: str, description: str, schema: type[BaseModel], fn: Callable[..., Any], mutating: bool) -> None:
        tools[name] = (
            ToolSpec(
                name=name,
                description=description,
                args_schema=schema,
                mutating=mutating,
                ast_dump=_function_ast(fn),
                source=inspect.getsource(fn),
            ),
            fn,
        )

    register(
        "extract_scored_actions",
        "Read unstructured peer-review CSV plus rubric rules. Output scored JSON only. Never calculate percentages.",
        SemanticInput,
        extract_scored_actions,
        True,
    )
    register(
        "calculate_normalized_percentages",
        "Deterministic Pandas calculator. Accepts LLM-scored JSON only — never the raw CSV.",
        CalculateInput,
        calculate_normalized_percentages,
        True,
    )
    return tools


TOOL_REGISTRY = _build_registry()


def openai_tool_schemas() -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for spec, _ in TOOL_REGISTRY.values():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.args_schema.model_json_schema(),
                },
            }
        )
    return schemas


def execute_tool(tool_name: str, arguments: dict[str, Any], actor_role: str) -> dict[str, Any]:
    if tool_name not in TOOL_REGISTRY:
        return {"status": "error", "reason": "unreadable_data", "message": f"Unknown tool: {tool_name}"}
    spec, fn = TOOL_REGISTRY[tool_name]
    if spec.mutating and not can_execute_tools(actor_role):
        return {"status": "error", "reason": "rbac_denied", "message": "Only an admin can execute this tool."}
    parsed_args = spec.args_schema.model_validate(arguments)
    return fn(**parsed_args.model_dump())


def tool_ast(tool_name: str) -> dict[str, Any]:
    spec, _ = TOOL_REGISTRY[tool_name]
    return spec.ast_dump
