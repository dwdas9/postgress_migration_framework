-- PostgreSQL Migration Framework - Sample SQL Scripts
-- These scripts are templates for common migration tasks

-- ============================================================================
-- 1. PRE-MIGRATION ASSESSMENT QUERIES (Run on Source - v11)
-- ============================================================================

-- Get comprehensive database stats
SELECT 
  current_database() AS database_name,
  version() AS postgres_version,
  pg_size_pretty(pg_database_size(current_database())) AS database_size,
  (SELECT count(*) FROM pg_tables WHERE schemaname = 'public') AS table_count,
  (SELECT count(*) FROM pg_indexes WHERE schemaname = 'public') AS index_count,
  (SELECT count(*) FROM pg_proc WHERE pronamespace != 11) AS function_count
FROM pg_stat_database 
WHERE datname = current_database();

-- Table row counts and sizes (top 20 by size)
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS table_size,
  n_live_tup AS row_count,
  ROUND(100.0 * n_live_tup / NULLIF(
    (SELECT sum(n_live_tup) FROM pg_stat_user_tables), 0), 2) AS pct_of_total
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
LIMIT 20;

-- Index analysis
SELECT 
  schemaname,
  tablename,
  indexname,
  idx_scan AS scans,
  idx_tup_read AS tuples_read,
  pg_size_pretty(pg_relation_size(indexrelname::regclass)) AS index_size,
  CASE 
    WHEN idx_scan = 0 THEN 'UNUSED'
    WHEN idx_scan < 10 THEN 'RARELY_USED'
    ELSE 'IN_USE'
  END AS usage_status
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC, pg_relation_size(indexrelname::regclass) DESC;

-- Slow query analysis (enable slow query log first)
SELECT 
  query,
  calls,
  total_time,
  mean_time,
  max_time,
  CASE 
    WHEN mean_time > 1000 THEN 'VERY_SLOW'
    WHEN mean_time > 100 THEN 'SLOW'
    ELSE 'ACCEPTABLE'
  END AS performance_category
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_time DESC
LIMIT 20;

-- ============================================================================
-- 2. SCHEMA EXPORT TEMPLATES
-- ============================================================================

-- Create schema metadata table (run on source)
CREATE TABLE migration_metadata (
  metadata_id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  schema_name TEXT NOT NULL,
  row_count BIGINT,
  size_bytes BIGINT,
  column_count INT,
  primary_key_columns TEXT,
  has_indexes BOOLEAN,
  export_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(table_name, schema_name)
);

-- Populate metadata table
INSERT INTO migration_metadata (
  table_name, schema_name, row_count, size_bytes, column_count
)
SELECT 
  t.tablename,
  t.schemaname,
  s.n_live_tup,
  pg_total_relation_size(t.schemaname || '.' || t.tablename),
  (SELECT count(*) FROM information_schema.columns 
   WHERE table_schema = t.schemaname AND table_name = t.tablename)
FROM pg_tables t
LEFT JOIN pg_stat_user_tables s ON s.relname = t.tablename 
  AND s.schemaname = t.schemaname
WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. TARGET DATABASE SETUP (Run on Azure PostgreSQL v14)
-- ============================================================================

-- Create migration schema structure
CREATE SCHEMA IF NOT EXISTS raw_schema;
CREATE SCHEMA IF NOT EXISTS validated_schema;
CREATE SCHEMA IF NOT EXISTS gold_schema;

-- Create validation metadata table
CREATE TABLE IF NOT EXISTS migration_validation_log (
  validation_id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  validation_type VARCHAR(50),
  validation_status VARCHAR(10),
  source_count BIGINT,
  target_count BIGINT,
  difference BIGINT,
  validation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  details JSONB
);

-- Create index for frequent queries
CREATE INDEX idx_validation_log_table_timestamp 
  ON migration_validation_log(table_name, validation_timestamp DESC);

-- ============================================================================
-- 4. ROW COUNT RECONCILIATION (Run on Target - Post Load)
-- ============================================================================

