# PostgreSQL Migration - Runbook

## Quick Reference Guide for Operations Team

---

## Pre-Migration Checklist (Week 1)

### Infrastructure Verification
```bash
# 1. Verify source database connectivity
psql -h on-prem-db.internal -U pg_migration_user -d production -c "SELECT VERSION();"

# 2. Verify target database connectivity
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c "SELECT VERSION();"

# 3. Verify SHIR connectivity
ping self-hosted-ir-vm.internal

# 4. Verify Azure Function deployment
az functionapp show --name migration-validation-function --resource-group migration-rg

# 5. Verify Cosmos DB connectivity
az cosmosdb database list --name cosmosdb-prod --resource-group migration-rg
```

### Network Connectivity Check
```bash
# VPN Status
az network vnet show --name on-prem-vnet --resource-group on-prem-rg

# ExpressRoute Status
az network express-route show --name migration-circuit --resource-group migration-rg

# Latency Check (< 100ms expected)
ping -c 5 postgresql-prod.postgres.database.azure.com
```

---

## Full Load Migration (Week 3-4)

### Execute Full Load Pipeline
```bash
# 1. Start ADF pipeline
az datafactory pipeline create-run \
  --name FullLoad_PostgreSQL_Migration \
  --factory-name migration-adf \
  --resource-group migration-rg

# 2. Monitor execution
az datafactory pipeline-run show \
  --run-id <pipeline-run-id> \
  --factory-name migration-adf \
  --resource-group migration-rg

# 3. Check for errors
az datafactory activity-run query \
  --factory-name migration-adf \
  --pipeline-name FullLoad_PostgreSQL_Migration \
  --resource-group migration-rg \
  --run-id <pipeline-run-id>
```

### Post-Load Validation
```sql
-- Verify all tables migrated
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'raw_schema';

-- Row count reconciliation
SELECT 
  table_name,
  source_count,
  target_count,
  CASE WHEN source_count = target_count THEN 'PASS' ELSE 'FAIL' END AS status
FROM migration_metadata m
LEFT JOIN validation_results v ON m.table_name = v.table_name;

-- Check for NULL violations
SELECT * FROM migration_validation_log
WHERE validation_type = 'NULL_CONSTRAINT' AND validation_status = 'FAIL';
```

---

## Incremental Sync (Week 5-6)

### Daily Incremental Load
```bash
# 1. Trigger incremental pipeline
az datafactory pipeline create-run \
  --name IncrementalSync_DeltaLoad \
  --factory-name migration-adf \
  --resource-group migration-rg \
  --parameters "LastSyncTimestamp=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# 2. Monitor replication lag
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "SELECT slot_name, replication_lag_seconds FROM pg_replication_slots WHERE slot_name = 'adf_migration_slot';"

# 3. Check validation queue depth
az storage queue metadata show \
  --account-name stgmigration \
  --name validation-tasks \
  --connection-string $AZURE_STORAGE_CONNECTION_STRING
```

### Continuous Validation Monitoring
```bash
# Monitor validation dashboard
open https://migration-validation-dashboard.azurewebsites.net

# Check latest validation results
curl https://migration-validation.azurewebsites.net/api/migration/metrics

# Alert if validation fails
az monitor metrics list-definitions \
  --resource /subscriptions/<sub-id>/resourceGroups/migration-rg/providers/Microsoft.Insights/components/migration-app-insights
```

---

## Pre-Cutover (Week 7)

### Final Sync & Read-Only Test
```bash
# 1. Enable read-only on source
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# 2. Execute final delta load
az datafactory pipeline create-run \
  --name IncrementalSync_DeltaLoad \
  --factory-name migration-adf \
  --resource-group migration-rg

# 3. Enable read-only on target
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# 4. Run comprehensive validation
curl -X POST https://migration-validation.azurewebsites.net/api/validate-all \
  -H "Content-Type: application/json" \
  -d '{"validation_type": "COMPREHENSIVE"}'

# 5. Verify validation pass rate
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT (SELECT COUNT(*) FROM migration_validation_log WHERE validation_status = 'PASS') * 100.0 / COUNT(*) AS pass_rate FROM migration_validation_log;"
```

