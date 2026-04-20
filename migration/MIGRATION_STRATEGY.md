# PostgreSQL Migration Strategy

## Executive Overview

This document outlines the phased migration strategy for moving PostgreSQL from on-premises (v11) to Azure PostgreSQL (v14). The strategy emphasizes zero-downtime migration, comprehensive validation, and rollback capability throughout the 8-week implementation window.

## Migration Approach: Phased & Incremental

### Philosophy
- **Minimize Risk**: Validate at every step before proceeding
- **Enable Rollback**: Source system remains active throughout
- **Incremental Load**: Start small, build confidence, scale up
- **Real-Time Validation**: Catch discrepancies immediately, not post-cutover

---

## Phase 1: Infrastructure & Planning (Weeks 1-2)

### Objectives
1. ✅ Provision all Azure resources
2. ✅ Establish secure connectivity
3. ✅ Deploy monitoring & logging
4. ✅ Train team on new infrastructure

### Tasks

#### 1.1 Azure Resource Provisioning

**PostgreSQL Instance**
```
Service Tier: Burstable (B2s initially)
Storage: 500GB (expandable)
vCores: 2 (during migration), scale down post-cutover
Backup Retention: 35 days
High Availability: Disabled (during migration), enabled post-cutover
Networking: Private Link, no public endpoint
```

**Azure Data Factory**
```
Deployment: Standard tier
Integration Runtime: Self-Hosted on on-premises VM
Linked Services: PostgreSQL source + target
Pipelines: Parameterized for flexibility
Triggers: Manual + scheduled (for CDC)
```

**Azure Functions**
```
Runtime: Python 3.11
Plan: Consumption (auto-scale)
Storage: Queue (validation tasks) + Blob (logs)
Timeout: 600 seconds (10 minutes per function)
```

#### 1.2 Network Connectivity

**Option A: ExpressRoute (Recommended)**
- 1Gbps dedicated circuit
- Private connectivity (no internet)
- SLA: 99.95% availability
- Setup time: 4-6 weeks (order early!)

**Option B: VPN (Fast Track)**
- Site-to-Site VPN
- Deployed in hours
- Bandwidth: 1.25Gbps (theoretically)
- Cost-effective for short-term

**Recommended Hybrid**: Deploy VPN immediately, maintain ExpressRoute as backup

#### 1.3 Self-Hosted Integration Runtime (SHIR)

```
Hardware: Windows VM (on-prem or DMZ)
Specs: 4 vCores, 8GB RAM minimum
Network: Connected to both source DB and Azure
Registration: Via Azure Data Factory portal
Agents: Default 4 concurrent jobs per IR
```

#### 1.4 Security Configuration

**Authentication**
```yaml
Source DB:
  - User: pg_migration_service
  - Permissions: SELECT, LOCK on all tables
  - Network: Local socket (no remote exposure)

Target DB:
  - Authentication: Managed Identity (preferred)
  - Fallback: Strong credentials in Key Vault
  - Permissions: CREATE TABLE, INSERT, UPDATE, DELETE on target schemas

Key Vault:
  - Store: Connection strings, credentials, encryption keys
  - Access: RBAC + Managed Identities
  - Rotation: 90-day policy for service accounts
```

**Network Security**
```
On-Prem to Azure:
  - TLS 1.2+ for all connections
  - Private IP ranges (10.x.x.x, 172.16.x.x, 192.168.x.x)
  - NSG rules: Restrict to specific source/destination IPs

Azure Internal:
  - Service endpoints for PostgreSQL
  - Private Link for Functions
  - No public endpoints exposed
```

#### 1.5 Baseline Metrics

Before migration begins, capture source metrics:

