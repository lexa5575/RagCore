# Code Patterns

## Established Patterns

### Session Manager Pattern
```python
# Основной паттерн для работы с сессиями
class SessionManager:
    def __init__(self, db_path: str, max_messages: int = 200):
        self.db_path = db_path
        self.max_messages = max_messages
        self._init_database()
        
    def add_key_moment(self, session_id: str, moment_type: KeyMomentType, 
                      title: str, summary: str, **kwargs) -> bool:
        # Стандартный способ сохранения важных событий
```

### AST Parsing Pattern
```python
# Извлечение символов из Python кода
import ast

def parse_python_ast(content: str) -> List[CodeSymbol]:
    try:
        tree = ast.parse(content)
        symbols = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                # Извлекаем информацию о символе
        return symbols
    except SyntaxError:
        return []
```

### MCP Response Format
```json
{
  "message": "Success description",
  "data": {
    "results": [],
    "count": 0
  },
  "timestamp": "2025-01-14T01:20:00Z"
}
```

### File Organization
```
chanki/
├── session_manager.py    # Core session logic
├── rag_server.py        # HTTP API endpoints
├── mcp-server/          # MCP stdio integration
├── memory-bank/         # Context markdown files
└── *_docs/             # Framework documentation
```

## Naming Conventions
- **Functions**: camelCase / snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Files**: kebab-case / snake_case

## Code Style Guidelines
- **Docstrings**: Русские комментарии для внутренней логики, английские для API
- **Error handling**: Всегда логировать ошибки с контекстом
- **Type hints**: Обязательны для всех функций и методов
- **MCP functions**: Всегда возвращать структурированный ответ с message
- **Database**: Использовать контекстные менеджеры для SQLite соединений

## Testing Patterns
```python
# Паттерн тестирования SessionManager
def test_ast_parsing():
    # Arrange
    session_manager = SessionManager(db_path="test_session.db")
    python_code = '''class TestClass: pass'''
    
    # Act
    snapshot_id = session_manager.save_file_snapshot(
        session_id="test", file_path="test.py", 
        content=python_code, language="python"
    )
    
    # Assert
    symbols = session_manager.search_symbols(query="TestClass")
    assert len(symbols) > 0
    assert symbols[0]['symbol_type'] == 'class'
```

## Memory Bank Patterns
```python
# Автоматическое обновление Memory Bank
def update_memory_bank_context(session_id: str, context_data: dict):
    """Обновление активного контекста с новыми данными"""
    # Стандартный способ синхронизации Memory Bank
```

---
*Последнее обновление: автоматически*
