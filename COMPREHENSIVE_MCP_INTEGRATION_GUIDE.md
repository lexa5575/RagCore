# Comprehensive MCP Integration Guide - Memory Bank & FileSnapshot System

## 🎯 Overview
This project has been enhanced with a professional Memory Bank system inspired by Cursor/Cline and a comprehensive FileSnapshot system for file versioning. The system provides 15+ MCP functions through a RAG server integration.

## 🏦 Memory Bank System

### Architecture
The Memory Bank creates a structured project context system with 5 markdown files:

```
memory-bank/
├── project-context.md    # Technical stack, architecture principles
├── active-context.md     # Current session state, ongoing tasks
├── progress.md          # Milestones, completed work, blockers
├── decisions.md         # Architecture decisions with ADR format
└── code-patterns.md     # Established patterns, naming conventions
```

### MCP Functions
- `mcp__rag-server__init_memory_bank` - Initialize Memory Bank structure
- `mcp__rag-server__get_memory_context` - Get context (project/active/progress/decisions/patterns)
- `mcp__rag-server__update_active_context` - Update session state and tasks
- `mcp__rag-server__log_decision` - Log architectural decisions with ADR format
- `mcp__rag-server__search_memory_bank` - Search across Memory Bank files

### Usage Example
```javascript
// Initialize Memory Bank for project
await mcp_call("init_memory_bank", {});

// Update active context
await mcp_call("update_active_context", {
    session_state: "Working on user authentication system",
    tasks: ["Implement login", "Add password reset", "Setup 2FA"],
    decisions: ["Using JWT tokens", "PostgreSQL for user data"]
});

// Log important decision
await mcp_call("log_decision", {
    title: "Database Choice for Authentication",
    context: "Need reliable storage for user credentials",
    decision: "PostgreSQL with bcrypt for password hashing",
    consequences: "Better security, ACID compliance, easier scaling"
});
```

## 📁 FileSnapshot System

### Features
- **Automatic file versioning** when using `open_file`
- **Content deduplication** using SHA-256 hashing
- **Language auto-detection** for 15+ programming languages
- **Full-text search** across file contents
- **Version history** tracking for each file

### Database Schema
```sql
CREATE TABLE file_snapshots (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    encoding TEXT DEFAULT 'utf-8',
    session_id TEXT NOT NULL
);

CREATE TABLE code_snippets (
    id TEXT PRIMARY KEY,
    file_snapshot_id TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    context_before TEXT DEFAULT '',
    context_after TEXT DEFAULT '',
    timestamp REAL NOT NULL
);
```

### MCP Functions
- `mcp__rag-server__open_file` - Read file + auto-save snapshot
- `mcp__rag-server__search_files` - Search file contents by query/language
- `mcp__rag-server__get_file_history` - Get version history for specific file

### Usage Example
```javascript
// Open file (automatically saves snapshot)
await mcp_call("open_file", { path: "src/auth.py" });

// Search for functions in Python files
await mcp_call("search_files", {
    query: "def authenticate",
    language: "python",
    limit: 10
});

// Get version history
await mcp_call("get_file_history", { file_path: "src/auth.py" });
```

## 🔧 Enhanced Session Management

### Key Moments System
Automatically detects and categorizes important events:

- **error_solved** - Bug fixes and error resolutions
- **feature_completed** - Completed features and implementations
- **config_changed** - Configuration and settings updates
- **breakthrough** - Major discoveries or solutions
- **file_created** - New file creation
- **deployment** - Deployment activities
- **important_decision** - Architecture or design decisions
- **refactoring** - Code refactoring activities

### Extended KeyMoment Schema
```python
@dataclass
class KeyMoment:
    id: str
    timestamp: float
    type: KeyMomentType
    title: str
    summary: str
    importance: int  # 1-10
    files_involved: List[str]
    context: str
    related_messages: List[str]
    # Enhanced fields
    file_snapshots: List[str]     # Linked file snapshot IDs
    code_snippets: List[str]      # Linked code snippet IDs
    project_context: Dict[str, Any]  # Project state at moment
```

## 🚀 Full MCP Function Reference

### Core RAG Functions
- `mcp__rag-server__ask_rag` - Query RAG system with framework detection
- `mcp__rag-server__list_frameworks` - List available frameworks
- `mcp__rag-server__get_stats` - System statistics and document counts

### Session Management
- `mcp__rag-server__save_key_moment` - Save important moments manually
- `mcp__rag-server__get_recent_changes` - Get recent key moments from session

### FileSnapshot Functions
- `mcp__rag-server__open_file` - Read file with auto-snapshot
- `mcp__rag-server__search_files` - Search file contents
- `mcp__rag-server__get_file_history` - File version history

### Memory Bank Functions
- `mcp__rag-server__init_memory_bank` - Initialize Memory Bank structure
- `mcp__rag-server__get_memory_context` - Retrieve context by type
- `mcp__rag-server__update_active_context` - Update active session state
- `mcp__rag-server__log_decision` - Log architectural decisions
- `mcp__rag-server__search_memory_bank` - Search Memory Bank content

## 🔄 Auto-Detection Features

### File Language Detection
Supports 20+ languages including:
- Python (.py) → python
- JavaScript (.js, .jsx) → javascript  
- TypeScript (.ts, .tsx) → typescript
- Vue (.vue) → vue
- PHP (.php) → php
- And many more...

### Key Moment Auto-Detection
Analyzes tool calls and content for automatic key moment creation:
- Error keywords → error_solved
- Completion keywords → feature_completed
- Config file changes → config_changed
- Creation actions → file_created
- Decision keywords → important_decision

## 🎯 Best Practices for New Claude Sessions

### 1. System Overview
```javascript
// Get system stats first
await mcp_call("get_stats");
await mcp_call("list_frameworks");
```

### 2. Initialize Memory Bank
```javascript
// Setup Memory Bank structure
await mcp_call("init_memory_bank");
await mcp_call("get_memory_context", { context_type: "active" });
```

### 3. Review Recent Work
```javascript
// Check recent activity
await mcp_call("get_recent_changes");
```

### 4. Search Capabilities
```javascript
// Search through project files
await mcp_call("search_files", { query: "authentication" });
await mcp_call("search_memory_bank", { query: "database" });
```

## 🏗️ Technical Implementation

### HTTP Endpoints
All MCP functions map to HTTP endpoints at `http://localhost:8000`:
- `/ask` - RAG queries
- `/sessions/*` - Session management
- `/file-snapshots/*` - FileSnapshot operations
- `/memory-bank/*` - Memory Bank operations

### Error Handling
- Comprehensive logging in session_manager.py
- 500 error fixes for KeyMoment creation
- Graceful fallbacks for missing data
- Auto-retry mechanisms for network issues

### Performance Optimizations
- File content deduplication using SHA-256
- Efficient database indexing
- Automatic session cleanup
- Smart caching mechanisms

## 🔮 Future Enhancements

### Planned Features
- AI-powered code pattern detection
- Automatic test case generation from FileSnapshots
- Enhanced Memory Bank search with vector embeddings
- Integration with IDE extensions
- Team collaboration features

### Extensibility
The system is designed for easy extension:
- Modular MCP function architecture
- Pluggable storage backends
- Configurable auto-detection rules
- Customizable Memory Bank templates

## 📊 System Metrics
- **6,405 total documents** in RAG system
- **15+ MCP functions** available
- **5 Memory Bank files** per project
- **Automatic file versioning** for all opened files
- **Multi-language support** (20+ programming languages)

This system transforms the RAG integration into a professional AI coding assistant comparable to Cursor/Cline, with comprehensive project memory and intelligent file management.