```sql
-- Source Database Snapshot
SELECT 
  current_database() AS database,
  version() AS postgres_version,
  COUNT(*) AS total_tables,
  SUM(total_bytes) AS total_size_bytes
FROM (
  SELECT 
    schemaname,
    tablename,
    pg_total_relation_size(schemaname || '.' || tablename) AS total_bytes
  FROM pg_tables
  WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
) t
GROUP BY database, postgres_version;

-- Table Row Counts
SELECT 
  schemaname,
  tablename,
  n_live_tup AS row_count,
  pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- Index Information
SELECT 
  schemaname,
  tablename,
  indexname,
  idx_scan AS index_scans,
  idx_tup_read AS tuples_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

#### 1.6 Team Enablement

- Security training: Data handling, compliance requirements
- Azure services overview: Functions, Data Factory, PostgreSQL
- Tool training: ADF pipeline development, Python validation logic
- Runbook review: Cutover, rollback procedures

---

## Phase 2: Full Load Migration (Weeks 3-4)

### Objectives
1. ✅ Transfer all schema and data
2. ✅ Validate data integrity post-load
3. ✅ Establish baseline performance
4. ✅ Address any blockers before incremental sync

### Strategy: Full Extract & Load (EL)

#### 2.1 Schema Migration

**Step 1: Export Schema from Source**
```bash
# Using pg_dump to extract DDL only
pg_dump -h SOURCE_HOST \
        -U pg_migration_service \
        --schema-only \
        --no-privileges \
        --no-owner \
        database_name > source_schema.sql
```

**Step 2: Pre-processing for v14 Compatibility**

PostgreSQL 11 → 14 migration considerations:
- ❌ Remove deprecated `serial` types → ✅ Replace with `bigserial`
- ❌ Update JSON/JSONB operators (improved in v14)
- ❌ Review partitioning strategy (v14 has better hash partitioning)
- ❌ Validate datetime functions (interval type handling)

**Step 3: Deploy Schema to Target**

Create separate schemas in target for data isolation:
```sql
-- On Azure PostgreSQL v14
CREATE SCHEMA raw_schema;
CREATE SCHEMA validated_schema;
CREATE SCHEMA gold_schema;

-- Apply source schema to raw_schema
SET search_path TO raw_schema;
\i source_schema.sql

-- Replicate to validated_schema
CREATE SCHEMA validated_schema AS 
  SELECT * FROM raw_schema LIMIT 0;
```

#### 2.2 Full Data Extract via ADF Pipeline

**ADF Pipeline Configuration**

```json
{
  "pipeline": {
    "name": "FullLoad_AllTables",
    "activities": [
      {
        "name": "GetTableList",
        "type": "Lookup",
        "inputs": ["SourceLinkedService"],
        "outputs": "TableList"
      },
      {
        "name": "ForEachTable",
        "type": "ForEach",
        "items": "@activity('GetTableList').output.value",
        "activities": [
          {
            "name": "ExtractTableData",
            "type": "Copy",
            "source": {
              "type": "PostgreSQLSource",
              "query": "SELECT * FROM @{item().SchemaName}.@{item().TableName}"
            },
            "sink": {
              "type": "PostgreSQLSink",
              "preCopyScript": "TRUNCATE @{item().SchemaName}.@{item().TableName}",
              "tableName": "@{item().TableName}",
              "schemaName": "raw_schema"
            },
            "parallelCopies": 4,
            "enableStaging": true,
            "stagingSettings": {
              "linkedServiceName": "AzureBlobStorageStaging",
              "path": "adf-staging/@{item().TableName}"
            }
          },
          {
            "name": "QueueValidationJob",
            "type": "ExecuteFunction",
            "inputs": {
              "functionName": "ValidationEngine",
              "payload": {
                "tableSchema": "@{item().SchemaName}",
                "tableName": "@{item().TableName}",
                "validationType": "FULL_LOAD",
                "correlationId": "@{pipeline().RunId}"
              }
            }
          }
        ]
      }
    ]
  }
}
```

**Performance Tuning**
- Parallel copies: 4-8 (depends on network capacity)
- Staging enabled: Improves reliability for large tables
- Batch insert size: 10,000 rows
- Max rows per batch: 100MB

#### 2.3 Post-Load Validation

**Validation Checklist**

| Validation | SQL | Expected Result |
|-----------|-----|-----------------|
| Row Count | `SELECT COUNT(*) FROM raw_schema.TABLE` vs source | Match exactly |
| Column Count | `SELECT COUNT(*) FROM information_schema.columns` | Match schema |
| Data Types | Compare pg_type between v11 and v14 | Compatible types |
| Null Constraints | Check `IS NOT NULL` violations | Zero violations |
| Primary Keys | Verify uniqueness of PK columns | No duplicates |
| Foreign Keys | Test referential integrity | All refs valid |

**Sample Validation Query**
```sql
-- Compare source vs target row counts
SELECT 
  t1.table_name,
  COALESCE(t1.row_count, 0) AS source_count,
  COALESCE(t2.row_count, 0) AS target_count,
  CASE 
    WHEN t1.row_count = t2.row_count THEN 'PASS'
    ELSE 'FAIL'
  END AS validation_result
