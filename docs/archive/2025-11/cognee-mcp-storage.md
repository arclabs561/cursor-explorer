# Cognee Storage Locations

## Current Storage Paths

Based on the current configuration, Cognee stores data in the following locations:

### System Root (Databases & System Files)
**Location:** `/Users/arc/Documents/dev/devdev/cognee/cognee-mcp/.venv/lib/python3.13/site-packages/cognee/.cognee_system`

**Contains:**
- **Databases directory:** `{system_root}/databases/`
  - Graph database (Kuzu): `cognee_graph_kuzu` (and `.wal` file)
  - Vector database (LanceDB): `cognee.lancedb`
  - Relational database (SQLite): `cognee_db`

### Data Root (User Data Storage)
**Location:** `/Users/arc/Documents/dev/devdev/cognee/cognee-mcp/.venv/lib/python3.13/site-packages/cognee/.data_storage`

**Contains:**
- Raw data files
- Processed documents
- User-uploaded content

### Cache Root (Temporary Cache)
**Location:** `/Users/arc/Documents/dev/devdev/cognee/cognee-mcp/.venv/lib/python3.13/site-packages/cognee/.cognee_cache`

**Contains:**
- Temporary cache files
- Processed embeddings cache

### Logs
**Location:** `{cognee_package}/logs/` (default) or `COGNEE_LOGS_DIR` env var

## Problem: Data Stored in venv

**Issue:** All data is currently stored inside the Python virtual environment, which means:
- Data is lost when venv is deleted/recreated
- Data is not easily accessible or portable
- Data is mixed with package files

## Solution: Configure Custom Storage Paths

You can configure Cognee to store data in a better location using environment variables or programmatic configuration:

### Option 1: Environment Variables

Add to your `.env` file:

```bash
# Set custom storage paths (absolute paths required)
SYSTEM_ROOT_DIRECTORY=/Users/arc/Documents/dev/devdev/cognee-data/.cognee_system
DATA_ROOT_DIRECTORY=/Users/arc/Documents/dev/devdev/cognee-data/.data_storage
CACHE_ROOT_DIRECTORY=/Users/arc/Documents/dev/devdev/cognee-data/.cognee_cache
COGNEE_LOGS_DIR=/Users/arc/Documents/dev/devdev/cognee-data/logs
```

### Option 2: Programmatic Configuration

In your MCP server initialization or startup script:

```python
import cognee

# Configure storage paths before using Cognee
cognee.config.system_root_directory("/Users/arc/Documents/dev/devdev/cognee-data/.cognee_system")
cognee.config.data_root_directory("/Users/arc/Documents/dev/devdev/cognee-data/.data_storage")
```

## Database Files

The knowledge graph and memories are stored in:

1. **Graph Database (Kuzu):** `{system_root}/databases/cognee_graph_kuzu`
   - Stores entity relationships and knowledge graph structure
   - Contains your "memories" as connected entities

2. **Vector Database (LanceDB):** `{system_root}/databases/cognee.lancedb`
   - Stores embeddings for semantic search
   - Contains vector representations of your data

3. **Relational Database (SQLite):** `{system_root}/databases/cognee_db`
   - Stores metadata, datasets, users
   - Contains structured metadata about your data

## Migration

To move existing data to a new location:

1. Stop any running Cognee processes
2. Copy the `.cognee_system` directory to the new location
3. Update environment variables or configuration
4. Restart Cognee

## Recommended Setup

For a production-like setup, store data outside the venv:

```
/Users/arc/Documents/dev/devdev/
├── cognee-data/              # All Cognee data (gitignored)
│   ├── .cognee_system/       # System files & databases
│   ├── .data_storage/       # User data
│   ├── .cognee_cache/       # Cache
│   └── logs/                 # Logs
└── cognee/                   # Source code
    └── cognee-mcp/           # MCP server
```






