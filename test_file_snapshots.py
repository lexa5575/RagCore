#!/usr/bin/env python3
"""
Тестирование новой системы FileSnapshot и CodeSnippet
"""

import os
import sys
import tempfile
from session_manager import SessionManager, FileSnapshot, CodeSnippet

def test_database_tables():
    """Тест создания новых таблиц в базе данных"""
    print("🧪 Тестирование создания таблиц в БД...")
    
    # Создаем временную базу данных
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    
    try:
        # Инициализируем SessionManager с временной БД
        session_manager = SessionManager(db_path=tmp_db_path)
        
        # Проверяем что таблицы созданы
        import sqlite3
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        
        # Проверяем наличие новых таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['sessions', 'file_snapshots', 'code_snippets']
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ Отсутствуют таблицы: {missing_tables}")
            return False
        else:
            print(f"✅ Все таблицы созданы: {tables}")
        
        # Проверяем структуру таблицы file_snapshots
        cursor.execute("PRAGMA table_info(file_snapshots)")
        columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = ['id', 'file_path', 'content', 'content_hash', 'language', 'size_bytes', 'timestamp', 'encoding', 'session_id']
        missing_columns = [col for col in expected_columns if col not in columns]
        
        if missing_columns:
            print(f"❌ Отсутствуют колонки в file_snapshots: {missing_columns}")
            return False
        else:
            print(f"✅ Структура file_snapshots корректна: {len(columns)} колонок")
        
        conn.close()
        return True
        
    finally:
        # Удаляем временный файл
        os.unlink(tmp_db_path)

