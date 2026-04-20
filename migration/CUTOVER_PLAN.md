# Production Cutover Plan

## Executive Summary

This document outlines the detailed procedures for migrating the production PostgreSQL database from on-premises (v11) to Azure PostgreSQL (v14) with a target downtime window of **2-3 hours**. The cutover is scheduled for **Week 62, Saturday 2:00 PM UTC**.

---

## Pre-Cutover Timeline

### Week 61: Final Preparation

**Monday-Wednesday**: Pre-cutover Checklist
```
□ Verify all systems operational
□ Execute final validation tests (100% pass required)
□ Confirm team availability & on-call assignments
□ Prepare and test all cutover scripts
□ Verify communications channels (Slack, Teams, email)
□ Brief all stakeholders on timeline & expectations
□ Confirm executive sponsor approval
```

**Thursday**: Final Rehearsal
```
□ Execute cutover dry-run on non-production environment
□ Test rollback procedures
□ Document any issues & resolutions
□ Finalize team runbooks
□ Conduct team walkthrough of cutover procedures
```

**Friday**: Cutover Go-Ahead Decision
```
Steering Committee determines:
  ✅ All systems ready for cutover
  ✅ Risk assessment acceptable
  ✅ Executive approval obtained
  ✅ Cutover proceeds as planned (Saturday, Week 62)
OR
  ❌ Defer cutover if critical issues found (reschedule for following weekend)
```

---

## Cutover Execution Window

### Timeline Overview

```
SATURDAY WEEK 62

T-48:00  Friday 2:00 PM UTC
         ├─ Final data sync begins
         ├─ Infrastructure last-minute checks
         └─ Team assembles in war room (virtual)

T-24:00  Saturday 2:00 AM UTC (12 hours before cutover)
         ├─ Backup all source systems
         ├─ Create database snapshots (Azure)
         ├─ Alert threshold monitoring activated
         └─ 24/7 operations team on duty

T-01:00  Saturday 1:00 PM UTC (1 hour before)
         ├─ Final validation tests executed
         ├─ All cutover scripts verified
         ├─ Team readiness check (all hands in war room)
         └─ Go/No-Go decision (final gate)

T-00:00  Saturday 2:00 PM UTC ⭐ CUTOVER BEGINS
         ├─ Phase 1: Source Lock (10 min)
         ├─ Phase 2: Final Delta Sync (20-30 min)
         ├─ Phase 3: Application Switchover (20-30 min)
         ├─ Phase 4: Smoke Testing (15-20 min)
         └─ Cutover Complete (Total: 65-90 minutes)

T+02:00  Saturday 4:00 PM UTC
         ├─ System stability validated
         ├─ Business users test critical functions
         └─ Post-cutover communications sent
```

---

## Detailed Cutover Procedures

### Phase 1: Source Database Lock (T+0 to T+10)

**Objective**: Lock source database to read-only to capture final state

**Step 1.1**: Notify all users (T+0)
```bash
# Send emergency maintenance notification
  Subject: URGENT - Database Maintenance (90 minutes)
  To: All application users, IT operations, leadership
  
  Message:
  "The production database will be offline for 90 minutes starting
   at 2:00 PM UTC (Saturday) for maintenance migration. All 
   applications will be unavailable during this time."
```

**Step 1.2**: Drain application connections (T+2)
```bash
# Stop accepting new connections
psql -h on-prem-db.internal -U pg_admin -d production -c \
  "ALTER SYSTEM SET max_connections = 100; SELECT pg_reload_conf();"

# Wait for existing connections to drain
while [ $(psql -h on-prem-db.internal -c "SELECT COUNT(*) FROM pg_stat_activity WHERE state != 'idle';" | tail -1) -gt 0 ]; do
  echo "$(date): Waiting for connections to drain..."
  sleep 5
done
```

**Step 1.3**: Enable read-only mode (T+5)
```bash
# Make source database read-only
psql -h on-prem-db.internal -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# Verify read-only status
psql -h on-prem-db.internal -U pg_admin -d production -c \
  "SHOW default_transaction_read_only;"
# Expected output: on

# Record final LSN (Log Sequence Number)
FINAL_LSN=$(psql -h on-prem-db.internal -U pg_admin -d production -t -c \
  "SELECT pg_current_wal_lsn();")
echo "Final LSN: $FINAL_LSN"
```

**Step 1.4**: Verify no active transactions (T+8)
```bash
# Check for any remaining transactions
psql -h on-prem-db.internal -U pg_admin -d production -c \
  "SELECT pid, usename, state, query FROM pg_stat_activity WHERE state != 'idle';"
# Expected output: (no rows)

# Log: Source database locked successfully
echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] Source locked at LSN: $FINAL_LSN" >> cutover_log.txt
```

