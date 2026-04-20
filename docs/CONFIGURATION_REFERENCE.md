# PostgreSQL Migration - Configuration Reference

## Environment Variables & Configuration

### Source Database Configuration
```bash
# SOURCE DATABASE (PostgreSQL v11 On-Premises)
SOURCE_DB_HOST=on-prem-db.internal
SOURCE_DB_PORT=5432
SOURCE_DB_NAME=production
SOURCE_DB_USER=pg_migration_user
SOURCE_DB_PASSWORD=<stored-in-keyvault>

# Connection string format:
# postgresql://pg_migration_user@on-prem-db.internal:5432/production
```

### Target Database Configuration
```bash
# TARGET DATABASE (Azure PostgreSQL v14 Managed)
TARGET_DB_HOST=postgresql-prod.postgres.database.azure.com
TARGET_DB_PORT=5432
TARGET_DB_NAME=production
TARGET_DB_USER=pg_admin@postgresql-prod
TARGET_DB_PASSWORD=<stored-in-keyvault>

# Connection string format:
# postgresql://pg_admin@postgresql-prod@postgresql-prod.postgres.database.azure.com:5432/production?sslmode=require
```

### Azure Services Configuration
```bash
# AZURE DATA FACTORY
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=migration-rg
ADF_FACTORY_NAME=migration-adf
ADF_LINKED_SERVICE_SOURCE=SourcePostgreSqlDB
ADF_LINKED_SERVICE_TARGET=TargetPostgreSqlDB

# AZURE FUNCTIONS
FUNCTION_APP_NAME=migration-validation-function
FUNCTION_RUNTIME=python
FUNCTION_RUNTIME_VERSION=3.11
FUNCTION_TIMEOUT_SECONDS=600

# COSMOS DB
COSMOS_ENDPOINT=https://cosmosdb-prod.documents.azure.com:443/
COSMOS_DB=migration_metadata
COSMOS_CONTAINER=validations
COSMOS_PARTITION_KEY=/table_name

# AZURE STORAGE (Staging & Logs)
AZURE_STORAGE_ACCOUNT=stgmigration
AZURE_STORAGE_CONTAINER_STAGING=adf-staging
AZURE_STORAGE_CONTAINER_LOGS=migration-logs
AZURE_STORAGE_CONNECTION_STRING=<stored-in-keyvault>

# KEY VAULT
KEY_VAULT_NAME=kv-migration-prod
KEY_VAULT_URL=https://kv-migration-prod.vault.azure.com/

# QUEUE STORAGE (Validation Jobs)
QUEUE_CONNECTION_STRING=<stored-in-keyvault>
VALIDATION_QUEUE_NAME=validation-tasks
```

### Migration Execution Configuration
```bash
# MIGRATION PHASES
VALIDATION_PHASE=INCREMENTAL_SYNC  # FULL_LOAD, INCREMENTAL_SYNC, PRE_CUTOVER, POST_CUTOVER
MAX_PARALLEL_COPIES=4
BATCH_SIZE=10000
STAGING_ENABLED=true
ENABLE_COMPRESSION=true

# VALIDATION SETTINGS
VALIDATION_TIMEOUT_MINUTES=5
ROW_COUNT_TOLERANCE=0  # Zero tolerance for mismatches
DATA_ACCURACY_TARGET=99.98
REPLICATION_LAG_THRESHOLD_SECONDS=30

# PERFORMANCE TUNING
CONNECTION_POOL_SIZE=100
QUERY_TIMEOUT_SECONDS=600
MAX_WORKER_THREADS=8
SHARED_BUFFERS_PERCENT=25
EFFECTIVE_CACHE_SIZE_PERCENT=75
RANDOM_PAGE_COST=1.1  # SSD storage

# CDC SETTINGS
CDC_SLOT_NAME=adf_migration_slot
CDC_REPLICATION_MODE=logical
CDC_MAX_WAL_SENDERS=10
CDC_WAL_LEVEL=logical
CDC_SYNC_INTERVAL_SECONDS=300
```

### Monitoring & Alerting
```bash
# AZURE MONITOR
APP_INSIGHTS_INSTRUMENTATION_KEY=<key>
LOG_ANALYTICS_WORKSPACE_ID=<workspace-id>
LOG_ANALYTICS_WORKSPACE_KEY=<key>

# ALERTING THRESHOLDS
ALERT_ERROR_RATE_THRESHOLD=0.1  # 0.1% error rate
ALERT_CPU_THRESHOLD=80
ALERT_MEMORY_THRESHOLD=85
ALERT_DISK_THRESHOLD=90
ALERT_REPLICATION_LAG_THRESHOLD=60  # seconds

# NOTIFICATIONS
ALERT_EMAIL=team@company.com
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/...
PAGERDUTY_INTEGRATION_KEY=<key>
```