FROM source_metadata t1
FULL OUTER JOIN target_metadata t2 
  ON t1.table_name = t2.table_name
ORDER BY validation_result DESC, source_count DESC;
```

#### 2.4 Performance Baseline

Execute EXPLAIN ANALYZE on critical queries:
```sql
-- Capture query plans
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM orders WHERE order_date > CURRENT_DATE - INTERVAL '30 days';

-- Store baseline for comparison post-migration
INSERT INTO performance_baseline (query_name, plan_json, execution_time_ms)
VALUES ('orders_30day', plan_json, exec_time);
```

---

## Phase 3: Incremental Sync with CDC (Weeks 5-6)

### Objectives
1. ✅ Enable binary log replication from source
2. ✅ Implement daily delta loads
3. ✅ Validate incremental changes in real-time
4. ✅ Measure replication lag and data currency

### Change Data Capture Strategy

#### 3.1 Enable Source-Side CDC

**PostgreSQL Logical Decoding Setup**

```sql
-- On source PostgreSQL 11 (run as superuser)

-- Enable logical decoding
ALTER SYSTEM SET wal_level = logical;
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET max_replication_slots = 10;

-- Restart PostgreSQL
systemctl restart postgresql-11

-- Create replication slot
SELECT * FROM pg_create_logical_replication_slot('adf_migration_slot', 'test_decoding');

-- Verify slot status
SELECT * FROM pg_replication_slots;
```

#### 3.2 Incremental Load Pipeline

```json
{
  "pipeline": {
    "name": "IncrementalSync_DeltaLoad",
    "parameters": [
      {"name": "LastSyncTimestamp", "type": "string", "defaultValue": "2024-01-01T00:00:00Z"}
    ],
    "activities": [
      {
        "name": "GetChangedTables",
        "type": "SqlServerLookup",
        "linkedServiceName": "SourcePostgres",
        "query": "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
      },
      {
        "name": "ForEachChangedTable",
        "type": "ForEach",
        "items": "@activity('GetChangedTables').output.value",
        "activities": [
          {
            "name": "ExtractChanges",
            "type": "Copy",
            "source": {
              "type": "PostgreSQLSource",
              "query": "SELECT * FROM @{item().schemaname}.@{item().tablename} WHERE updated_at > '@{pipeline().parameters.LastSyncTimestamp}' OR created_at > '@{pipeline().parameters.LastSyncTimestamp}'"
            },
            "sink": {
              "type": "PostgreSQLSink",
              "tableName": "@{item().tablename}",
              "schemaName": "staging_deltas",
              "writeMethod": "BulkInsert"
            }
          },
          {
            "name": "MergeToValidated",
            "type": "ExecuteStoredProcedure",
            "linkedServiceName": "TargetPostgres",
            "storedProcedureName": "merge_delta_data",
            "parameters": {
              "schemaName": "@{item().schemaname}",
              "tableName": "@{item().tablename}",
              "correlationId": "@{pipeline().RunId}"
            }
          }
        ]
      },
      {
        "name": "UpdateSyncTimestamp",
        "type": "Stored Procedure",
        "linkedServiceName": "TargetPostgres",
        "query": "UPDATE migration_metadata SET last_sync_utc = CURRENT_TIMESTAMP WHERE pipeline_name = 'IncrementalSync_DeltaLoad'"
      }
    ]
  }
}
```

#### 3.3 Replication Lag Monitoring

```sql
-- Monitor CDC lag
SELECT 
  slot_name,
  slot_type,
  database,
  active,
  restart_lsn,
  confirmed_flush_lsn,
  NOW() - pg_wal_lsn_offset(confirmed_flush_lsn) AS replication_lag_seconds
