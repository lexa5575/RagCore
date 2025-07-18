from typing import List, Tuple
from models.enums import KeyMomentType

def auto_detect_key_moments(message_content: str, actions: List[str], files: List[str]) -> List[Tuple[KeyMomentType, str, str]]:
    """Автоматическое обнаружение ключевых моментов из контента"""
    moments = []
    content_lower = message_content.lower()
    
    # Обнаружение решения ошибок (русские и английские слова)
    error_keywords = [
        # Английские
        "error", "fix", "solved", "resolved", "bug", "issue", "problem",
        # Русские
        "ошибка", "исправлен", "решен", "решена", "исправлена", "починен", "починена",
        "баг", "проблема", "устранен", "устранена", "фикс", "исправление"
    ]
    if any(word in content_lower for word in error_keywords):
        moments.append((
            KeyMomentType.ERROR_SOLVED,
            "Решение ошибки",
            f"Обнаружено и исправлено: {message_content[:200]}..."
        ))
    
    # Обнаружение создания файлов
    creation_actions = ["create", "write", "add", "создать", "написать", "добавить"]
    if any(action in actions for action in creation_actions) and files:
        moments.append((
            KeyMomentType.FILE_CREATED,
            f"Создание файла {files[0]}",
            f"Создан файл {files[0]} с функциональностью: {message_content[:200]}..."
        ))
    
    # Обнаружение завершения функций (русские и английские слова)
    completion_keywords = [
        # Английские
        "completed", "finished", "done", "implemented", "ready", "success",
        # Русские
        "завершен", "завершена", "готов", "готова", "выполнен", "выполнена",
        "реализован", "реализована", "закончен", "закончена", "сделан", "сделана"
    ]
    if any(word in content_lower for word in completion_keywords):
        moments.append((
            KeyMomentType.FEATURE_COMPLETED,
            "Завершение функции",
            f"Реализована функция: {message_content[:200]}..."
        ))
    
    # Обнаружение изменений конфигурации (русские и английские слова)
    config_keywords = [
        # Английские
        "config", "settings", "yaml", "json", "configuration",
        # Русские
        "конфигурация", "настройки", "настройка", "конфиг", "параметры"
    ]
    if any(word in content_lower for word in config_keywords) and files:
        moments.append((
            KeyMomentType.CONFIG_CHANGED,
            "Изменение конфигурации",
            f"Обновлена конфигурация в {files[0]}: {message_content[:200]}..."
        ))
    
    # Обнаружение рефакторинга (русские и английские слова)
    refactoring_keywords = [
        # Английские
        "refactor", "refactored", "restructure", "optimize", "optimized",
        # Русские
        "рефакторинг", "рефакторил", "рефакторила", "оптимизирован", "оптимизирована",
        "переработан", "переработана", "реструктуризация", "улучшен", "улучшена"
    ]
    if any(word in content_lower for word in refactoring_keywords):
        moments.append((
            KeyMomentType.REFACTORING,
            "Рефакторинг кода",
            f"Проведен рефакторинг: {message_content[:200]}..."
        ))
    
    # Обнаружение важных решений (русские и английские слова)
    decision_keywords = [
        # Английские
        "decided", "decision", "choice", "selected", "approach",
        # Русские
        "решил", "решила", "решение", "выбор", "подход", "стратегия",
        "принято решение", "выбран", "выбрана"
    ]
    if any(word in content_lower for word in decision_keywords):
        moments.append((
            KeyMomentType.IMPORTANT_DECISION,
            "Важное решение",
            f"Принято решение: {message_content[:200]}..."
        ))
    
    return moments