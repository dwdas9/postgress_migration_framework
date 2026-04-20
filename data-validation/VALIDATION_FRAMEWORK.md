# Data Validation Framework

## Overview

This framework provides comprehensive data validation across all migration phases. It ensures 100% data integrity and consistency between source (PostgreSQL v11) and target (Azure PostgreSQL v14) systems.

## Validation Layers

### Layer 1: Structural Validation
- **Schema Compatibility**: Column names, data types, constraints
- **Index Verification**: All indexes present and valid
- **Constraint Checks**: PK, FK, Unique, Check constraints

### Layer 2: Data Quality Validation
- **Row Count Reconciliation**: Source vs target row counts
- **Column-Level Validation**: Data type compliance, null constraints
- **Data Profile Analysis**: Min/max/avg values for numeric columns

### Layer 3: Business Logic Validation
- **Referential Integrity**: Foreign keys valid
- **Custom Business Rules**: Domain-specific validations
- **Historical Accuracy**: Data completeness over time windows

### Layer 4: Performance Validation
- **Query Performance**: Baseline vs post-migration comparison
- **Index Utilization**: Query plans and index usage
- **Connection Pooling**: Response times and connection overhead

## Validation Rules Engine

### Rule Definition Format

```yaml
validation_rule:
  rule_id: "ROW_COUNT_RECONCILIATION"
  rule_name: "Source vs Target Row Count Match"
  severity: "CRITICAL"
  enabled: true
  tables: ["*"]  # Apply to all tables
  frequency: "AFTER_EACH_LOAD"
  tolerance: 0  # Zero tolerance for row count mismatch
  
  query_source: |
    SELECT COUNT(*) as row_count FROM {schema}.{table}
    
  query_target: |
    SELECT COUNT(*) as row_count FROM raw_schema.{table}
    
  validation_logic: |
    source_count == target_count
    
  actions_on_failure:
    - severity: "CRITICAL"
      action: "PAUSE_CUTOVER"
      notification: "Email,Slack"
      escalation_time_minutes: 15

---

validation_rule:
  rule_id: "NULL_CONSTRAINT_VALIDATION"
  rule_name: "NOT NULL Constraint Compliance"
  severity: "HIGH"
  enabled: true
  frequency: "AFTER_EACH_LOAD"
  
  validation_logic: |
    For each column with NOT NULL constraint:
      violations = COUNT(*) WHERE column IS NULL
      FAIL if violations > 0
      
  actions_on_failure:
    - severity: "HIGH"
      action: "LOG_AND_REVIEW"
      notification: "Email"

---

validation_rule:
  rule_id: "PRIMARY_KEY_UNIQUENESS"
  rule_name: "Primary Key Uniqueness Check"
  severity: "CRITICAL"
  enabled: true
  frequency: "AFTER_EACH_LOAD"
  
  validation_logic: |
    For each table with PRIMARY KEY:
      duplicate_count = COUNT(*) - COUNT(DISTINCT pk_columns)
      FAIL if duplicate_count > 0
      
  actions_on_failure:
    - severity: "CRITICAL"
      action: "PAUSE_CUTOVER"

---

validation_rule:
  rule_id: "FOREIGN_KEY_REFERENTIAL_INTEGRITY"
  rule_name: "Foreign Key Constraint Validation"
  severity: "CRITICAL"
  enabled: true
  frequency: "AFTER_EACH_LOAD"
  
  validation_logic: |
    For each foreign key constraint:
      orphaned_count = COUNT(*) of child records with no matching parent
      FAIL if orphaned_count > 0
      
  actions_on_failure:
    - severity: "CRITICAL"
      action: "PAUSE_CUTOVER"
```

## Validation Metrics & KPIs

### Real-Time Dashboards Metrics

```json
{
  "migration_phase": "INCREMENTAL_SYNC",
  "validation_metrics": {
    "timestamp_utc": "2024-03-15T14:32:00Z",
    "tables_validated": 127,
    "tables_passed": 125,
    "tables_failed": 2,
    "pass_rate_percent": 98.4,
    "total_rows_validated": 45328192,
    "total_rows_passed": 45298431,
    "data_accuracy_percent": 99.93,
    "validation_duration_seconds": 847,
    "average_rows_per_second": 53512,
    "errors_found": [
      {
        "table": "orders",
        "error_type": "ROW_COUNT_MISMATCH",
        "source_count": 1000000,
        "target_count": 999998,
        "difference": -2,
        "severity": "HIGH",
        "action_required": "Review missing records"
      }
    ]
  },
  "replication_metrics": {
    "replication_lag_seconds": 8,
    "last_sync_timestamp": "2024-03-15T14:30:15Z",
    "next_scheduled_sync": "2024-03-15T14:35:15Z",
    "sync_frequency_seconds": 300
  },
  "performance_metrics": {
    "extract_throughput_mbps": 125.5,
    "load_throughput_mbps": 112.3,
    "validation_throughput_mbps": 95.2
  }
}
```

## Exception Handling & Resolution

### Exception Classification

| Exception Type | Severity | Root Cause | Resolution |
|---|---|---|---|
| Row Count Mismatch | CRITICAL | Network interruption, incomplete load, source transaction rollback | Re-run load, verify network connectivity |
| NULL Constraint Violation | HIGH | Data quality issue in source | Manual data review, source data correction |
| FK Referential Integrity | CRITICAL | Out-of-order load, orphaned records | Verify load order, investigate source data |
| Data Type Mismatch | HIGH | Schema version incompatibility | Validate schema migration, check v11 vs v14 compatibility |
| Duplicate Primary Key | CRITICAL | Data corruption, duplicate inserts | Investigate load process, check for duplicates in source |

