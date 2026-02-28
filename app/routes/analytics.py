"""Analytics endpoints for event inspection and metrics.

Provides read-only access to event_outbox for analytics and event history queries.
Supports user/project isolation and pagination.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event_outbox import EventOutbox
from app.models.user_project import UserProject
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/my/projects", tags=["analytics"])

# Pagination constants
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_OFFSET = 0


class EventRecord:
    """Event record for API response."""

    def __init__(self, event: EventOutbox):
        self.id = event.id
        self.aggregate_type = event.aggregate_type
        self.aggregate_id = event.aggregate_id
        self.event_type = event.event_type
        self.payload = event.payload
        self.status = event.status
        self.retry_count = event.retry_count
        self.created_at = event.created_at
        self.published_at = event.published_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "id": str(self.id),
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "event_type": self.event_type,
            "payload": self.payload,
            "status": self.status,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
        }


async def verify_project_access(
    db: AsyncSession, user_id: UUID, project_id: UUID
) -> UserProject:
    """Verify user has access to project."""
    result = await db.execute(
        select(UserProject).where(
            and_(
                UserProject.id == project_id,
                UserProject.user_id == user_id,
            )
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project not found or access denied",
        )
    return project


@router.get("/{project_id}/events", response_model=dict[str, Any])
async def get_project_events(
    project_id: UUID,
    user_id: UUID = Query(..., description="User ID (from JWT)"),
    event_type: str | None = Query(None, description="Filter by event type"),
    aggregate_type: str | None = Query(None, description="Filter by aggregate type"),
    status: str | None = Query(None, description="Filter by status (pending/published/failed)"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(DEFAULT_OFFSET, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Task 5.1: Get events for a project.

    Returns all events for a project ordered by creation date (newest first).
    Supports filtering by event_type, aggregate_type, and status.
    """
    # Verify project access
    await verify_project_access(db, user_id, project_id)

    # Build query
    query = select(EventOutbox).where(
        EventOutbox.project_id == project_id,
    )

    # Apply filters
    if event_type:
        query = query.where(EventOutbox.event_type == event_type)
    if aggregate_type:
        query = query.where(EventOutbox.aggregate_type == aggregate_type)
    if status:
        query = query.where(EventOutbox.status == status)

    # Order by created_at descending (newest first)
    query = query.order_by(desc(EventOutbox.created_at))

    # Get total count
    count_result = await db.execute(
        select(EventOutbox).where(EventOutbox.project_id == project_id)
    )
    total_count = len(count_result.fetchall())

    # Apply pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "items": [EventRecord(event).to_dict() for event in events],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{project_id}/analytics/sessions/{session_id}/events",
    response_model=dict[str, Any],
)
async def get_session_events(
    project_id: UUID,
    session_id: UUID,
    user_id: UUID = Query(..., description="User ID (from JWT)"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(DEFAULT_OFFSET, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Task 5.2: Get events for a specific session.

    Returns all events related to a specific chat session.
    Filters by session_id in event payload.
    """
    # Verify project access
    await verify_project_access(db, user_id, project_id)

    # Build query - search for session_id in payload
    # For now, we get all events and filter in Python since JSONB filtering is complex
    # In production, would use PostgreSQL JSONB @> operator
    query = select(EventOutbox).where(
        EventOutbox.project_id == project_id,
    )

    if event_type:
        query = query.where(EventOutbox.event_type == event_type)

    query = query.order_by(desc(EventOutbox.created_at))

    result = await db.execute(query)
    all_events = result.scalars().all()

    # Filter by session_id in payload
    filtered_events = [
        event
        for event in all_events
        if event.payload and event.payload.get("session_id") == str(session_id)
    ]

    # Get total count
    total_count = len(filtered_events)

    # Apply pagination
    paginated_events = filtered_events[offset : offset + limit]

    return {
        "items": [EventRecord(event).to_dict() for event in paginated_events],
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "session_id": str(session_id),
    }


@router.get("/{project_id}/analytics", response_model=dict[str, Any])
async def get_project_analytics(
    project_id: UUID,
    user_id: UUID = Query(..., description="User ID (from JWT)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Task 5.3: Get analytics summary for a project.

    Returns aggregated metrics about events in a project:
    - Total events count
    - Events by type
    - Events by status
    - Publication latency stats
    - Event retention info
    """
    # Verify project access
    await verify_project_access(db, user_id, project_id)

    # Get all events for the project
    result = await db.execute(
        select(EventOutbox).where(EventOutbox.project_id == project_id)
    )
    events = result.scalars().all()

    # Calculate metrics
    total_events = len(events)
    
    # Events by type
    events_by_type: dict[str, int] = {}
    for event in events:
        events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1

    # Events by status
    events_by_status: dict[str, int] = {}
    for event in events:
        events_by_status[event.status] = events_by_status.get(event.status, 0) + 1

    # Publication latency stats (for published events)
    published_events = [
        e for e in events if e.published_at and e.created_at
    ]
    latency_ms_list = [
        (e.published_at - e.created_at).total_seconds() * 1000
        for e in published_events
    ]

    latency_stats = {
        "min_ms": min(latency_ms_list) if latency_ms_list else None,
        "max_ms": max(latency_ms_list) if latency_ms_list else None,
        "avg_ms": sum(latency_ms_list) / len(latency_ms_list)
        if latency_ms_list
        else None,
        "count": len(published_events),
    }

    # Event retention info
    oldest_event = min((e.created_at for e in events), default=None)
    newest_event = max((e.created_at for e in events), default=None)

    return {
        "project_id": str(project_id),
        "total_events": total_events,
        "events_by_type": events_by_type,
        "events_by_status": events_by_status,
        "latency_stats": latency_stats,
        "retention": {
            "oldest_event": oldest_event.isoformat() if oldest_event else None,
            "newest_event": newest_event.isoformat() if newest_event else None,
            "retention_days": (
                (newest_event - oldest_event).days
                if oldest_event and newest_event
                else None
            ),
        },
    }
