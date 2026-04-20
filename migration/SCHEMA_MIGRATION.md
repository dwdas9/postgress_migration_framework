# Schema Migration & Compatibility Guide

## PostgreSQL 11 → 14 Compatibility Checklist

### Data Type Changes

#### 1. Serial Types (DEPRECATED in v14)

**Before (v11):**
```sql
CREATE TABLE users (
  user_id serial PRIMARY KEY,
  name varchar(255)
);
```

**After (v14 - PREFERRED):**
```sql
CREATE TABLE users (
  user_id bigserial PRIMARY KEY,
  name varchar(255)
);
```

**Migration Script:**
```sql
-- For existing tables, convert serial to bigserial
ALTER TABLE users DROP CONSTRAINT users_pkey;
ALTER TABLE users ALTER COLUMN user_id TYPE bigint;
ALTER TABLE users ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

-- Update sequence
DROP SEQUENCE IF EXISTS users_user_id_seq;
CREATE SEQUENCE users_user_id_seq
  START WITH 1 INCREMENT BY 1;
ALTER TABLE users ALTER COLUMN user_id SET DEFAULT nextval('users_user_id_seq');
```

#### 2. JSON → JSONB (v14 Improvements)

**Status**: JSONB is now default. Migrate JSON to JSONB for better performance.

```sql
-- Migration
ALTER TABLE products 
ALTER COLUMN metadata TYPE jsonb USING metadata::jsonb;

-- Verify
SELECT jsonb_object_keys(metadata) FROM products LIMIT 5;
```

#### 3. Interval Type Precision

**Before (v11):**
```sql
CREATE TABLE events (
  event_id int PRIMARY KEY,
  duration interval
);
```

**After (v14 - With Precision):**
```sql
CREATE TABLE events (
  event_id int PRIMARY KEY,
  duration interval DAY TO SECOND
);
```

### Function & Operator Changes

#### 1. VACUUM Behavior

```sql
-- v11: VACUUM requires maintenance window
VACUUM ANALYZE;

-- v14: Improved autovacuum, but manual still supported
VACUUM (ANALYZE, VERBOSE) schema_name.table_name;
```

#### 2. Collation Changes

```sql
-- v14: New collation algorithm (ICU)
-- Verify existing collations work

SELECT collname, collprovider FROM pg_collation 
WHERE collname NOT LIKE 'pg_%';

-- If issues, rebuild indexes:
REINDEX INDEX index_name;
```

### Index Considerations

#### 1. Hash Partitioning (v14 Improvement)

**Before (v11 - Range/List only):**
```sql
CREATE TABLE orders_2024 (
  order_id int PRIMARY KEY,
  order_date date
) PARTITION BY RANGE (order_date);
```

**After (v14 - Hash Partitioning Available):**
```sql
CREATE TABLE orders (
  order_id int PRIMARY KEY,
  order_id_hash int
) PARTITION BY HASH (order_id_hash);

-- Create partitions
CREATE TABLE orders_p0 PARTITION OF orders FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE orders_p1 PARTITION OF orders FOR VALUES WITH (MODULUS 4, REMAINDER 1);
-- ... etc
```

#### 2. BRIN Indexes (v14 Enhancements)

```sql
-- BRIN indexes are more efficient for large tables
CREATE INDEX idx_events_timestamp ON events USING brin (event_timestamp)
WITH (pages_per_range = 128);

-- Better for time-series data than B-tree
```

### Constraint Migrations

#### 1. Foreign Key ON DELETE/UPDATE Behavior

**Verify existing constraints are compatible:**
```sql
SELECT 
  constraint_name,
  constraint_type,
  delete_rule,
  update_rule
FROM information_schema.referential_constraints
ORDER BY constraint_name;

-- Expected values: CASCADE, RESTRICT, SET NULL, SET DEFAULT, NO ACTION
```

#### 2. Check Constraints with Generated Columns

```sql
-- v14: Can now use generated columns in constraints
CREATE TABLE products (
  product_id int PRIMARY KEY,
  price_usd numeric(10,2),
  price_eur numeric(10,2) GENERATED ALWAYS AS (price_usd * 0.92) STORED,
  CONSTRAINT price_check CHECK (price_usd > 0 AND price_eur > 0)
);
```

### Sequence & Identity Changes

#### 1. IDENTITY Columns (Recommended over SERIAL)

**Before (v11):**
```sql
CREATE TABLE accounts (
  account_id serial PRIMARY KEY
);
```

**After (v14):**
```sql
CREATE TABLE accounts (
  account_id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY
);
```

**Migration Script:**
```sql
-- For new tables in v14, use IDENTITY
-- For migrated tables, keep serial for compatibility
-- v14 can handle both, but prefer IDENTITY for new code
```

### Trigger & Procedure Compatibility

#### 1. Function Language Stability

```sql
-- Review all function definitions
SELECT 
  proname,
  prolang,
  prosecdef,
  provolatile
FROM pg_proc
WHERE proowner != 10
ORDER BY proname;

-- Migrate PL/pgSQL: Compatible with v14
-- Migrate PL/Python: May need version update (3.6+ → 3.9+)
-- Migrate PL/Perl: Generally compatible
```

#### 2. Example: Trigger Compatibility Check

