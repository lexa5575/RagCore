from enum import Enum

class KeyMomentType(Enum):
    """Типы ключевых моментов"""
    ERROR_SOLVED = "error_solved"
    FEATURE_COMPLETED = "feature_completed"
    CONFIG_CHANGED = "config_changed"
    BREAKTHROUGH = "breakthrough"
    FILE_CREATED = "file_created"
    DEPLOYMENT = "deployment"
    IMPORTANT_DECISION = "important_decision"
    REFACTORING = "refactoring"

# Важность по типам ключевых моментов
MOMENT_IMPORTANCE = {
    KeyMomentType.BREAKTHROUGH: 9,
    KeyMomentType.ERROR_SOLVED: 8,
    KeyMomentType.DEPLOYMENT: 8,
    KeyMomentType.FEATURE_COMPLETED: 7,
    KeyMomentType.IMPORTANT_DECISION: 7,
    KeyMomentType.CONFIG_CHANGED: 6,
    KeyMomentType.REFACTORING: 6,
    KeyMomentType.FILE_CREATED: 5,
}

class SessionStatus(Enum):
    """Статусы сессий"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"