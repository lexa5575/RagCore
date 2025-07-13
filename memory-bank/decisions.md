# Decision Log

## Architecture Decisions
### [ADR-20250713-1903] Выбор архитектуры Memory Bank
**Date**: 2025-07-13 19:03:04
**Status**: Accepted
**Context**: Необходимо было создать систему отслеживания контекста проекта, аналогичную Cursor/Cline
**Decision**: Реализована Memory Bank система с 5 markdown файлами: project-context, active-context, progress, decisions, code-patterns
**Consequences**: Обеспечивает структурированное хранение контекста, упрощает навигацию по проекту и поддерживает непрерывность работы между сессиями

### [ADR-20250713-1843] Интеграция Memory Bank по примеру Cursor/Cline
**Date**: 2025-07-13 18:43:47
**Status**: Accepted
**Context**: Для улучшения системы памяти AI ассистента требовалось создать структуру файлов для хранения контекста проекта
**Decision**: Реализована полная Memory Bank система с 5 markdown файлами и HTTP endpoints
**Consequences**: Теперь AI может отслеживать контекст проекта, решения, прогресс и паттерны кода как профессиональные AI coding assistants


### [ADR-20250714-0120] AST-based Code Search Implementation
**Date**: 2025-01-14 01:20:00
**Status**: Accepted
**Context**: Нужно было реализовать умный поиск по коду, как в Cursor/Cline
**Decision**: Использован Python ast модуль для парсинга классов, функций, переменных с сохранением в отдельной таблице code_symbols
**Consequences**: Поиск по коду стал структурным, можно искать по типу символа, сигнатуре, документации

### [ADR-20250714-0100] Memory Bank Data Integration
**Date**: 2025-01-14 01:00:00
**Status**: Accepted  
**Context**: Memory Bank возвращал undefined вместо структурированных данных
**Decision**: Интегрировать реальные данные из 20+ ключевых моментов в markdown файлы
**Consequences**: Memory Bank теперь отражает реальное состояние проекта и историю разработки

## Technical Choices

### Framework Selection
**Choice**: FastAPI + MCP Protocol + ChromaDB
**Reasoning**: FastAPI для быстрого HTTP API, MCP для интеграции с Claude Code CLI, ChromaDB для векторного поиска
**Alternatives considered**: Django (слишком тяжелый), Flask (мало возможностей), Pinecone (платный)

### Database Design
**Choice**: SQLite + ChromaDB + File-based гибрид
**Reasoning**: SQLite для сессий и метаданных, ChromaDB для векторов, файлы для Memory Bank
**Alternatives considered**: PostgreSQL (сложность развертывания), Redis (не подходит для сложных запросов)

### AST Parsing Strategy
**Choice**: Python ast module + JavaScript regex patterns
**Reasoning**: Python ast - надежный и полный, JS regex - быстрый для базовых случаев
**Alternatives considered**: Babel parser (сложность интеграции), Esprima (требует Node.js)

## Pattern Decisions
- **Dual-mode architecture**: HTTP API + MCP stdio для максимальной совместимости
- **FileSnapshot deduplication**: SHA-256 хеши для экономии места
- **Memory-first approach**: Все важные события сохраняются как ключевые моменты
- **Framework-agnostic design**: Поддержка 6 фреймворков одновременно

---
*Последнее обновление: автоматически*
