"""SDLC State Management for LangGraph.

This module defines the state schema used across all SDLC agents,
following the structured artifact communication model from MetaGPT.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, TypedDict
import operator

from pydantic import BaseModel, Field


class SDLCPhase(str, Enum):
    """SDLC workflow phases."""
    
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    CODING = "coding"
    TESTING = "testing"
    CICD = "cicd"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


class ApprovalStatus(str, Enum):
    """Human approval gate statuses."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class TaskState(str, Enum):
    """A2A-compatible task states."""
    
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Structured Artifacts (PRD, Design Docs, Architecture, etc.)
# ============================================================================

class UserStory(BaseModel):
    """User story with acceptance criteria."""
    
    id: str = Field(description="User story ID (e.g., US-001)")
    title: str = Field(description="Story title")
    description: str = Field(description="As a <role>, I want <feature> so that <benefit>")
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = Field(default="medium", description="high/medium/low")
    story_points: int | None = Field(default=None)


class PRD(BaseModel):
    """Product Requirements Document artifact."""
    
    project_name: str
    version: str = Field(default="1.0.0")
    description: str
    goals: list[str] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    non_functional_requirements: dict[str, str] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataModel(BaseModel):
    """Database schema definition."""
    
    name: str
    type: str = Field(description="table/collection/document")
    columns: dict[str, dict[str, Any]] = Field(default_factory=dict)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)


class APIEndpoint(BaseModel):
    """API endpoint specification."""
    
    path: str
    method: str = Field(description="GET/POST/PUT/DELETE/PATCH")
    description: str
    request_schema: dict[str, Any] | None = Field(default=None)
    response_schema: dict[str, Any] | None = Field(default=None)
    auth_required: bool = Field(default=True)


class SystemDesign(BaseModel):
    """System design artifact."""
    
    version: str = Field(default="1.0.0")
    data_models: list[DataModel] = Field(default_factory=list)
    api_endpoints: list[APIEndpoint] = Field(default_factory=list)
    system_architecture: str = Field(default="", description="Mermaid diagram or description")
    component_diagram: str = Field(default="")
    sequence_diagrams: dict[str, str] = Field(default_factory=dict)


class TechStackDecision(BaseModel):
    """Technology stack decision."""
    
    category: str = Field(description="frontend/backend/database/infrastructure/etc.")
    choice: str = Field(description="Selected technology")
    rationale: str = Field(description="Why this choice was made")
    alternatives_considered: list[str] = Field(default_factory=list)


class ArchitectureDecision(BaseModel):
    """Architecture decision artifact."""
    
    version: str = Field(default="1.0.0")
    tech_stack: list[TechStackDecision] = Field(default_factory=list)
    project_structure: dict[str, str] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    build_configuration: dict[str, Any] = Field(default_factory=dict)
    adr_records: list[dict[str, str]] = Field(default_factory=list)  # Architecture Decision Records


class CodeFile(BaseModel):
    """Generated code file artifact."""
    
    path: str = Field(description="Relative file path")
    content: str = Field(description="File content")
    language: str = Field(description="Programming language")
    module: str = Field(default="", description="Module/component this belongs to")
    generated_by: str = Field(default="coding_agent")
    reviewed: bool = Field(default=False)


class TestResult(BaseModel):
    """Test execution result."""
    
    test_name: str
    status: str = Field(description="passed/failed/skipped")
    duration_ms: float
    error_message: str | None = Field(default=None)
    stack_trace: str | None = Field(default=None)


class TestReport(BaseModel):
    """Test execution report artifact."""
    
    test_type: str = Field(description="unit/integration/e2e")
    total_tests: int
    passed: int
    failed: int
    skipped: int
    coverage_percentage: float | None = Field(default=None)
    results: list[TestResult] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeploymentStatus(BaseModel):
    """Deployment status artifact."""
    
    environment: str = Field(description="dev/staging/production")
    status: str = Field(description="pending/deploying/deployed/failed")
    url: str | None = Field(default=None)
    version: str = Field(default="")
    deployed_at: datetime | None = Field(default=None)
    health_check: bool = Field(default=False)
    logs: list[str] = Field(default_factory=list)


# ============================================================================
# Main SDLC State (LangGraph TypedDict)
# ============================================================================

class SDLCState(TypedDict):
    """
    Main state schema for SDLC workflow.
    
    Uses Annotated types with operator.add for list accumulation
    across parallel agent executions.
    """
    
    # Project metadata
    project_id: str
    project_name: str
    user_input: str
    
    # Current workflow state
    current_phase: SDLCPhase
    iteration_count: int
    max_iterations: int
    
    # Human approval gates
    approval_status: ApprovalStatus
    approval_feedback: str
    pending_approval_phase: SDLCPhase | None
    
    # Structured artifacts (immutable per phase)
    prd: dict | None  # PRD artifact as dict
    system_design: dict | None  # SystemDesign artifact
    architecture: dict | None  # ArchitectureDecision artifact
    
    # Code artifacts (accumulated via parallel coding agents)
    code_files: Annotated[list[dict], operator.add]  # List of CodeFile as dicts
    
    # Test artifacts
    test_results: dict | None  # TestReport artifact
    test_failures: list[dict]
    
    # Deployment artifacts
    deployment_status: dict | None  # DeploymentStatus artifact
    
    # CI/CD configuration
    cicd_config: dict | None
    
    # Agent messages (LangGraph message accumulation)
    messages: Annotated[list[dict], operator.add]
    
    # Error handling
    errors: list[str]
    last_error: str | None
    
    # Metadata
    started_at: str
    updated_at: str
    

def create_initial_state(
    project_id: str,
    project_name: str,
    user_input: str,
    max_iterations: int = 10,
) -> SDLCState:
    """Create initial SDLC state for a new workflow.
    
    Args:
        project_id: Unique project identifier
        project_name: Human-readable project name
        user_input: Initial user requirements/description
        max_iterations: Max code-test-fix iterations
        
    Returns:
        Initialized SDLCState
    """
    now = datetime.now(timezone.utc).isoformat()
    
    return SDLCState(
        project_id=project_id,
        project_name=project_name,
        user_input=user_input,
        current_phase=SDLCPhase.REQUIREMENTS,
        iteration_count=0,
        max_iterations=max_iterations,
        approval_status=ApprovalStatus.PENDING,
        approval_feedback="",
        pending_approval_phase=None,
        prd=None,
        system_design=None,
        architecture=None,
        code_files=[],
        test_results=None,
        test_failures=[],
        deployment_status=None,
        cicd_config=None,
        messages=[],
        errors=[],
        last_error=None,
        started_at=now,
        updated_at=now,
    )


# ============================================================================
# State Reducers for Agent Updates
# ============================================================================

def update_phase(state: SDLCState, new_phase: SDLCPhase) -> dict:
    """Create state update for phase transition."""
    return {
        "current_phase": new_phase,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def update_artifact(
    state: SDLCState,
    artifact_type: str,
    artifact: BaseModel,
) -> dict:
    """Create state update for artifact.
    
    Args:
        state: Current state
        artifact_type: One of 'prd', 'system_design', 'architecture', etc.
        artifact: Pydantic model to serialize
        
    Returns:
        State update dict
    """
    return {
        artifact_type: artifact.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def add_code_files(state: SDLCState, files: list[CodeFile]) -> dict:
    """Create state update to add code files (uses operator.add)."""
    return {
        "code_files": [f.model_dump() for f in files],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def record_error(state: SDLCState, error: str) -> dict:
    """Record an error in state."""
    return {
        "errors": state.get("errors", []) + [error],
        "last_error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
