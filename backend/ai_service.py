from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, TypedDict

from sqlalchemy import inspect, text

from database import engine
from services import get_reports, get_station_detail, list_passenger_amenities, list_stations, list_units, list_works

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - keeps the API importable when deps are not installed yet.
    END = None
    StateGraph = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


MAX_SQL_ROWS = 200
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
QUESTION_STOPWORDS = {"SHOW", "GIVE", "WHAT", "WHICH", "WITH", "FROM", "WORKS", "UNITS", "TELL", "ABOUT", "EVERYTHING", "PENDING", "LICENSE", "FEE"}
logger = logging.getLogger("rail_dashboard.ai")

BLOCKED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|merge|grant|revoke|copy|vacuum|attach|detach|pragma|execute|call)\b",
    re.IGNORECASE,
)


class AiState(TypedDict, total=False):
    question: str
    context: dict[str, Any]
    intent: str
    plan: dict[str, Any]
    tool_result: dict[str, Any]
    answer: dict[str, Any]
    mode: str
    planner_error: str
    answer_error: str


@dataclass
class AiToolResult:
    answer_hint: str
    rows: list[dict[str, Any]]
    cards: list[dict[str, Any]]
    charts: list[dict[str, Any]]
    sources: list[str]
    suggested_actions: list[str]
    sql: str | None = None
    mode: str = "tool"
    planner_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_hint": self.answer_hint,
            "rows": self.rows,
            "cards": self.cards,
            "charts": self.charts,
            "sources": self.sources,
            "suggested_actions": self.suggested_actions,
            "sql": self.sql,
            "mode": self.mode,
            "planner_error": self.planner_error,
        }


def database_schema_context() -> str:
    inspector = inspect(engine)
    allowed = {
        "stations",
        "units",
        "earnings",
        "works",
        "work_links",
        "earning_links",
        "station_infra",
        "platform_details",
        "wheel_chair_availability",
        "trolley_paths",
        "passenger_amenity_works",
        "station_platform_extension_status",
        "platform_extension_summaries",
    }
    lines = []
    for table in sorted(name for name in inspector.get_table_names() if name in allowed):
      columns = [column["name"] for column in inspector.get_columns(table)]
      lines.append(f"{table}({', '.join(columns)})")
    return "\n".join(lines)


def station_code_from_question(question: str, context: dict[str, Any] | None = None) -> str | None:
    if context and context.get("station_code"):
        return str(context["station_code"]).strip().upper()
    candidates = [match.group(0) for match in re.finditer(r"\b[A-Z]{2,5}[A-Z0-9]?\b", question.upper())]
    if not candidates:
        return None
    try:
        station_codes = {row.get("station_code") for row in list_stations() if row.get("station_code")}
        for token in candidates:
            if token in station_codes:
                return token
    except Exception:
        pass
    for token in candidates:
        if token not in QUESTION_STOPWORDS:
            return token
    return None


def guard_readonly_sql(sql: str) -> str:
    candidate = re.sub(r"--.*?$|/\*.*?\*/", "", sql.strip(), flags=re.MULTILINE | re.DOTALL)
    candidate = candidate.rstrip(";").strip()
    if not re.match(r"^(select|with)\b", candidate, flags=re.IGNORECASE):
        raise ValueError("Only SELECT/WITH read-only queries are allowed")
    if BLOCKED_SQL.search(candidate):
        raise ValueError("Query contains a blocked SQL operation")
    if ";" in candidate:
        raise ValueError("Only one SQL statement is allowed")
    if not re.search(r"\blimit\s+\d+\b", candidate, flags=re.IGNORECASE):
        candidate = f"{candidate} LIMIT {MAX_SQL_ROWS}"
    return candidate


def run_readonly_sql(sql: str) -> AiToolResult:
    safe_sql = guard_readonly_sql(sql)
    with engine.connect() as connection:
        rows = [dict(row._mapping) for row in connection.execute(text(safe_sql)).fetchmany(MAX_SQL_ROWS)]
    return AiToolResult(
        answer_hint=f"Read-only SQL returned {len(rows)} rows.",
        rows=rows,
        cards=[{"label": "Rows", "value": len(rows), "tone": "accent"}],
        charts=[],
        sources=_sources_from_sql(safe_sql),
        suggested_actions=["Review result rows", "Export visible rows"],
        sql=safe_sql,
    )


