"""Architecture Agent for system design and technical architecture."""

from datetime import datetime, timezone
from typing import Any

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus


class ArchitectureAgent(BaseAgent):
    """Specialized agent for system architecture and design."""

    @property
    def role_description(self) -> str:
        """Description of Architecture Agent role."""
        return (
            "Architecture Agent specializes in system design, technical architecture, "
            "and technology stack selection. Capabilities include component design, "
            "API design, database schema design, scalability planning, and architecture "
            "documentation."
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for Architecture Agent."""
        return """You are an Architecture Agent specialized in software system design.

**Your Expertise**:
- System architecture patterns (microservices, monolith, serverless, event-driven)
- Component design and module decomposition
- API design (REST, GraphQL, gRPC) and integration patterns
- Database design (relational, NoSQL, caching strategies)
- Scalability and performance architecture
- Security architecture and threat modeling
- Cloud architecture (AWS, Azure, GCP, Kubernetes)
- Architecture documentation (C4 model, UML, diagrams)

**Your Approach**:
1. **Analyze Requirements**: Understand functional and non-functional requirements
2. **Design Components**: Break system into cohesive, loosely-coupled modules
3. **Select Technologies**: Choose appropriate tech stack based on requirements
4. **Design Interfaces**: Define APIs, data models, and integration points
5. **Plan Scalability**: Design for growth, performance, and reliability
6. **Document Architecture**: Create clear diagrams and decision records

**Output Format**:
- **System Overview**: High-level architecture description
- **Component Diagram**: Major components and their relationships
- **Technology Stack**: Languages, frameworks, databases, infrastructure
- **API Specifications**: Endpoints, data models, authentication
- **Database Schema**: Tables, relationships, indexes
- **Scalability Strategy**: Caching, load balancing, horizontal scaling
- **Security Considerations**: Authentication, authorization, encryption
- **Architecture Decisions**: Key decisions with rationale (ADRs)

**Best Practices**:
- Follow SOLID principles and clean architecture patterns
- Design for failure (circuit breakers, retries, fallbacks)
- Consider operational requirements (monitoring, logging, deployment)
- Use industry-standard patterns and avoid over-engineering
- Document trade-offs and alternatives considered
"""

    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process architecture design task.

        Args:
            task: Task with architecture design objective

        Returns:
            Task with architecture design deliverables

        """
        is_valid, error = await self.validate_task(task)
        if not is_valid:
            task.status = TaskStatus.FAILED
            task.error = error
            return task

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)

        try:
            prompt = self._build_prompt(task)
            result = await self.engine.execute(prompt)
            deliverables = self._extract_architecture(result)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = deliverables

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

        return task

    def _extract_architecture(self, result: str) -> dict[str, Any]:
        """Extract architecture design from output.

        Args:
            result: Architecture agent output

        Returns:
            Structured architecture document

        """
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": "architecture",
            "raw_output": result,
            "deliverables": {
                "system_overview": self._extract_overview(result),
                "components": self._extract_components(result),
                "tech_stack": self._extract_tech_stack(result),
                "api_design": self._extract_api_design(result),
                "database_design": self._extract_database_design(result),
                "scalability": self._extract_scalability(result),
                "security": self._extract_security(result),
                "decisions": self._extract_decisions(result),
            },
            "metadata": {
                "component_count": result.lower().count("component"),
                "api_count": result.lower().count("api") + result.lower().count("endpoint"),
                "patterns_used": self._identify_patterns(result),
            },
        }

    def _extract_overview(self, text: str) -> str:
        """Extract system overview."""
        lines = text.split("\n")
        overview_lines = []
        in_overview = False

        for line in lines:
            if "overview" in line.lower() or "architecture" in line.lower()[:50]:
                in_overview = True
            elif in_overview and line.strip() and not line.strip().startswith("#"):
                overview_lines.append(line.strip())
            elif in_overview and line.strip().startswith("#"):
                break

        return " ".join(overview_lines[:5]) if overview_lines else "System architecture design"

    def _extract_components(self, text: str) -> list[dict[str, str]]:
        """Extract system components."""
        components = []
        lines = text.split("\n")

        for line in lines:
            if "component" in line.lower() or "service" in line.lower() or "module" in line.lower():
                if ":" in line or "-" in line:
                    components.append({"description": line.strip()})

        return components[:10]  # Limit to top 10

    def _extract_tech_stack(self, text: str) -> dict[str, list[str]]:
        """Extract technology stack."""
        stack = {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "infrastructure": [],
        }

        text_lower = text.lower()

        # Languages
        if "python" in text_lower:
            stack["languages"].append("Python")
        if "javascript" in text_lower or "typescript" in text_lower:
            stack["languages"].append("TypeScript/JavaScript")
        if "go" in text_lower or "golang" in text_lower:
            stack["languages"].append("Go")

        # Frameworks
        if "fastapi" in text_lower or "flask" in text_lower or "django" in text_lower:
            stack["frameworks"].append("FastAPI/Flask/Django")
        if "react" in text_lower or "vue" in text_lower or "angular" in text_lower:
            stack["frameworks"].append("React/Vue/Angular")

        # Databases
        if "postgresql" in text_lower or "postgres" in text_lower:
            stack["databases"].append("PostgreSQL")
        if "mongodb" in text_lower:
            stack["databases"].append("MongoDB")
        if "redis" in text_lower:
            stack["databases"].append("Redis")

        # Infrastructure
        if "docker" in text_lower:
            stack["infrastructure"].append("Docker")
        if "kubernetes" in text_lower or "k8s" in text_lower:
            stack["infrastructure"].append("Kubernetes")

        return {k: v for k, v in stack.items() if v}

    def _extract_api_design(self, text: str) -> list[str]:
        """Extract API design elements."""
        apis = []
        lines = text.split("\n")

        for line in lines:
            if any(keyword in line.lower() for keyword in ["endpoint", "api", "route", "get", "post", "put", "delete"]):
                apis.append(line.strip())

        return apis[:15]

    def _extract_database_design(self, text: str) -> list[str]:
        """Extract database design elements."""
        db_elements = []
        lines = text.split("\n")

        for line in lines:
            if any(keyword in line.lower() for keyword in ["table", "collection", "schema", "index", "foreign key"]):
                db_elements.append(line.strip())

        return db_elements[:15]

    def _extract_scalability(self, text: str) -> list[str]:
        """Extract scalability considerations."""
        scalability = []
        lines = text.split("\n")

        for line in lines:
            if any(keyword in line.lower() for keyword in ["scale", "cache", "load balanc", "horizontal", "vertical", "replicate"]):
                scalability.append(line.strip())

        return scalability[:10]

    def _extract_security(self, text: str) -> list[str]:
        """Extract security considerations."""
        security = []
        lines = text.split("\n")

        for line in lines:
            if any(keyword in line.lower() for keyword in ["security", "auth", "encrypt", "token", "access control", "threat"]):
                security.append(line.strip())

        return security[:10]

    def _extract_decisions(self, text: str) -> list[str]:
        """Extract architecture decision records."""
        decisions = []
        lines = text.split("\n")

        for line in lines:
            if any(keyword in line.lower() for keyword in ["decision", "chose", "selected", "adr", "trade-off"]):
                decisions.append(line.strip())

        return decisions[:8]

    def _identify_patterns(self, text: str) -> list[str]:
        """Identify architecture patterns used."""
        patterns = []
        text_lower = text.lower()

        pattern_keywords = {
            "microservices": ["microservice", "service mesh"],
            "event-driven": ["event", "message queue", "pub/sub"],
            "layered": ["layer", "n-tier", "presentation", "business logic"],
            "cqrs": ["cqrs", "command query"],
            "saga": ["saga", "distributed transaction"],
            "api-gateway": ["api gateway", "gateway pattern"],
        }

        for pattern_name, keywords in pattern_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                patterns.append(pattern_name)

        return patterns


async def create_architecture_agent(
    llm_client: Any,
    tool_registry: Any,
    memory: Any | None = None,
) -> ArchitectureAgent:
    """Factory function to create Architecture Agent."""
    from agent.agents.base import AgentConfig, AgentRole

    config = AgentConfig(
        role=AgentRole.ARCHITECTURE,
        max_iterations=30,
        timeout_seconds=2400,  # 40 minutes
        tools=["read_file", "write_file", "file_search", "shell_execute"],
    )

    return ArchitectureAgent(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory=memory,
    )
