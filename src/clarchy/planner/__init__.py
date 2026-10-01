"""Planning: from a requirements document to an explained architecture.

See pipeline.py for the stages, rules.py for the no-AI planner and agent.py for the
Claude agent that designs with Clarchy's MCP tools.
"""

from clarchy.planner.pipeline import PlanError, PlanOptions, PlanResult, run_plan

__all__ = ["PlanError", "PlanOptions", "PlanResult", "run_plan"]
