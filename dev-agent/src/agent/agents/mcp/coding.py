"""Coding Agent - Implementation and Code Generation.

Specializes in:
- Feature implementation
- Code generation following patterns
- Refactoring and optimization
- Code review and quality assurance
"""

from typing import Any

from agent.langgraph.state import CodeFile, SDLCPhase, SDLCState
from .base import AgentOutput, MCPAgentBase


class CodingAgent(MCPAgentBase):
    """
    Coding Agent for SDLC Phase 4.
    
    Responsibilities:
    - Implement features according to design
    - Generate clean, maintainable code
    - Follow established patterns and conventions
    - Write inline documentation
    - Create type-safe implementations
    
    MCP Tools:
    - Filesystem: Read/write code files
    - Git: Version control operations
    - Shell: Run build commands, linting
    - Docker: Container operations
    """
    
    PHASE = SDLCPhase.CODING
    
    @property
    def role_description(self) -> str:
        return """Senior Full-Stack Developer specializing in Next.js and TypeScript.
        Expert in clean code, modern patterns, and production-ready implementations."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior Full-Stack Developer building SaaS applications.

## Core Responsibilities
- Implement features according to PRD and design specs
- Write clean, maintainable, type-safe code
- Follow project conventions and patterns
- Create reusable components and utilities
- Ensure code quality and performance

## Tech Stack Conventions

### TypeScript
- Strict mode enabled
- Explicit types for function parameters and returns
- Use interfaces for object shapes
- Avoid `any` - use `unknown` if needed
- Use Zod for runtime validation

### Next.js Patterns
- App Router with file-based routing
- Server Components as default
- Client Components only when needed (interactivity, hooks)
- Server Actions for mutations
- Route Handlers for API endpoints
- Middleware for auth/redirects

### Component Patterns
```typescript
// Server Component (default)
export default async function Page({ params }: PageProps) {
  const data = await fetchData(params.id);
  return <ClientComponent data={data} />;
}

// Client Component
"use client";
import { useState } from "react";
export function ClientComponent({ data }: Props) {
  const [state, setState] = useState(data);
  return <div>...</div>;
}
```

### Supabase Patterns
```typescript
// Server-side client
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll(), setAll: () => {} } }
  );
}

// Client-side client  
import { createBrowserClient } from "@supabase/ssr";
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
```

### Form Patterns
```typescript
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export function LoginForm() {
  const form = useForm({ resolver: zodResolver(schema) });
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        {/* fields */}
      </form>
    </Form>
  );
}
```

## Code Quality Standards
- ESLint: Follow project rules
- Prettier: Format on save
- TypeScript: No errors
- Naming: camelCase functions, PascalCase components
- Files: kebab-case filenames

## File Organization
```
src/
├── app/              # Next.js App Router
│   ├── (auth)/       # Auth routes
│   ├── (dashboard)/  # Protected routes
│   ├── api/          # API routes
│   └── layout.tsx
├── components/
│   ├── ui/           # shadcn/ui components
│   └── features/     # Feature components
├── lib/
│   ├── supabase/     # Supabase clients
│   ├── utils/        # Utility functions
│   └── validators/   # Zod schemas
├── hooks/            # Custom hooks
├── types/            # TypeScript types
└── styles/           # Global styles
```

## Output
- Write code files directly using filesystem tools
- Run linting/formatting commands
- Create git commits for logical changes
- Document complex logic with comments"""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process coding phase from state."""
        architecture = state.get("phase_outputs", {}).get("architecture", {})
        design = state.get("phase_outputs", {}).get("design", {})
        
        # Get specific coding task if available
        coding_task = state.get("current_task", {})
        user_request = state.get("user_request", "")
        
        task_prompt = f"""## Implementation Task

**User Request:**
{user_request}

**Architecture Context:**
{str(architecture)[:1500]}

**Design Context:**
{str(design)[:1500]}

**Instructions:**
1. Review the architecture and design documents
2. Identify files to create/modify
3. Implement the feature following conventions
4. Ensure type safety throughout
5. Run linting and fix any issues
6. Create logical git commits

Focus on:
- Clean, readable code
- Proper error handling
- Type safety
- Following established patterns

Write files to the `/workspace/src/` directory structure."""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        # Extract created files from tool log
        created_files = []
        for call in tool_log:
            if call["tool"] in ["write_file", "create_file"]:
                path = call["args"].get("path", "")
                if path:
                    created_files.append(path)
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "files_created": created_files,
            "coding_complete": True,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=created_files,
            next_actions=["Review generated code", "Proceed to testing phase"],
            requires_approval=False,  # Code doesn't require approval by default
        )