FROM pg_replication_slots
WHERE slot_name = 'adf_migration_slot';
```

**Target SLA**: Lag < 30 seconds
- If lag > 60 seconds: Page on-call engineer
- If lag > 300 seconds: Pause cutover, investigate

#### 3.4 Incremental Validation Rules

```python
# Azure Function: Validate Incremental Changes

def validate_incremental_changes(table_metadata: dict, correlation_id: str):
    """
    Validation engine for incremental delta loads
    """
    results = {
        'table': table_metadata['table_name'],
        'correlation_id': correlation_id,
        'validations': []
    }
    
    # 1. Row count comparison (source vs target)
    source_delta_count = query_source(f"""
        SELECT COUNT(*) FROM {table_metadata['schema']}.{table_metadata['table_name']}
        WHERE updated_at > %s
    """, [table_metadata['last_sync_time']])
    
    target_delta_count = query_target(f"""
        SELECT COUNT(*) FROM raw_schema.{table_metadata['table_name']}
        WHERE updated_at > %s
    """, [table_metadata['last_sync_time']])
    
    results['validations'].append({
        'type': 'ROW_COUNT_DELTA',
        'source_count': source_delta_count,
        'target_count': target_delta_count,
        'status': 'PASS' if source_delta_count == target_delta_count else 'FAIL'
    })
    
    # 2. Null constraints on non-nullable columns
    null_violations = query_target(f"""
        SELECT COUNT(*) FROM raw_schema.{table_metadata['table_name']}
        WHERE {' OR '.join([f'{col} IS NULL' for col in table_metadata['not_null_columns']])}
    """)
    
    results['validations'].append({
        'type': 'NULL_CONSTRAINTS',
        'violations': null_violations,
        'status': 'PASS' if null_violations == 0 else 'FAIL'
    })
    
    # 3. Duplicate key detection
    duplicate_keys = query_target(f"""
        SELECT COUNT(*) - COUNT(DISTINCT {','.join(table_metadata['primary_key_columns'])})
        FROM raw_schema.{table_metadata['table_name']}
    """)
    
    results['validations'].append({
        'type': 'UNIQUENESS',
        'duplicates': duplicate_keys,
        'status': 'PASS' if duplicate_keys == 0 else 'FAIL'
    })
    
    return results
```

---

## Phase 4: Pre-Cutover & Testing (Week 7)

### Objectives
1. ✅ Perform final full-sync
2. ✅ Execute read-only production simulation
3. ✅ Validate all applications against target
4. ✅ Confirm rollback procedure

#### 4.1 Final Sync & Freeze Window

```
Friday EOD (5:00 PM): Production freeze begins
  - Source: Read-only mode enabled
  - No new transactions accepted
  
Friday 5:00 PM - Saturday 12:00 PM: Final delta sync
  - Extract final changes from source (12-18 hours of data)
  - Load to target staging
  - Execute comprehensive validation suite
  
Saturday 12:00 PM: Go/No-Go Decision
  - Data validation: 100% pass rate required
  - Performance testing: P95 latency < 200ms
  - Application UAT: All critical paths tested
```

#### 4.2 Read-Only Production Test

```sql
-- On target database (Saturday morning)

-- Enable read-only mode
ALTER SYSTEM SET default_transaction_read_only = on;

-- Application team executes critical reports
-- Example: 
--   - Customer dashboard
--   - Order history
--   - Invoice generation
--   - Analytics queries

-- Capture performance metrics
SELECT 
  query,
  calls,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

#### 4.3 Rollback Procedure Test

```bash
#!/bin/bash
# Dry-run rollback test

# 1. Verify source database is accessible
psql -h SOURCE_HOST -U pg_migration_service -c "SELECT NOW()" || exit 1

# 2. Verify connection strings in application config
grep "SOURCE_HOST" /app/config/connection.yaml

# 3. Test application failover
curl -H "X-Force-Source-DB: true" https://app.internal/health

# 4. Simulate switchback (don't execute, just verify procedure)
echo "Rollback procedure verified - ready for execution"
```

---

## Phase 5: Cutover & Go-Live (Week 8)

