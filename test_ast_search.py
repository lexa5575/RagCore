#!/usr/bin/env python3
"""
Тест AST поиска для проверки новой функциональности
"""

import json
import tempfile
import os
from session_manager import SessionManager, KeyMomentType

def test_ast_parsing():
    """Тест AST парсинга Python кода"""
    
    print("=== Тест AST парсинга Python ===")
    
    # Создаем временный файл с Python кодом
    python_code = '''
class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def create_user(self, name: str, email: str) -> dict:
        """Создание нового пользователя"""
        user_data = {
            'name': name,
            'email': email,
            'created_at': datetime.now()
        }
        return self.db.insert('users', user_data)
    
    def get_user_by_email(self, email: str):
        """Поиск пользователя по email"""
        return self.db.query('SELECT * FROM users WHERE email = ?', [email])

def calculate_total(items):
    """Расчет общей суммы"""
    return sum(item.price for item in items)

API_VERSION = "1.0.0"
DEBUG_MODE = True
'''
    
    # Создаем SessionManager для тестирования
    session_manager = SessionManager(db_path="test_ast_session.db")
    
    # Создаем тестовую сессию
    session_id = session_manager.create_session("ast_test_project")
    print(f"Создана тестовая сессия: {session_id}")
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(python_code)
        temp_file = f.name
    
    try:
        # Сохраняем файл через FileSnapshot с AST парсингом
        snapshot_result = session_manager.save_file_snapshot(
            session_id=session_id,
            file_path=temp_file,
            content=python_code,
            language="python"
        )
        
        print(f"Снимок файла сохранен: {snapshot_result}")
        
        # Проверяем, что символы были извлечены
        import sqlite3
        conn = sqlite3.connect(session_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol_type, name, full_name, signature, docstring, start_line, end_line
            FROM code_symbols 
            WHERE file_snapshot_id = ?
            ORDER BY start_line
        """, (snapshot_result,))
        
        symbols = cursor.fetchall()
        print(f"\nИзвлечено символов из кода: {len(symbols)}")
        
        for symbol in symbols:
            symbol_type, name, full_name, signature, docstring, start_line, end_line = symbol
            print(f"  {symbol_type}: {name}")
            print(f"    Полное имя: {full_name}")
            print(f"    Строки: {start_line}-{end_line}")
            if signature:
                print(f"    Сигнатура: {signature[:100]}...")
            if docstring:
                print(f"    Документация: {docstring[:100]}...")
            print()
        
        conn.close()
        
        # Тестируем поиск символов
        search_results = session_manager.search_symbols(
            query="user",
            symbol_type="",
            language="python",
            limit=10
        )
        
        print(f"Результаты поиска по 'user': {len(search_results)} найдено")
        for result in search_results:
            print(f"  - {result['symbol_type']}: {result['name']} ({result['file_path']}:{result['start_line']})")
        
        # Поиск функций
        function_results = session_manager.search_symbols(
            query="create",
            symbol_type="function",
            language="python",
            limit=5
        )
        
        print(f"\nРезультаты поиска функций с 'create': {len(function_results)} найдено")
        for result in function_results:
            print(f"  - {result['name']}: {result['signature'][:80]}...")
        
    finally:
        # Удаляем временный файл
        os.unlink(temp_file)

def test_javascript_ast():
    """Тест AST парсинга JavaScript кода"""
    
    print("\n=== Тест JavaScript парсинга ===")
    
    # JavaScript код для тестирования
    js_code = '''
class ApiService {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json'
        };
    }
    
    async fetchUser(userId) {
        const response = await fetch(`${this.baseUrl}/users/${userId}`);
        return response.json();
    }
    
    async createPost(postData) {
        return fetch(`${this.baseUrl}/posts`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(postData)
        });
    }
}

function calculateDiscount(price, percentage) {
    return price * (percentage / 100);
}

const API_ENDPOINT = 'https://api.example.com';
const MAX_RETRIES = 3;
'''
    
    session_manager = SessionManager(db_path="test_ast_session.db")
    session_id = session_manager.create_session("js_ast_test")
    
    # Создаем временный JavaScript файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_file = f.name
    
    try:
        # Сохраняем JS файл
        snapshot_result = session_manager.save_file_snapshot(
            session_id=session_id,
            file_path=temp_file,
            content=js_code,
            language="javascript"
        )
        
        # Проверяем извлеченные символы
        import sqlite3
        conn = sqlite3.connect(session_manager.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symbol_type, name, full_name, signature, start_line, end_line
            FROM code_symbols 
            WHERE file_snapshot_id = ? AND language = 'javascript'
            ORDER BY start_line
        """, (snapshot_result,))
        
        symbols = cursor.fetchall()
        print(f"Извлечено JavaScript символов: {len(symbols)}")
        
        for symbol in symbols:
            symbol_type, name, full_name, signature, start_line, end_line = symbol
            print(f"  {symbol_type}: {name} (строки {start_line}-{end_line})")
        
        conn.close()
        
        # Тестируем поиск
        search_results = session_manager.search_symbols(
            query="fetch",
            language="javascript"
        )
        
        print(f"\nПоиск 'fetch' в JavaScript: {len(search_results)} найдено")
        for result in search_results:
            print(f"  - {result['symbol_type']}: {result['name']}")
    
    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    test_ast_parsing()
    test_javascript_ast()
    print("\n✅ Тестирование AST функциональности завершено")