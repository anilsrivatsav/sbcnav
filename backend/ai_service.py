from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, TypedDict

from sqlalchemy import inspect, text

from database import engine
from services import get_reports, get_station_detail, list_commercial_contracts, list_earnings, list_passenger_amenities, list_stations, list_units, list_works

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
        "commercial_contracts",
        "commercial_contract_station_links",
        "commercial_contract_payments",
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
            "commercial_contracts": len(detail.get("commercial_contracts", [])),
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
            {"label": "Commercial", "value": len(detail.get("commercial_contracts", [])), "tone": "accent"},
            {"label": "Open PA Works", "value": summary.get("open_pa_works") or 0, "tone": "danger" if summary.get("open_pa_works") else "accent"},
        ],
        charts=[],
        sources=["stations", "units", "earnings", "works", "passenger_amenities", "commercial_contracts"],
        suggested_actions=[f"Open {station.get('station_code')} Station 360", "Export station summary"],
    )


def get_inspection_draft_tool(
    station_code: str | None,
    action_letter: bool = False,
) -> AiToolResult:
    """Build a source-backed draft without mutating an inspection or finding."""
    if station_code:
        detail = get_station_detail(station_code)
        if not detail:
            return AiToolResult(
                f"No station found for {station_code}.", [], [], [], ["stations"], ["Search stations"]
            )
        station = detail["station"]
        action = detail.get("action_centre", {})
        findings = action.get("open_findings", [])
        comparison = action.get("inspection_comparison", {})
        label = station.get("station_code") or station_code
        source_rows = [
            {
                "finding_id": row.get("finding_id"),
                "title": row.get("title"),
                "description": row.get("description"),
                "severity": row.get("severity"),
                "responsible_party": row.get("responsible_party"),
                "target_date": row.get("target_date"),
                "status": row.get("status"),
            }
            for row in findings[:MAX_SQL_ROWS]
        ]
        if action_letter:
            lines = [
                f"Draft action letter - {label}",
                "",
                f"The following {len(source_rows)} open inspection finding(s) require action:",
            ]
            for index, row in enumerate(source_rows, 1):
                lines.append(
                    f"{index}. {row.get('title') or 'Finding'} "
                    f"({row.get('severity') or 'unclassified'}); "
                    f"responsible party: {row.get('responsible_party') or 'to be assigned'}; "
                    f"target date: {row.get('target_date') or 'not recorded'}."
                )
            lines.extend(["", "This is a draft for officer review. Do not issue without verification."])
            answer = "\n".join(lines)
        else:
            current = comparison.get("current") or {}
            previous = comparison.get("previous") or {}
            answer = (
                f"Inspection summary for {label}: {len(source_rows)} open finding(s), "
                f"current score {current.get('score', 'not recorded')}, "
                f"previous score {previous.get('score', 'not recorded')}, "
                f"score delta {comparison.get('score_delta', 'not available')}."
            )
        return AiToolResult(
            answer_hint=answer,
            rows=source_rows,
            cards=[
                {"label": "Open findings", "value": len(source_rows), "tone": "danger" if source_rows else "accent"},
                {"label": "Current score", "value": (comparison.get("current") or {}).get("score") or "NA", "tone": "accent"},
                {"label": "Previous score", "value": (comparison.get("previous") or {}).get("score") or "NA", "tone": "accent"},
            ],
            charts=[],
            sources=["inspections", "inspection_findings", "inspection_responses", "stations"],
            suggested_actions=[f"Open {label} Station 360", "Review each finding before issuing the draft"],
            mode="inspection_draft",
        )

    report = get_reports()
    findings = report.get("inspections", {}).get("open_findings", [])[:MAX_SQL_ROWS]
    return AiToolResult(
        answer_hint=f"There are {len(findings)} open inspection finding(s) in the current management report. Select a station for a station-specific draft.",
        rows=findings,
        cards=[{"label": "Open findings", "value": len(findings), "tone": "danger" if findings else "accent"}],
        charts=[],
        sources=["inspections", "inspection_findings"],
        suggested_actions=["Ask for an inspection summary for a station"],
        mode="inspection_draft",
    )


