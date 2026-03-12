-- Include result_summary in project full-text search vector
-- so "find my research about X" matches results, not just the original request.
ALTER TABLE research_projects DROP COLUMN IF EXISTS search_vector;

ALTER TABLE research_projects ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(project_name, '') || ' ' ||
            coalesce(original_user_request, '') || ' ' ||
            coalesce(result_summary, '')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_projects_search ON research_projects USING GIN(search_vector);