-- Generate reconciliation report
WITH table_list AS (
  SELECT tablename 
  FROM pg_tables 
  WHERE schemaname = 'raw_schema'
),
source_counts AS (
  SELECT 
    table_name,
    COUNT(*) AS source_row_count
  FROM migration_metadata
  GROUP BY table_name
),
target_counts AS (
  SELECT 
    tablename AS table_name,
    (SELECT n_live_tup FROM pg_stat_user_tables 
     WHERE relname = tablename AND schemaname = 'raw_schema') AS target_row_count
  FROM table_list
)
SELECT 
  COALESCE(s.table_name, t.table_name) AS table_name,
  COALESCE(s.source_row_count, 0) AS source_count,
  COALESCE(t.target_row_count, 0) AS target_count,
  COALESCE(t.target_row_count, 0) - COALESCE(s.source_row_count, 0) AS difference,
  CASE 
    WHEN s.source_row_count = t.target_row_count THEN 'PASS'
    ELSE 'FAIL'
  END AS validation_result,
  CURRENT_TIMESTAMP AS validation_time
FROM source_counts s
FULL OUTER JOIN target_counts t ON s.table_name = t.table_name
ORDER BY 
  CASE WHEN s.source_row_count != t.target_row_count THEN 1 ELSE 2 END,
  table_name;

-- ============================================================================
-- 5. DATA QUALITY VALIDATION QUERIES
-- ============================================================================

-- Identify NULL violations in NOT NULL columns
SELECT 
  table_name,
  column_name,
  COUNT(*) AS null_count,
  'NULL_VIOLATION' AS issue_type
FROM (
  SELECT 
    'table_name' AS table_name,
    'column_name' AS column_name,
    column_value
  FROM raw_schema.your_table
  WHERE column_name IS NULL
) violations
GROUP BY table_name, column_name
HAVING COUNT(*) > 0;

-- Find duplicate primary keys
SELECT 
  table_name,
  COUNT(*) - COUNT(DISTINCT pk_column1, pk_column2) AS duplicate_count,
  'DUPLICATE_PK' AS issue_type
FROM raw_schema.your_table
GROUP BY table_name
HAVING COUNT(*) != COUNT(DISTINCT pk_column1, pk_column2);

-- Identify orphaned foreign key records
SELECT 
  'orders' AS child_table,
  COUNT(*) AS orphaned_records,
  'ORPHANED_FK' AS issue_type
FROM raw_schema.orders o
LEFT JOIN raw_schema.customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL
HAVING COUNT(*) > 0;

-- ============================================================================
-- 6. INCREMENTAL LOAD HELPERS (CDC)
-- ============================================================================

-- Create tracking table for incremental syncs (on target)
CREATE TABLE IF NOT EXISTS incremental_sync_log (
  sync_id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  last_sync_timestamp TIMESTAMP,
  current_sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  rows_extracted BIGINT,
  rows_loaded BIGINT,
  rows_updated BIGINT,
  sync_status VARCHAR(20),
  error_message TEXT,
  sync_duration_seconds NUMERIC,
  UNIQUE(table_name, current_sync_timestamp)
);

-- Merge stored procedure for incremental loads
CREATE OR REPLACE FUNCTION merge_delta_data(
  p_table_name TEXT,
  p_schema_name TEXT DEFAULT 'public'
)
RETURNS TABLE (rows_inserted BIGINT, rows_updated BIGINT) AS $$
DECLARE
  v_rows_inserted BIGINT := 0;
  v_rows_updated BIGINT := 0;
