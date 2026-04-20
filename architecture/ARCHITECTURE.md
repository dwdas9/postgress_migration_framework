# PostgreSQL Migration to Azure - Architecture Overview

## Executive Summary

This document outlines the enterprise-grade architecture for migrating PostgreSQL v11 (on-premise) to Azure PostgreSQL v14 with comprehensive data validation and governance controls. The solution leverages Azure Data Factory for orchestration, Azure Functions for validation logic, and maintains data integrity across staging and production layers.

## Architecture Principles

1. **Zero-Trust Data Validation**: All data transformations are validated before proceeding
2. **Phased Migration**: Non-disruptive, incremental migration with rollback capability
3. **Separation of Concerns**: Clear boundaries between migration, validation, and governance layers
4. **Auditability**: All operations logged for compliance and forensics
5. **Scalability**: Supports migration of databases from 100GB to 100TB+

## Target State Architecture

### Component Layers

#### 1. Source Layer (On-Premise)
- **PostgreSQL v11** cluster running on-premises
- Binary logs enabled for change data capture (CDC)
- Network connectivity: ExpressRoute / VPN to Azure
- Dedicated database accounts for migration and replication

#### 2. Ingestion Layer (Azure Data Factory)
- **Azure Data Factory (ADF)** orchestration pipelines
- Self-Hosted Integration Runtime for secure on-prem connectivity
- Parameterized linked services for source/target flexibility
- Error handling and retry logic (exponential backoff)

#### 3. Staging Layer (Azure PostgreSQL)
- **Azure Database for PostgreSQL** v14 (Burstable tier during testing)
- Separate schemas for raw, validated, and transformed data
- CDC staging tables for incremental syncs
- Point-in-time restore (35-day retention)

#### 4. Validation Layer (Azure Functions)
- **Python-based validation engine** (Azure Functions serverless)
- Row count reconciliation
- Column-level data type and constraint validation
- Business rule validation
- Asynchronous job processing with Azure Queue Storage

#### 5. Presentation Layer (React Dashboard)
- **React SPA** hosted on Azure Static Web Apps
- Real-time validation metrics and progress tracking
- Validation result visualization
- Stakeholder approval workflow integration

#### 6. Production Layer (Gold)
- **Azure Database for PostgreSQL** v14 (Standard tier)
- High availability configuration (read replicas)
- Connection pooling with PgBouncer
- Backup and disaster recovery (geo-redundant)

## Data Flow

```
On-Prem PostgreSQL v11
    ↓ (CDC + Full Load)
    ↓ ExpressRoute/VPN
    ↓
Azure Data Factory Pipeline
    ↓ (Orchestration & Parameterized Loads)
    ↓
Azure PostgreSQL Staging (raw_schema)
    ↓ (Transformation)
    ↓
Azure PostgreSQL Staging (validated_schema)
    ↓ (Validation Functions)
    ↓
Azure Functions (Python Validation Engine)
    ↓ (Results Queue)
    ↓
Cosmos DB / Event Hub (Audit Log)
    ↓ (Approval)
    ↓
Azure PostgreSQL Production (Gold Layer)
    ↓
React Dashboard (KPIs & Stakeholder View)
```

## Technical Specifications

### Database Migration Strategy

**Phase 1: Infrastructure Setup** (Week 1-2)
- Provision Azure resources (PostgreSQL, Functions, ADF)
- Configure networking and security
- Deploy monitoring and logging

**Phase 2: Full Load** (Week 3-4)
- Initial snapshot of all tables
- Schema compatibility validation
- Identify and resolve migration blockers

**Phase 3: Incremental Sync** (Week 5-6)
- Enable CDC on source
- Deploy ADF pipelines for delta loads
- Real-time validation during incremental sync

**Phase 4: Cutover & Validation** (Week 7-8)
- Final incremental sync
- Read-only validation run
- Application switchover
- Rollback procedure if issues detected

### Version Compatibility

| Component | Source | Target |
|-----------|--------|--------|
| PostgreSQL | 11.18 | 14.7 |
| Operating System | CentOS 7 | Linux (Azure Managed) |
| Encoding | UTF-8 | UTF-8 |
| Timezone | UTC | UTC |

### Security Architecture

- **Network**: Private Link for Azure PostgreSQL (no public endpoint)
- **Authentication**: Azure AD integrated with managed identities
- **Encryption**: TLS 1.2+ for transit, encrypted at rest
- **Audit**: Azure Monitor + Log Analytics for all operations
- **Secrets**: Azure Key Vault for connection strings and credentials

## Performance Considerations

### Source Database Optimization
- Disable triggers during bulk load
- Increase `maintenance_work_mem` for reindex operations
- Monitor slow query logs during extraction

### Target Database Tuning
- Connection pooling: 100-200 connections per application server
- Shared buffers: 25% of available memory
- Work memory: 4MB per sort operation
- Parallelization: 4 workers for large scan operations

### Validation Parallelization
- Partition large tables by 1M-5M row chunks
- Parallel validation functions (Azure Functions scale-out)
- Batch validation result aggregation

## Disaster Recovery

- **RPO (Recovery Point Objective)**: 15 minutes (incremental sync frequency)
- **RTO (Recovery Time Objective)**: 2 hours (full failback to source)
- **Backup Strategy**: Automated daily backups, 35-day retention
- **Rollback Plan**: Source database remains active during cutover window

## Cost Optimization

- **Compute**: Use Azure Burstable tier (B2s) during migration phases, scale down post-cutover
- **Storage**: Azure Storage Lifecycle policies for archived validation logs
- **Data Transfer**: Leverage Azure Data Factory's native connectors (reduced egress costs)
- **Monitoring**: Aggregate logs to Archive storage after 30 days

## Monitoring & Alerting

| Metric | Threshold | Action |
|--------|-----------|--------|
| Source DB CPU | > 80% | Throttle extraction |
| Target DB Connection Pool | > 90% | Page on-call |
| Validation Error Rate | > 5% | Pause cutover, investigate |
| Replication Lag | > 30 seconds | Alert team |
| Data Discrepancy Count | > 0 | Manual review required |

## Governance & Compliance

- **Change Control**: All ADF pipelines require code review + approval
- **Data Lineage**: Cosmos DB tracks transformation metadata
- **Audit Trail**: Immutable log in Azure Storage (365-day retention)
- **Compliance**: GDPR-compliant anonymization for sensitive data during validation

---

**Next Steps**:
1. Review [MIGRATION_STRATEGY.md](../migration/MIGRATION_STRATEGY.md) for phased approach details
2. Review [VALIDATION_FRAMEWORK.md](../data-validation/VALIDATION_FRAMEWORK.md) for validation rules
3. Review [GOVERNANCE.md](../governance/GOVERNANCE.md) for roles and responsibilities
