"""Shared Wave 3 enums and constants."""

from __future__ import annotations

from enum import Enum


class StudyType(str, Enum):
    EXPERIMENTAL = "experimental"
    OBSERVATIONAL = "observational"
    BENCHMARK = "benchmark"
    SURVEY = "survey"
    SIMULATION = "simulation"
    QUALITATIVE = "qualitative"
    META_ANALYSIS = "meta_analysis"
    IMPLEMENTATION_REPORT = "implementation_report"
    DOCUMENTATION = "documentation"


STUDY_TYPE_CHECKLISTS: dict[str, tuple[str, ...]] = {
    StudyType.EXPERIMENTAL.value: (
        "randomization",
        "control_group",
        "pre_registered",
        "blinding",
    ),
    StudyType.OBSERVATIONAL.value: (
        "confounding_controls",
        "cohort_definition",
        "follow_up_window",
    ),
    StudyType.BENCHMARK.value: (
        "dataset_version",
        "harness_version",
        "compute_budget",
        "metric_definition",
    ),
    StudyType.SURVEY.value: ("sampling_frame", "response_rate", "non_response_bias"),
    StudyType.SIMULATION.value: ("model_assumptions", "parameter_sweep", "validation_data"),
    StudyType.QUALITATIVE.value: ("coding_scheme", "saturation", "audit_trail"),
    StudyType.META_ANALYSIS.value: ("inclusion_criteria", "heterogeneity", "publication_bias"),
    StudyType.IMPLEMENTATION_REPORT.value: (
        "environment_pin",
        "repro_steps",
        "baseline_commit",
    ),
}


class MatrixStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    NO_BEARING = "no_bearing"
    UNKNOWN = "unknown"


class ConflictCause(str, Enum):
    DEFINITIONAL = "definitional"
    METHOD = "method"
    POPULATION = "population"
    TEMPORAL = "temporal"
    MODEL_HARNESS = "model_harness"
    METRIC = "metric"
    IMPLEMENTATION = "implementation"
    UNRESOLVED = "unresolved"


class ChallengeCategory(str, Enum):
    WRONG_FRAMING = "wrong_framing"
    SIMPLER_BASELINE = "simpler_baseline"
    OMITTED_COUNTEREVIDENCE = "omitted_counterevidence"
    INFEASIBLE_DEPENDENCY = "infeasible_dependency"
    METRIC_GAMING = "metric_gaming"
    CONFOUNDING = "confounding"
    SCALE_SHIFT = "scale_shift"
    SAFETY_LEGAL_HARM = "safety_legal_harm"


class AuditSeverity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NOTE = "note"


class GapKind(str, Enum):
    MISSING_EVIDENCE = "missing_evidence"
    INACCESSIBLE_SOURCE = "inaccessible_source"
    UNTESTED_TRANSFER = "untested_transfer"
    UNAVAILABLE_IMPLEMENTATION = "unavailable_implementation"
    UNRESOLVED_CAUSE = "unresolved_cause"


METHODS_FIXTURE_KINDS = (
    "misleading_average",
    "missing_denominator",
    "no_variance",
    "weak_baseline",
    "leakage",
    "causal_overclaim",
)

FALSIFICATION_REJECT_REASONS = (
    "tautology",
    "moving_target",
    "impossible_measurement",
    "confirms_only",
)

MAX_SKEPTIC_ROUNDS = 3
DEFAULT_FOLLOWUP_MAX_ROUNDS = 1
