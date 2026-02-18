"""Project management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.user_isolation import get_current_user_id
from app.models.user_project import UserProject
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.core.worker_space_manager import WorkerSpaceManager
from app.core.starter_pack import initialize_starter_pack

router = APIRouter(prefix="/my/projects", tags=["projects"])


def get_worker_space_manager() -> WorkerSpaceManager:
    """Get worker space manager dependency (singleton)."""
    return WorkerSpaceManager()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    manager: WorkerSpaceManager = Depends(get_worker_space_manager),
) -> ProjectResponse:
    """Create new project for user with Default Starter Pack or return existing.

    If a project with the same name already exists for the user, returns the existing project.
    Otherwise, automatically initializes a new project with:
    - Default project record in database
    - Default Starter Pack agents (CodeAssistant, DataAnalyst, DocumentWriter)
    - User Worker Space for the project

    Args:
        project_data: Project creation data (name, workspace_path)
        request: FastAPI request with user context
        db: Database session
        manager: Worker space manager

    Returns:
        ProjectResponse with created or existing project information
    """
    from app.logging_config import get_logger
    logger = get_logger(__name__)
    
    user_id = get_current_user_id(request)

    # Check if project with same name already exists for this user
    result = await db.execute(
        select(UserProject).where(
            (UserProject.user_id == user_id) & (UserProject.name == project_data.name)
        )
    )
    existing_project = result.scalar_one_or_none()
    
    if existing_project:
        logger.info(
            "project_already_exists",
            user_id=str(user_id),
            project_id=str(existing_project.id),
            project_name=project_data.name,
        )
        return ProjectResponse.model_validate(existing_project)

    # Create project in database
    project = UserProject(
        user_id=user_id,
        name=project_data.name,
        workspace_path=project_data.workspace_path,
    )
    db.add(project)
    await db.flush()  # Flush to get project.id

    # Initialize Default Starter Pack agents for the project
    try:
        agents = await initialize_starter_pack(db, user_id, project.id)
        logger.info(
            "starter_pack_initialized",
            user_id=str(user_id),
            project_id=str(project.id),
            agents_count=len(agents),
        )
    except Exception as e:
        # Log error but don't fail project creation
        logger.warning(
            "starter_pack_init_error",
            user_id=str(user_id),
            project_id=str(project.id),
            error=str(e),
        )

    # Commit all changes (project + agents)
    await db.commit()
    await db.refresh(project)

    logger.info(
        "project_created",
        user_id=str(user_id),
        project_id=str(project.id),
        project_name=project.name,
    )

    return ProjectResponse.model_validate(project)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """Get all projects for current user.

    Args:
        request: FastAPI request with user context
        db: Database session

    Returns:
        ProjectListResponse with list of user projects
    """
    user_id = get_current_user_id(request)

    # Query all projects for user
    result = await db.execute(
        select(UserProject).where(UserProject.user_id == user_id)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.get("/{project_id}/", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project information by ID.

    Args:
        project_id: Project UUID
        request: FastAPI request with user context
        db: Database session

    Returns:
        ProjectResponse with project information

    Raises:
        HTTPException: 404 if project not found or doesn't belong to user
    """
    user_id = get_current_user_id(request)

    # Query project with authorization check
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

    return ProjectResponse.model_validate(project)


@router.put("/{project_id}/", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project information.

    Args:
        project_id: Project UUID
        project_data: Project update data
        request: FastAPI request with user context
        db: Database session

    Returns:
        ProjectResponse with updated project information

    Raises:
        HTTPException: 404 if project not found or doesn't belong to user
    """
    user_id = get_current_user_id(request)

    # Query project with authorization check
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

    # Update fields if provided
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.workspace_path is not None:
        project.workspace_path = project_data.workspace_path

    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    manager: WorkerSpaceManager = Depends(get_worker_space_manager),
) -> None:
    """Delete project.

    Note: Only deletes backend resources (User Worker Space and database entry).
    User workspace files are NOT deleted.

    Args:
        project_id: Project UUID
        request: FastAPI request with user context
        db: Database session
        manager: Worker space manager

    Raises:
        HTTPException: 404 if project not found or doesn't belong to user
    """
    user_id = get_current_user_id(request)

    # Query project with authorization check
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

    # Cleanup backend resources (User Worker Space)
    await manager.remove(user_id, str(project_id))

    # Delete project from database
    # Cascade will delete all related agents, sessions, etc.
    await db.delete(project)
    await db.commit()
