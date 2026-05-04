"""Shared LangGraph state and structured P1 data contracts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

try:
    from langgraph.graph import add_messages
except ModuleNotFoundError:
    def add_messages(left, right):
        return (left or []) + (right or [])
from typing_extensions import TypedDict


class DatasetMeta(TypedDict, total=False):
    file_name: str
    file_path: str
    file_storage_id: str
    source_type: Literal["file", "database", "api"]
    source_ref: str
    query: str
    num_rows: int
    num_cols: int
    columns: list[str]
    dtypes: dict[str, str]
    preview: str | list[list[Any]]
    missing_info: dict[str, int]


class DatabaseSource(TypedDict, total=False):
    """Enterprise database source descriptor.

    P1 does not open arbitrary business databases directly. The contract is:
    register a read-only connection by alias, validate SQL, execute through a
    controlled adapter, and materialize a result dataset for reproducibility.
    """

    alias: str
    dialect: str
    read_only: bool
    allowed_schemas: list[str]
    connection_ref: str


class AnalysisIntent(TypedDict, total=False):
    intent_type: str
    business_question: str
    analysis_goal: str
    target_entities: list[str]
    metrics: list[str]
    dimensions: list[str]
    time_range: str
    filters: list[str]
    output_expectation: list[str]
    required_inputs: list[str]
    ambiguities: list[str]
    confidence: float
    requires_data: bool


class QueryIntent(TypedDict, total=False):
    task_type: str
    business_domain: str
    raw_metrics: list[str]
    raw_dimensions: list[str]
    raw_filters: list[str]
    raw_time: str
    comparison: str
    output_purpose: str
    requires_data: bool
    high_risk: bool


class ContextProfile(TypedDict, total=False):
    user_id: str
    team: str
    business_domain: str
    roles: list[str]
    preferences: dict[str, Any]
    report_context: dict[str, Any]


class SemanticCandidates(TypedDict, total=False):
    metrics: list[dict[str, Any]]
    dimensions: list[dict[str, Any]]
    time_ranges: list[dict[str, Any]]
    verified_queries: list[dict[str, Any]]


class DisambiguationResult(TypedDict, total=False):
    action: Literal["auto_select", "clarify", "blocked"]
    selected_metric: dict[str, Any]
    selected_time_range: dict[str, Any]
    questions: list[str]
    reason: str


class LogicalPlan(TypedDict, total=False):
    plan_type: str
    metric: dict[str, Any]
    dimensions: list[dict[str, Any]]
    filters: list[dict[str, Any]]
    time_range: dict[str, Any]
    output_purpose: str
    semantic_version: str
    steps: list[dict[str, Any]]


class PolicyDecision(TypedDict, total=False):
    allowed: bool
    checks: list[dict[str, Any]]
    reason: str


class TaskItem(TypedDict, total=False):
    id: str
    plan_id: str
    turn_id: str
    agent: str
    description: str
    depends_on: list[str]
    input_dataset_ids: list[str]
    expected_evidence: list[str]
    status: Literal["pending", "running", "completed", "failed"]
    attempt_count: int
    result_summary: str
    failure_reason: str


class AnalysisPlan(TypedDict, total=False):
    id: str
    session_id: str
    turn_id: str
    user_message: str
    intent: AnalysisIntent
    assumptions: list[str]
    tasks: list[TaskItem]
    expected_outputs: list[str]
    risk_controls: list[str]
    status: Literal["clarifying", "planned", "running", "completed", "failed"]


class CodeResult(TypedDict, total=False):
    code: str
    stdout: str
    stderr: str
    success: bool
    figures: list[str]
    dataframes: dict[str, str]


class EvidenceItem(TypedDict, total=False):
    id: str
    plan_id: str
    task_id: str
    turn_id: str
    evidence_type: str
    content: dict[str, Any]
    code: str
    stdout: str
    stderr: str
    figure_paths: list[str]
    dataset_refs: list[str]
    metric_refs: dict[str, Any]
    success: bool


class ValidationResult(TypedDict, total=False):
    id: str
    validation_type: str
    status: Literal["passed", "failed"]
    checks: list[dict[str, Any]]
    error_message: str
    failure_reasons: list[dict[str, Any]]
    failure_summary: str


class AuditEvent(TypedDict, total=False):
    id: str
    event_type: str
    resource_type: str
    resource_id: str
    status: str
    details: dict[str, Any]


class MemoryCandidate(TypedDict, total=False):
    id: str
    user_id: str
    session_id: str
    turn_id: str
    plan_id: str
    memory_type: str
    memory_key: str
    memory_value: dict[str, Any]
    scope: str
    business_domain: str
    confidence: float
    status: Literal["candidate", "confirmed", "rejected"]
    source: dict[str, Any]
    rationale: str


class AnalysisState(TypedDict, total=False):
    session_id: str
    turn_id: str
    messages: Annotated[list, add_messages]
    user_id: str
    team: str
    roles: list[str]
    auth_context: dict[str, Any]
    preferences: dict[str, Any]
    report_context: dict[str, Any]

    intent: str
    structured_intent: AnalysisIntent
    query_intent: QueryIntent
    context_profile: ContextProfile
    semantic_candidates: SemanticCandidates
    disambiguation: DisambiguationResult
    logical_plan: LogicalPlan
    policy_decision: PolicyDecision
    generated_query: dict[str, Any]
    sql_validation: dict[str, Any]
    task_type: str
    next_agent: str

    clarification_required: bool
    clarification_questions: list[str]
    clarification_id: str

    analysis_plan: AnalysisPlan
    plan_id: str
    task_queue: list[TaskItem]
    current_task: TaskItem
    current_task_id: str
    completed_tasks: list[TaskItem]
    failed_tasks: list[TaskItem]
    scheduling_complete: bool
    supervisor_decision: str

    datasets: list[DatasetMeta]
    database_sources: list[DatabaseSource]
    active_dataset_index: int

    current_code: str
    code_result: CodeResult
    retry_count: int
    max_retry: int
    needs_debug: bool
    needs_retry: bool

    evidence: list[EvidenceItem]
    validation_results: list[ValidationResult]
    audit_events: list[AuditEvent]
    validation_failure: dict[str, Any]
    memory_candidates: list[MemoryCandidate]

    report: str
    figures: list[str]
    error: str