BEGIN
  -- UPDATE existing records (assume update_timestamp available)
  EXECUTE format('
    UPDATE validated_schema.%I t
    SET %I = s.%I
    FROM staging_deltas.%I s
    WHERE t.id = s.id AND s.updated_at > t.last_updated_at
  ', p_table_name, 'last_updated_at', 'updated_at', p_table_name)
  INTO v_rows_updated;

  -- INSERT new records
  EXECUTE format('
    INSERT INTO validated_schema.%I
    SELECT * FROM staging_deltas.%I s
    WHERE NOT EXISTS (
      SELECT 1 FROM validated_schema.%I t
      WHERE t.id = s.id
    )
  ', p_table_name, p_table_name, p_table_name)
  INTO v_rows_inserted;

  -- Cleanup staging
  EXECUTE format('DELETE FROM staging_deltas.%I', p_table_name);

  RETURN QUERY SELECT v_rows_inserted, v_rows_updated;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. PERFORMANCE BASELINE CAPTURE
-- ============================================================================

-- Create performance baseline table
CREATE TABLE IF NOT EXISTS query_performance_baseline (
  baseline_id BIGSERIAL PRIMARY KEY,
  query_name TEXT NOT NULL,
  query_text TEXT,
  execution_count INT,
  mean_execution_time_ms NUMERIC,
  max_execution_time_ms NUMERIC,
  p95_execution_time_ms NUMERIC,
  rows_scanned BIGINT,
  baseline_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(query_name, baseline_timestamp)
);

-- Capture query statistics (if pg_stat_statements enabled)
INSERT INTO query_performance_baseline (
  query_name, query_text, execution_count, 
  mean_execution_time_ms, max_execution_time_ms
)
SELECT 
  'query_' || row_number() OVER (ORDER BY mean_time DESC),
  query,
  calls,
  mean_time,
  max_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%' AND query NOT LIKE '%migration%'
ORDER BY mean_time DESC
LIMIT 50;

-- ============================================================================
-- 8. GOLD LAYER FINALIZATION (Post-Cutover)
-- ============================================================================

-- Create views on gold schema for application access
CREATE OR REPLACE VIEW gold_schema.customer_summary AS
SELECT 
  c.customer_id,
  c.name,
  c.email,
  COUNT(o.order_id) AS total_orders,
  SUM(o.amount) AS total_spending,
  MAX(o.order_date) AS last_order_date
FROM validated_schema.customers c
LEFT JOIN validated_schema.orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.email;

-- Grant permissions to application roles
GRANT USAGE ON SCHEMA gold_schema TO application_role;
GRANT SELECT ON ALL TABLES IN SCHEMA gold_schema TO application_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA gold_schema TO application_role;

-- ============================================================================
-- 9. ROLLBACK HELPERS
-- ============================================================================

-- Backup current state (if rollback needed)
CREATE TABLE IF NOT EXISTS rollback_checkpoint (
  checkpoint_id BIGSERIAL PRIMARY KEY,
  checkpoint_name TEXT NOT NULL UNIQUE,
  checkpoint_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  table_row_counts JSONB,
  notes TEXT
);

-- Capture current state
INSERT INTO rollback_checkpoint (checkpoint_name, table_row_counts, notes)
SELECT 
  'pre_cutover_state_' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDD_HH24MI'),
  jsonb_object_agg(
    tablename,
    (SELECT n_live_tup FROM pg_stat_user_tables 
     WHERE relname = tablename AND schemaname = 'validated_schema')
  ),
  'Checkpoint before production cutover'
FROM pg_tables
WHERE schemaname = 'validated_schema';

-- ============================================================================
-- 10. CLEANUP & DECOMMISSIONING (Post-Migration)
-- ============================================================================

-- Archive migration logs (after cutover complete + 30 days)
CALL archive_migration_logs_to_blob();

-- Drop staging schemas (if no longer needed)
-- DROP SCHEMA IF EXISTS staging_deltas CASCADE;

-- Reset sequences to next available value
SELECT setval(
  pg_get_serial_sequence(schemaname || '.' || tablename, attname),
  (SELECT MAX(CAST(attname AS BIGINT)) + 1 
   FROM pg_attribute a
   WHERE a.attrelid = (schemaname || '.' || tablename)::regclass)
)
FROM pg_class c
JOIN pg_attribute a ON a.attrelid = c.oid
JOIN pg_tables t ON t.tablename = c.relname
WHERE a.atthasdef = true
  AND schemaname = 'public';

-- ============================================================================
-- END OF SAMPLE SCRIPTS
-- ============================================================================
