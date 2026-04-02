"""Event handlers for user synchronization from auth-service"""

import logging
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.user_project import UserProject
from app.models.user_agent import UserAgent
from app.models.chat_session import ChatSession
from app.models.message import Message

logger = logging.getLogger(__name__)


class UserEventHandlers:
    """Handlers for user synchronization events from auth-service"""

    @staticmethod
    async def handle_user_created(event: dict) -> None:
        """
        Handle user.created event - create user profile in core-service.
        
        Idempotent: if user already exists, just return.
        
        Args:
            event: Event dict with user data
        
        Raises:
            Exception: Any exception triggers retry
        """
        try:
            # Extract user data from event
            event_data = event.get("data", {})
            
            if isinstance(event_data, str):
                event_data = json.loads(event_data)
            
            user_id = event_data.get("user_id")
            email = event_data.get("email")
            
            if not user_id or not email:
                logger.error(
                    f"Invalid user.created event: missing user_id or email"
                )
                raise ValueError("Invalid user.created event")
            
            # Convert user_id to UUID
            user_id_uuid = UUID(user_id)
            
            # Get DB session
            async for session in get_db():
                try:
                    # Check if user already exists (idempotency)
                    result = await session.execute(
                        select(User).where(User.id == user_id_uuid)
                    )
                    existing_user = result.scalar_one_or_none()
                    
                    if existing_user:
                        logger.info(
                            f"User already exists, skipping creation: "
                            f"user_id={user_id}"
                        )
                        return
                    
                    # Create new user
                    user = User(
                        id=user_id_uuid,
                        email=email,
                        created_at=datetime.now(timezone.utc),
                    )
                    
                    session.add(user)
                    await session.commit()
                    
                    logger.info(
                        f"User created from auth-service event: "
                        f"user_id={user_id}, email={email}"
                    )

                except Exception as e:
                    await session.rollback()
                    logger.error(
                        f"Failed to create user: user_id={user_id}, error={str(e)}"
                    )
                    raise
                finally:
                    await session.close()

        except Exception as e:
            logger.error(
                f"Error handling user.created event: {str(e)}"
            )
            raise

    @staticmethod
    async def handle_user_updated(event: dict) -> None:
        """
        Handle user.updated event - update user profile in core-service.
        
        Idempotent: if user doesn't exist, skip with warning.
        
        Args:
            event: Event dict with updated user data
        
        Raises:
            Exception: Any exception triggers retry
        """
        try:
            # Extract user data from event
            event_data = event.get("data", {})
            
            if isinstance(event_data, str):
                event_data = json.loads(event_data)
            
            user_id = event_data.get("user_id")
            email = event_data.get("email")
            changes = event_data.get("changes", [])
            
            if not user_id:
                logger.error(
                    f"Invalid user.updated event: missing user_id"
                )
                raise ValueError("Invalid user.updated event")
            
            # Convert user_id to UUID
            user_id_uuid = UUID(user_id)
            
            # Get DB session
            async for session in get_db():
                try:
                    # Get existing user
                    result = await session.execute(
                        select(User).where(User.id == user_id_uuid)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        logger.warning(
                            f"User not found for update (race condition?): "
                            f"user_id={user_id}"
                        )
                        return
                    
                    # Update user fields if they changed
                    if "email" in changes and email:
                        user.email = email
                    
                    # Update modified timestamp
                    user.updated_at = datetime.now(timezone.utc)
                    
                    await session.commit()
                    
                    logger.info(
                        f"User updated from auth-service event: "
                        f"user_id={user_id}, changes={changes}"
                    )

                except Exception as e:
                    await session.rollback()
                    logger.error(
                        f"Failed to update user: user_id={user_id}, error={str(e)}"
                    )
                    raise
                finally:
                    await session.close()

        except Exception as e:
            logger.error(
                f"Error handling user.updated event: {str(e)}"
            )
            raise

    @staticmethod
    async def handle_user_deleted(event: dict) -> None:
        """
        Handle user.deleted event - CASCADE delete all user data.
        
        Deletes in order:
        1. Messages (no FK to others)
        2. ChatSessions
        3. UserAgents
        4. UserProjects
        5. User profile
        
        Idempotent: if user already deleted, just log and return.
        
        Args:
            event: Event dict with deletion data
        
        Raises:
            Exception: Any exception triggers retry
        """
        try:
            # Extract user data from event
            event_data = event.get("data", {})
            
            if isinstance(event_data, str):
                event_data = json.loads(event_data)
            
            user_id = event_data.get("user_id")
            reason = event_data.get("reason", "unknown")
            
            if not user_id:
                logger.error(
                    f"Invalid user.deleted event: missing user_id"
                )
                raise ValueError("Invalid user.deleted event")
            
            # Convert user_id to UUID
            user_id_uuid = UUID(user_id)
            
            # Get DB session
            async for session in get_db():
                try:
                    # Check if user exists
                    result = await session.execute(
                        select(User).where(User.id == user_id_uuid)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        logger.info(
                            f"User already deleted or never existed: "
                            f"user_id={user_id}"
                        )
                        return
                    
                    # CASCADE delete in correct order
                    logger.info(
                        f"Starting cascade delete for user: "
                        f"user_id={user_id}, reason={reason}"
                    )
                    
                    # 1. Delete messages
                    await session.execute(
                        delete(Message).where(Message.user_id == user_id_uuid)
                    )
                    logger.debug(f"Deleted messages for user: {user_id}")
                    
                    # 2. Delete chat sessions
                    await session.execute(
                        delete(ChatSession).where(ChatSession.user_id == user_id_uuid)
                    )
                    logger.debug(f"Deleted chat sessions for user: {user_id}")
                    
                    # 3. Delete user agents
                    await session.execute(
                        delete(UserAgent).where(UserAgent.user_id == user_id_uuid)
                    )
                    logger.debug(f"Deleted user agents for user: {user_id}")
                    
                    # 4. Delete user projects
                    await session.execute(
                        delete(UserProject).where(UserProject.user_id == user_id_uuid)
                    )
                    logger.debug(f"Deleted user projects for user: {user_id}")
                    
                    # 5. Delete user profile
                    await session.delete(user)
                    logger.debug(f"Deleted user profile: {user_id}")
                    
                    # Commit all deletions
                    await session.commit()
                    
                    logger.info(
                        f"User cascade deletion completed: "
                        f"user_id={user_id}, reason={reason}"
                    )

                except Exception as e:
                    await session.rollback()
                    logger.error(
                        f"Failed to cascade delete user: "
                        f"user_id={user_id}, error={str(e)}"
                    )
                    raise
                finally:
                    await session.close()

        except Exception as e:
            logger.error(
                f"Error handling user.deleted event: {str(e)}"
            )
            raise

    @staticmethod
    async def handle_token_revoked(event: dict) -> None:
        """
        Handle token.revoked event - logging only.
        
        This event is informational. The actual token blacklist check
        happens in the middleware. No DB changes needed.
        
        Args:
            event: Event dict with token revocation data
        """
        try:
            event_data = event.get("data", {})
            
            if isinstance(event_data, str):
                event_data = json.loads(event_data)
            
            token_jti = event_data.get("token_jti")
            user_id = event_data.get("user_id")
            reason = event_data.get("reason", "unknown")
            
            logger.info(
                f"Token revoked event received: "
                f"token_jti={token_jti}, user_id={user_id}, reason={reason}"
            )

        except Exception as e:
            logger.error(
                f"Error handling token.revoked event: {str(e)}"
            )
            # Don't raise - this is just logging


# Create handler instances for registration
handlers = UserEventHandlers()
