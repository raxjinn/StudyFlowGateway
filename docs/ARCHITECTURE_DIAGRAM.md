# Architecture Diagrams

This document contains visual architecture diagrams for the DICOM Gateway system.

## Viewing the Diagrams

### Mermaid Diagrams

The diagrams are written in Mermaid syntax and can be viewed in:

1. **GitHub/GitLab**: Automatically rendered in markdown files
2. **VS Code**: Install "Markdown Preview Mermaid Support" extension
3. **Online**: https://mermaid.live/
4. **CLI**: Install mermaid-cli: `npm install -g @mermaid-js/mermaid-cli`

### Rendering Locally

```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Render to PNG
mmdc -i docs/architecture.mermaid -o docs/architecture.png

# Render to SVG
mmdc -i docs/architecture.mermaid -o docs/architecture.svg
```

## System Architecture

```mermaid
graph TB
    subgraph External["External Systems"]
        DICOM_CLIENT["DICOM Clients<br/>(Modalities/PACS)"]
        WEB_USER["Web Users<br/>(Browser)"]
    end

    subgraph Gateway["DICOM Gateway System"]
        subgraph Network["Network Layer"]
            NGINX["Nginx<br/>(HTTPS :443)"]
            SCP["C-STORE SCP<br/>(Receiver :104)"]
        end

        subgraph API["API Layer"]
            FASTAPI["FastAPI<br/>(REST API :8000)"]
            VUE["Vue.js<br/>(Web UI)"]
        end

        subgraph Workers["Worker Services"]
            QUEUE_WORKER["Queue Worker<br/>(Process Jobs)"]
            FORWARD_WORKER["Forwarding Worker<br/>(Forward Studies)"]
            DB_WORKER["DB Pool Worker<br/>(Batch Writes)"]
            SCU["C-STORE SCU<br/>(Forwarder)"]
        end

        subgraph Storage["Storage"]
            DB[(PostgreSQL<br/>Database)]
            FILESYSTEM["Filesystem<br/>/var/lib/dicom-gw/"]
        end
    end

    subgraph Destinations["Remote Destinations"]
        PACS["Remote PACS<br/>(C-STORE SCP)"]
        ARCHIVE["DICOM Archive<br/>(C-STORE SCP)"]
    end

    DICOM_CLIENT -->|C-STORE| SCP
    WEB_USER -->|HTTPS| NGINX
    NGINX -->|HTTP| FASTAPI
    NGINX -->|Static Files| VUE
    VUE -->|API Calls| FASTAPI
    SCP -->|Store File| FILESYSTEM
    SCP -->|Queue Job| DB
    FASTAPI -->|Read/Write| DB
    DB -->|LISTEN/NOTIFY| QUEUE_WORKER
    QUEUE_WORKER -->|Read File| FILESYSTEM
    QUEUE_WORKER -->|Create Jobs| DB
    DB -->|Poll Jobs| FORWARD_WORKER
    FORWARD_WORKER -->|Read File| FILESYSTEM
    FORWARD_WORKER -->|Forward| SCU
    SCU -->|C-STORE| PACS
    SCU -->|C-STORE| ARCHIVE
    FORWARD_WORKER -->|Update Status| DB
    DB -->|Batch Events| DB_WORKER
    DB_WORKER -->|Batch Inserts| DB
```

## Data Flow

```mermaid
sequenceDiagram
    participant Client as DICOM Client
    participant SCP as C-STORE SCP
    participant FS as Filesystem
    participant DB as PostgreSQL
    participant QW as Queue Worker
    participant FW as Forwarding Worker
    participant SCU as C-STORE SCU
    participant PACS as Remote PACS

    Note over Client,PACS: Receiving Flow
    Client->>SCP: C-STORE Request
    SCP->>FS: Write File (Byte-Preserving)
    SCP->>DB: Create Job (pending)
    DB-->>SCP: Job Created
    SCP-->>Client: Success Response

    Note over DB,PACS: Processing Flow
    DB->>QW: LISTEN/NOTIFY (New Job)
    QW->>FS: Read DICOM File
    QW->>QW: Parse Metadata
    QW->>DB: Create Study/Series/Instance
    QW->>DB: Create Forward Jobs

    Note over DB,PACS: Forwarding Flow
    DB->>FW: Poll for Pending Jobs
    FW->>FS: Read DICOM File
    FW->>SCU: Forward File
    SCU->>PACS: C-STORE Request
    PACS-->>SCU: Success Response
    FW->>DB: Update Job Status (completed)
```