### Security & Access Control
```bash
# AUTHENTICATION
AZURE_CLIENT_ID=<client-id>
AZURE_CLIENT_SECRET=<stored-in-keyvault>
AZURE_TENANT_ID=<tenant-id>

# RBAC ROLES
READER_ROLE=Dashboard Viewer
APPROVER_ROLE=Migration Approver
ADMIN_ROLE=Migration Administrator

# DATA CLASSIFICATION
CLASSIFY_DATA_ON_LOAD=true
ANONYMIZE_PII_IN_STAGING=true
ENCRYPT_AT_REST=true
ENCRYPT_IN_TRANSIT=true
MIN_TLS_VERSION=1.2

# AUDIT & COMPLIANCE
AUDIT_LOG_RETENTION_DAYS=2555  # 7 years
ENABLE_FIELD_LEVEL_ENCRYPTION=true
ENABLE_ROW_LEVEL_SECURITY=true
GDPR_COMPLIANCE_MODE=true
```

### Deployment & Network
```bash
# NETWORKING
VNET_NAME=migration-vnet
VNET_ADDRESS_SPACE=10.0.0.0/16
SUBNET_AZURE_SERVICES=10.0.1.0/24
SUBNET_SHIR=10.0.2.0/24
NSG_ENABLE_FLOWLOGS=true

# EXPRESSROUTE
EXPRESSROUTE_CIRCUIT_NAME=migration-circuit
EXPRESSROUTE_BANDWIDTH_MBPS=1000
EXPRESSROUTE_BGP_ASN=65515

# VPN FALLBACK
VPN_GATEWAY_NAME=migration-vpn-gateway
VPN_CONNECTION_NAME=on-prem-to-azure
VPN_PSK=<stored-in-keyvault>

# SELF-HOSTED IR
SHIR_VM_NAME=shir-vm-prod
SHIR_VM_SIZE=Standard_D4s_v3
SHIR_ENABLE_AUTO_UPDATE=true
SHIR_CONCURRENT_JOBS=4
SHIR_LOG_LEVEL=INFO
```

---

## Sample Configuration Files

### Azure Functions - local.settings.json
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;...",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "FUNCTIONS_EXTENSION_VERSION": "~4",
    "SOURCE_DB_HOST": "on-prem-db.internal",
    "SOURCE_DB_PORT": "5432",
    "SOURCE_DB_NAME": "production",
    "SOURCE_DB_USER": "pg_migration_user",
    "TARGET_DB_HOST": "postgresql-prod.postgres.database.azure.com",
    "TARGET_DB_PORT": "5432",
    "TARGET_DB_NAME": "production",
    "TARGET_DB_USER": "pg_admin@postgresql-prod",
    "COSMOS_ENDPOINT": "https://cosmosdb-prod.documents.azure.com:443/",
    "COSMOS_DB": "migration_metadata",
    "COSMOS_CONTAINER": "validations",
    "KEY_VAULT_URL": "https://kv-migration-prod.vault.azure.com/"
  }
}
```

### ADF - Parameters Configuration
```json
{
  "sourceDatabase": {
    "type": "string",
    "defaultValue": "production"
  },
  "targetDatabase": {
    "type": "string",
    "defaultValue": "production"
  },
  "stagingContainer": {
    "type": "string",
    "defaultValue": "adf-staging"
  },
  "parallelCopies": {
    "type": "int",
    "defaultValue": 4
  },
  "batchSize": {
    "type": "int",
    "defaultValue": 10000
  },
  "validationPhase": {
    "type": "string",
    "defaultValue": "FULL_LOAD"
  }
}
```

### Monitoring - Alert Rules
```json
{
  "alerts": [
    {
      "name": "HighErrorRate",
      "condition": "metric 'Request Failed Percentage' > 1.0",
      "evaluationFrequency": "PT1M",
      "windowSize": "PT5M",
      "severity": 2,
      "actions": ["send_email", "send_slack"]
    },
    {
      "name": "ReplicationLagHigh",
      "condition": "metric 'Replication Lag Seconds' > 60",
      "evaluationFrequency": "PT1M",
      "windowSize": "PT5M",
      "severity": 1,
      "actions": ["send_email", "page_oncall"]
    },
    {
      "name": "ValidationFailureRate",
      "condition": "metric 'Validation Pass Rate' < 99.5",
      "evaluationFrequency": "PT5M",
      "windowSize": "PT15M",
      "severity": 2,
      "actions": ["send_email", "send_slack", "create_incident"]
    }
  ]
}
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All Azure resources created
- [ ] SHIR installed and registered with ADF
- [ ] Network connectivity verified (latency < 100ms)
- [ ] VPN & ExpressRoute active
- [ ] Key Vault secrets created
- [ ] RBAC roles assigned
- [ ] Monitoring configured
- [ ] Alert rules deployed

### Deployment
- [ ] Configuration files committed to Git
- [ ] Secrets stored in Key Vault (NOT in code)
- [ ] ADF pipelines published
- [ ] Azure Functions deployed
- [ ] Cosmos DB containers created
- [ ] Storage accounts configured
- [ ] Monitor active and alerting

### Post-Deployment
- [ ] Test connectivity to source & target
- [ ] Verify credentials in Key Vault
- [ ] Test ADF pipeline on sample data
- [ ] Verify Azure Function execution
- [ ] Test monitoring alerts
- [ ] Document any deviations from standard config
- [ ] Get sign-off from infrastructure team

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Q1 2024 | Initial configuration reference |

---

**Configuration Reference**: Version 1.0 | **Last Updated**: Q1 2024