**✅ Phase 1 Complete** (T+10)

---

### Phase 2: Final Delta Sync (T+10 to T+40)

**Objective**: Extract and apply all changes since last sync

**Step 2.1**: Execute final incremental load (T+10)
```bash
# Trigger ADF pipeline for delta sync
az datafactory pipeline create-run \
  --name IncrementalSync_DeltaLoad \
  --factory-name migration-adf \
  --resource-group migration-rg \
  --parameters "LastSyncTimestamp=$FINAL_LSN" \
  > /tmp/pipeline_run.json

PIPELINE_RUN_ID=$(jq -r '.runId' /tmp/pipeline_run.json)
echo "[$(date)] Pipeline run started: $PIPELINE_RUN_ID"

# Monitor pipeline execution
until [ $PIPELINE_STATUS = "Succeeded" ] || [ $PIPELINE_STATUS = "Failed" ]; do
  PIPELINE_STATUS=$(az datafactory pipeline-run show \
    --run-id $PIPELINE_RUN_ID \
    --factory-name migration-adf \
    --resource-group migration-rg \
    --query status -o tsv)
  echo "[$(date)] Pipeline status: $PIPELINE_STATUS"
  sleep 10
done

if [ $PIPELINE_STATUS != "Succeeded" ]; then
  echo "[ERROR] Pipeline failed! Check logs and consider rollback."
  exit 1
fi

echo "[$(date)] Delta sync completed successfully"
```

**Step 2.2**: Verify delta sync results (T+35)
```bash
# Count rows in target database for key tables
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT table_name, row_count FROM migration_metadata 
   WHERE sync_timestamp > NOW() - INTERVAL '30 minutes';"

# Validate data integrity
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT 'All tables valid' FROM migration_validation_log 
   WHERE validation_status = 'PASS' 
   GROUP BY validation_status HAVING COUNT(*) = (SELECT COUNT(DISTINCT table_name) FROM information_schema.tables WHERE table_schema = 'public');"
```

**Step 2.3**: Record target state (T+38)
```bash
# Capture post-sync metrics
TARGET_SYNC_TIME=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
echo "[${TARGET_SYNC_TIME}] Delta sync completed, target ready" >> cutover_log.txt
```

**✅ Phase 2 Complete** (T+40)

---

### Phase 3: Application Switchover (T+40 to T+70)

**Objective**: Update application connection strings & perform rolling restart

**Step 3.1**: Update configuration in all deployment repositories (T+40)
```bash
# Update main application config
sed -i.bak \
  's/on-prem-db\.internal/postgresql-prod.postgres.database.azure.com/g' \
  /etc/myapp/database.yaml

sed -i \
  's/:5432/:5432/g' \
  /etc/myapp/database.yaml

# Verify changes
diff /etc/myapp/database.yaml.bak /etc/myapp/database.yaml
```

**Step 3.2**: Perform rolling restart of application servers (T+42)
```bash
#!/bin/bash
# Rolling restart script

APP_SERVERS=("app-server-1" "app-server-2" "app-server-3")

for i in "${!APP_SERVERS[@]}"; do
  server="${APP_SERVERS[$i]}"
  echo "[$(date)] Restarting $server ($((i+1))/${#APP_SERVERS[@]})"
  
  # Restart application
  ssh $server "systemctl restart myapp"
  
  # Wait for application to start
  sleep 20
  
  # Verify health check passes
  MAX_RETRIES=5
  RETRY_COUNT=0
  until curl -s https://$server/health | grep -q '"status":"healthy"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
      echo "[ERROR] $server failed health check after $MAX_RETRIES retries"
      exit 1
    fi
    echo "[$(date)] Waiting for $server to become healthy (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 10
  done
  
  echo "[$(date)] ✅ $server healthy and operational"
  
  # Stagger restarts (except last server)
  if [ $i -lt $((${#APP_SERVERS[@]} - 1)) ]; then
    sleep 30
  fi
done

echo "[$(date)] ✅ All application servers restarted successfully"
```

**Step 3.3**: Verify connectivity & transactions (T+60)
```bash
# Check active connections
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT datname, count(*) as connections FROM pg_stat_activity GROUP BY datname;"

# Verify transactions are working
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "BEGIN; SELECT COUNT(*) FROM orders; COMMIT;"

# Check replication lag (should be ~0)
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT NOW() - pg_postmaster_start_time() as uptime;"
```

**Step 3.4**: Enable read-write on target (T+68)
```bash
# Enable write access to target database
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = off; SELECT pg_reload_conf();"

# Verify write is enabled
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SHOW default_transaction_read_only;"
# Expected output: off
```

