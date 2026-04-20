# Architecture Diagrams

## End-to-End Migration Flow

```mermaid
graph TD
    A["On-Premise<br/>PostgreSQL v11"] -->|CDC + Binary Logs| B["Azure Data Factory<br/>Self-Hosted IR"]
    B -->|Full Load| C["Azure PostgreSQL<br/>Staging - Raw"]
    B -->|Incremental Delta| C
    C -->|Transform & Denormalize| D["Azure PostgreSQL<br/>Staging - Validated"]
    D -->|Partition & Queue| E["Azure Functions<br/>Validation Engine<br/>Python"]
    E -->|Validation Results| F["Azure Queue Storage<br/>Audit Log"]
    E -->|Data Quality Metrics| G["Cosmos DB<br/>Validation Metadata"]
    G -->|Aggregate Metrics| H["React Dashboard<br/>KPI & Status"]
    H -->|Stakeholder Review| I{Approval<br/>Gate?}
    I -->|APPROVED| J["Azure PostgreSQL<br/>Production Gold"]
    I -->|REJECTED| K["Rollback &<br/>Investigation"]
    K -->|Fix Issues| C
    J -->|Read Replicas| L["Analytics Layer<br/>Read-Only Reports"]
    
    style A fill:#ffcccc
    style B fill:#cce5ff
    style C fill:#ccffcc
    style D fill:#ccffcc
    style E fill:#ffccff
    style H fill:#ffffcc
    style J fill:#90EE90
```

## Data Validation Workflow

```mermaid
graph LR
    A["Stage 1: Extraction<br/>Source Table"] -->|Read| B["Stage 2: Row Count<br/>Reconciliation"]
    B -->|Pass| C["Stage 3: Column<br/>Validation"]
    B -->|Fail| Z["❌ REJECT<br/>& Alert"]
    C -->|Data Type Match| D["Stage 4: Null<br/>Constraints"]
    C -->|Type Mismatch| Z
    D -->|Constraint Met| E["Stage 5: Business<br/>Rule Validation"]
    D -->|Constraint Failed| Z
    E -->|Rules Pass| F["Stage 6: Uniqueness<br/>Constraints"]
    E -->|Rules Failed| Z
    F -->|No Duplicates| G["✅ PASS<br/>& Transform"]
    F -->|Duplicates Found| Z
    G -->|Approved| H["Stage 7: Load<br/>to Production"]
    H -->|Success| I["Audit & Archive<br/>Validation Report"]
    Z -->|Log Error| J["Error Resolution<br/>Queue"]
    J -->|Manual Review| K["Data Steward<br/>Intervention"]
    
    style B fill:#e1f5ff
    style C fill:#e1f5ff
    style D fill:#e1f5ff
    style E fill:#e1f5ff
    style F fill:#e1f5ff
    style G fill:#90EE90
    style H fill:#90EE90
    style Z fill:#ffcccc
    style K fill:#fff3cd
```

## Component Architecture (Detailed)

```mermaid
graph TB
    subgraph OnPrem["On-Premise (Data Center)"]
        PG11["PostgreSQL 11.18<br/>Primary"]
        CDC["Binary Log<br/>Replication"]
        PG11 --> CDC
    end
    
    subgraph Network["Network & Security"]
        ER["ExpressRoute<br/>Circuit<br/>1Gbps"]
        SHIR["Self-Hosted<br/>Integration Runtime<br/>Windows VM"]
    end
    
    subgraph Azure["Azure Cloud Platform"]
        subgraph ADF["Data Factory Layer"]
            ADFPIPE["ADF Pipelines<br/>Parameterized"]
            ADFMETA["Metadata<br/>Repository"]
        end
        
        subgraph Storage["Data Storage Layer"]
            RAW["PostgreSQL<br/>raw_schema<br/>Burstable Tier"]
            VALIDATED["PostgreSQL<br/>validated_schema"]
            PROD["PostgreSQL<br/>gold_schema<br/>Standard Tier"]
        end
        
        subgraph Validation["Validation & Processing"]
            FUNC["Azure Functions<br/>Python 3.11"]
            QUEUE["Queue Storage<br/>Validation Tasks"]
            COSMOS["Cosmos DB<br/>Metadata Store"]
        end
        
        subgraph Presentation["Presentation Layer"]
            DASH["React Dashboard<br/>SPA"]
            SWAPP["Static Web Apps<br/>Hosting"]
        end
        
        subgraph Governance["Governance & Audit"]
            KEYVAULT["Key Vault<br/>Secrets"]
            MONITOR["Monitor +<br/>Log Analytics"]
            STORAGE["Blob Storage<br/>Audit Logs"]
        end
    end
    
    CDC --> SHIR
    SHIR --> ER --> ADFPIPE
    ADFPIPE --> RAW
    RAW --> VALIDATED
    VALIDATED --> QUEUE
    QUEUE --> FUNC
    FUNC --> COSMOS
    COSMOS --> DASH
    DASH --> SWAPP
    ADFPIPE -.->|Secrets| KEYVAULT
    FUNC -.->|Secrets| KEYVAULT
    VALIDATED -.->|Monitor| MONITOR
    FUNC -.->|Audit| STORAGE
    COSMOS -.->|Audit| MONITOR
    
    style OnPrem fill:#ffeeee
    style Azure fill:#eeeeff
    style Network fill:#f0f0f0
    style Storage fill:#d1f2ff
    style Validation fill:#fff5d1
    style Presentation fill:#d1ffd1
    style Governance fill:#f5d1ff
```

