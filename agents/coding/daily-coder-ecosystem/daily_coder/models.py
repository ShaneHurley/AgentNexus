from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Phase(str, Enum):
    NEW="NEW"; INTAKE="INTAKE"; SIZE="SIZE"; RESEARCH="RESEARCH"; BRAINSTORM="BRAINSTORM"; DECIDE="DECIDE"; TEST_DESIGN="TEST_DESIGN"; PLAN="PLAN"; PLAN_REVIEW="PLAN_REVIEW"; READY_TO_BUILD="READY_TO_BUILD"; IMPLEMENT="IMPLEMENT"; TEST_AUTHOR="TEST_AUTHOR"; TEST_EXECUTE="TEST_EXECUTE"; CODE_REVIEW="CODE_REVIEW"; DOCUMENT="DOCUMENT"; ALIGNMENT="ALIGNMENT"; ACCEPTANCE="ACCEPTANCE"; COMPLETE="COMPLETE"; DIAGNOSE="DIAGNOSE"; WAITING_HUMAN="WAITING_HUMAN"; WAITING_JOB="WAITING_JOB"; ESCALATED="ESCALATED"; FAILED="FAILED"; CANCELLED="CANCELLED"

class RunStatus(str, Enum):
    """Execution status, tracked independently of workflow phase."""
    ACTIVE="ACTIVE"; WAITING_HUMAN="WAITING_HUMAN"; WAITING_JOB="WAITING_JOB"; BLOCKED="BLOCKED"; FAILED="FAILED"; COMPLETE="COMPLETE"; SIMULATED="SIMULATED"; CANCELLED="CANCELLED"

@dataclass(frozen=True)
class Invocation:
    run_id:str; role:str; prompt:str; input_packet:dict[str,Any]; model_tier:str; max_output_tokens:int; idempotency_key:str
    model:str="unknown"; tools:tuple=(); tool_results:tuple=(); turn:int=0; reasoning:bool=False; output_schema:dict|None=None

@dataclass
class ToolCall:
    name:str; arguments:dict[str,Any]; call_id:str=""

@dataclass
class InvocationResult:
    output:dict[str,Any]|None=None; input_tokens:int=0; output_tokens:int=0; model:str="unknown"; raw_ref:str|None=None; tool_calls:list[ToolCall]=field(default_factory=list)
