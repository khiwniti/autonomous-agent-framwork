"""Monitoring Agent - Observability and Operations.

Specializes in:
- Application monitoring
- Error tracking
- Performance metrics
- Alerting configuration
"""

from typing import Any

from agent.langgraph.state import SDLCPhase, SDLCState
from .base import AgentOutput, MCPAgentBase


class MonitoringAgent(MCPAgentBase):
    """
    Monitoring Agent for SDLC Phase 8.
    
    Responsibilities:
    - Configure application monitoring
    - Set up error tracking
    - Implement performance metrics
    - Configure alerting
    
    MCP Tools:
    - Filesystem: Write configuration files
    - Shell: Install monitoring tools
    - Browser: Verify dashboards
    """
    
    PHASE = SDLCPhase.MONITORING
    
    @property
    def role_description(self) -> str:
        return """Site Reliability Engineer and Observability Specialist.
        Expert in monitoring, alerting, and production operations."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior SRE specializing in observability.

## Core Responsibilities
- Configure application monitoring
- Set up error tracking (Sentry)
- Implement performance metrics
- Configure alerting rules
- Create operational dashboards

## Monitoring Stack

### Sentry (Error Tracking)
```typescript
// lib/sentry.ts
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
});
```

### Sentry Configuration (sentry.client.config.ts)
```typescript
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
  debug: false,
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  integrations: [
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});
```

### Sentry Configuration (sentry.server.config.ts)
```typescript
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
  debug: false,
});
```

### Vercel Analytics & Speed Insights
```typescript
// app/layout.tsx
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/next';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
```

### Custom Metrics (OpenTelemetry)
```typescript
// lib/metrics.ts
import { metrics } from '@opentelemetry/api';

const meter = metrics.getMeter('my-app');

export const requestCounter = meter.createCounter('http_requests_total', {
  description: 'Total HTTP requests',
});

export const requestDuration = meter.createHistogram('http_request_duration_ms', {
  description: 'HTTP request duration in milliseconds',
});

// Usage in API route
import { requestCounter, requestDuration } from '@/lib/metrics';

export async function GET(request: Request) {
  const start = Date.now();
  requestCounter.add(1, { method: 'GET', route: '/api/users' });
  
  // ... handle request
  
  requestDuration.record(Date.now() - start, { method: 'GET', route: '/api/users' });
}
```

### Health Check Endpoint
```typescript
// app/api/health/route.ts
import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

export async function GET() {
  const checks = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.APP_VERSION || '1.0.0',
    checks: {
      database: 'unknown',
      cache: 'unknown',
    },
  };

  try {
    await prisma.$queryRaw`SELECT 1`;
    checks.checks.database = 'healthy';
  } catch (error) {
    checks.checks.database = 'unhealthy';
    checks.status = 'degraded';
  }

  try {
    await redis.ping();
    checks.checks.cache = 'healthy';
  } catch (error) {
    checks.checks.cache = 'unhealthy';
    checks.status = 'degraded';
  }

  return NextResponse.json(checks, {
    status: checks.status === 'healthy' ? 200 : 503,
  });
}
```

### Logging (Pino)
```typescript
// lib/logger.ts
import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: process.env.NODE_ENV !== 'production',
    },
  },
});

// Usage
import { logger } from '@/lib/logger';

logger.info({ userId, action: 'login' }, 'User logged in');
logger.error({ error, requestId }, 'Request failed');
```

## Alerting Configuration

### Sentry Alerts
- Error rate > 1% in 5 minutes → Critical
- New error type → Warning
- Performance regression > 20% → Warning

### Uptime Monitoring
```yaml
# Better Uptime / Checkly configuration
checks:
  - name: API Health
    url: https://your-app.vercel.app/api/health
    frequency: 60
    assertions:
      - type: statusCode
        value: 200
      - type: jsonBody
        path: $.status
        value: healthy
```

## Required Environment Variables
```env
# Sentry
NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_AUTH_TOKEN=sntrys_xxx
SENTRY_ORG=your-org
SENTRY_PROJECT=your-project

# Logging
LOG_LEVEL=info1
```

## Output Format
1. Configure Sentry SDK
2. Add Vercel Analytics
3. Create health check endpoint
4. Set up logging
5. Configure alerting rules
6. Document runbooks

Create monitoring configuration in `/workspace/`."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process monitoring phase from state."""
        deployment = state.get("deployment_status")
        deployment_url = deployment.get("url") if deployment else None
        
        task_prompt = f"""## Monitoring Setup Task

**Deployment URL:** {deployment_url or "Not yet deployed"}

**Instructions:**
1. Configure Sentry
   - Create sentry.client.config.ts
   - Create sentry.server.config.ts
   - Update next.config.js with Sentry plugin

2. Add Vercel Analytics
   - Update app/layout.tsx with Analytics component
   - Add SpeedInsights component

3. Create health check endpoint
   - Write app/api/health/route.ts
   - Check database connectivity
   - Check external service health

4. Set up logging
   - Create lib/logger.ts with Pino
   - Add structured logging to API routes

5. Create operational documentation
   - Write RUNBOOK.md with common procedures
   - Document alert response procedures

Write all files to `/workspace/`

After setup, verify health endpoint:
```bash
curl {deployment_url}/api/health
```"""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        # Check if monitoring is configured
        monitoring_configured = False
        files_created = []
        for call in tool_log:
            if call["tool"] in ["write_file", "create_file"]:
                path = call.get("args", {}).get("path", "")
                files_created.append(path)
                if "sentry" in path.lower() or "health" in path.lower():
                    monitoring_configured = True
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "files_created": files_created,
            "monitoring_configured": monitoring_configured,
            "monitoring_tools": [
                "Sentry (Error Tracking)",
                "Vercel Analytics",
                "Pino (Logging)",
                "Health Check",
            ],
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success" if monitoring_configured else "pending",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=files_created,
            next_actions=[
                "Configure Sentry project settings",
                "Set up alert notifications",
                "Create operational dashboards",
                "SDLC cycle complete - ready for iteration",
            ],
            requires_approval=False,
        )