### Escalation Procedure

```
Level 1 (0-5 minutes): Automated logging, email to team
  └─ Alert team of exception

Level 2 (5-15 minutes): Slack notification, on-call engineer paged
  └─ Manual investigation starts

Level 3 (15-60 minutes): Management escalation, cutover pause
  └─ Escalation meeting initiated

Level 4 (60+ minutes): Executive escalation, rollback decision
  └─ Steering committee notified, rollback option discussed
```

## Validation Result Storage

### Cosmos DB Schema

```json
{
  "id": "validation_2024-03-15T14:32:00Z_orders",
  "partition_key": "2024-03-15",
  "validation_run_id": "00000000-0000-0000-0000-000000000000",
  "correlation_id": "pipeline_run_12345",
  "timestamp_utc": "2024-03-15T14:32:00Z",
  "table_name": "orders",
  "table_schema": "public",
  "phase": "INCREMENTAL_SYNC",
  "validations": [
    {
      "validation_id": "ROW_COUNT_RECONCILIATION",
      "validation_name": "Row Count Match",
      "status": "PASS",
      "source_count": 1000000,
      "target_count": 1000000,
      "duration_ms": 235
    },
    {
      "validation_id": "NULL_CONSTRAINT_VALIDATION",
      "validation_name": "NOT NULL Constraints",
      "status": "PASS",
      "violations_found": 0,
      "columns_checked": 15,
      "duration_ms": 412
    }
  ],
  "overall_status": "PASS",
  "failed_validations": 0,
  "total_duration_ms": 1047,
  "auditing": {
    "created_by": "azure_function_validation_engine",
    "created_timestamp": "2024-03-15T14:32:00Z",
    "ttl": 7776000  // 90 days
  }
}
```

## Report Generation

### Validation Summary Report

```
PostgreSQL Migration Validation Report
Generated: 2024-03-15 14:35 UTC
Migration Phase: INCREMENTAL_SYNC
Reporting Period: 2024-03-15 10:00 UTC - 2024-03-15 14:30 UTC

EXECUTIVE SUMMARY
═════════════════════════════════════════════════════════════════
Overall Status:                          ✅ PASS
Data Accuracy:                           99.98%
Validation Pass Rate:                    100% (127/127 tables)
Replication Lag:                         8 seconds (Within SLA)
Total Records Validated:                 45.3M
Duration:                                2h 14m

VALIDATION BREAKDOWN
═════════════════════════════════════════════════════════════════
Row Count Reconciliation:                ✅ 127/127 tables match
Column-Level Validation:                 ✅ All columns compliant
Null Constraint Validation:              ✅ Zero violations
Primary Key Uniqueness:                  ✅ No duplicates found
Foreign Key Referential Integrity:       ✅ All references valid
Data Type Compliance:                    ✅ 100% compliant
Business Rule Validation:                ✅ All rules passed

EXCEPTION DETAILS
═════════════════════════════════════════════════════════════════
None

PERFORMANCE METRICS
═════════════════════════════════════════════════════════════════
Extract Throughput:                      125.5 MB/s
Load Throughput:                         112.3 MB/s
Validation Throughput:                   95.2 MB/s

ANOMALIES & WARNINGS
═════════════════════════════════════════════════════════════════
None

NEXT STEPS
═════════════════════════════════════════════════════════════════
1. Continue monitoring incremental sync
2. Schedule next validation cycle: 2024-03-15 14:40 UTC
3. Prepare for cutover: Week 8 (2024-04-15)

Validation Framework: PostgreSQL Migration v2.0
```

## Automated Validation SLA

| Phase | Validation Frequency | Max Duration | Pass Requirement |
|-------|--------|---------------|----|
| Full Load | After each table | 5 minutes per table | 100% |
| Incremental Sync | Every 5 minutes | 2 minutes | 100% |
| Pre-Cutover | Continuous | 15 minutes total | 100% + Performance baseline |
| Post-Cutover | Every 10 minutes (24h) | 3 minutes | 99.9% (log exceptions) |

## Validation Checklist for Each Phase

### Phase 1: Infrastructure Setup
- [ ] SHIR connectivity to source verified
- [ ] Target PostgreSQL v14 accessibility confirmed
- [ ] Key Vault secrets created and tested
- [ ] Function app deployment successful
- [ ] Storage queues created
- [ ] Cosmos DB provisioned

### Phase 2: Full Load
- [ ] Schema migration completed
- [ ] Row count validation: 100% match
- [ ] Column validation: All columns present
- [ ] Data type validation: No type mismatches
- [ ] Constraint validation: All constraints satisfied
- [ ] Index validation: All indexes created

### Phase 3: Incremental Sync
- [ ] Replication lag < 30 seconds
- [ ] Delta validation: Each increment validated
- [ ] Null constraint validation: Zero violations
- [ ] FK referential integrity: All refs valid
- [ ] Performance baseline: P95 latency < 200ms

### Phase 4: Pre-Cutover
- [ ] Final delta sync complete
- [ ] Read-only production test: Passed
- [ ] Application UAT: All critical paths verified
- [ ] Rollback procedure: Dry-run successful
- [ ] Stakeholder approval: Signed off

---

**Validation Framework Document**: Version 1.0
**Last Updated**: Q1 2024
**Maintained By**: Data Engineering Team
