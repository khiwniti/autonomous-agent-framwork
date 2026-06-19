"""Requirements Agent - PRD and User Story Generation.

Specializes in:
- Extracting requirements from user input
- Creating structured PRDs
- Generating user stories with acceptance criteria
- Defining MVP scope
"""

from typing import Any

from pydantic import BaseModel, Field

from agent.langgraph.state import PRD, SDLCPhase, SDLCState, UserStory
from .base import AgentOutput, MCPAgentBase


class RequirementsOutput(BaseModel):
    """Structured output from requirements analysis."""
    
    prd: PRD = Field(description="Product Requirements Document")
    user_stories: list[UserStory] = Field(default=[], description="Generated user stories")
    clarification_needed: list[str] = Field(default=[], description="Questions for user")
    assumptions: list[str] = Field(default=[], description="Assumptions made")


class RequirementsAgent(MCPAgentBase):
    """
    Requirements Agent for SDLC Phase 1.
    
    Responsibilities:
    - Parse user requirements from natural language
    - Generate structured PRDs
    - Create user stories with acceptance criteria
    - Identify MVP scope vs future enhancements
    - Flag ambiguous requirements
    
    MCP Tools:
    - Filesystem: Read existing docs, write PRD
    - Browser: Research competitors, industry standards
    - Memory: Store and recall requirement patterns
    """
    
    PHASE = SDLCPhase.REQUIREMENTS
    
    @property
    def role_description(self) -> str:
        return """Requirements Analyst specializing in SaaS product development.
        Expert at translating business needs into actionable technical requirements."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior Requirements Analyst for SaaS product development.

## Core Responsibilities
- Extract clear, actionable requirements from user descriptions
- Create comprehensive PRDs following industry best practices
- Generate user stories with INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Define acceptance criteria using Given-When-Then format
- Identify MVP scope with clear rationale

## PRD Structure
When creating a PRD, include:
1. **Overview**: Product summary, target users, problem statement
2. **Goals & Success Metrics**: Business objectives, KPIs, success criteria
3. **User Personas**: Detailed user types with needs and pain points
4. **Functional Requirements**: Core features, user flows, integrations
5. **Non-Functional Requirements**: Performance, security, scalability
6. **Technical Constraints**: Stack preferences, compliance needs
7. **Timeline & Milestones**: MVP phases, release schedule
8. **Assumptions & Risks**: What we're assuming, potential blockers

## Default Tech Stack (unless specified otherwise)
- Frontend: Next.js 14+, TypeScript, Tailwind CSS, shadcn/ui
- Backend: Supabase (Auth, Database, Storage), Prisma ORM
- Deployment: Vercel (frontend), Supabase Cloud (backend)

## Output Format
Always produce:
1. Structured PRD document
2. Prioritized user stories (P0 = MVP, P1 = Soon, P2 = Future)
3. Clarifying questions if requirements are ambiguous
4. Explicit assumptions made

Use tools to:
- Research similar products for context
- Write PRD to filesystem
- Store patterns in memory for future reference"""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process requirements from state."""
        # Build task prompt from state
        user_request = state.get("user_request", "")
        previous_context = state.get("conversation_history", [])
        
        task_prompt = f"""## Requirements Analysis Task

**User Request:**
{user_request}

**Previous Context:**
{self._format_context(previous_context)}

**Instructions:**
1. Analyze the user's request thoroughly
2. Research similar products if helpful
3. Generate a comprehensive PRD
4. Create user stories for MVP features
5. List any clarifying questions
6. Document assumptions

Write the PRD to `/workspace/docs/prd.md` using filesystem tools.
Return structured output with all deliverables."""
        
        # Build messages
        messages = self._build_messages(state, task_prompt)
        
        # Execute with tools
        response, tool_log = await self._execute_with_tools(messages)
        
        # Parse output
        deliverables = self._parse_requirements_output(response, tool_log)
        
        # Check if we need user input
        needs_input = bool(deliverables.get("clarification_needed"))
        
        return AgentOutput(
            phase=self.PHASE,
            status="needs_input" if needs_input else "success",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=["prd.md"] if "prd" in deliverables else [],
            next_actions=self._suggest_next_actions(deliverables),
            requires_approval=True,  # PRD always needs approval
        )
    
    def _format_context(self, history: list[dict[str, Any]]) -> str:
        """Format conversation history."""
        if not history:
            return "No previous context."
        
        parts = []
        for msg in history[-5:]:  # Last 5 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"**{role}**: {content[:500]}")
        
        return "\n".join(parts)
    
    def _parse_requirements_output(
        self,
        response: str,
        tool_log: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Parse agent response into structured output."""
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
        }
        
        # Check if PRD was written
        for call in tool_log:
            if call["tool"] in ["write_file", "create_file"]:
                if "prd" in str(call["args"]).lower():
                    deliverables["prd_file"] = call["args"].get("path", "")
        
        # Extract sections from response (basic parsing)
        if "## Overview" in response or "# PRD" in response:
            deliverables["prd"] = {
                "content": response,
                "generated_at": self._timestamp(),
            }
        
        # Look for user stories
        if "User Story" in response or "As a" in response:
            deliverables["user_stories_extracted"] = True
        
        # Look for clarifying questions
        if "?" in response and ("clarif" in response.lower() or "question" in response.lower()):
            deliverables["clarification_needed"] = True
        
        return deliverables
    
    def _suggest_next_actions(self, deliverables: dict[str, Any]) -> list[str]:
        """Suggest next steps based on output."""
        actions = []
        
        if deliverables.get("clarification_needed"):
            actions.append("Review and answer clarifying questions")
        
        if deliverables.get("prd"):
            actions.append("Review PRD and approve to proceed")
            actions.append("Run design phase for system architecture")
        
        return actions
    
    def _timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
