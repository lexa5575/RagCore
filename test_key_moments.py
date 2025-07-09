#!/usr/bin/env python3
"""
Тест для проверки сохранения ключевых моментов
"""

import json
from session_manager import SessionManager, KeyMomentType, auto_detect_key_moments

def test_auto_detect_key_moments():
    """Тест автоматического обнаружения ключевых моментов"""
    
    # Тестовые случаи
    test_cases = [
        {
            "content": "Исправлена ошибка в функции авторизации",
            "actions": ["provide_answer"],
            "files": ["auth.py"],
            "expected_types": [KeyMomentType.ERROR_SOLVED]
        },
        {
            "content": "Создан новый компонент для отображения пользователей",
            "actions": ["create", "write"],
            "files": ["UserComponent.vue"],
            "expected_types": [KeyMomentType.FILE_CREATED]
        },
        {
            "content": "Функция регистрации пользователей completed successfully",
            "actions": ["provide_answer"],
            "files": [],
            "expected_types": [KeyMomentType.FEATURE_COMPLETED]
        },
        {
            "content": "Обновлены настройки конфигурации в config.yaml",
            "actions": ["provide_answer"],
            "files": ["config.yaml"],
            "expected_types": [KeyMomentType.CONFIG_CHANGED]
        }
    ]
    
    print("=== Тест автоматического обнаружения ключевых моментов ===")
    
    for i, test_case in enumerate(test_cases):
        print(f"\nТест {i+1}: {test_case['content'][:50]}...")
        
        detected_moments = auto_detect_key_moments(
            test_case['content'],
            test_case['actions'],
            test_case['files']
        )
        
        print(f"  Обнаружено моментов: {len(detected_moments)}")
        for moment_type, title, summary in detected_moments:
            print(f"  - {moment_type.value}: {title}")
            print(f"    Описание: {summary[:100]}...")
        
        if not detected_moments:
            print("  ❌ Ничего не обнаружено!")
        else:
            print("  ✅ Моменты обнаружены")

def test_session_manager_key_moments():
    """Тест сохранения ключевых моментов через SessionManager"""
    
    print("\n=== Тест SessionManager ===")
    
    # Создаем новый SessionManager для тестирования
    session_manager = SessionManager(db_path="test_session.db")
    
    # Создаем тестовую сессию
    session_id = session_manager.create_session("test_project")
    print(f"Создана тестовая сессия: {session_id}")
    
    # Добавляем сообщение с потенциально ключевым моментом
    message_content = "Successfully fixed the authentication bug in login.py"
    session_manager.add_message(
        session_id,
        "assistant",
        message_content,
        actions=["provide_answer"],
        files=["login.py"],
        metadata={"framework": "laravel"}
    )
    
    # Проверяем автоматическое обнаружение
    detected_moments = auto_detect_key_moments(
        message_content,
        ["provide_answer"],
        ["login.py"]
    )
    
    print(f"Автоматически обнаружено моментов: {len(detected_moments)}")
    for moment_type, title, summary in detected_moments:
        print(f"  - {moment_type.value}: {title}")
        
        # Добавляем ключевой момент
        success = session_manager.add_key_moment(
            session_id,
            moment_type,
            title,
            summary,
            files=["login.py"],
            context=message_content
        )
        print(f"  Сохранение: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    # Проверяем, что ключевые моменты сохранились
    session_context = session_manager.get_session_context(session_id)
    key_moments = session_context.get('key_moments', [])
    
    print(f"\nСохранено ключевых моментов в сессии: {len(key_moments)}")
    for km in key_moments:
        print(f"  - {km['type']}: {km['title']}")
        print(f"    Важность: {km['importance']}")
        print(f"    Файлы: {km['files_involved']}")
    
    # Добавляем ключевой момент вручную
    manual_success = session_manager.add_key_moment(
        session_id,
        KeyMomentType.FEATURE_COMPLETED,
        "Завершена система авторизации",
        "Полностью реализована система авторизации с проверкой прав доступа",
        importance=8,
        files=["auth.py", "login.py"],
        context="Ручное добавление для тестирования"
    )
    
    print(f"\nРучное добавление ключевого момента: {'✅ Успешно' if manual_success else '❌ Ошибка'}")
    
    # Проверяем финальное состояние
    final_context = session_manager.get_session_context(session_id)
    final_key_moments = final_context.get('key_moments', [])
    
    print(f"\nФинальное количество ключевых моментов: {len(final_key_moments)}")
    for km in final_key_moments:
        print(f"  - {km['type']}: {km['title']} (важность: {km['importance']})")

if __name__ == "__main__":
    test_auto_detect_key_moments()
    test_session_manager_key_moments()