def get_quality_diagnostic_tool(question: str) -> AiToolResult:
    """Return read-only data quality findings for the assistant."""
    q = question.lower()
    reports = get_reports()
    rows: list[dict[str, Any]] = []
    sources: list[str] = []
    if "duplicate" in q and "contract" in q:
        contracts = list_commercial_contracts()
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for row in contracts:
            key = (
                str(row.get("station_code") or row.get("raw_station_value") or "").strip().casefold(),
                str(row.get("contract_name") or "").strip().casefold(),
                str(row.get("policy") or "").strip().casefold(),
            )
            grouped.setdefault(key, []).append(row)
        for duplicate_rows in grouped.values():
            if len(duplicate_rows) > 1:
                rows.extend({**row, "diagnostic": "Possible duplicate contract identity"} for row in duplicate_rows)
        rows = rows[:MAX_SQL_ROWS]
        sources.append("commercial_contracts")
        answer = f"Found {len(rows)} commercial contract row(s) belonging to possible duplicate identities."
    elif "duplicate" in q:
        earnings = [row for row in list_earnings() if int(row.get("duplicate_count") or 0) > 0]
        rows.extend({**row, "diagnostic": "Duplicate receipt rows"} for row in earnings[:MAX_SQL_ROWS])
        sources.append("earnings")
        answer = f"Found {len(rows)} earning record(s) with duplicate source-row indicators."
    elif "inconsistent" in q or "contradiction" in q or "status" in q:
        contradictions = reports.get("works", {}).get("contradiction_rows", [])
        rows.extend({**row, "diagnostic": "Work status/progress contradiction"} for row in contradictions[:MAX_SQL_ROWS])
        sources.extend(["works", "work_progress_updates"])
        answer = f"Found {len(rows)} work record(s) with inconsistent status and progress."
    elif "missing station link" in q or "missing link" in q:
        station_codes = {
            row.get("station_code")
            for row in list_stations()
            if row.get("station_code")
        }
        units = list_units()
        for row in units:
            if not row.get("station_code") or row.get("station_code") not in station_codes:
                rows.append({**row, "diagnostic": "Unit station link missing or unmatched"})
        earnings = list_earnings()
        unit_codes = {row.get("unit_no") for row in units if row.get("unit_no")}
        for row in earnings:
            if (
                (row.get("unit_no") and row.get("unit_no") not in unit_codes)
                or (row.get("station_code") and row.get("station_code") not in station_codes)
                or not row.get("station_code")
            ):
                rows.append({**row, "diagnostic": "Earning unit or station link missing or unmatched"})
        works = list_works()
        for row in works:
            if row.get("scope_type") == "Station" and (
                not row.get("station_code") or row.get("station_code") not in station_codes
            ):
                rows.append({**row, "diagnostic": "Work station link missing or unmatched"})
        contracts = list_commercial_contracts()
        for row in contracts:
            if row.get("station_match_status") in {"unmatched", "asset_scope", "missing link"}:
                rows.append({**row, "diagnostic": "Commercial contract station link needs review"})
        rows = rows[:MAX_SQL_ROWS]
        sources.extend(["stations", "units", "earnings", "works", "work_links", "commercial_contracts"])
        answer = f"Found {len(rows)} concrete record(s) with missing or unmatched station links."
    else:
        quality = reports.get("data_quality", {})
        for label, count in quality.items():
            if count:
                rows.append({"diagnostic": label, "count": count})
        sources.extend(["stations", "units", "earnings", "works", "work_links"])
        answer = "Missing-link diagnostics were loaded from the management data-quality report."
    return AiToolResult(
        answer_hint=answer,
        rows=rows,
        cards=[{"label": "Diagnostic rows", "value": len(rows), "tone": "danger" if rows else "accent"}],
        charts=[],
        sources=sorted(set(sources)),
        suggested_actions=["Review the linked record", "Correct the source link before importing again"],
        mode="quality_diagnostic",
    )


def deterministic_tool(question: str, context: dict[str, Any] | None = None) -> AiToolResult:
    q = question.lower()
    code = station_code_from_question(question, context)
    if "action letter" in q or "draft remark" in q or "draft remarks" in q:
        return get_inspection_draft_tool(code, action_letter=True)
    if "inspection summary" in q or "inspection" in q and ("summary" in q or "finding" in q):
        return get_inspection_draft_tool(code)
    if "duplicate" in q or "inconsistent" in q or "contradiction" in q or "missing station link" in q:
        return get_quality_diagnostic_tool(question)
    if "commercial" in q or "ooh" in q or "parking" in q or "atm" in q or "mobile asset" in q:
        rows = list_commercial_contracts(q=question[:80], station_code=code)[:MAX_SQL_ROWS]
        if not rows:
            rows = list_commercial_contracts(station_code=code)[:MAX_SQL_ROWS] if code else list_commercial_contracts()[:MAX_SQL_ROWS]
        return AiToolResult("Commercial contract rows were loaded from non-catering contracts.", rows, [{"label": "Commercial Contracts", "value": len(rows), "tone": "accent"}], [], ["commercial_contracts"], ["Open Commercial Contracts"])
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
    q = question.lower()
    commercial_requested = any(token in q for token in ["commercial", "ooh", "parking", "atm", "mobile asset"])
    inspection_draft_requested = any(
        phrase in q
        for phrase in ("inspection summary", "draft remark", "draft remarks", "action letter")
    )
    quality_diagnostic_requested = any(
        phrase in q
        for phrase in ("duplicate", "inconsistent", "contradiction", "missing station link")
    )
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        plan = {
            "tool": "deterministic" if inspection_draft_requested or quality_diagnostic_requested or commercial_requested or not fallback_code else "station_360",
            "station_code": fallback_code,
        }
        reason = "OPENAI_API_KEY is not configured" if not os.getenv("OPENAI_API_KEY") else "OpenAI package is not installed"
        return {**state, "intent": "offline_fallback", "plan": plan, "mode": "offline_fallback", "planner_error": reason}
    schema = database_schema_context()
    system = (
        "You are a railway dashboard query planner. Return JSON only. "
        "Choose one tool: station_360, readonly_sql, deterministic. "
        "Use deterministic for inspection summaries, draft remarks, and action letters. "
        "Use deterministic for duplicate, inconsistent-status, and missing-link diagnostics. "
        "For SQL, produce only safe SELECT/WITH SQL with LIMIT. Never write SQL that changes data."
    )
    user = json.dumps({"question": question, "context": context, "schema": schema})
    try:
        plan = call_openai_json(system, user)
    except Exception as exc:
        logger.exception("LangGraph planner failed")
        plan = {
            "tool": "deterministic" if inspection_draft_requested or quality_diagnostic_requested or commercial_requested or not fallback_code else "station_360",
            "station_code": fallback_code,
        }
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
        if result.mode == "tool":
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
        "applied_filters": {
            **(state.get("context") or {}),
            **({"station_code": state.get("plan", {}).get("station_code")} if state.get("plan", {}).get("station_code") else {}),
            "tool": state.get("plan", {}).get("tool") or "deterministic",
        },
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
