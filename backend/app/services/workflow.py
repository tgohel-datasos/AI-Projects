from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import combine_plan, pipeline_for, select_agents
from app.agents.registry import build_agent
from app.config import settings
from app.db import SessionLocal
from app.models import AgentExecution, TravelPlan, TravelRequest, User, Workflow
from app.schemas import AgentEnvelope, CreatePlanBody, TripRequest


class WorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_queued(self, body: CreatePlanBody) -> Workflow:
        user = await self._get_or_create_user(body.user_display_name, body.user_email)
        req = TravelRequest(
            user_id=user.id,
            payload=body.trip.model_dump(mode="json"),
            raw_text=body.raw_text,
            status="queued",
        )
        self.session.add(req)
        await self.session.flush()
        selected = select_agents(body.trip)
        dag = [{"stage": s, "agents": a, "mode": m} for s, a, m in pipeline_for(selected)]
        wf = Workflow(request_id=req.id, status="queued", selected_agents=selected, dag=dag)
        self.session.add(wf)
        await self.session.commit()
        await self.session.refresh(wf)
        return await self.get_workflow(wf.id)

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        q = (
            select(Workflow)
            .options(selectinload(Workflow.executions), selectinload(Workflow.plan), selectinload(Workflow.request))
            .where(Workflow.id == workflow_id)
        )
        res = await self.session.execute(q)
        return res.scalar_one()

    async def _get_or_create_user(self, name: str, email: str | None) -> User:
        if email:
            res = await self.session.execute(select(User).where(User.email == email))
            existing = res.scalar_one_or_none()
            if existing:
                return existing
        user = User(display_name=name, email=email)
        self.session.add(user)
        await self.session.flush()
        return user


async def execute_workflow(workflow_id: UUID) -> None:
    async with SessionLocal() as session:
        svc = WorkflowService(session)
        wf = await svc.get_workflow(workflow_id)
        trip = TripRequest.model_validate(wf.request.payload)
        selected = wf.selected_agents or select_agents(trip)
        wf.status = "running"
        wf.started_at = _now()
        wf.request.status = "running"
        await session.commit()
        results: dict[str, AgentEnvelope] = {}
        try:
            for stage, agents, mode in pipeline_for(selected):
                if stage not in {"stage0_input", "stage1_feasibility", "stage1b_weather", "stage5_audit"}:
                    planner = results.get("travel_planner")
                    if planner and planner.result.get("is_trip_possible") is False:
                        continue
                context: dict[str, Any] = {"agent_results": results}
                if stage == "stage0_input":
                    context["validator_phase"] = "input"
                if stage == "stage5_audit":
                    context["validator_phase"] = "audit"
                if mode == "parallel" and len(agents) > 1:
                    envelopes = await asyncio.gather(
                        *[_run_agent(workflow_id, agent_id, stage, trip, context) for agent_id in agents]
                    )
                    for agent_id, env in zip(agents, envelopes, strict=True):
                        results[agent_id] = env
                else:
                    for agent_id in agents:
                        env = await _run_agent(workflow_id, agent_id, stage, trip, context)
                        key = "validator_audit" if stage == "stage5_audit" else agent_id
                        results[key] = env
                        context["agent_results"] = results

                        if stage == "stage0_input" and env.status != "ok":
                            wf = await svc.get_workflow(workflow_id)
                            wf.status = "needs_input"
                            wf.error = "; ".join(env.missing_information + env.errors + env.warnings) or "Input validation did not pass."
                            wf.finished_at = _now()
                            wf.request.status = "needs_input"
                            await session.commit()
                            return

            wf = await svc.get_workflow(workflow_id)
            plan_doc = combine_plan(trip, results)
            session.add(
                TravelPlan(
                    workflow_id=wf.id,
                    feasibility="YES" if plan_doc["trip_status"]["is_possible"] else "NO",
                    summary=plan_doc,
                )
            )
            audit = results.get("validator_audit")
            audit_approved = audit is None or audit.result.get("is_valid") is True
            wf.status = "completed" if audit_approved else "needs_review"
            if not audit_approved:
                warnings = (audit.result or {}).get("flags_or_warnings", [])
                wf.error = "; ".join(warnings) or "The final audit could not verify one or more required checks."
            wf.finished_at = _now()
            wf.request.status = wf.status
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            wf = await svc.get_workflow(workflow_id)
            wf.status = "failed"
            wf.error = str(exc)
            wf.finished_at = _now()
            wf.request.status = "failed"
            await session.commit()


async def _run_agent(
    workflow_id: UUID,
    agent_id: str,
    stage: str,
    trip: TripRequest,
    context: dict[str, Any],
) -> AgentEnvelope:
    # Each parallel agent owns a separate AsyncSession; SQLAlchemy sessions cannot
    # safely be used concurrently by asyncio tasks.
    async with SessionLocal() as session:
        execution = AgentExecution(
            workflow_id=workflow_id,
            agent_id=agent_id,
            stage=stage,
            status="running",
            attempt=1,
            input_payload={**trip.public_dict(), "validated_context": _context_snapshot(context)},
            started_at=_now(),
        )
        session.add(execution)
        await session.commit()
        await session.refresh(execution)

        last_error = None
        for attempt in range(1, settings.max_agent_retries + 2):
            execution.attempt = attempt
            execution.status = "running" if attempt == 1 else "retrying"
            await session.commit()
            try:
                agent = build_agent(agent_id)
                env = await agent.run(trip, context)
                if env.status == "failed":
                    raise RuntimeError("; ".join(env.errors) or f"{agent_id} returned failed status")
                execution.status = (
                    "succeeded" if env.status in {"ok", "partial", "degraded", "needs_input", "no_data"} else "failed"
                )
                execution.output_payload = env.model_dump()
                execution.finished_at = _now()
                execution.error = None if execution.status == "succeeded" else "; ".join(env.errors)
                await session.commit()
                return env
            except Exception as exc:  # noqa: BLE001
                last_error = f"{exc}\n{traceback.format_exc()}"
                execution.error = str(exc)
                await session.commit()

        execution.status = "failed"
        execution.finished_at = _now()
        env = AgentEnvelope(agent=agent_id, status="failed", errors=[last_error or "unknown"], result={})
        execution.output_payload = env.model_dump()
        await session.commit()
        return env


def _context_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    results = context.get("agent_results", {})
    return {
        "validator_phase": context.get("validator_phase"),
        "agent_results": {
            key: value.model_dump() if isinstance(value, AgentEnvelope) else value
            for key, value in results.items()
        },
    }


def _now():
    return datetime.now(timezone.utc)


def workflow_to_dict(wf: Workflow) -> dict[str, Any]:
    executions = sorted(wf.executions, key=lambda e: (e.started_at or wf.created_at, e.agent_id))
    return {
        "id": str(wf.id),
        "status": wf.status,
        "selected_agents": wf.selected_agents,
        "dag": wf.dag,
        "error": wf.error,
        "started_at": wf.started_at.isoformat() if wf.started_at else None,
        "finished_at": wf.finished_at.isoformat() if wf.finished_at else None,
        "request": wf.request.payload if wf.request else {},
        "executions": [
            {
                "id": str(e.id),
                "agent_id": e.agent_id,
                "stage": e.stage,
                "status": e.status,
                "attempt": e.attempt,
                "error": e.error,
                "output": e.output_payload,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            }
            for e in executions
        ],
        "plan": {
            "id": str(wf.plan.id),
            "feasibility": wf.plan.feasibility,
            "summary": wf.plan.summary,
        }
        if wf.plan
        else None,
    }