### Cutover Window: Saturday 2:00 PM UTC

#### 5.1 Pre-Cutover Tasks (Friday Evening)

- ✅ Backup source database (offline backup)
- ✅ Verify all migration pipelines are stopped
- ✅ Confirm target database is in read-write mode
- ✅ Update DNS/connection strings (staged, not yet deployed)

#### 5.2 Cutover Steps (Saturday 2:00 PM)

**Step 1: Source Lock (2:00 PM)**
```sql
-- Disable all write operations on source
ALTER SYSTEM SET default_transaction_read_only = on;
SELECT pg_reload_conf();

-- Wait for existing transactions to complete (timeout: 300 seconds)
SELECT * FROM pg_stat_activity WHERE state = 'active';
```

**Step 2: Final Validation (2:05 PM)**
```sql
-- Verify no pending changes
SELECT COUNT(*) FROM raw_schema.TABLES_LIST 
INTERSECT
SELECT COUNT(*) FROM source.TABLES_LIST;
```

**Step 3: Application Switchover (2:10 PM)**
```bash
#!/bin/bash
# Automated switchover script

# 1. Update application connection strings
sed -i 's/SOURCE_HOST/TARGET_AZURE_HOST/g' /app/config/connection.yaml

# 2. Restart application servers (rolling restart)
for server in $(cat /etc/app/servers.txt); do
  echo "Restarting $server..."
  ssh $server "systemctl restart myapp"
  sleep 10
done

# 3. Validate application connectivity
curl https://app.internal/health || exit 1

# 4. Run smoke tests
pytest tests/smoke_tests.py -v
```

**Step 4: Monitoring & Stabilization (2:30 PM - ongoing)**
```
Real-time Metrics:
  - Application error rate (target: < 0.1%)
  - Database connection pool usage (target: < 70%)
  - Query latency P95 (target: < 200ms)
  - Failed transactions (target: 0)
  - Memory usage (target: < 80%)

If issues detected:
  - Threshold exceeded: Page on-call
  - Critical error: Automatic rollback trigger
```

#### 5.3 Rollback Decision Point (T+60 minutes)

```
At 3:10 PM, assess status:

✅ STABLE: Continue with post-cutover validation
❌ ISSUES: Execute rollback procedure

Rollback Procedure:
  1. Update connection strings back to source
  2. Restart application servers
  3. Verify source database still in read-only
  4. Post-mortem: Identify root cause
  5. No data loss (source untouched)
```

---

## Post-Migration Activities (Weeks 9+)

### Immediate (Week 8)
- ✅ Decommission SHIR
- ✅ Disable source replication slot
- ✅ Archive migration logs to cold storage
- ✅ Update runbooks for operations team

### Short-Term (Weeks 9-12)
- ✅ Enable read replicas for load balancing
- ✅ Optimize indexes based on v14 query patterns
- ✅ Implement monitoring dashboards
- ✅ Scale Azure PostgreSQL to Standard tier

### Long-Term (Months 3-12)
- ✅ Decommission on-premises database
- ✅ Repatriate workload optimization efforts
- ✅ Evaluate cost savings
- ✅ Plan for future scale (sharding, partitioning)

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Network connectivity failure | Low | High | VPN + ExpressRoute redundancy |
| Data corruption during migration | Low | Critical | Comprehensive validation suite + source backup |
| Replication lag > acceptable threshold | Medium | High | Dedicated network bandwidth, monitoring alerts |
| Application incompatibility with v14 | Medium | Medium | Extensive UAT, test on staging first |
| Performance regression post-cutover | Medium | Medium | Baseline comparison, index optimization, query tuning |
| Insufficient capacity planning | Low | High | Load testing, capacity forecasting, auto-scaling setup |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data Accuracy | 100% match source | Row count + checksum validation |
| Migration Duration | 8 weeks | Calendar days |
| Downtime | < 2 hours | Application unavailability window |
| Data Validation Pass Rate | 100% | All validation checks pass |
| Rollback Capability | Proven | Tested dry-run |
| Documentation Completion | 100% | All runbooks updated |

---

**Document Owner**: Migration Lead
**Last Updated**: Q1 2024
**Version**: 2.0