## Component Interaction

```mermaid
graph LR
    subgraph Input["Input"]
        DICOM[DICOM Files]
        WEB[Web Requests]
    end

    subgraph Processing["Processing"]
        SCP[SCP Receiver]
        API[REST API]
        QUEUE[Queue]
    end

    subgraph Workers["Workers"]
        QW[Queue Worker]
        FW[Forward Worker]
        DW[DB Worker]
    end

    subgraph Storage["Storage"]
        DB[(Database)]
        FS[Filesystem]
    end

    subgraph Output["Output"]
        PACS[Remote PACS]
        METRICS[Metrics]
    end

    DICOM --> SCP
    WEB --> API
    SCP --> QUEUE
    SCP --> FS
    API --> DB
    QUEUE --> QW
    QW --> FW
    QW --> DB
    FW --> PACS
    FW --> DB
    DB --> DW
    FS --> FW
    DB --> METRICS
```

## Deployment Scenarios

### Single Server Deployment

```mermaid
graph TB
    subgraph Server["Single Server"]
        NGINX[Nginx]
        API[FastAPI]
        SCP[C-STORE SCP]
        W1[Queue Worker]
        W2[Forward Worker]
        W3[DB Worker]
        DB[(PostgreSQL)]
        FS[Filesystem]
    end

    CLIENT[DICOM Clients] --> SCP
    USER[Web Users] --> NGINX
    NGINX --> API
    SCP --> FS
    SCP --> DB
    API --> DB
    DB --> W1
    DB --> W2
    DB --> W3
    W1 --> DB
    W2 --> FS
    W2 --> PACS[Remote PACS]
    W3 --> DB
```

### Distributed Deployment

```mermaid
graph TB
    subgraph LB["Load Balancer"]
        NGINX[Nginx]
    end

    subgraph API_CLUSTER["API Cluster"]
        API1[FastAPI 1]
        API2[FastAPI 2]
    end

    subgraph WORKER_CLUSTER["Worker Cluster"]
        QW1[Queue Worker 1]
        QW2[Queue Worker 2]
        FW1[Forward Worker 1]
        FW2[Forward Worker 2]
        FW3[Forward Worker 3]
        FW4[Forward Worker 4]
    end

    subgraph STORAGE["Storage"]
        DB[(PostgreSQL<br/>Cluster)]
        NFS[Shared Storage<br/>NFS/Gluster]
    end

    CLIENT[DICOM Clients] --> SCP[C-STORE SCP]
    USER[Web Users] --> NGINX
    NGINX --> API1
    NGINX --> API2
    API1 --> DB
    API2 --> DB
    SCP --> NFS
    SCP --> DB
    DB --> QW1
    DB --> QW2
    DB --> FW1
    DB --> FW2
    DB --> FW3
    DB --> FW4
    QW1 --> DB
    QW2 --> DB
    FW1 --> NFS
    FW2 --> NFS
    FW3 --> NFS
    FW4 --> NFS
    FW1 --> PACS[Remote PACS]
    FW2 --> PACS
    FW3 --> PACS
    FW4 --> PACS
```

## Full Diagram Files

See the following files for complete diagram definitions:

- **System Architecture**: `docs/architecture.mermaid`
- **Data Flow**: `docs/data-flow.mermaid`

These can be rendered using Mermaid tools or viewed in any Mermaid-compatible viewer.

