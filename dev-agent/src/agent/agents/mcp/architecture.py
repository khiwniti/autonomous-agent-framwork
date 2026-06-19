"""Architecture Agent - Technical Architecture and ADRs.

Specializes in:
- Creating architecture decision records (ADRs)
- Defining technical architecture
- Technology stack validation
- Infrastructure planning
"""

from typing import Any

from agent.langgraph.state import ArchitectureDecision, SDLCPhase, SDLCState
from .base import AgentOutput, MCPAgentBase


class ArchitectureAgent(MCPAgentBase):
    """
    Architecture Agent for SDLC Phase 3.
    
    Responsibilities:
    - Validate and refine technology choices
    - Create Architecture Decision Records (ADRs)
    - Define deployment architecture
    - Plan for scalability and security
    - Document integration patterns
    
    MCP Tools:
    - Filesystem: Read design docs, write ADRs
    - Git: Review existing codebase patterns
    - Browser: Research latest best practices
    """
    
    PHASE = SDLCPhase.ARCHITECTURE
    
    @property
    def role_description(self) -> str:
        return """Software Architect specializing in scalable SaaS systems.
        Expert in cloud-native patterns, security, and modern web architectures."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior Software Architect for SaaS applications.

## Core Responsibilities
- Validate technology stack choices
- Create Architecture Decision Records (ADRs)
- Design for scalability, security, and maintainability
- Define integration and communication patterns
- Plan infrastructure and deployment strategy

## ADR Format
Use this structure for each significant decision:

```markdown
# ADR-{number}: {title}

## Status
Proposed/Accepted/Deprecated/Superseded

## Context
Why this decision is needed.

## Decision
What we decided to do.

## Consequences
Positive and negative outcomes.

## Alternatives Considered
Other options we evaluated.
```

## Default Architecture (Next.js + Supabase)
Standard patterns for the tech stack:

1. **Frontend Architecture**
   - App Router with Server Components
   - Client components for interactivity
   - Server Actions for mutations
   - Middleware for auth protection

2. **Backend Architecture**
   - Supabase for Auth, Database, Storage
   - Edge Functions for custom logic
   - Row Level Security (RLS) policies
   - Realtime subscriptions where needed

3. **State Management**
   - Server state: Tanstack Query
   - Client state: Zustand (if needed)
   - Form state: React Hook Form

4. **Security Patterns**
   - JWT-based authentication
   - RLS for data access control
   - CORS configuration
   - Input validation (Zod)

## Scalability Considerations
- Database: Connection pooling, query optimization
- Frontend: Edge caching, ISR, image optimization
- API: Rate limiting, pagination, caching

## Output Format
Produce:
1. Architecture overview document
2. ADRs for all significant decisions
3. Deployment architecture diagram
4. Security architecture plan

Write to `/workspace/docs/architecture/` directory."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process architecture phase from state."""
        design = state.get("phase_outputs", {}).get("design", {})
        prd = state.get("phase_outputs", {}).get("requirements", {})
        
        task_prompt = f"""## Architecture Design Task

**Previous Artifacts:**
- PRD: Available
- System Design: Available

**Design Summary:**
{str(design)[:2000]}

**Instructions:**
1. Review the PRD and system design
2. Validate technology choices
3. Create ADRs for key decisions:
   - Authentication approach
   - Database design patterns
   - State management strategy
   - Deployment architecture
   - Security model
4. Document the overall architecture
5. Create deployment architecture diagram

Write outputs to:
- `/workspace/docs/architecture/overview.md`
- `/workspace/docs/architecture/adr/` (one file per ADR)
- `/workspace/docs/architecture/security.md`
- `/workspace/docs/architecture/deployment.md`"""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "architecture_complete": True,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=["architecture/overview.md"],
            next_actions=["Review architecture decisions", "Proceed to coding phase"],
            requires_approval=True,
        )