**✅ Phase 3 Complete** (T+70)

---

### Phase 4: Smoke Testing & Validation (T+70 to T+90)

**Objective**: Verify system functionality and data integrity

**Step 4.1**: Execute smoke tests (T+70)
```bash
# Run critical business process tests
pytest tests/smoke_tests.py::TestCriticalPaths -v --tb=short

# Expected: ALL TESTS PASSED

# Sample tests:
#   ✅ test_customer_order_creation
#   ✅ test_invoice_generation
#   ✅ test_financial_reporting
#   ✅ test_customer_lookup
#   ✅ test_api_connectivity
```

**Step 4.2**: Verify data accuracy (T+77)
```bash
# Compare row counts between source and target
declare -a CRITICAL_TABLES=("customers" "orders" "invoices" "line_items" "payments")

for table in "${CRITICAL_TABLES[@]}"; do
  SOURCE_COUNT=$(psql -h on-prem-db.internal -U pg_admin -d production -t -c \
    "SELECT COUNT(*) FROM $table;")
  TARGET_COUNT=$(psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -t -c \
    "SELECT COUNT(*) FROM $table;")
  
  if [ "$SOURCE_COUNT" -eq "$TARGET_COUNT" ]; then
    echo "✅ $table: $SOURCE_COUNT rows (match)"
  else
    echo "❌ $table: Source=$SOURCE_COUNT, Target=$TARGET_COUNT (MISMATCH)"
  fi
done
```

**Step 4.3**: Capture metrics (T+82)
```bash
# Record post-cutover performance metrics
curl -s https://app.internal/metrics | jq . > metrics_post_cutover.json

# Verify error rate is acceptable
ERROR_RATE=$(jq '.error_rate_percent' metrics_post_cutover.json)
if (( $(echo "$ERROR_RATE < 0.1" | bc -l) )); then
  echo "✅ Error rate acceptable: $ERROR_RATE%"
else
  echo "❌ Error rate too high: $ERROR_RATE%"
fi

# Verify latency acceptable
LATENCY_P95=$(jq '.latency_p95_ms' metrics_post_cutover.json)
if (( $(echo "$LATENCY_P95 < 500" | bc -l) )); then
  echo "✅ Latency acceptable: ${LATENCY_P95}ms"
else
  echo "⚠️  Latency elevated: ${LATENCY_P95}ms"
fi
```

**Step 4.4**: Notify business users for validation (T+85)
```bash
# Send go-live notification
cat << EOF | sendmail team@company.com
Subject: ✅ System Live on Azure - Please Validate

The production database has been successfully migrated to Azure PostgreSQL.
The system is now live and fully operational.

Please test your critical business functions and report any issues immediately.

Contact Operations if you experience any problems.

Cutover completed at: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
Total downtime: ~$((SECONDS / 60)) minutes
EOF
```

**✅ Phase 4 Complete - CUTOVER SUCCESSFUL** (T+90)

---

## Rollback Procedures

### Emergency Rollback Trigger

Rollback is initiated if **ANY** of the following occur:
- ❌ Critical data corruption detected
- ❌ Error rate > 1% sustained for > 10 minutes
- ❌ Unrecoverable connectivity failure
- ❌ Steering Committee decision (executive authority)

### Rollback Execution (Total Time: 45-60 minutes)

**Step 1**: Notify all stakeholders (5 min)
```bash
# Send emergency rollback notification
sendmail -v << EOF
Subject: 🚨 EMERGENCY ROLLBACK IN PROGRESS

The production system is being rolled back to the on-premises database.
Please stop any critical operations and wait for notifications.

Estimated rollback completion: 45 minutes
EOF
```

**Step 2**: Disable target database writes (10 min)
```bash
# Set target to read-only immediately
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# Verify read-only status
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SHOW default_transaction_read_only;"
```

**Step 3**: Restore source connection strings (10 min)
```bash
# Rollback config changes
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "mv /etc/myapp/database.yaml.backup /etc/myapp/database.yaml"
done
```

**Step 4**: Rolling restart to source (15 min)
```bash
# Restart applications back to source
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "systemctl restart myapp"
  sleep 20
  
  # Verify health
  curl -s https://$server/health || exit 1
done
```

**Step 5**: Verify source connectivity (5 min)
```bash
# Test source database
psql -h on-prem-db.internal -U pg_admin -d production -c \
  "SELECT NOW() as current_time;" | grep -q "current_time"

# Run smoke tests against source
pytest tests/smoke_tests.py::TestCriticalPaths -v
```

