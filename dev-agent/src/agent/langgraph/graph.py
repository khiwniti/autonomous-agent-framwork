"""LangGraph SDLC Workflow Graph.

This module implements the main SDLC workflow using LangGraph v1.0:
- Hierarchical supervisor pattern for phase orchestration
- Swarm-style handoffs for code-test-fix inner loop
- Human-in-the-loop approval gates via interrupt()
- Parallel execution for design and architecture phases
"""

from typing import Any, Callable, Literal
from datetime import datetime, timezone

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command, Send
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from agent.langgraph.state import (
    SDLCState,
    SDLCPhase,
    ApprovalStatus,
    create_initial_state,
)


class SDLCWorkflowGraph:
    """
    Main SDLC workflow graph using LangGraph v1.0.
    
    Implements the workflow:
    User Input → [Requirements Agent] → APPROVAL GATE
      → [Design Agent ∥ Architecture Agent] (parallel)
      → APPROVAL GATE
      → [Coding Orchestrator → Coding Workers] (orchestrator-worker, parallel)
      → [Testing Agent ⟷ Coding Agent] (evaluator-optimizer loop)
      → [CI/CD Agent] → [Deployment Agent] → [Monitoring Agent]
    """
    
    def __init__(
        self,
        db_uri: str,
        agent_factory: "AgentFactory",
        durability: Literal["full", "async", "exit"] = "full",
    ):
        """
        Initialize SDLC workflow graph.
        
        Args:
            db_uri: PostgreSQL connection URI for checkpointing
            agent_factory: Factory for creating SDLC agents
            durability: Checkpoint durability mode ("full" for SDLC workflows)
        """
        self.db_uri = db_uri
        self.agent_factory = agent_factory
        self.durability = durability
        
        # Initialize checkpointer and store
        self.checkpointer = PostgresSaver.from_conn_string(db_uri)
        self.store = PostgresStore.from_conn_string(
            db_uri,
            index={
                "dims": 1536,
                "embed": "openai:text-embedding-3-small",
            },
        )
        
        # Build the graph
        self.graph = self._build_graph()
        self.compiled_graph = None
        
    def _build_graph(self) -> StateGraph:
        """Build the SDLC workflow graph."""
        
        graph = StateGraph(SDLCState)
        
        # ====================================================================
        # Phase 1: Requirements
        # ====================================================================
        graph.add_node("requirements_agent", self._requirements_node)
        graph.add_node("requirements_approval", self._requirements_approval_node)
        
        # ====================================================================
        # Phase 2 & 3: Design and Architecture (parallel)
        # ====================================================================
        graph.add_node("design_agent", self._design_node)
        graph.add_node("architecture_agent", self._architecture_node)
        graph.add_node("design_approval", self._design_approval_node)
        
        # ====================================================================
        # Phase 4: Coding (orchestrator-worker pattern)
        # ====================================================================
        graph.add_node("coding_orchestrator", self._coding_orchestrator_node)
        graph.add_node("coding_worker", self._coding_worker_node)
        
        # ====================================================================
        # Phase 5: Testing (evaluator-optimizer loop)
        # ====================================================================
        graph.add_node("testing_agent", self._testing_node)
        
        # ====================================================================
        # Phase 6: CI/CD
        # ====================================================================
        graph.add_node("cicd_agent", self._cicd_node)
        
        # ====================================================================
        # Phase 7: Deployment
        # ====================================================================
        graph.add_node("deployment_agent", self._deployment_node)
        graph.add_node("deployment_approval", self._deployment_approval_node)
        
        # ====================================================================
        # Phase 8: Monitoring Setup
        # ====================================================================
        graph.add_node("monitoring_agent", self._monitoring_node)
        
        # ====================================================================
        # Define Edges
        # ====================================================================
        
        # Start -> Requirements
        graph.add_edge(START, "requirements_agent")
        graph.add_edge("requirements_agent", "requirements_approval")
        
        # Requirements approval routing
        graph.add_conditional_edges(
            "requirements_approval",
            self._route_requirements_approval,
            {
                "approved": "design_agent",
                "rejected": "requirements_agent",
            },
        )
        
        # Design -> Architecture happens in sequence (could be parallel)
        graph.add_edge("design_agent", "architecture_agent")
        graph.add_edge("architecture_agent", "design_approval")
        
        # Design approval routing
        graph.add_conditional_edges(
            "design_approval",
            self._route_design_approval,
            {
                "approved": "coding_orchestrator",
                "rejected_design": "design_agent",
                "rejected_architecture": "architecture_agent",
            },
        )
        
        # Coding orchestrator dispatches to workers via Send()
        graph.add_conditional_edges(
            "coding_orchestrator",
            self._dispatch_coding_workers,
        )
        
        # Coding workers -> Testing
        graph.add_edge("coding_worker", "testing_agent")
        
        # Testing loop (evaluator-optimizer pattern)
        graph.add_conditional_edges(
            "testing_agent",
            self._route_test_results,
            {
                "pass": "cicd_agent",
                "fail": "coding_orchestrator",
                "max_iterations": "cicd_agent",  # Force continue after max retries
            },
        )
        
        # CI/CD -> Deployment
        graph.add_edge("cicd_agent", "deployment_agent")
        graph.add_edge("deployment_agent", "deployment_approval")
        
        # Deployment approval routing
        graph.add_conditional_edges(
            "deployment_approval",
            self._route_deployment_approval,
            {
                "approved": "monitoring_agent",
                "rejected": "deployment_agent",
            },
        )
        
        # Monitoring -> End
        graph.add_edge("monitoring_agent", END)
        
        return graph
    
    def compile(self):
        """Compile the graph with checkpointer and store."""
        self.checkpointer.setup()  # Create tables if needed
        self.compiled_graph = self.graph.compile(
            checkpointer=self.checkpointer,
            store=self.store,
        )
        return self.compiled_graph
    
    async def run(
        self,
        project_id: str,
        project_name: str,
        user_input: str,
        config: dict[str, Any] | None = None,
    ) -> SDLCState:
        """
        Run the SDLC workflow.
        
        Args:
            project_id: Unique project identifier
            project_name: Human-readable project name
            user_input: Initial user requirements
            config: Optional LangGraph config overrides
            
        Returns:
            Final SDLCState after workflow completion
        """
        if not self.compiled_graph:
            self.compile()
            
        initial_state = create_initial_state(
            project_id=project_id,
            project_name=project_name,
            user_input=user_input,
        )
        
        run_config = {
            "configurable": {
                "thread_id": f"project-{project_id}",
            },
            **(config or {}),
        }
        
        try:
            result = await self.compiled_graph.ainvoke(initial_state, run_config)
            return result
        except Exception as e:
            # Resume from last checkpoint on failure
            result = await self.compiled_graph.ainvoke(None, run_config)
            return result
    
    async def resume(
        self,
        project_id: str,
        approval_response: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> SDLCState:
        """
        Resume a paused workflow (e.g., after human approval).
        
        Args:
            project_id: Project identifier
            approval_response: Human approval response for interrupt
            config: Optional config overrides
            
        Returns:
            Updated SDLCState
        """
        if not self.compiled_graph:
            self.compile()
            
        run_config = {
            "configurable": {
                "thread_id": f"project-{project_id}",
            },
            **(config or {}),
        }
        
        # Resume with approval response if provided
        input_data = approval_response if approval_response else None
        result = await self.compiled_graph.ainvoke(input_data, run_config)
        return result
    
    # ========================================================================
    # Node Implementations
    # ========================================================================
    
    async def _requirements_node(self, state: SDLCState) -> dict:
        """Requirements agent node."""
        agent = self.agent_factory.get_requirements_agent()
        result = await agent.generate_prd(
            user_input=state["user_input"],
            context=state,
        )
        return {
            "prd": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.REQUIREMENTS,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _requirements_approval_node(self, state: SDLCState) -> dict:
        """Human approval gate for requirements."""
        approval = interrupt({
            "phase": "requirements_approval",
            "artifact": state.get("prd"),
            "question": "Approve this PRD before design begins?",
        })
        return {
            "approval_status": ApprovalStatus(approval.get("action", "pending")),
            "approval_feedback": approval.get("feedback", ""),
            "pending_approval_phase": SDLCPhase.REQUIREMENTS,
        }
    
    async def _design_node(self, state: SDLCState) -> dict:
        """System design agent node."""
        agent = self.agent_factory.get_design_agent()
        result = await agent.generate_design(
            prd=state.get("prd"),
            context=state,
        )
        return {
            "system_design": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.DESIGN,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _architecture_node(self, state: SDLCState) -> dict:
        """Architecture decision agent node."""
        agent = self.agent_factory.get_architecture_agent()
        result = await agent.make_decisions(
            prd=state.get("prd"),
            system_design=state.get("system_design"),
            context=state,
        )
        return {
            "architecture": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.ARCHITECTURE,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _design_approval_node(self, state: SDLCState) -> dict:
        """Human approval gate for design & architecture."""
        approval = interrupt({
            "phase": "design_approval",
            "system_design": state.get("system_design"),
            "architecture": state.get("architecture"),
            "question": "Approve system design and architecture before coding begins?",
        })
        return {
            "approval_status": ApprovalStatus(approval.get("action", "pending")),
            "approval_feedback": approval.get("feedback", ""),
            "pending_approval_phase": SDLCPhase.DESIGN,
        }
    
    async def _coding_orchestrator_node(self, state: SDLCState) -> list[Send]:
        """
        Coding orchestrator using LangGraph's Send API.
        
        Dispatches parallel coding workers for different modules.
        """
        agent = self.agent_factory.get_coding_orchestrator()
        
        # Get modules/files to generate
        modules = await agent.plan_modules(
            prd=state.get("prd"),
            system_design=state.get("system_design"),
            architecture=state.get("architecture"),
            existing_code=state.get("code_files", []),
            test_failures=state.get("test_failures", []),
        )
        
        # Dispatch parallel workers
        return [
            Send("coding_worker", {"module": module, "parent_state": state})
            for module in modules
        ]
    
    async def _coding_worker_node(self, state: dict) -> dict:
        """Individual coding worker for a module."""
        agent = self.agent_factory.get_coding_agent()
        
        module = state.get("module", {})
        parent_state = state.get("parent_state", {})
        
        result = await agent.generate_code(
            module=module,
            prd=parent_state.get("prd"),
            system_design=parent_state.get("system_design"),
            architecture=parent_state.get("architecture"),
        )
        
        return {
            "code_files": [r.model_dump() if hasattr(r, 'model_dump') else r for r in result],
            "current_phase": SDLCPhase.CODING,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _testing_node(self, state: SDLCState) -> dict:
        """Testing agent node (evaluator in the evaluator-optimizer loop)."""
        agent = self.agent_factory.get_testing_agent()
        
        result = await agent.run_tests(
            code_files=state.get("code_files", []),
            prd=state.get("prd"),
            system_design=state.get("system_design"),
        )
        
        # Increment iteration counter
        iteration = state.get("iteration_count", 0) + 1
        
        return {
            "test_results": result.model_dump() if hasattr(result, 'model_dump') else result,
            "test_failures": result.get("failures", []) if isinstance(result, dict) else [],
            "current_phase": SDLCPhase.TESTING,
            "iteration_count": iteration,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _cicd_node(self, state: SDLCState) -> dict:
        """CI/CD configuration agent node."""
        agent = self.agent_factory.get_cicd_agent()
        
        result = await agent.configure_pipeline(
            code_files=state.get("code_files", []),
            architecture=state.get("architecture"),
        )
        
        return {
            "cicd_config": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.CICD,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _deployment_node(self, state: SDLCState) -> dict:
        """Deployment agent node."""
        agent = self.agent_factory.get_deployment_agent()
        
        result = await agent.deploy(
            code_files=state.get("code_files", []),
            cicd_config=state.get("cicd_config"),
            architecture=state.get("architecture"),
        )
        
        return {
            "deployment_status": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.DEPLOYMENT,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _deployment_approval_node(self, state: SDLCState) -> dict:
        """Human approval gate for production deployment."""
        approval = interrupt({
            "phase": "deployment_approval",
            "deployment_status": state.get("deployment_status"),
            "question": "Approve deployment to production?",
        })
        return {
            "approval_status": ApprovalStatus(approval.get("action", "pending")),
            "approval_feedback": approval.get("feedback", ""),
            "pending_approval_phase": SDLCPhase.DEPLOYMENT,
        }
    
    async def _monitoring_node(self, state: SDLCState) -> dict:
        """Monitoring setup agent node."""
        agent = self.agent_factory.get_monitoring_agent()
        
        result = await agent.setup_monitoring(
            deployment_status=state.get("deployment_status"),
            architecture=state.get("architecture"),
        )
        
        return {
            "monitoring_config": result.model_dump() if hasattr(result, 'model_dump') else result,
            "current_phase": SDLCPhase.MONITORING,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # ========================================================================
    # Routing Functions
    # ========================================================================
    
    def _route_requirements_approval(self, state: SDLCState) -> str:
        """Route based on requirements approval status."""
        status = state.get("approval_status")
        if status == ApprovalStatus.APPROVED:
            return "approved"
        return "rejected"
    
    def _route_design_approval(self, state: SDLCState) -> str:
        """Route based on design approval status."""
        status = state.get("approval_status")
        feedback = state.get("approval_feedback", "")
        
        if status == ApprovalStatus.APPROVED:
            return "approved"
        elif "architecture" in feedback.lower():
            return "rejected_architecture"
        return "rejected_design"
    
    def _dispatch_coding_workers(self, state: SDLCState) -> list[Send]:
        """This is handled by the orchestrator node returning Send objects."""
        # The orchestrator node itself returns Send objects
        # This routing function just ensures proper edge configuration
        return []
    
    def _route_test_results(self, state: SDLCState) -> str:
        """Route based on test results (evaluator-optimizer loop)."""
        test_results = state.get("test_results", {})
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 10)
        
        # Check if max iterations reached
        if iteration >= max_iterations:
            return "max_iterations"
        
        # Check test status
        if isinstance(test_results, dict):
            failed = test_results.get("failed", 0)
            if failed == 0:
                return "pass"
        
        return "fail"
    
    def _route_deployment_approval(self, state: SDLCState) -> str:
        """Route based on deployment approval status."""
        status = state.get("approval_status")
        if status == ApprovalStatus.APPROVED:
            return "approved"
        return "rejected"