```sql
-- Extract trigger definition
SELECT pg_get_triggerdef(oid) 
FROM pg_trigger
WHERE tgname = 'your_trigger_name';

-- Verify function exists on target
SELECT EXISTS (
  SELECT 1 FROM pg_proc WHERE proname = 'trigger_function_name'
);
```

### Full Schema Export/Import Procedure

#### Step 1: Export from v11

```bash
#!/bin/bash
# Export schema from PostgreSQL 11

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="production_db"
SOURCE_HOST="on-prem-db.internal"
EXPORT_FILE="/migration/exports/${DB_NAME}_schema_${TIMESTAMP}.sql"

# Full schema export
pg_dump \
  -h $SOURCE_HOST \
  -U pg_migration_user \
  --format=plain \
  --schema-only \
  --no-privileges \
  --no-owner \
  --verbose \
  $DB_NAME > $EXPORT_FILE

echo "Schema exported to $EXPORT_FILE"
echo "File size: $(du -h $EXPORT_FILE | cut -f1)"
```

#### Step 2: Pre-Processing for v14

```python
#!/usr/bin/env python3
# Pre-process schema for v14 compatibility

import re
import sys

def preprocess_schema(input_file, output_file):
    with open(input_file, 'r') as f:
        content = f.read()
    
    # 1. Replace serial with bigserial
    content = re.sub(r'\bserial\b', 'bigserial', content)
    
    # 2. Update deprecated GUC parameters
    deprecated_params = {
        'quote_all_identifiers': 'None',  # Removed in v14
        'bytea_output': 'Keep',  # Still valid
    }
    
    # 3. Convert JSON to JSONB where applicable
    # content = re.sub(r"'json'(\s*,|,\s|$)", "'jsonb'\\1", content)
    
    # 4. Remove v11-specific comments
    content = re.sub(r'-- PostgreSQL 11', '-- PostgreSQL 14', content)
    
    with open(output_file, 'w') as f:
        f.write(content)
    
    print(f"Preprocessed schema written to {output_file}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: preprocess_schema.py <input> <output>")
        sys.exit(1)
    
    preprocess_schema(sys.argv[1], sys.argv[2])
```

#### Step 3: Import to v14

```bash
#!/bin/bash
# Import preprocessed schema to PostgreSQL 14

PREPROCESSED_FILE="$1"
TARGET_HOST="postgresql-prod.postgres.database.azure.com"
DB_NAME="production_db"
USERNAME="pg_admin@postgresql-prod"

# Test connection
psql -h $TARGET_HOST -U $USERNAME -d postgres \
  -c "SELECT version();" || exit 1

# Create database
psql -h $TARGET_HOST -U $USERNAME -d postgres \
  -c "CREATE DATABASE $DB_NAME;"

# Import schema
psql -h $TARGET_HOST -U $USERNAME -d $DB_NAME \
  --set ON_ERROR_STOP=on \
  < $PREPROCESSED_FILE

echo "Schema import completed"

# Validate
psql -h $TARGET_HOST -U $USERNAME -d $DB_NAME \
  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
```

### Data Type Mapping Table

| PostgreSQL 11 | PostgreSQL 14 | Action | Notes |
|---------------|---------------|--------|-------|
| `serial` | `bigserial` | Migrate | 32-bit → 64-bit |
| `json` | `jsonb` | Recommend | JSONB faster |
| `timestamp` | `timestamp` | Keep | Compatible |
| `interval` | `interval` | Verify | Precision options improved |
| `text[]` | `text[]` | Keep | Compatible |
| `uuid` | `uuid` | Keep | Compatible (install extension) |
| `money` | `numeric` | Consider | Avoid for new data |
| `point`, `line` | `geometry` (PostGIS) | Verify | Need PostGIS extension |

### Extension Compatibility

```sql
-- Check extensions on source (v11)
SELECT extname, extversion FROM pg_extension 
WHERE extname NOT LIKE 'plpgsql';

-- Install on target (v14)
-- Common extensions:
CREATE EXTENSION IF NOT EXISTS uuid-ossp;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Verify compatibility
SELECT extname, extversion FROM pg_extension 
WHERE extname NOT LIKE 'plpgsql';
```

### Performance Tuning for v14

```sql
-- Updated GUC parameters for v14
ALTER DATABASE production_db SET shared_buffers = '16GB';
ALTER DATABASE production_db SET effective_cache_size = '48GB';
ALTER DATABASE production_db SET work_mem = '4MB';
ALTER DATABASE production_db SET maintenance_work_mem = '2GB';
ALTER DATABASE production_db SET random_page_cost = 1.1;  -- For SSD storage
ALTER DATABASE production_db SET max_parallel_workers_per_gather = 4;
ALTER DATABASE production_db SET max_worker_processes = 8;

-- Apply changes
SELECT pg_reload_conf();
```

### Validation Checklist

- [ ] All tables migrated with correct schema
- [ ] All columns have correct data types
- [ ] Primary keys preserved
- [ ] Foreign key constraints verified
- [ ] Unique constraints maintained
- [ ] Check constraints compatible
- [ ] Default values transferred
- [ ] Sequences reset correctly
- [ ] Indexes recreated
- [ ] Triggers re-enabled
- [ ] Functions/procedures working
- [ ] Extensions installed
- [ ] Row counts match source