**✅ ROLLBACK COMPLETE** - System restored to source database

---

## Post-Cutover Monitoring (24/7)

### Week 1: Hypercare Phase

**Day 1 (Cutover Day - Saturday)**
```
2:00 PM   - Cutover begins
5:00 PM   - Cutover complete, all systems verified
6:00 PM   - Evening support team assumes 24/7 watch
            - Monitor for any issues in evening hours
```

**Days 2-7 (Sunday - Friday)**
```
Monitoring Activities (Every 4 hours):
  □ Health checks (database, application, API)
  □ Performance metrics review (CPU, connections, latency)
  □ Error log scan for exceptions
  □ User-reported issues triage & resolution
  □ Database integrity validation

Support Escalation:
  Severity 1 (Critical): Immediate escalation to DBA on-call
  Severity 2 (High): Escalation to engineering lead within 30 min
  Severity 3 (Medium): Regular business hour response
```

### Week 2-4: Extended Support Phase

**Monitoring frequency**: Every 8 hours
**Support model**: 16/7 (business hours + evening), on-call for emergencies
**Focus**: Performance optimization, issue stabilization

### Week 5+: Normal Operations

**Monitoring frequency**: Daily during business hours
**Support model**: Business hours only, on-call emergency rotation
**Handoff**: To operations team

---

## Success Criteria

Cutover is considered **SUCCESSFUL** if all criteria are met within 24 hours:

| Criteria | Target | Status |
|----------|--------|--------|
| Downtime window | ≤ 3 hours | ✅ |
| Zero data loss | 0 rows | ✅ |
| Data accuracy | 100% match | ✅ |
| Error rate | < 0.1% | ✅ |
| Application health | 100% online | ✅ |
| User satisfaction | > 95% | ✅ |

---

## Communication Plan

### Pre-Cutover Communications

**Friday (1 day before)**
```
To: All users, stakeholders, support team
Message: "Database migration cutover scheduled for Saturday 2:00 PM UTC
         System will be offline for ~90 minutes. Plan accordingly."
```

**Saturday 1:00 PM (1 hour before)**
```
To: Operations, support, executive sponsor
Message: "Cutover proceeding as scheduled. All systems ready.
         Final go-ahead decision: APPROVED"
```

### Cutover-Time Communications

**Saturday 2:00 PM (Cutover start)**
```
To: All users
Subject: Database maintenance begins - 90 minute downtime
```

**Saturday 3:30 PM (Cutover complete)**
```
To: All stakeholders
Subject: Database migration complete - System online
```

### Post-Cutover Communications

**Saturday 6:00 PM**
```
To: All stakeholders
Subject: System stabilization - All critical functions validated
```

**Sunday morning**
```
To: Executive sponsor
Subject: Cutover post-mortem - Success metrics review
```

---

## Contingency Plans

### Scenario: Application Cannot Connect to Target DB

**Root causes**: Network connectivity, credentials, TLS certificates

**Recovery** (15-30 minutes):
1. Verify network routes to target database
2. Validate connection string format
3. Check Key Vault secrets (credentials)
4. Verify firewall rules & NSG rules
5. If unresolved: initiate rollback procedure

### Scenario: Data Mismatch Detected

**Root causes**: Incomplete delta sync, data corruption

**Recovery** (30-60 minutes):
1. Stop application writes to target (set to read-only)
2. Run detailed data reconciliation
3. Identify scope of mismatch (tables affected)
4. If > 5% mismatch: initiate rollback
5. If < 5% mismatch: fix via replay & rollback (if needed)

### Scenario: Sustained High Error Rate (>1%)

**Root causes**: Performance degradation, resource exhaustion

**Recovery** (15-45 minutes):
1. Check database resource utilization (CPU, memory, connections)
2. Scale up database tier if needed (auto-scale can help)
3. Identify slow queries via monitoring
4. If sustained > 10 minutes: consider rollback

---

## Sign-Off & Approvals

### Pre-Cutover Sign-Off

- [ ] Project Manager: All deliverables complete
- [ ] Steering Committee Chair: Go/No-Go approval
- [ ] CTO: Architecture & performance approved
- [ ] CISO: Security controls validated
- [ ] CFO: Budget & resource allocations approved

### Post-Cutover Sign-Off (48 hours after cutover)

- [ ] VP Operations: System stable & performing
- [ ] VP Finance: Financial reporting working correctly
- [ ] VP Customer Success: Customer data intact & accessible
- [ ] Steering Committee: Project complete - Go-live successful

---

**Cutover Plan Version**: 2.0
**Last Updated**: Q1 2024
**Status**: Ready for execution (Week 62, Saturday 2:00 PM UTC)
