"""A2A Agent Card Implementation.

Agent Cards advertise capabilities via /.well-known/agent.json following
the A2A protocol specification. They enable other agents to discover
what an agent can do before sending tasks.

Spec: https://google.github.io/A2A/specification/#agent-card
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class A2ACapability(str, Enum):
    """A2A protocol capabilities supported by an agent."""
    
    # Core capabilities
    STREAMING = "streaming"  # Server-Sent Events for real-time updates
    PUSH_NOTIFICATIONS = "pushNotifications"  # Webhook-based notifications
    STATE_PERSISTENCE = "statePersistence"  # Persist task state to history
    
    # Extended capabilities
    HUMAN_IN_LOOP = "humanInLoopApproval"  # Can pause for human approval
    FILE_UPLOAD = "fileUpload"  # Accepts file attachments
    MULTI_AGENT = "multiAgentDelegation"  # Can delegate to other agents


class InputMode(str, Enum):
    """Input modalities supported by the agent."""
    
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class OutputMode(str, Enum):
    """Output modalities produced by the agent."""
    
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class AgentIdentity(BaseModel):
    """Agent identity information for the Agent Card."""
    
    name: str = Field(description="Human-readable agent name")
    description: str = Field(description="Brief description of agent purpose")
    version: str = Field(default="1.0.0", description="Agent version")
    vendor: str = Field(default="", description="Organization/vendor name")
    homepage: str | None = Field(default=None, description="Agent homepage URL")
    documentation_url: str | None = Field(default=None, description="Documentation URL")
    icon_url: str | None = Field(default=None, description="Agent icon URL")


class AgentSkill(BaseModel):
    """
    A skill represents a specific capability the agent can perform.
    
    Skills are the primary way agents advertise what they can do.
    Other agents use skill information to route tasks appropriately.
    """
    
    id: str = Field(description="Unique skill identifier")
    name: str = Field(description="Human-readable skill name")
    description: str = Field(description="Detailed description of what the skill does")
    
    # Input/output specification
    input_modes: list[InputMode] = Field(
        default=[InputMode.TEXT],
        description="Accepted input modalities",
    )
    output_modes: list[OutputMode] = Field(
        default=[OutputMode.TEXT],
        description="Produced output modalities",
    )
    
    # Task behavior
    tags: list[str] = Field(default=[], description="Searchable tags for skill discovery")
    examples: list[str] = Field(default=[], description="Example task descriptions")
    
    # Schema for structured input (optional)
    input_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for structured input validation",
    )


class AuthenticationMethod(BaseModel):
    """Authentication method supported by the agent."""
    
    type: str = Field(description="Auth type: none, apiKey, oauth2, bearer")
    required: bool = Field(default=True, description="Whether auth is required")
    
    # OAuth2-specific fields
    authorization_url: str | None = Field(default=None, description="OAuth2 auth URL")
    token_url: str | None = Field(default=None, description="OAuth2 token URL")
    scopes: list[str] | None = Field(default=None, description="Required OAuth2 scopes")


class RateLimits(BaseModel):
    """Rate limiting configuration for the agent."""
    
    requests_per_minute: int | None = Field(default=None, description="Max requests/minute")
    requests_per_hour: int | None = Field(default=None, description="Max requests/hour")
    concurrent_tasks: int | None = Field(default=None, description="Max concurrent tasks")


class AgentCard(BaseModel):
    """
    A2A Agent Card - the primary capability advertisement mechanism.
    
    Served at /.well-known/agent.json to enable discovery.
    
    Example:
        {
            "name": "Requirements Agent",
            "description": "Analyzes requirements and produces PRDs",
            "version": "1.0.0",
            "url": "https://agent.example.com",
            "skills": [...],
            "capabilities": {...}
        }
    """
    
    # Required identity fields
    name: str = Field(description="Agent name")
    description: str = Field(description="Agent description")
    url: str = Field(description="Base URL for A2A endpoints")
    
    # Optional identity fields
    version: str = Field(default="1.0.0", description="Agent version")
    vendor: str | None = Field(default=None, description="Vendor/organization")
    documentation_url: str | None = Field(default=None)
    icon_url: str | None = Field(default=None)
    
    # Skills
    default_input_modes: list[InputMode] = Field(
        default=[InputMode.TEXT],
        description="Default input modalities",
    )
    default_output_modes: list[OutputMode] = Field(
        default=[OutputMode.TEXT],
        description="Default output modalities",
    )
    skills: list[AgentSkill] = Field(default=[], description="Agent capabilities")
    
    # Protocol capabilities
    capabilities: dict[str, bool] = Field(
        default={
            A2ACapability.STREAMING: True,
            A2ACapability.PUSH_NOTIFICATIONS: False,
            A2ACapability.STATE_PERSISTENCE: True,
        },
        description="Supported A2A capabilities",
    )
    
    # Security & limits
    authentication: AuthenticationMethod | None = Field(
        default=None,
        description="Authentication requirements",
    )
    rate_limits: RateLimits | None = Field(default=None, description="Rate limits")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    supported_protocol_versions: list[str] = Field(
        default=["1.0"],
        description="Supported A2A protocol versions",
    )
    
    def to_wellknown_json(self) -> dict[str, Any]:
        """Format for /.well-known/agent.json endpoint."""
        return self.model_dump(exclude_none=True, by_alias=True)


# ============================================================================
# Factory Functions for SDLC Agent Cards
# ============================================================================

def create_agent_card(
    name: str,
    description: str,
    url: str,
    skills: list[AgentSkill],
    capabilities: list[A2ACapability] | None = None,
    version: str = "1.0.0",
) -> AgentCard:
    """
    Factory function to create an Agent Card.
    
    Args:
        name: Agent name
        description: Agent description
        url: Base URL for A2A endpoints
        skills: List of agent skills
        capabilities: Optional list of supported capabilities
        version: Agent version
        
    Returns:
        Configured AgentCard
    """
    caps = {
        A2ACapability.STREAMING: True,
        A2ACapability.STATE_PERSISTENCE: True,
        A2ACapability.HUMAN_IN_LOOP: True,
    }
    
    if capabilities:
        for cap in capabilities:
            caps[cap] = True
    
    return AgentCard(
        name=name,
        description=description,
        url=url,
        version=version,
        skills=skills,
        capabilities=caps,
    )


# ============================================================================
# Pre-defined SDLC Agent Skills
# ============================================================================

REQUIREMENTS_SKILLS = [
    AgentSkill(
        id="analyze-requirements",
        name="Analyze Requirements",
        description="Analyze user/stakeholder input and extract structured requirements",
        input_modes=[InputMode.TEXT, InputMode.FILE],
        output_modes=[OutputMode.TEXT, OutputMode.DATA],
        tags=["requirements", "analysis", "prd"],
        examples=[
            "Analyze the requirements for a user authentication system",
            "Extract features from this product brief",
        ],
    ),
    AgentSkill(
        id="generate-prd",
        name="Generate PRD",
        description="Generate a Product Requirements Document from analyzed requirements",
        output_modes=[OutputMode.TEXT, OutputMode.DATA],
        tags=["prd", "document", "requirements"],
    ),
    AgentSkill(
        id="prioritize-features",
        name="Prioritize Features",
        description="Apply MoSCoW prioritization to features based on business value",
        tags=["prioritization", "moscow", "features"],
    ),
]

DESIGN_SKILLS = [
    AgentSkill(
        id="create-system-design",
        name="Create System Design",
        description="Design high-level system architecture from requirements",
        tags=["design", "architecture", "system"],
    ),
    AgentSkill(
        id="design-database-schema",
        name="Design Database Schema",
        description="Create database schema design with entity relationships",
        output_modes=[OutputMode.TEXT, OutputMode.DATA],
        tags=["database", "schema", "erd"],
    ),
    AgentSkill(
        id="design-api",
        name="Design API",
        description="Design REST/GraphQL API endpoints from system requirements",
        tags=["api", "rest", "graphql", "endpoints"],
    ),
]

ARCHITECTURE_SKILLS = [
    AgentSkill(
        id="evaluate-architecture",
        name="Evaluate Architecture",
        description="Evaluate architecture decisions using ATAM or similar methods",
        tags=["architecture", "evaluation", "atam"],
    ),
    AgentSkill(
        id="select-technology",
        name="Select Technology Stack",
        description="Recommend technology stack based on requirements and constraints",
        tags=["technology", "stack", "selection"],
    ),
    AgentSkill(
        id="document-adr",
        name="Document Architecture Decision",
        description="Create Architecture Decision Records (ADRs)",
        tags=["adr", "documentation", "decisions"],
    ),
]

CODING_SKILLS = [
    AgentSkill(
        id="implement-feature",
        name="Implement Feature",
        description="Implement a feature based on design specifications",
        input_modes=[InputMode.TEXT, InputMode.FILE],
        output_modes=[OutputMode.TEXT, OutputMode.FILE],
        tags=["code", "implementation", "feature"],
    ),
    AgentSkill(
        id="refactor-code",
        name="Refactor Code",
        description="Refactor existing code for improved quality",
        tags=["refactor", "code-quality"],
    ),
    AgentSkill(
        id="review-code",
        name="Review Code",
        description="Perform code review and suggest improvements",
        tags=["review", "code-quality", "pr"],
    ),
]

TESTING_SKILLS = [
    AgentSkill(
        id="generate-tests",
        name="Generate Tests",
        description="Generate unit, integration, and e2e tests",
        output_modes=[OutputMode.TEXT, OutputMode.FILE],
        tags=["testing", "unit-tests", "integration-tests"],
    ),
    AgentSkill(
        id="run-tests",
        name="Run Tests",
        description="Execute test suites and report results",
        output_modes=[OutputMode.TEXT, OutputMode.DATA],
        tags=["testing", "execution", "results"],
    ),
    AgentSkill(
        id="analyze-coverage",
        name="Analyze Test Coverage",
        description="Analyze code coverage and identify gaps",
        tags=["coverage", "testing", "quality"],
    ),
]

CICD_SKILLS = [
    AgentSkill(
        id="create-pipeline",
        name="Create CI/CD Pipeline",
        description="Generate CI/CD pipeline configuration",
        output_modes=[OutputMode.FILE],
        tags=["cicd", "pipeline", "github-actions"],
    ),
    AgentSkill(
        id="configure-deployment",
        name="Configure Deployment",
        description="Set up deployment configuration and environments",
        tags=["deployment", "configuration", "environments"],
    ),
]

DEPLOYMENT_SKILLS = [
    AgentSkill(
        id="deploy-application",
        name="Deploy Application",
        description="Deploy application to target environment",
        tags=["deployment", "release", "production"],
    ),
    AgentSkill(
        id="manage-infrastructure",
        name="Manage Infrastructure",
        description="Provision and manage cloud infrastructure",
        tags=["infrastructure", "terraform", "kubernetes"],
    ),
    AgentSkill(
        id="rollback-deployment",
        name="Rollback Deployment",
        description="Rollback to previous deployment version",
        tags=["rollback", "deployment", "recovery"],
    ),
]

MONITORING_SKILLS = [
    AgentSkill(
        id="setup-monitoring",
        name="Setup Monitoring",
        description="Configure monitoring, logging, and alerting",
        tags=["monitoring", "logging", "alerting"],
    ),
    AgentSkill(
        id="analyze-metrics",
        name="Analyze Metrics",
        description="Analyze system metrics and identify issues",
        tags=["metrics", "analysis", "performance"],
    ),
    AgentSkill(
        id="incident-response",
        name="Incident Response",
        description="Respond to incidents and perform root cause analysis",
        tags=["incidents", "rca", "response"],
    ),
]


def get_skills_for_phase(phase: str) -> list[AgentSkill]:
    """Get pre-defined skills for an SDLC phase."""
    phase_skills = {
        "requirements": REQUIREMENTS_SKILLS,
        "design": DESIGN_SKILLS,
        "architecture": ARCHITECTURE_SKILLS,
        "coding": CODING_SKILLS,
        "testing": TESTING_SKILLS,
        "cicd": CICD_SKILLS,
        "deployment": DEPLOYMENT_SKILLS,
        "monitoring": MONITORING_SKILLS,
    }
    return phase_skills.get(phase, [])
