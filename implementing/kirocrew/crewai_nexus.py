#!/usr/bin/env python3
"""CrewAI Multi-Agent Implementation of AgentNexus Workflows.

Translates KEEP-6 orchestrators and key specialists into CrewAI Agents,
Tasks, and Crews with sequential / hierarchical execution.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from crewai import Agent, Crew, Process, Task
except ImportError:
    print("CrewAI is not installed. To run this script, execute:\n  pip install crewai crewai-tools", file=sys.stderr)
    sys.exit(0)


def build_nexus_crew(task_description: str, verbose: bool = True) -> Crew:
    # 1. Agents
    researcher = Agent(
        role="Deep Evidence Researcher",
        goal="Gather factual, source-backed evidence from the codebase without modifying any files.",
        backstory="You are deep-research from AgentNexus. You operate in read-only mode, extracting exact citations, symbols, and patterns.",
        verbose=verbose,
        allow_delegation=False
    )

    plan_reviewer = Agent(
        role="Adversarial Plan Reviewer",
        goal="Audit proposed architecture and implementation plans for breaking changes, edge cases, and test gaps.",
        backstory="You are plan-reviewer and adversarial-skeptic from AgentNexus. You challenge assumptions and demand rigorous test coverage.",
        verbose=verbose,
        allow_delegation=False
    )

    coder = Agent(
        role="Audited Implementer & Test Author",
        goal="Formulate minimal, verifiable diffs and unit tests according to the approved plan.",
        backstory="You are daily-coder from AgentNexus. You believe in artifact-driven development and strict test verification.",
        verbose=verbose,
        allow_delegation=False
    )

    # 2. Tasks
    t1 = Task(
        description=f"Conduct evidence research on: {task_description}. Identify relevant modules, classes, and constraints.",
        expected_output="A structured Research Brief with exact file citations and known limitations.",
        agent=researcher
    )

    t2 = Task(
        description=f"Based on the research brief, formulate an implementation plan and review it adversarially for risks on: {task_description}.",
        expected_output="An adversarial review report with PASS/REVISE verdict and a finalized plan.",
        agent=plan_reviewer
    )

    t3 = Task(
        description=f"Draft the exact implementation code and corresponding unit tests for: {task_description}.",
        expected_output="Complete, production-ready code diffs and unit test cases.",
        agent=coder
    )

    # 3. Assemble Crew
    nexus_crew = Crew(
        agents=[researcher, plan_reviewer, coder],
        tasks=[t1, t2, t3],
        process=Process.sequential,
        verbose=verbose
    )

    return nexus_crew


def main():
    parser = argparse.ArgumentParser(description="Run AgentNexus CrewAI Pipeline")
    parser.add_argument("--task", required=True, help="Task description to execute")
    args = parser.parse_args()

    crew = build_nexus_crew(args.task)
    print(f"\n[CrewAI Nexus] Starting crew for task: {args.task}\n")
    result = crew.kickoff()
    print("\n" + "=" * 60)
    print("CREW WORKFLOW COMPLETED RESULT:")
    print(result)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
