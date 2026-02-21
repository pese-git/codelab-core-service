"""SQLAlchemy models for Tool execution logging"""

from sqlalchemy import Column, String, JSON, DateTime, Integer, Boolean, UUID as SQLUUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class ToolExecution(Base):
    """Tool execution log (optional database persistence)
    
    Stores execution history for auditing and debugging purposes.
    Sensitive data like file contents is masked before storage.
    """
    
    __tablename__ = "tool_executions"
    
    # Primary key
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    user_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    project_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(SQLUUID(as_uuid=True), nullable=True, index=True)
    approval_id = Column(SQLUUID(as_uuid=True), nullable=True, index=True)
    
    # Tool execution details
    tool_name = Column(String(50), nullable=False, index=True)
    tool_params = Column(JSON, nullable=True)  # Masked sensitive data
    result = Column(JSON, nullable=True)  # Tool result (also masked if needed)
    
    # Risk and approval information
    risk_level = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH
    requires_approval = Column(Boolean, default=False)
    
    # Execution status
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, approved, rejected, completed, failed
    
    # Error handling
    error = Column(String(1000), nullable=True)
    error_type = Column(String(100), nullable=True)
    
    # Performance metrics
    execution_time_ms = Column(Integer, default=0)  # milliseconds
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Additional metadata
    metadata_json = Column(JSON, nullable=True)  # Custom metadata
    
    def __repr__(self):
        return (
            f"<ToolExecution(id={self.id}, tool={self.tool_name}, "
            f"status={self.status}, risk={self.risk_level})>"
        )
    
    @property
    def execution_duration_seconds(self) -> float:
        """Get execution duration in seconds"""
        if self.completed_at and self.created_at:
            delta = self.completed_at - self.created_at
            return delta.total_seconds()
        return 0.0
    
    @property
    def is_approved(self) -> bool:
        """Check if execution was approved"""
        return self.status in ("approved", "completed")
    
    @property
    def is_failed(self) -> bool:
        """Check if execution failed"""
        return self.status in ("failed", "rejected")


class ApprovalLog(Base):
    """Approval request log for tool executions
    
    Tracks approval workflow for audit trail.
    """
    
    __tablename__ = "tool_approval_logs"
    
    # Primary key
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    tool_execution_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    approval_request_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    
    # Approval details
    action = Column(String(20), nullable=False)  # approved, rejected
    reason = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return (
            f"<ApprovalLog(id={self.id}, tool_id={self.tool_execution_id}, "
            f"action={self.action})>"
        )
