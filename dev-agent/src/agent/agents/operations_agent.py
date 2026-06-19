"""Operations Agent for monitoring, incident response, and operational excellence."""

from datetime import datetime, timezone
from typing import Any

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus


class OperationsAgent(BaseAgent):
    """Specialized agent for operations, monitoring, and incident response."""

    @property
    def role_description(self) -> str:
        """Description of Operations Agent role."""
        return (
            "Operations Agent specializes in system monitoring, incident response, "
            "and operational excellence. Capabilities include observability setup, "
            "alerting configuration, incident management, and performance optimization."
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for Operations Agent."""
        return """You are an Operations Agent specialized in system operations and reliability.

**Your Expertise**:
- Observability and Monitoring (Prometheus, Grafana, Datadog, New Relic)
- Logging and Tracing (ELK Stack, Splunk, Jaeger, OpenTelemetry)
- Incident Response and Management (PagerDuty, Opsgenie)
- Performance Optimization and Capacity Planning
- SRE Practices (SLO, SLI, Error Budgets)
- Chaos Engineering and Resilience Testing
- Automation and Runbooks

**Monitoring Best Practices**:
- Four Golden Signals: Latency, Traffic, Errors, Saturation
- RED Method: Rate, Errors, Duration (for services)
- USE Method: Utilization, Saturation, Errors (for resources)
- Implement structured logging with correlation IDs
- Set up distributed tracing for microservices
- Monitor business metrics, not just infrastructure

**Alerting Principles**:
- Alert on symptoms, not causes
- Make alerts actionable (what to do when it fires)
- Avoid alert fatigue (quality over quantity)
- Use appropriate severity levels
- Include context and runbook links
- Test alert channels regularly

**Incident Response Framework**:
1. **Detection**: Automated monitoring and alerting
2. **Triage**: Assess severity and impact
3. **Investigation**: Use logs, metrics, traces to diagnose
4. **Mitigation**: Quick fixes to restore service
5. **Resolution**: Permanent fix implementation
6. **Post-Mortem**: Blameless analysis and prevention

**SRE Principles**:
- Service Level Indicators (SLI): Metrics that matter to users
- Service Level Objectives (SLO): Target SLI values
- Error Budgets: Acceptable failure rate based on SLO
- Toil Reduction: Automate repetitive operational work
- Capacity Planning: Proactive resource management

**Output Format**:
```yaml
# Prometheus Alert Rules
groups:
  - name: application_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} (threshold: 0.05)"
          runbook: "https://runbooks.example.com/high-error-rate"

# Grafana Dashboard
{
  "dashboard": {
    "title": "Application Overview",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      }
    ]
  }
}

# Runbook Template
## Incident: High Memory Usage

### Symptoms
- Memory usage > 85%
- OOMKiller events in logs
- Slow response times

### Investigation Steps
1. Check memory metrics: `kubectl top pods`
2. Review logs: `kubectl logs <pod> | grep -i memory`
3. Analyze heap dump if needed

### Mitigation
- Scale horizontally: `kubectl scale deployment app --replicas=5`
- Restart high-memory pods if needed

### Prevention
- Implement memory limits
- Add memory leak detection
- Regular performance profiling
```

**Observability Stack Components**:
- **Metrics**: Prometheus, StatsD, CloudWatch
- **Logs**: ELK (Elasticsearch, Logstash, Kibana), Loki
- **Traces**: Jaeger, Zipkin, AWS X-Ray
- **APM**: Datadog APM, New Relic, Dynatrace
- **Dashboards**: Grafana, Kibana, CloudWatch Dashboards

**Performance Optimization**:
- Identify bottlenecks using profiling tools
- Optimize database queries and indexes
- Implement caching strategies
- Use CDN for static content
- Enable compression and minification
- Optimize resource allocation

**Chaos Engineering**:
- Test failure scenarios in production-like environments
- Inject latency, errors, resource constraints
- Verify system resilience and recovery
- Document failure modes and mitigations

**Operational Metrics to Track**:
- **Availability**: Uptime percentage, incident frequency
- **Performance**: Response time, throughput, resource usage
- **Reliability**: Error rate, failure rate, MTBF/MTTR
- **Capacity**: Resource utilization, growth trends
- **User Experience**: Apdex score, user satisfaction
"""

    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process operations and monitoring task."""
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
            deliverables = self._extract_operations_artifacts(result)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = deliverables

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

        return task

    def _extract_operations_artifacts(self, result: str) -> dict[str, Any]:
        """Extract operations artifacts from output."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": "operations",
            "raw_output": result,
            "deliverables": {
                "monitoring_configs": self._extract_monitoring_configs(result),
                "alert_rules": self._extract_alert_rules(result),
                "dashboards": self._extract_dashboards(result),
                "runbooks": self._extract_runbooks(result),
                "slos": self._extract_slos(result),
            },
            "metrics": {
                "alert_rule_count": self._count_alert_rules(result),
                "dashboard_count": self._count_dashboards(result),
                "runbook_count": self._count_runbooks(result),
            },
            "quality_indicators": {
                "has_structured_logging": any(
                    keyword in result.lower()
                    for keyword in ["correlation_id", "trace_id", "structured", "json logging"]
                ),
                "has_distributed_tracing": any(
                    keyword in result.lower()
                    for keyword in ["jaeger", "zipkin", "x-ray", "opentelemetry", "trace"]
                ),
                "has_slo_defined": "slo" in result.lower() or "service level" in result.lower(),
                "has_runbooks": "runbook" in result.lower() or "playbook" in result.lower(),
                "follows_golden_signals": any(
                    keyword in result.lower() for keyword in ["latency", "traffic", "errors", "saturation"]
                ),
            },
        }

    def _extract_monitoring_configs(self, text: str) -> list[dict[str, Any]]:
        """Extract monitoring configuration files."""
        configs = []
        lines = text.split("\n")
        current_config = None
        config_content = []

        monitoring_indicators = [
            "prometheus",
            "grafana",
            "datadog",
            "metrics",
            "scrape_configs",
        ]

        for i, line in enumerate(lines):
            # Detect monitoring config
            if any(indicator in line.lower() for indicator in monitoring_indicators):
                if "config" in line.lower() or "yml" in line.lower() or "yaml" in line.lower():
                    if current_config:
                        configs.append(
                            {
                                "type": current_config,
                                "content": "\n".join(config_content),
                                "line": i + 1,
                            }
                        )
                    current_config = line.strip()
                    config_content = []
            elif current_config:
                config_content.append(line)

        if current_config:
            configs.append({"type": current_config, "content": "\n".join(config_content)})

        return configs

    def _extract_alert_rules(self, text: str) -> list[dict[str, Any]]:
        """Extract alert rule definitions."""
        alert_rules = []
        lines = text.split("\n")

        current_alert = None
        alert_content = []

        for i, line in enumerate(lines):
            # Detect alert definition
            if "alert:" in line.lower() or "- alert:" in line:
                if current_alert and alert_content:
                    alert_rules.append(current_alert)

                alert_name = line.split(":")[-1].strip() if ":" in line else ""
                current_alert = {
                    "name": alert_name,
                    "line": i + 1,
                    "severity": "unknown",
                    "expression": "",
                    "description": "",
                }
                alert_content = [line]

            elif current_alert:
                alert_content.append(line)

                # Extract alert properties
                if "severity:" in line.lower():
                    current_alert["severity"] = line.split(":")[-1].strip()
                elif "expr:" in line.lower():
                    current_alert["expression"] = line.split(":")[-1].strip()
                elif "description:" in line.lower():
                    current_alert["description"] = line.split(":")[-1].strip().strip('"')
                elif "summary:" in line.lower() and not current_alert["description"]:
                    current_alert["description"] = line.split(":")[-1].strip().strip('"')

        if current_alert and alert_content:
            alert_rules.append(current_alert)

        return alert_rules

    def _extract_dashboards(self, text: str) -> list[dict[str, Any]]:
        """Extract dashboard definitions."""
        dashboards = []
        lines = text.split("\n")

        current_dashboard = None
        dashboard_content = []
        panel_count = 0

        for i, line in enumerate(lines):
            # Detect dashboard
            if "dashboard" in line.lower() and ("title" in line.lower() or "{" in line):
                if current_dashboard and dashboard_content:
                    current_dashboard["panel_count"] = panel_count
                    current_dashboard["content"] = "\n".join(dashboard_content)
                    dashboards.append(current_dashboard)

                title = ""
                if "title" in line.lower():
                    title = line.split(":")[-1].strip().strip('"').strip("'")

                current_dashboard = {
                    "title": title or f"Dashboard_{i}",
                    "line": i + 1,
                }
                dashboard_content = [line]
                panel_count = 0

            elif current_dashboard:
                dashboard_content.append(line)
                if "panel" in line.lower():
                    panel_count += 1

        if current_dashboard and dashboard_content:
            current_dashboard["panel_count"] = panel_count
            current_dashboard["content"] = "\n".join(dashboard_content)
            dashboards.append(current_dashboard)

        return dashboards

    def _extract_runbooks(self, text: str) -> list[dict[str, Any]]:
        """Extract runbook definitions."""
        runbooks = []
        lines = text.split("\n")

        current_runbook = None
        runbook_content = []

        for i, line in enumerate(lines):
            # Detect runbook start
            if "runbook" in line.lower() or "playbook" in line.lower():
                if ":" in line or "#" in line:
                    if current_runbook and runbook_content:
                        current_runbook["content"] = "\n".join(runbook_content)
                        runbooks.append(current_runbook)

                    title = line.split(":")[-1].strip() if ":" in line else line.strip("#").strip()
                    current_runbook = {
                        "title": title,
                        "line": i + 1,
                        "sections": [],
                    }
                    runbook_content = [line]

            elif current_runbook:
                runbook_content.append(line)

                # Extract sections
                if line.startswith("##") or line.startswith("###"):
                    section_title = line.strip("#").strip()
                    current_runbook["sections"].append(section_title)

        if current_runbook and runbook_content:
            current_runbook["content"] = "\n".join(runbook_content)
            runbooks.append(current_runbook)

        return runbooks

    def _extract_slos(self, text: str) -> list[dict[str, Any]]:
        """Extract Service Level Objective definitions."""
        slos = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "slo" in line_lower or "service level" in line_lower:
                # Extract SLO information
                slo = {
                    "line": i + 1,
                    "definition": line.strip(),
                    "target": None,
                }

                # Try to extract target percentage
                if "%" in line:
                    parts = line.split("%")
                    for part in parts:
                        try:
                            # Find numeric value before %
                            nums = "".join(c for c in part if c.isdigit() or c == ".")
                            if nums:
                                slo["target"] = float(nums)
                                break
                        except ValueError:
                            pass

                # Extract indicator type
                if "latency" in line_lower:
                    slo["indicator"] = "latency"
                elif "availability" in line_lower or "uptime" in line_lower:
                    slo["indicator"] = "availability"
                elif "error" in line_lower:
                    slo["indicator"] = "error_rate"
                elif "throughput" in line_lower:
                    slo["indicator"] = "throughput"
                else:
                    slo["indicator"] = "custom"

                slos.append(slo)

        return slos

    def _count_alert_rules(self, text: str) -> int:
        """Count alert rule definitions."""
        return text.lower().count("- alert:") + text.lower().count("alert:")

    def _count_dashboards(self, text: str) -> int:
        """Count dashboard definitions."""
        count = 0
        dashboard_indicators = ["dashboard:", '"dashboard"', "grafana dashboard"]
        for indicator in dashboard_indicators:
            count += text.lower().count(indicator)
        return count

    def _count_runbooks(self, text: str) -> int:
        """Count runbook definitions."""
        return text.lower().count("runbook") + text.lower().count("playbook")


async def create_operations_agent(
    llm_client: Any,
    tool_registry: Any,
    memory: Any | None = None,
) -> OperationsAgent:
    """Factory function to create Operations Agent."""
    from agent.agents.base import AgentConfig, AgentRole

    config = AgentConfig(
        role=AgentRole.OPERATIONS,
        max_iterations=25,
        timeout_seconds=2400,  # 40 minutes for complex operations
        tools=["read_file", "write_file", "file_search", "shell_execute"],
    )

    return OperationsAgent(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory=memory,
    )
