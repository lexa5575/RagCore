#!/usr/bin/env python3
"""
Тестирование новой универсальной RAG системы
"""

import requests
import json
import time
import yaml

def load_config():
    """Загрузка конфигурации"""
    with open("config.yaml", 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

CONFIG = load_config()
SERVER_CONFIG = CONFIG.get('server', {})
BASE_URL = f"http://{SERVER_CONFIG.get('host', 'localhost')}:{SERVER_CONFIG.get('port', 8000)}"

def test_api_connection():
    """Тестируем подключение к API"""
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print("✅ API доступен!")
            print(f"📊 Всего документов: {data['total_docs']}")
            print(f"🛠️ Поддерживаемые фреймворки: {list(data['frameworks'].keys())}")
            return True
        else:
            print(f"❌ API недоступен. Статус: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к API: {e}")
        return False

def test_frameworks_endpoint():
    """Тестируем endpoint фреймворков"""
    try:
        response = requests.get(f"{BASE_URL}/frameworks")
        if response.status_code == 200:
            data = response.json()
            print("\n🛠️ Доступные фреймворки:")
            for name, info in data.items():
                print(f"  {name}: {info['name']} ({info['type']})")
                print(f"    {info.get('description', 'Без описания')}")
            return True
        else:
            print(f"❌ Ошибка получения фреймворков: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_stats():
    """Тестируем endpoint статистики"""
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            data = response.json()
            print("\n📊 Статистика базы данных:")
            print(f"  Всего документов: {data['total_documents']}")
            print(f"  Размер кэша: {data['cache_size']}")
            print("  По фреймворкам:")
            for framework, count in data['frameworks'].items():
                print(f"    {framework.upper()}: {count}")
            return True
        else:
            print(f"❌ Ошибка получения статистики: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def ask_question(question, framework=None, context=None, show_details=True):
    """Задаем вопрос RAG системе"""
    try:
        payload = {"question": question}
        if framework:
            payload["framework"] = framework
        if context:
            payload["context"] = context
            
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        request_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            framework_info = f" [{framework.upper()}]" if framework else ""
            print(f"\n❓ Вопрос{framework_info}: {question}")
            print(f"✅ Ответ: {data['answer']}")
            
            if show_details:
                print(f"⚡ Время ответа: {data['response_time']:.2f}s (запрос: {request_time:.2f}s)")
                print(f"🎯 Определен фреймворк: {data.get('framework_detected', 'N/A')}")
                print(f"📚 Источников: {data['total_docs']}")
                print("📖 Использованные источники:")
                for i, source in enumerate(data['sources'][:3], 1):
                    print(f"  {i}. [{source['framework']}] {source['source']} - {source['heading']}")
            return True
        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_ide_integration():
    """Тестируем IDE интеграцию"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ: IDE Интеграция")
    print("="*60)
    
    # Тест 1: Vue файл
    vue_request = {
        "question": "Как добавить reactive ref?",
        "file_path": "/src/components/MyComponent.vue",
        "file_content": "<template><div>{{count}}</div></template>",
        "quick_mode": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/ide/ask", json=vue_request)
        if response.status_code == 200:
            data = response.json()
            print("✅ Vue файл - автоопределение фреймворка:")
            print(f"   Определен: {data.get('framework_detected')}")
            print(f"   Ответ: {data['answer'][:100]}...")
        else:
            print(f"❌ Ошибка IDE запроса: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка IDE теста: {e}")
    
    # Тест 2: Laravel файл
    laravel_request = {
        "question": "Как создать модель?",
        "file_path": "/app/Models/User.php",
        "file_content": "<?php class User extends Model {}",
        "quick_mode": False
    }
    
    try:
        response = requests.post(f"{BASE_URL}/ide/ask", json=laravel_request)
        if response.status_code == 200:
            data = response.json()
            print("✅ Laravel файл - автоопределение фреймворка:")
            print(f"   Определен: {data.get('framework_detected')}")
            print(f"   Ответ: {data['answer'][:100]}...")
        else:
            print(f"❌ Ошибка IDE запроса: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка IDE теста: {e}")

def test_cache():
    """Тестируем кэширование"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ: Кэширование")
    print("="*60)
    
    question = "Что такое реактивность?"
    
    # Первый запрос
    start_time = time.time()
    ask_question(question, show_details=False)
    first_time = time.time() - start_time
    
    # Второй запрос (должен быть из кэша)
    start_time = time.time()
    ask_question(question, show_details=False)
    second_time = time.time() - start_time
    
    print(f"⚡ Первый запрос: {first_time:.2f}s")
    print(f"⚡ Второй запрос: {second_time:.2f}s")
    print(f"🚀 Ускорение: {(first_time/second_time):.1f}x" if second_time > 0 else "N/A")

def main():
    print("🧪 Тестирование новой универсальной RAG системы")
    print("=" * 70)
    
    # Тест 1: Проверка подключения
    if not test_api_connection():
        print("❌ Сервер недоступен. Убедитесь, что rag_server_new.py запущен.")
        return
    
    # Тест 2: Фреймворки
    test_frameworks_endpoint()
    
    # Тест 3: Статистика
    test_stats()
    
    # Тест 4: Обычные вопросы
    print("\n" + "="*60)
    print("🧪 ТЕСТ: Обычные запросы")
    print("="*60)
    
    questions = [
        ("Что такое компонент?", None),
        ("Как создать Eloquent модель?", "laravel"),
        ("Как использовать Composition API?", "vue"),
    ]
    
    for question, framework in questions:
        ask_question(question, framework)
        time.sleep(0.5)
    
    # Тест 5: IDE интеграция
    test_ide_integration()
    
    # Тест 6: Кэширование
    if CONFIG.get('cache', {}).get('enabled', True):
        test_cache()
    
    # Очистка кэша
    try:
        response = requests.delete(f"{BASE_URL}/cache")
        if response.status_code == 200:
            print("\n🗑️ Кэш очищен")
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ Тестирование завершено!")
    print("🎯 Новая система готова к использованию!")
    print("💡 Для IDE интеграции используй endpoint /ide/ask")

if __name__ == "__main__":
    main()