### Cutover Dry-Run
```bash
# 1. Backup current connection configs
cp /app/config/database.yaml /app/config/database.yaml.backup

# 2. Update to target connection
sed -i 's/on-prem-db.internal/postgresql-prod.postgres.database.azure.com/g' /app/config/database.yaml

# 3. Restart app servers (rolling)
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "systemctl restart myapp"
  sleep 10
  # Verify connectivity
  curl -s https://$server/health || exit 1
done

# 4. Run smoke tests
pytest tests/smoke_tests.py -v

# 5. Rollback (restore original config)
mv /app/config/database.yaml.backup /app/config/database.yaml
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "systemctl restart myapp"
  sleep 10
done

# 6. Verify rolled back
curl -s https://app.internal/health
```

---

## Cutover Day (Week 8 - Saturday)

### T-2:00 (2:00 PM UTC) - Source Lock
```bash
# 1. Lock source database (read-only)
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# 2. Verify no active transactions
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "SELECT pid, usename, state FROM pg_stat_activity WHERE state != 'idle';"

# 3. Wait for existing transactions to complete (max 5 minutes)
sleep 300
```

### T-2:05 (2:05 PM UTC) - Final Delta Sync
```bash
# 1. Execute final incremental load
START_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
az datafactory pipeline create-run \
  --name IncrementalSync_DeltaLoad \
  --factory-name migration-adf \
  --resource-group migration-rg \
  --parameters "LastSyncTimestamp=$START_TIME"

# 2. Monitor completion
watch -n 5 'az datafactory pipeline-run show --run-id <pipeline-run-id> --factory-name migration-adf --resource-group migration-rg'

# 3. Verify no errors
az datafactory pipeline-run query-activity-runs \
  --run-id <pipeline-run-id> \
  --factory-name migration-adf \
  --resource-group migration-rg
```

### T-2:15 (2:15 PM UTC) - Application Switchover
```bash
#!/bin/bash
# Automated switchover script

set -e  # Exit on any error

# Update connection strings
echo "Updating connection strings..."
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "sed -i 's/on-prem-db.internal/postgresql-prod.postgres.database.azure.com/g' /app/config/database.yaml"
done

# Rolling restart
echo "Rolling restart of application servers..."
for i in {1..3}; do
  server="app-server-$i"
  echo "Restarting $server..."
  ssh $server "systemctl restart myapp"
  sleep 15
  
  # Verify connectivity
  if ! curl -s https://$server/health | grep -q '"status":"healthy"'; then
    echo "ERROR: $server failed health check!"
    exit 1
  fi
done

echo "Application switchover complete!"
```

### T-2:35 (2:35 PM UTC) - Smoke Tests
```bash
# Run critical health checks
pytest tests/smoke_tests.py::TestHealthChecks -v
pytest tests/smoke_tests.py::TestDatabaseConnectivity -v
pytest tests/smoke_tests.py::TestCriticalQueries -v

# Capture metrics
curl https://app.internal/metrics > metrics_post_cutover.json

# Check error rate (should be 0%)
ERROR_RATE=$(curl -s https://monitoring.azure.com/api/error-rate | jq '.error_rate')
if (( $(echo "$ERROR_RATE > 0.001" | bc -l) )); then
  echo "ERROR: Error rate too high: $ERROR_RATE"
  exit 1
fi
```

### T-2:45 (2:45 PM UTC) - Business User Sign-Off
```bash
# Send notification to business users
echo "System is live on Azure PostgreSQL v14. Please verify your critical reports."

# Monitor for user reports
watch -n 60 'tail -f /app/logs/application.log | grep -i "error\|exception"'

# Capture any issues
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT * FROM migration_validation_log WHERE validation_status = 'FAIL' ORDER BY validation_timestamp DESC LIMIT 10;"
```

### T-3:00 (3:00 PM UTC) - 24/7 Monitoring Begins
```bash
# Activate continuous monitoring
az monitor alert create \
  --name migration-cutover-monitoring \
  --resource-group migration-rg \
  --condition "avg Percentage CPU > 80 for 5 m" \
  --action email@example.com

# Log all metrics continuously
while true; do
  TIMESTAMP=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  echo "$TIMESTAMP - $(curl -s https://app.internal/metrics)" >> /var/log/migration_metrics.log
  sleep 60
done
```

