#!/usr/bin/env python3
"""
Тестирование HTTP-MCP сервера
"""

import requests
import json
import time

MCP_SERVER_URL = "http://127.0.0.1:8200"

def test_health():
    """Проверка health endpoint"""
    print("🔍 Проверка health endpoint...")
    try:
        response = requests.get(f"{MCP_SERVER_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print("✅ MCP сервер работает")
            print(f"   Версия: {data.get('version')}")
            print(f"   RAG сервер: {data.get('rag_server')}")
            print(f"   Включенные инструменты: {len(data.get('tools_enabled', []))}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Сервер недоступен: {e}")
        return False

def test_ask_rag():
    """Тест инструмента ask_rag"""
    print("\n📝 Тест ask_rag...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/ask_rag",
            json={
                "query": "Что такое компонент в Vue?",
                "framework": "vue",
                "max_results": 3
            }
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Получен ответ")
            print(f"   Ответ: {data['answer'][:200]}...")
            print(f"   Источников: {len(data.get('sources', []))}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"   {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_get_recent_changes():
    """Тест инструмента get_recent_changes"""
    print("\n📋 Тест get_recent_changes...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/get_recent_changes",
            json={"limit": 5}
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Получены изменения")
            print(f"   Количество: {len(data.get('changes', []))}")
            if data.get('error'):
                print(f"   ⚠️  {data['error']}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_run_tests():
    """Тест инструмента run_tests (stub)"""
    print("\n🧪 Тест run_tests...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/run_tests",
            json={}
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Тесты выполнены")
            print(f"   Статус: {data.get('status')}")
            print(f"   Лог: {data.get('log', '')[:100]}...")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_apply_patch():
    """Тест инструмента apply_patch"""
    print("\n🔧 Тест apply_patch...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/apply_patch",
            json={
                "diff": "--- a/test.js\n+++ b/test.js\n@@ -1,1 +1,1 @@\n-const a = 1;\n+const a = 2;",
                "files": ["test.js"]
            }
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Патч применен")
            print(f"   Статус: {data.get('status')}")
            print(f"   Сообщение: {data.get('message')}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_list_frameworks():
    """Тест инструмента list_frameworks"""
    print("\n📦 Тест list_frameworks...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/list_frameworks",
            json={}
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Получен список фреймворков")
            print(f"   Количество: {len(data.get('frameworks', []))}")
            for fw in data.get('frameworks', [])[:3]:
                print(f"   - {fw['name']} ({fw['key']})")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_stats_calls():
    """Тест статистики вызовов"""
    print("\n📊 Тест статистики вызовов...")
    try:
        response = requests.get(f"{MCP_SERVER_URL}/stats/calls")
        if response.status_code == 200:
            data = response.json()
            print("✅ Получена статистика")
            stats = data.get('stats', [])
            if stats:
                print("   Топ инструментов:")
                for stat in stats[:3]:
                    print(f"   - {stat['tool_name']}: {stat['call_count']} вызовов")
            else:
                print("   Пока нет статистики")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_postcss_scenario():
    """Мини-сценарий проверки PostCSS bug"""
    print("\n🎯 Сценарий PostCSS bug...")
    
    # 1. Задаем вопрос
    print("1️⃣ Спрашиваем про ошибку 'module is not defined'...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/ask_rag",
            json={
                "query": "Как исправить ошибку 'module is not defined' в postcss.config.js?",
                "max_results": 3
            }
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Получен ответ с рекомендациями")
            print(f"   {data['answer'][:150]}...")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 2. Применяем патч
    print("\n2️⃣ Применяем патч с export default...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/apply_patch",
            json={
                "diff": """--- a/postcss.config.js
+++ b/postcss.config.js
@@ -1,5 +1,5 @@
-module.exports = {
+export default {
   plugins: {
     tailwindcss: {},
     autoprefixer: {},
   },
 }""",
                "files": ["postcss.config.js"]
            }
        )
        if response.status_code == 200:
            print("✅ Патч применен")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 3. Запускаем тесты
    print("\n3️⃣ Запускаем тесты...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/run_tests",
            json={}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Тесты: {data.get('status')}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 4. Проверяем ключевые моменты
    print("\n4️⃣ Проверяем ключевые моменты...")
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/tool/get_recent_changes",
            json={"limit": 3}
        )
        if response.status_code == 200:
            data = response.json()
            changes = data.get('changes', [])
            if changes:
                print("✅ Найдены ключевые моменты:")
                for change in changes:
                    print(f"   - {change.get('title', 'Без названия')}")
            else:
                print("⚠️  Ключевые моменты не найдены")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    print("\n✅ Сценарий PostCSS bug завершен!")
    return True

def main():
    print("🚀 Тестирование HTTP-MCP сервера\n")
    
    # Проверяем доступность
    if not test_health():
        print("\n❌ MCP сервер недоступен!")
        print("Убедитесь, что:")
        print("1. RAG сервер запущен на http://localhost:8000")
        print("2. HTTP-MCP сервер запущен:")
        print("   cd mcp-server && npm install && npm run start:http")
        return
    
    # Запускаем тесты
    tests = [
        test_ask_rag,
        test_get_recent_changes,
        test_run_tests,
        test_apply_patch,
        test_list_frameworks,
        test_stats_calls,
        test_postcss_scenario
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        time.sleep(0.5)  # Небольшая пауза между тестами
    
    print(f"\n📊 Результаты: {passed}/{len(tests)} тестов пройдено")
    
    if passed == len(tests):
        print("✅ Все тесты пройдены успешно!")
    else:
        print("⚠️  Некоторые тесты не прошли")

if __name__ == "__main__":
    main()
