"""Deployment Agent - Infrastructure and Release Management.

Specializes in:
- Vercel deployment
- Supabase configuration
- Environment management
- Release orchestration
"""

from typing import Any

from agent.langgraph.state import DeploymentStatus, SDLCPhase, SDLCState
from .base import AgentOutput, MCPAgentBase


class DeploymentAgent(MCPAgentBase):
    """
    Deployment Agent for SDLC Phase 7.
    
    Responsibilities:
    - Deploy to Vercel
    - Configure Supabase
    - Manage environment variables
    - Orchestrate releases
    
    MCP Tools:
    - Shell: Deploy commands
    - Kubernetes: Container deployment
    - Docker: Build and push images
    """
    
    PHASE = SDLCPhase.DEPLOYMENT
    
    @property
    def role_description(self) -> str:
        return """Platform Engineer and Release Manager.
        Expert in cloud deployment, infrastructure, and release management."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior Platform Engineer specializing in deployment.

## Core Responsibilities
- Deploy applications to Vercel
- Configure Supabase projects
- Manage environment variables
- Orchestrate production releases
- Configure custom domains

## Deployment Architecture

### Vercel Deployment
```bash
# Install Vercel CLI
npm i -g vercel

# Link project
vercel link

# Deploy preview
vercel

# Deploy production
vercel --prod
```

### Vercel Configuration (vercel.json)
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm ci",
  "regions": ["iad1"],
  "env": {
    "NEXT_PUBLIC_APP_URL": "@app-url",
    "DATABASE_URL": "@database-url"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/api/$1"
    }
  ]
}
```

### Supabase Configuration
```bash
# Install Supabase CLI
npm i -g supabase

# Initialize Supabase
supabase init

# Link to project
supabase link --project-ref <project-id>

# Push database changes
supabase db push

# Deploy Edge Functions
supabase functions deploy
```

### Supabase Config (supabase/config.toml)
```toml
[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
shadow_port = 54320
major_version = 15

[studio]
enabled = true
port = 54323
api_url = "http://localhost"

[auth]
enabled = true
site_url = "http://localhost:3000"
additional_redirect_urls = ["https://localhost:3000"]
jwt_expiry = 3600
enable_signup = true
```

## Environment Management

### Required Environment Variables
```env
# App
NEXT_PUBLIC_APP_URL=https://your-app.vercel.app
NEXT_PUBLIC_APP_NAME="My SaaS App"

# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key

# Database
DATABASE_URL=postgresql://...

# Auth (if using external)
NEXTAUTH_URL=https://your-app.vercel.app
NEXTAUTH_SECRET=your-secret

# Third-party
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Environment Files
```
.env                # Local defaults
.env.local          # Local overrides (gitignored)
.env.production     # Production values (secrets in Vercel)
```

## Release Checklist
1. ✅ All tests passing
2. ✅ Build successful
3. ✅ Environment variables configured
4. ✅ Database migrations run
5. ✅ Preview deployment verified
6. ✅ Production deployment
7. ✅ Health check passing
8. ✅ Monitoring configured

## Rollback Strategy
```bash
# Vercel rollback
vercel rollback [deployment-url]

# Database rollback
npx prisma migrate resolve --rolled-back
```

## Output Format
1. Configure deployment settings
2. Set up environment variables
3. Deploy to staging/preview
4. Run health checks
5. Deploy to production
6. Verify deployment

Create `/workspace/vercel.json` and `/workspace/supabase/` configuration."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process deployment phase from state."""
        prd = state.get("prd")
        project_name = prd.project_name if prd else "my-saas-app"
        
        task_prompt = f"""## Deployment Task

**Project:** {project_name}

**Instructions:**
1. Create Vercel configuration
   - Write vercel.json with proper settings
   - Configure headers and rewrites
   - Set up environment variable references

2. Create Supabase configuration
   - Initialize supabase/ directory
   - Write config.toml
   - Set up database migrations folder

3. Create environment template
   - Write .env.example with all required variables
   - Document each variable's purpose

4. Create deployment scripts
   - Write scripts/deploy.sh for manual deployment
   - Include verification steps

5. Document deployment process
   - Write DEPLOYMENT.md with instructions
   - Include rollback procedures

Write all configuration to `/workspace/`

After creating configs, deploy to preview:
```bash
vercel
```"""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        # Check deployment status
        deployment_url = None
        deployment_success = False
        for call in tool_log:
            if call["tool"] == "run_command":
                result = call.get("result", "")
                if "vercel.app" in result or "Production:" in result:
                    deployment_success = True
                    # Extract URL if present
                    lines = result.split("\n")
                    for line in lines:
                        if "https://" in line and "vercel.app" in line:
                            deployment_url = line.strip()
                            break
        
        status = DeploymentStatus(
            environment="preview" if deployment_success else "pending",
            url=deployment_url,
            version=state.get("current_version", "0.1.0"),
            status="deployed" if deployment_success else "pending",
            health_check_passed=deployment_success,
        )
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "deployment_status": status.model_dump(),
            "deployment_url": deployment_url,
            "deployment_complete": deployment_success,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success" if deployment_success else "pending",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=["vercel.json", "supabase/", ".env.example"],
            next_actions=[
                f"Verify deployment at {deployment_url}" if deployment_url else "Deploy to preview",
                "Configure production environment",
                "Proceed to monitoring setup",
            ],
            requires_approval=True,  # Human approval before production
        )
