"""Design Agent - System Design and UI/UX Planning.

Specializes in:
- Creating system design documents
- Database schema design
- API design
- UI/UX wireframes and component planning
"""

from typing import Any

from agent.langgraph.state import SDLCPhase, SDLCState, SystemDesign
from .base import AgentOutput, MCPAgentBase


class DesignAgent(MCPAgentBase):
    """
    Design Agent for SDLC Phase 2.
    
    Responsibilities:
    - Create system design from PRD
    - Design database schema (Supabase/PostgreSQL)
    - Plan API endpoints and contracts
    - Create UI component hierarchy
    - Define state management approach
    
    MCP Tools:
    - Filesystem: Read PRD, write design docs
    - Browser: Research design patterns, UI libraries
    - Memory: Store reusable design patterns
    """
    
    PHASE = SDLCPhase.DESIGN
    
    @property
    def role_description(self) -> str:
        return """System Designer and UI/UX Specialist for SaaS applications.
        Expert in database design, API architecture, and modern frontend patterns."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior System Designer for SaaS product development.

## Core Responsibilities
- Translate PRD into technical system design
- Design scalable database schemas
- Create RESTful/GraphQL API specifications
- Plan UI component architecture
- Define data flow and state management

## Database Design (Supabase/PostgreSQL)
When designing schemas:
1. Use proper normalization (usually 3NF)
2. Define relationships with foreign keys
3. Plan indexes for query patterns
4. Include audit fields (created_at, updated_at)
5. Consider Row Level Security (RLS) policies
6. Plan for soft deletes where appropriate

## API Design
For API endpoints:
1. Follow RESTful conventions
2. Use consistent naming (kebab-case URLs, camelCase JSON)
3. Define request/response schemas
4. Plan authentication (Supabase Auth JWT)
5. Document error responses
6. Consider rate limiting needs

## UI/UX Design
When planning UI:
1. Use atomic design principles (atoms → molecules → organisms → pages)
2. Plan component props and state
3. Consider responsive breakpoints
4. Define navigation structure
5. Plan loading and error states
6. Ensure accessibility (a11y)

## Default Component Library
- shadcn/ui for base components
- Tailwind CSS for styling
- Lucide icons
- React Hook Form for forms
- Tanstack Query for server state

## Output Format
Produce:
1. System design document with diagrams (Mermaid)
2. Database schema (SQL or Prisma schema)
3. API specification (OpenAPI format)
4. Component hierarchy diagram
5. State management plan

Write outputs to `/workspace/docs/` directory."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process design phase from state."""
        # Get PRD from previous phase
        prd = state.get("phase_outputs", {}).get("requirements", {})
        user_request = state.get("user_request", "")
        
        task_prompt = f"""## System Design Task

**User Request:**
{user_request}

**PRD Summary:**
{self._summarize_prd(prd)}

**Instructions:**
1. Analyze the PRD thoroughly
2. Design the database schema
3. Create API specifications
4. Plan UI component hierarchy
5. Document state management approach

Write all design documents to appropriate files:
- `/workspace/docs/system-design.md` - Overview and architecture
- `/workspace/docs/database-schema.sql` - Database schema
- `/workspace/docs/api-spec.yaml` - OpenAPI specification
- `/workspace/docs/components.md` - UI component plan

Include Mermaid diagrams where helpful."""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "design_complete": True,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=["system-design.md", "database-schema.sql"],
            next_actions=["Review design documents", "Proceed to architecture phase"],
            requires_approval=True,
        )
    
    def _summarize_prd(self, prd: dict[str, Any]) -> str:
        """Summarize PRD for design context."""
        if not prd:
            return "No PRD available - design based on user request."
        
        content = prd.get("content", prd.get("raw_response", ""))
        return content[:3000] if content else str(prd)[:3000]
