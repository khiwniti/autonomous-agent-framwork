-- PostgreSQL Initialization Script for Autonomous Dev Agent
-- Creates databases, extensions, and schemas for LangGraph checkpointing

-- Create Langfuse database
CREATE DATABASE langfuse_db;

-- Enable pgvector extension in main database
\c agent_db;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema for LangGraph checkpointing
CREATE SCHEMA IF NOT EXISTS langgraph;

-- Checkpoints table (stores graph state snapshots)
CREATE TABLE IF NOT EXISTS langgraph.checkpoints (
    thread_id UUID NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id UUID NOT NULL,
    parent_checkpoint_id UUID,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- Checkpoint writes table (pending writes before commit)
CREATE TABLE IF NOT EXISTS langgraph.checkpoint_writes (
    thread_id UUID NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id UUID NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Checkpoint blobs table (stores large binary data)
CREATE TABLE IF NOT EXISTS langgraph.checkpoint_blobs (
    thread_id UUID NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    data BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- Create schema for vector memory storage
CREATE SCHEMA IF NOT EXISTS memory;

-- Episodic memory table (stores agent experiences)
CREATE TABLE IF NOT EXISTS memory.episodic (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL,
    phase TEXT NOT NULL,
    summary TEXT NOT NULL,
    embedding vector(1536),
    context JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create vector similarity index
CREATE INDEX IF NOT EXISTS episodic_embedding_idx 
ON memory.episodic 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Procedural memory table (stores learned patterns)
CREATE TABLE IF NOT EXISTS memory.procedural (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    implementation TEXT NOT NULL,
    embedding vector(1536),
    success_rate FLOAT DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (pattern_type, pattern_name)
);

-- Create index for procedural patterns
CREATE INDEX IF NOT EXISTS procedural_embedding_idx 
ON memory.procedural 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- Create schema for project data
CREATE SCHEMA IF NOT EXISTS projects;

-- Projects table
CREATE TABLE IF NOT EXISTS projects.projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    tech_stack JSONB DEFAULT '[]',
    status TEXT DEFAULT 'active',
    repository_url TEXT,
    deployment_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON langgraph.checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS checkpoints_created_at_idx ON langgraph.checkpoints(created_at DESC);
CREATE INDEX IF NOT EXISTS episodic_thread_id_idx ON memory.episodic(thread_id);
CREATE INDEX IF NOT EXISTS episodic_phase_idx ON memory.episodic(phase);
CREATE INDEX IF NOT EXISTS procedural_pattern_type_idx ON memory.procedural(pattern_type);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA langgraph TO agent_user;
GRANT ALL PRIVILEGES ON SCHEMA memory TO agent_user;
GRANT ALL PRIVILEGES ON SCHEMA projects TO agent_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA langgraph TO agent_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA memory TO agent_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA projects TO agent_user;

-- Create function for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for auto-updating timestamps
CREATE TRIGGER update_procedural_updated_at
BEFORE UPDATE ON memory.procedural
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_projects_updated_at
BEFORE UPDATE ON projects.projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Insert default patterns for procedural memory
INSERT INTO memory.procedural (pattern_type, pattern_name, implementation, metadata) VALUES
('api', 'rest_crud', 'Standard RESTful CRUD API pattern with proper error handling', '{"methods": ["GET", "POST", "PUT", "DELETE"]}'),
('auth', 'jwt_auth', 'JWT-based authentication with refresh tokens', '{"library": "jose"}'),
('database', 'prisma_pattern', 'Prisma ORM with connection pooling and error handling', '{"orm": "prisma"}'),
('ui', 'form_validation', 'React Hook Form with Zod validation', '{"libraries": ["react-hook-form", "zod"]}'),
('testing', 'vitest_component', 'Vitest with React Testing Library pattern', '{"libraries": ["vitest", "@testing-library/react"]}')
ON CONFLICT (pattern_type, pattern_name) DO NOTHING;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END $$;