---

## Emergency Rollback (If Needed)

### Automatic Rollback Trigger
```bash
#!/bin/bash
# Execute if critical issues detected within first hour post-cutover

echo "INITIATING EMERGENCY ROLLBACK..."

# 1. Disable target writes
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = on; SELECT pg_reload_conf();"

# 2. Revert connection strings
for server in app-server-1 app-server-2 app-server-3; do
  ssh $server "sed -i 's/postgresql-prod.postgres.database.azure.com/on-prem-db.internal/g' /app/config/database.yaml"
done

# 3. Rolling restart to source
for i in {1..3}; do
  server="app-server-$i"
  ssh $server "systemctl restart myapp"
  sleep 15
done

# 4. Verify connectivity restored
curl -s https://app.internal/health || exit 1

echo "ROLLBACK COMPLETE - Application restored to source database"
```

---

## Post-Cutover (First 7 Days)

### Daily Validation Checklist
```bash
# 1. Row count spot check (sample of 10 critical tables)
for table in orders customers invoices; do
  SOURCE=$(psql -h on-prem-db.internal -U pg_migration_user -d production -t -c "SELECT COUNT(*) FROM $table;")
  TARGET=$(psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -t -c "SELECT COUNT(*) FROM $table;")
  if [ "$SOURCE" != "$TARGET" ]; then
    echo "MISMATCH: $table (source: $SOURCE, target: $TARGET)"
  fi
done

# 2. Performance check
curl -s https://app.internal/metrics | jq '.query_latency_p95_ms'

# 3. Error rate check
curl -s https://monitoring.azure.com/api/error-rate | jq '.error_rate'

# 4. Data accuracy spot check
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "SELECT COUNT(*) FROM migration_validation_log WHERE validation_status = 'FAIL' AND validation_timestamp > NOW() - INTERVAL '24 hours';"
```

### Cleanup & Decommissioning
```bash
# After 7 days of stable operation:

# 1. Disable source replication
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "SELECT pg_drop_replication_slot('adf_migration_slot');"

# 2. Disable read-only on target
psql -h postgresql-prod.postgres.database.azure.com -U pg_admin -d production -c \
  "ALTER SYSTEM SET default_transaction_read_only = off; SELECT pg_reload_conf();"

# 3. Archive migration logs
az storage blob upload \
  --account-name stgmigration \
  --container-name migration-logs-archive \
  --name "migration_logs_$(date +%Y%m%d).json" \
  --file migration_metrics.log

# 4. Decommission SHIR (after 30 days)
az functionapp delete --name migration-validation-function --resource-group migration-rg
```

---

## Troubleshooting

### Replication Lag Spike
```bash
# Check SHIR status
systemctl status shir

# Monitor CDC producer lag
psql -h on-prem-db.internal -U pg_migration_user -d production -c \
  "SELECT confirmed_flush_lsn, NOW() - pg_wal_lsn_offset(confirmed_flush_lsn) as lag FROM pg_replication_slots WHERE slot_name = 'adf_migration_slot';"

# Restart SHIR if needed
systemctl restart shir
```

### Data Validation Failures
```bash
# Query failed validations
SELECT * FROM migration_validation_log 
WHERE validation_status = 'FAIL' 
ORDER BY validation_timestamp DESC 
LIMIT 10;

# Investigate specific table
SELECT * FROM migration_validation_log 
WHERE table_name = 'orders' AND validation_status = 'FAIL';

# Re-run validation
curl -X POST https://migration-validation.azurewebsites.net/api/validate \
  -H "Content-Type: application/json" \
  -d '{"table": "orders", "schema": "public"}'
```

### Performance Degradation
```bash
# Analyze slow queries
SELECT query, mean_time, calls FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 20;

# Check index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
WHERE idx_scan = 0 
ORDER BY pg_relation_size(indexrelname::regclass) DESC;

# Rebuild indexes if needed
REINDEX INDEX CONCURRENTLY index_name;
```

---

**Runbook Version**: 2.0 | **Last Updated**: Q1 2024