def _sources_from_sql(sql: str) -> list[str]:
    tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, flags=re.IGNORECASE)
    return sorted(set(tables))


def get_station_360_tool(station_code: str) -> AiToolResult:
    detail = get_station_detail(station_code)
    if not detail:
        return AiToolResult(
            answer_hint=f"No station found for {station_code}.",
            rows=[],
            cards=[],
            charts=[],
            sources=["stations"],
            suggested_actions=["Search stations"],
        )
    station = detail["station"]
    summary = detail.get("amenity_summary", {})
    rows = [
        {
            "station_code": station.get("station_code"),
            "station_name": station.get("station_name"),
            "division": station.get("division"),
            "section": station.get("section"),
            "category": station.get("categorisation"),
            "contracts": len(detail.get("contracts", [])),
            "earnings": len(detail.get("earnings", [])),
            "works": len(detail.get("works", [])),
            "platforms": summary.get("platforms"),
            "ramp_feasible": summary.get("ramp_feasible"),
            "lift_proposed": summary.get("lift_proposed"),
            "open_pa_works": summary.get("open_pa_works"),
        }
    ]
    return AiToolResult(
        answer_hint=f"Station 360 loaded for {station.get('station_code')} with contracts, earnings, works, and amenities.",
        rows=rows,
        cards=[
            {"label": "Contracts", "value": len(detail.get("contracts", [])), "tone": "accent"},
            {"label": "Earnings", "value": len(detail.get("earnings", [])), "tone": "accent"},
            {"label": "Works", "value": len(detail.get("works", [])), "tone": "accent"},
            {"label": "Open PA Works", "value": summary.get("open_pa_works") or 0, "tone": "danger" if summary.get("open_pa_works") else "accent"},
        ],
        charts=[],
        sources=["stations", "units", "earnings", "works", "passenger_amenities"],
        suggested_actions=[f"Open {station.get('station_code')} Station 360", "Export station summary"],
    )


def deterministic_tool(question: str, context: dict[str, Any] | None = None) -> AiToolResult:
    q = question.lower()
    code = station_code_from_question(question, context)
    if code and any(token in q for token in ["station", "summary", "everything", "360", "detail", "ksm", "sbc"]):
        return get_station_360_tool(code)
    if "pending" in q and "work" in q:
        rows = [row for row in list_works() if not re.search(r"complete|done", str(row.get("status") or ""), re.I)][:MAX_SQL_ROWS]
        return AiToolResult("Pending works were filtered from linked sanctioned works.", rows, [{"label": "Pending Works", "value": len(rows), "tone": "danger"}], [], ["works", "work_links"], ["Open Works report"])
    if "license" in q or "fee" in q or "alert" in q:
        reports = get_reports()
        rows = reports.get("license_fee_alerts", {}).get("rows", [])[:MAX_SQL_ROWS]
        return AiToolResult("License fee alert rows were loaded from reports.", rows, [{"label": "Alerts", "value": len(rows), "tone": "danger"}], [], ["units", "earnings"], ["Open Reports alerts"])
    if "ramp" in q or "lift" in q or "amenity" in q:
        rows = list_passenger_amenities(kind="pf_extension")[:MAX_SQL_ROWS]
        return AiToolResult("Passenger amenity ramp/lift rows were loaded.", rows, [{"label": "Amenity Rows", "value": len(rows), "tone": "accent"}], [], ["station_platform_extension_status"], ["Open Passenger Amenities"])
    if "unit" in q or "contract" in q:
        rows = list_units(q=context.get("station_code") if context else None)[:MAX_SQL_ROWS]
        return AiToolResult("Contract/unit rows were loaded.", rows, [{"label": "Units", "value": len(rows), "tone": "accent"}], [], ["units"], ["Open Contracts"])
    rows = list_stations(q=question[:30])[:MAX_SQL_ROWS]
    return AiToolResult("Station search rows were loaded.", rows, [{"label": "Stations", "value": len(rows), "tone": "accent"}], [], ["stations"], ["Open Stations"])


def call_openai_json(system: str, user: str) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("OpenAI package is not installed")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    client = OpenAI()
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(response.choices[0].message.content or "{}")