## Security & Compliance Architecture

```mermaid
graph TD
    A["User (Data Steward)"] -->|Azure AD| B["Azure AD<br/>Authentication"]
    B -->|Managed Identity| C["RBAC<br/>Role-Based Access Control"]
    C -->|Reader| D1["Viewers<br/>Dashboard Only"]
    C -->|Approver| D2["Approval Team<br/>Validation Control"]
    C -->|Admin| D3["Infrastructure<br/>Team"]
    
    D1 -->|Read Only| E["React Dashboard<br/>Metrics View"]
    D2 -->|Approve/Reject| F["Validation Queue<br/>Management"]
    D3 -->|Deploy| G["Infrastructure<br/>Provisioning"]
    
    F --> H["Key Vault<br/>Encryption Keys"]
    E -->|Query| I["PostgreSQL<br/>Row-Level Security"]
    G -->|Configure| I
    
    I --> J["Encrypted Connection<br/>TLS 1.2+"]
    J --> K["Azure Monitor<br/>Audit Logs"]
    K --> L["Compliance<br/>Archive<br/>365 Days"]
    
    M["Sensitive Data<br/>PII/PHI"] -->|Mask| N["Anonymized<br/>for Validation"]
    N -->|Test Only| E
    M -->|Production| I
    
    style B fill:#fff5d1
    style C fill:#fff5d1
    style H fill:#ffcccc
    style I fill:#d1ffd1
    style K fill:#f5d1ff
    style L fill:#f5d1ff
```

## Deployment Timeline & Phases

```mermaid
timeline
    title PostgreSQL Migration to Azure - 8 Week Timeline
    
    Week 1-2 : Infrastructure Setup : Provision Resources : Networking Config : Security Implementation
    Week 3-4 : Full Load Migration : Schema Transfer : Validation Baseline : Performance Tuning
    Week 5-6 : Incremental Sync : Enable CDC : Real-time Validation : Lag Monitoring
    Week 7 : Pre-Cutover : Final Sync : Read-only Testing : DR Validation
    Week 8 : Cutover : Production Switchover : Monitoring : Post-Migration Optimization
```

## Validation Result Aggregation

```mermaid
graph LR
    A["Individual Table<br/>Validations"] -->|Row Count| B["Aggregation<br/>Service"]
    A -->|Column Match| B
    A -->|Data Type| B
    A -->|Constraints| B
    B -->|Store| C["Cosmos DB<br/>Time-Series"]
    C -->|Query| D["Dashboard<br/>Real-time Metrics"]
    D -->|Visual| E["Status Cards"]
    D -->|Visual| F["Trend Charts"]
    D -->|Visual| G["Exception List"]
    
    style B fill:#ffcccc
    style C fill:#ffffcc
    style D fill:#ccffcc
    style E fill:#e1f5ff
    style F fill:#e1f5ff
    style G fill:#e1f5ff
```

---

**Legend:**
- 🟥 Red: Error/Rejection state
- 🟩 Green: Success/Approved state
- 🟨 Yellow: Manual intervention required
- 🟦 Blue: Information/Metadata layer
