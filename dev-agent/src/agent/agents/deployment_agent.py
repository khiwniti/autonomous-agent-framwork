"""Deployment Agent for Infrastructure as Code and CI/CD automation."""

from datetime import datetime, timezone
from typing import Any

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus


class DeploymentAgent(BaseAgent):
    """Specialized agent for deployment automation and infrastructure management."""

    @property
    def role_description(self) -> str:
        """Description of Deployment Agent role."""
        return (
            "Deployment Agent specializes in infrastructure automation, CI/CD pipelines, "
            "and deployment orchestration. Capabilities include Infrastructure as Code, "
            "containerization, Kubernetes orchestration, and deployment strategy design."
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for Deployment Agent."""
        return """You are a Deployment Agent specialized in infrastructure automation and CI/CD.

**Your Expertise**:
- Infrastructure as Code (Terraform, CloudFormation, Pulumi, Ansible)
- CI/CD Pipeline Design (GitHub Actions, GitLab CI, Jenkins, CircleCI)
- Container Orchestration (Docker, Kubernetes, Helm, Docker Compose)
- Deployment Strategies (Blue-Green, Canary, Rolling, A/B Testing)
- Configuration Management (ConfigMaps, Secrets, Environment Variables)
- Cloud Platforms (AWS, GCP, Azure, DigitalOcean)
- Monitoring & Observability Integration

**Infrastructure as Code Best Practices**:
- Version control all infrastructure definitions
- Use modules and reusable components
- Implement state management and locking
- Apply security scanning and compliance checks
- Document resource dependencies and relationships
- Use variables and parameterization for flexibility

**CI/CD Pipeline Principles**:
- Automate everything: build, test, deploy
- Fail fast: catch issues early in pipeline
- Implement quality gates at each stage
- Use caching for build optimization
- Separate build and deployment concerns
- Enable rollback mechanisms
- Implement deployment approval workflows

**Container & Kubernetes Best Practices**:
- Multi-stage Docker builds for optimization
- Security scanning for vulnerabilities
- Resource limits and requests
- Health checks (liveness, readiness, startup probes)
- ConfigMaps for configuration, Secrets for sensitive data
- Horizontal Pod Autoscaling (HPA)
- Network policies and ingress configuration

**Deployment Strategies**:
1. **Blue-Green Deployment**: Zero-downtime by switching traffic between environments
2. **Canary Deployment**: Gradual rollout to subset of users
3. **Rolling Deployment**: Progressive instance replacement
4. **A/B Testing**: Feature testing with traffic splitting

**Output Format**:
```yaml
# Terraform Infrastructure
resource "aws_instance" "app_server" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name = "AppServer"
    Environment = var.environment
  }
}

# GitHub Actions Pipeline
name: CI/CD Pipeline
on:
  push:
    branches: [main]
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: docker build -t app:${{ github.sha }} .
      - name: Deploy
        run: kubectl apply -f k8s/

# Kubernetes Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-deployment
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: app
        image: app:latest
        resources:
          limits:
            cpu: "1"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
```

**Security Considerations**:
- Never hardcode credentials in IaC or pipelines
- Use secret management systems (Vault, AWS Secrets Manager)
- Implement least privilege access (IAM roles, RBAC)
- Enable encryption at rest and in transit
- Regular security scanning of images and infrastructure
- Audit logging for all deployments

**Monitoring Integration**:
- Deployment success/failure metrics
- Resource utilization monitoring
- Application performance monitoring (APM)
- Alerting on deployment issues
- Rollback automation on critical failures
"""

    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process deployment automation task."""
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
            deliverables = self._extract_deployment_artifacts(result)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = deliverables

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

        return task

    def _extract_deployment_artifacts(self, result: str) -> dict[str, Any]:
        """Extract deployment artifacts from output."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": "deployment",
            "raw_output": result,
            "deliverables": {
                "iac_files": self._extract_iac_files(result),
                "ci_cd_pipelines": self._extract_pipelines(result),
                "container_configs": self._extract_container_configs(result),
                "k8s_manifests": self._extract_k8s_manifests(result),
                "deployment_strategy": self._extract_deployment_strategy(result),
            },
            "metrics": {
                "iac_file_count": self._count_iac_files(result),
                "pipeline_count": self._count_pipelines(result),
                "k8s_resource_count": self._count_k8s_resources(result),
            },
            "quality_indicators": {
                "has_health_checks": "livenessProbe" in result or "readinessProbe" in result,
                "has_resource_limits": "limits:" in result and "requests:" in result,
                "has_secrets_management": any(
                    keyword in result.lower()
                    for keyword in ["secret", "vault", "sealed-secret", "external-secrets"]
                ),
                "has_rollback_strategy": any(
                    keyword in result.lower() for keyword in ["rollback", "rollout undo", "blue-green"]
                ),
                "uses_version_control": ".git" in result or "version:" in result,
            },
        }

    def _extract_iac_files(self, text: str) -> list[dict[str, str]]:
        """Extract Infrastructure as Code file definitions."""
        iac_files = []
        lines = text.split("\n")
        current_file = None
        file_content = []
        iac_extensions = (".tf", ".yaml", ".yml", ".json", ".pkr.hcl", ".pkr.json")

        for line in lines:
            # Detect IaC file header
            if any(ext in line.lower() for ext in iac_extensions):
                if "file:" in line.lower() or "#" in line[:5]:
                    if current_file:
                        iac_files.append({"path": current_file, "content": "\n".join(file_content)})
                    current_file = line.split(":")[-1].strip() if ":" in line else line.strip("#").strip()
                    file_content = []
            elif current_file:
                file_content.append(line)

        if current_file:
            iac_files.append({"path": current_file, "content": "\n".join(file_content)})

        return iac_files

    def _extract_pipelines(self, text: str) -> list[dict[str, Any]]:
        """Extract CI/CD pipeline definitions."""
        pipelines = []
        lines = text.split("\n")

        # Detection patterns for different CI/CD systems
        pipeline_indicators = {
            "github_actions": ["name:", "on:", "jobs:", "runs-on:"],
            "gitlab_ci": ["stages:", "script:", "image:", "before_script:"],
            "jenkins": ["pipeline {", "stages {", "agent ", "steps {"],
            "circleci": ["version:", "workflows:", "executors:", "orbs:"],
        }

        current_pipeline = None
        pipeline_content = []

        for i, line in enumerate(lines):
            # Detect pipeline start
            for pipeline_type, indicators in pipeline_indicators.items():
                if any(indicator in line for indicator in indicators):
                    if current_pipeline is None:
                        current_pipeline = {
                            "type": pipeline_type,
                            "start_line": i + 1,
                            "stages": [],
                        }
                    pipeline_content.append(line)

                    # Extract stages/jobs
                    if "stage:" in line.lower() or "job:" in line.lower():
                        stage_name = line.split(":")[-1].strip()
                        if stage_name:
                            current_pipeline["stages"].append(stage_name)

            # Detect pipeline end (empty line or new section after substantial content)
            if current_pipeline and len(pipeline_content) > 10:
                if not line.strip() or line.startswith("#"):
                    current_pipeline["content"] = "\n".join(pipeline_content)
                    pipelines.append(current_pipeline)
                    current_pipeline = None
                    pipeline_content = []

        if current_pipeline and pipeline_content:
            current_pipeline["content"] = "\n".join(pipeline_content)
            pipelines.append(current_pipeline)

        return pipelines

    def _extract_container_configs(self, text: str) -> list[dict[str, str]]:
        """Extract container configuration files (Dockerfile, docker-compose.yml)."""
        configs = []
        lines = text.split("\n")
        current_config = None
        config_content = []

        for line in lines:
            if "dockerfile" in line.lower() or "docker-compose" in line.lower():
                if "file:" in line.lower() or "#" in line[:5]:
                    if current_config:
                        configs.append({"type": current_config, "content": "\n".join(config_content)})
                    current_config = (
                        "Dockerfile" if "dockerfile" in line.lower() else "docker-compose.yml"
                    )
                    config_content = []
            elif current_config:
                config_content.append(line)

        if current_config:
            configs.append({"type": current_config, "content": "\n".join(config_content)})

        return configs

    def _extract_k8s_manifests(self, text: str) -> list[dict[str, Any]]:
        """Extract Kubernetes manifest definitions."""
        manifests = []
        lines = text.split("\n")

        current_manifest = None
        manifest_content = []

        for i, line in enumerate(lines):
            # Detect Kubernetes manifest start
            if "apiVersion:" in line or "kind:" in line:
                if current_manifest and manifest_content:
                    current_manifest["content"] = "\n".join(manifest_content)
                    manifests.append(current_manifest)

                if "apiVersion:" in line:
                    current_manifest = {
                        "api_version": line.split(":")[-1].strip(),
                        "line": i + 1,
                    }
                    manifest_content = [line]
                elif "kind:" in line and current_manifest:
                    current_manifest["kind"] = line.split(":")[-1].strip()
                    manifest_content.append(line)
            elif current_manifest:
                manifest_content.append(line)

                # Extract metadata name
                if "name:" in line and "metadata" in "\n".join(manifest_content[-5:]):
                    current_manifest["name"] = line.split(":")[-1].strip()

        if current_manifest and manifest_content:
            current_manifest["content"] = "\n".join(manifest_content)
            manifests.append(current_manifest)

        return manifests

    def _extract_deployment_strategy(self, text: str) -> dict[str, Any]:
        """Extract deployment strategy information."""
        strategy = {
            "type": "rolling",  # default
            "description": "",
            "rollback_enabled": False,
            "monitoring_enabled": False,
            "approval_required": False,
        }

        text_lower = text.lower()

        # Detect deployment strategy type
        if "blue-green" in text_lower or "blue/green" in text_lower:
            strategy["type"] = "blue-green"
        elif "canary" in text_lower:
            strategy["type"] = "canary"
        elif "rolling" in text_lower:
            strategy["type"] = "rolling"
        elif "recreate" in text_lower:
            strategy["type"] = "recreate"

        # Detect features
        strategy["rollback_enabled"] = any(
            keyword in text_lower for keyword in ["rollback", "rollout undo", "revision"]
        )
        strategy["monitoring_enabled"] = any(
            keyword in text_lower
            for keyword in [
                "prometheus",
                "grafana",
                "datadog",
                "monitoring",
                "metrics",
                "alert",
            ]
        )
        strategy["approval_required"] = any(
            keyword in text_lower for keyword in ["approval", "manual", "review", "gate"]
        )

        # Extract strategy description
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "strategy" in line.lower() and ":" in line:
                # Get next few lines as description
                desc_lines = []
                for j in range(i, min(i + 5, len(lines))):
                    if lines[j].strip():
                        desc_lines.append(lines[j].strip())
                strategy["description"] = " ".join(desc_lines)
                break

        return strategy

    def _count_iac_files(self, text: str) -> int:
        """Count Infrastructure as Code files."""
        count = 0
        iac_patterns = [".tf", "terraform", "cloudformation", "pulumi", "ansible"]
        for pattern in iac_patterns:
            count += text.lower().count(pattern)
        return count

    def _count_pipelines(self, text: str) -> int:
        """Count CI/CD pipeline definitions."""
        pipeline_markers = ["jobs:", "stages:", "pipeline {", "workflows:"]
        return sum(1 for marker in pipeline_markers if marker in text)

    def _count_k8s_resources(self, text: str) -> int:
        """Count Kubernetes resource definitions."""
        return text.count("apiVersion:")


async def create_deployment_agent(
    llm_client: Any,
    tool_registry: Any,
    memory: Any | None = None,
) -> DeploymentAgent:
    """Factory function to create Deployment Agent."""
    from agent.agents.base import AgentConfig, AgentRole

    config = AgentConfig(
        role=AgentRole.DEPLOYMENT,
        max_iterations=25,
        timeout_seconds=2400,  # 40 minutes for complex IaC
        tools=["read_file", "write_file", "file_search", "shell_execute"],
    )

    return DeploymentAgent(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory=memory,
    )