def classify_and_plan(state: AiState) -> AiState:
    question = state["question"]
    context = state.get("context") or {}
    fallback_code = station_code_from_question(question, context)
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        plan = {"tool": "station_360" if fallback_code else "deterministic", "station_code": fallback_code}
        reason = "OPENAI_API_KEY is not configured" if not os.getenv("OPENAI_API_KEY") else "OpenAI package is not installed"
        return {**state, "intent": "offline_fallback", "plan": plan, "mode": "offline_fallback", "planner_error": reason}
    schema = database_schema_context()
    system = (
        "You are a railway dashboard query planner. Return JSON only. "
        "Choose one tool: station_360, readonly_sql, deterministic. "
        "For SQL, produce only safe SELECT/WITH SQL with LIMIT. Never write SQL that changes data."
    )
    user = json.dumps({"question": question, "context": context, "schema": schema})
    try:
        plan = call_openai_json(system, user)
    except Exception as exc:
        logger.exception("LangGraph planner failed")
        plan = {"tool": "station_360" if fallback_code else "deterministic", "station_code": fallback_code}
        return {**state, "intent": "planner_fallback", "plan": plan, "mode": "planner_fallback", "planner_error": str(exc)}
    return {**state, "intent": str(plan.get("tool") or "deterministic"), "plan": plan, "mode": "langgraph_openai"}


def run_tool_node(state: AiState) -> AiState:
    plan = state.get("plan") or {}
    question = state["question"]
    context = state.get("context") or {}
    tool = plan.get("tool")
    try:
        if tool == "station_360":
            result = get_station_360_tool(str(plan.get("station_code") or station_code_from_question(question, context) or ""))
        elif tool == "readonly_sql" and plan.get("sql"):
            result = run_readonly_sql(str(plan["sql"]))
        else:
            result = deterministic_tool(question, context)
        result.mode = state.get("mode", "tool")
        result.planner_error = state.get("planner_error")
    except Exception as exc:
        logger.exception("AI tool execution failed")
        result = AiToolResult(str(exc), [], [{"label": "Error", "value": "1", "tone": "danger"}], [], [], ["Refine the question"], mode="tool_error")
    return {**state, "tool_result": result.to_dict()}


def answer_node(state: AiState) -> AiState:
    result = state.get("tool_result") or {}
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        answer = result.get("answer_hint") or "I found matching railway dashboard data."
    else:
        system = "Return concise JSON with key 'answer'. Explain the records using only supplied tool_result."
        user = json.dumps({"question": state["question"], "tool_result": result}, default=str)
        try:
            answer = call_openai_json(system, user).get("answer") or result.get("answer_hint")
        except Exception as exc:
            logger.exception("LangGraph answer node failed")
            state["answer_error"] = str(exc)
            answer = result.get("answer_hint") or "I found matching railway dashboard data."
    data = {
        "answer": str(answer or "I found matching railway dashboard data."),
        "rows": result.get("rows", []) if isinstance(result.get("rows", []), list) else [],
        "cards": result.get("cards", []) if isinstance(result.get("cards", []), list) else [],
        "charts": result.get("charts", []) if isinstance(result.get("charts", []), list) else [],
        "sources": result.get("sources", []) if isinstance(result.get("sources", []), list) else [],
        "suggested_actions": result.get("suggested_actions", []) if isinstance(result.get("suggested_actions", []), list) else [],
        "sql": result.get("sql"),
        "mode": result.get("mode") or state.get("mode") or "unknown",
        "graph": "langgraph",
        "model": AI_MODEL if os.getenv("OPENAI_API_KEY") and OpenAI is not None else None,
        "planner_error": result.get("planner_error"),
        "answer_error": state.get("answer_error"),
    }
    return {**state, "answer": data}


def build_ai_graph():
    if StateGraph is None:
        return None
    graph = StateGraph(AiState)
    graph.add_node("classify_and_plan", classify_and_plan)
    graph.add_node("run_tool", run_tool_node)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("classify_and_plan")
    graph.add_edge("classify_and_plan", "run_tool")
    graph.add_edge("run_tool", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def query_ai(question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("question is required")
    initial: AiState = {"question": question.strip(), "context": context or {}}
    graph = build_ai_graph()
    if graph is None:
        state = answer_node(run_tool_node(classify_and_plan(initial)))
    else:
        state = graph.invoke(initial)
    return state["answer"]
