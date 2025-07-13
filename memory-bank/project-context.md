# Project Context - Universal RAG System

## Technical Stack
- **Language**: Python 3.8+, JavaScript (Node.js), TypeScript
- **Framework**: FastAPI (HTTP API), MCP Protocol, ChromaDB
- **Database**: SQLite (sessions), ChromaDB (vector embeddings), File-based (snapshots)
- **Tools**: Claude Code CLI, RAG Server, Session Manager, AST Parser

## Architecture Principles
- **Dual-mode integration**: HTTP API + MCP stdio for maximum compatibility
- **Memory-aware design**: Professional session management like Cursor/Cline
- **Code-aware search**: AST parsing for structured code understanding
- **Framework-agnostic**: Support for Laravel, Vue, Filament, Alpine, Inertia, TailwindCSS

## Development Guidelines
- **Memory Bank first**: All important decisions and moments must be captured
- **FileSnapshot everything**: Version all code changes with deduplication
- **AST over text**: Use structured parsing for code analysis when possible
- **MCP integration**: All features must be accessible through Claude Code CLI

## Key Dependencies
- **Core**: FastAPI, ChromaDB, sentence-transformers, SQLite3
- **MCP**: @modelcontextprotocol/sdk, axios
- **AST**: Python ast module, JavaScript regex patterns
- **Vector Search**: sentence-transformers/all-MiniLM-L6-v2

## Environment Setup
```bash
# Start complete RAG system
./start-rag-system.sh

# Check system status
./check-rag-system.sh

# Test MCP integration
./test-mcp-availability.sh
```

## Important Notes
- **6,405 documents** indexed across 6 frameworks
- **AST parsing** working for Python, partial for JavaScript
- **20+ key moments** tracked in development history
- **Enterprise-ready** with professional memory management

---
*Последнее обновление: 2025-01-14 автоматически*
