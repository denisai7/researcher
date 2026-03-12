-- Research Projects table
CREATE TABLE IF NOT EXISTS research_projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    project_name TEXT NOT NULL,
    original_user_request TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    notebooklm_project_id TEXT,
    result_type TEXT,
    result_ref TEXT,
    result_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON research_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON research_projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON research_projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_user_status ON research_projects(user_id, status);

-- Research Materials table
CREATE TABLE IF NOT EXISTS research_materials (
    material_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(project_id) ON DELETE CASCADE,
    material_type TEXT NOT NULL,
    source_value TEXT NOT NULL,
    display_name TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'received'
);

CREATE INDEX IF NOT EXISTS idx_materials_project_id ON research_materials(project_id);
CREATE INDEX IF NOT EXISTS idx_materials_status ON research_materials(status);

-- Full-text search support
ALTER TABLE research_projects ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(project_name, '') || ' ' || coalesce(original_user_request, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_projects_search ON research_projects USING GIN(search_vector);