def test_file_snapshot_saving():
    """Тест сохранения снимков файлов"""
    print("\n🧪 Тестирование сохранения FileSnapshot...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    
    try:
        session_manager = SessionManager(db_path=tmp_db_path)
        
        # Создаем тестовую сессию
        session_id = session_manager.create_session("test_project")
        print(f"✅ Создана тестовая сессия: {session_id}")
        
        # Тестовый файл Python
        test_content = '''#!/usr/bin/env python3
def hello_world():
    """Простая тестовая функция"""
    print("Hello, World!")
    return "success"

if __name__ == "__main__":
    result = hello_world()
    print(f"Result: {result}")
'''
        
        # Сохраняем снимок файла
        snapshot_id = session_manager.save_file_snapshot(
            session_id=session_id,
            file_path="test_hello.py", 
            content=test_content
        )
        
        print(f"✅ Снимок файла сохранен: {snapshot_id}")
        
        # Сохраняем тот же файл повторно (должен вернуть тот же ID)
        snapshot_id2 = session_manager.save_file_snapshot(
            session_id=session_id,
            file_path="test_hello.py",
            content=test_content
        )
        
        if snapshot_id == snapshot_id2:
            print("✅ Дедупликация работает - повторный снимок не создан")
        else:
            print("❌ Дедупликация не работает - создан дублирующий снимок")
            return False
        
        # Тестируем автоопределение языка
        js_content = 'function test() { console.log("test"); }'
        js_snapshot_id = session_manager.save_file_snapshot(
            session_id=session_id,
            file_path="test.js",
            content=js_content
        )
        
        print(f"✅ JavaScript файл сохранен: {js_snapshot_id}")
        
        return True
        
    finally:
        os.unlink(tmp_db_path)

def test_file_search():
    """Тест поиска по содержимому файлов"""
    print("\n🧪 Тестирование поиска по файлам...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    
    try:
        session_manager = SessionManager(db_path=tmp_db_path)
        session_id = session_manager.create_session("search_test")
        
        # Создаем несколько тестовых файлов
        files_data = [
            ("utils.py", 'def calculate_sum(a, b):\n    return a + b\n\ndef format_output(data):\n    return f"Result: {data}"'),
            ("api.js", 'async function fetchData() {\n    const response = await fetch("/api/data");\n    return response.json();\n}'),
            ("config.yaml", 'database:\n  host: localhost\n  port: 5432\n  name: myapp')
        ]
        
        snapshot_ids = []
        for file_path, content in files_data:
            snapshot_id = session_manager.save_file_snapshot(
                session_id=session_id,
                file_path=file_path,
                content=content
            )
            snapshot_ids.append(snapshot_id)
        
        print(f"✅ Сохранено {len(snapshot_ids)} тестовых файлов")
        
        # Тестируем поиск
        # Поиск по функции
        results = session_manager.search_file_content("function")
        print(f"✅ Поиск 'function': найдено {len(results)} результатов")
        
        if len(results) > 0:
            print(f"  - Файл: {results[0]['file_path']}")
            print(f"  - Язык: {results[0]['language']}")
        
        # Поиск по языку
        python_results = session_manager.search_file_content("def", language="python")
        print(f"✅ Поиск 'def' в Python: найдено {len(python_results)} результатов")
        
        # Поиск несуществующего
        empty_results = session_manager.search_file_content("nonexistent_function")
        print(f"✅ Поиск несуществующего: найдено {len(empty_results)} результатов")
        
        return True
        
    finally:
        os.unlink(tmp_db_path)

def test_file_history():
    """Тест истории изменений файла"""
    print("\n🧪 Тестирование истории файлов...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    
    try:
        session_manager = SessionManager(db_path=tmp_db_path)
        session_id = session_manager.create_session("history_test")
        
        file_path = "evolving_script.py"
        
        # Версия 1
        content_v1 = 'print("Version 1")'
        snapshot1 = session_manager.save_file_snapshot(session_id, file_path, content_v1)
        
        # Версия 2
        content_v2 = 'print("Version 2")\nprint("Added feature")'
        snapshot2 = session_manager.save_file_snapshot(session_id, file_path, content_v2)
        
        # Версия 3
        content_v3 = 'def main():\n    print("Version 3")\n    print("Refactored")\n\nif __name__ == "__main__":\n    main()'
        snapshot3 = session_manager.save_file_snapshot(session_id, file_path, content_v3)
        
        # Получаем историю
        history = session_manager.get_file_history(file_path)
        
        print(f"✅ История файла {file_path}: {len(history)} версий")
        
        if len(history) == 3:
            print("✅ Все версии сохранены корректно")
            for i, version in enumerate(history):
                print(f"  - Версия {i+1}: {version['content_hash'][:8]}, размер: {version['size_bytes']} байт")
            return True
        else:
            print(f"❌ Ожидалось 3 версии, получено {len(history)}")
            return False
        
    finally:
        os.unlink(tmp_db_path)

def test_language_detection():
    """Тест автоопределения языков программирования"""
    print("\n🧪 Тестирование автоопределения языков...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    
    try:
        session_manager = SessionManager(db_path=tmp_db_path)
        
        # Тестируем определение языков
        test_cases = [
            ("script.py", "python"),
            ("app.js", "javascript"), 
            ("component.vue", "vue"),
            ("styles.css", "css"),
            ("config.yaml", "yaml"),
            ("data.json", "json"),
            ("README.md", "markdown"),
            ("unknown.xyz", "text")
        ]
        
        all_correct = True
        for file_path, expected_language in test_cases:
            detected = session_manager._detect_language(file_path)
            if detected == expected_language:
                print(f"✅ {file_path} -> {detected}")
            else:
                print(f"❌ {file_path} -> {detected} (ожидалось {expected_language})")
                all_correct = False
        
        return all_correct
        
    finally:
        os.unlink(tmp_db_path)

def main():
    """Запуск всех тестов"""
    print("🚀 Запуск тестов FileSnapshot системы\n")
    
    tests = [
        ("Создание таблиц БД", test_database_tables),
        ("Сохранение снимков", test_file_snapshot_saving),
        ("Поиск по файлам", test_file_search),
        ("История файлов", test_file_history),
        ("Определение языков", test_language_detection)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_name}: ПРОЙДЕН")
                passed += 1
            else:
                print(f"❌ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            print(f"💥 {test_name}: ОШИБКА - {e}")
    
    print(f"\n📊 Результаты: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты успешно пройдены!")
        return True
    else:
        print("⚠️  Некоторые тесты провалены")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)