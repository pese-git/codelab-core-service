"""Project validation middleware and dependencies."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.user_isolation import get_current_user_id
from app.models.user_project import UserProject


async def get_project_with_validation(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserProject:
    """Get and validate project belongs to current user.

    Validates that:
    - Project exists in database
    - Project belongs to current user

    Args:
        project_id: UUID of the project to validate
        request: FastAPI request with user context
        db: Database session

    Returns:
        UserProject object

    Raises:
        HTTPException: 404 if project not found or doesn't belong to user
    """
    user_id = get_current_user_id(request)

    result = await db.execute(
        select(UserProject).where(
            (UserProject.id == project_id) & (UserProject.user_id == user_id)
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project
