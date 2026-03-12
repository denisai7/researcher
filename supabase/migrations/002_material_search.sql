-- Add full-text search support for materials (search by file names and sources)
ALTER TABLE research_materials ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(display_name, '') || ' ' || coalesce(source_value, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_materials_search ON research_materials USING GIN(search_vector);

-- Add index on display_name for ilike queries
CREATE INDEX IF NOT EXISTS idx_materials_display_name ON research_materials(display_name);
