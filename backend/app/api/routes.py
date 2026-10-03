import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Workflow
from app.schemas import CreatePlanBody
from app.services.workflow import WorkflowService, execute_workflow, workflow_to_dict

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"ok": True}


@router.post("/plans")
async def create_plan(body: CreatePlanBody, session: AsyncSession = Depends(get_session)):
    svc = WorkflowService(session)
    wf = await svc.create_queued(body)
    asyncio.create_task(execute_workflow(wf.id))
    return workflow_to_dict(wf)


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: UUID, session: AsyncSession = Depends(get_session)):
    q = (
        select(Workflow)
        .options(selectinload(Workflow.executions), selectinload(Workflow.plan), selectinload(Workflow.request))
        .where(Workflow.id == workflow_id)
    )
    res = await session.execute(q)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return workflow_to_dict(wf)


@router.get("/workflows")
async def list_workflows(session: AsyncSession = Depends(get_session)):
    q = (
        select(Workflow)
        .options(selectinload(Workflow.executions), selectinload(Workflow.plan), selectinload(Workflow.request))
        .order_by(Workflow.created_at.desc())
        .limit(30)
    )
    res = await session.execute(q)
    return [workflow_to_dict(w) for w in res.scalars().all()]
