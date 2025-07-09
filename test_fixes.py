#!/usr/bin/env python3
"""
Тестирование исправлений критических проблем
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8200"

def test_long_response():
    """Тест на обрезание длинных ответов"""
    print("\n🔍 Тест 1: Проверка длинных ответов")
    
    # Запрос, который должен вернуть длинный ответ
    response = requests.post(f"{BASE_URL}/tool/ask_rag", json={
        "query": "Расскажи подробно о всех хуках в Vue 3 Composition API с примерами кода для каждого",
        "framework": "vue",
        "max_results": 10
    })
    
    if response.status_code == 200:
        data = response.json()
        answer = data.get('answer', '')
        
        # Проверяем, что ответ не обрывается
        print(f"   Длина ответа: {len(answer)} символов")
        
        # Проверяем отсутствие артефактов
        artifacts = ['Created Question', 'Created Answer', 'Human:', 'Assistant:', '```\n```']
        found_artifacts = []
        for artifact in artifacts:
            if artifact in answer:
                found_artifacts.append(artifact)
        
        if found_artifacts:
            print(f"   ⚠️ Найдены артефакты: {found_artifacts}")
        else:
            print("   ✅ Артефакты не найдены")
        
        # Проверяем, что ответ не обрывается на середине слова
        if answer and answer[-1] in '.!?;:)]\'"»':
            print("   ✅ Ответ завершается корректно")
        else:
            print(f"   ⚠️ Ответ может быть обрезан. Последние символы: '{answer[-20:]}'")
        
        return True
    else:
        print(f"   ❌ Ошибка: {response.status_code}")
        return False

def test_json_error_handling():
    """Тест обработки невалидного JSON"""
    print("\n🔍 Тест 2: Обработка невалидного JSON")
    
    # Отправляем невалидный JSON
    response = requests.post(
        f"{BASE_URL}/tool/ask_rag",
        data='{"query": "test", invalid json}',
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 400:
        try:
            data = response.json()
            if 'error' in data:
                print(f"   ✅ Корректная обработка ошибки: {data['error']}")
                return True
            else:
                print("   ⚠️ Ответ не содержит поля error")
                return False
        except:
            print("   ❌ Ответ не является валидным JSON")
            return False
    else:
        print(f"   ❌ Неожиданный статус код: {response.status_code}")
        return False

def test_path_validation():
    """Тест валидации путей файлов"""
    print("\n🔍 Тест 3: Валидация путей файлов")
    
    # Попытка прочитать файл вне рабочей директории
    dangerous_paths = [
        "/etc/passwd",
        "../../../etc/passwd",
        "~/.ssh/id_rsa",
        "/Users/aleksejcuprynin/.ssh/id_rsa"
    ]
    
    for path in dangerous_paths:
        response = requests.post(f"{BASE_URL}/tool/open_file", json={
            "path": path
        })
        
        if response.status_code == 500:
            data = response.json()
            if "Доступ запрещен" in data.get('error', ''):
                print(f"   ✅ Путь {path} заблокирован")
            else:
                print(f"   ⚠️ Путь {path} - неожиданная ошибка: {data.get('error', '')}")
        else:
            print(f"   ❌ Путь {path} - небезопасный доступ разрешен!")
            return False
    
    # Проверка доступа к файлам в рабочей директории
    safe_path = "../config.yaml"  # config.yaml находится в родительской директории
    response = requests.post(f"{BASE_URL}/tool/open_file", json={
        "path": safe_path
    })
    
    if response.status_code == 200:
        print(f"   ✅ Безопасный путь {safe_path} доступен")
        return True
    else:
        print(f"   ❌ Безопасный путь {safe_path} недоступен")
        return False

def test_model_availability():
    """Тест доступности моделей"""
    print("\n🔍 Тест 4: Проверка доступности моделей")
    
    # Получаем список моделей
    response = requests.post(f"{BASE_URL}/tool/list_models", json={})
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        default_model = data.get('default', '')
        
        print(f"   Доступные модели: {len(models)}")
        print(f"   Модель по умолчанию: {default_model}")
        
        # Проверяем работу с моделью по умолчанию
        response = requests.post(f"{BASE_URL}/tool/ask_rag", json={
            "query": "Что такое ref в Vue?",
            "framework": "vue",
            "max_results": 1
        })
        
        if response.status_code == 200:
            print(f"   ✅ Модель по умолчанию ({default_model}) работает")
            return True
        else:
            print(f"   ❌ Модель по умолчанию ({default_model}) недоступна")
            return False
    else:
        print("   ❌ Не удалось получить список моделей")
        return False

def test_response_cleaning():
    """Тест очистки ответов от артефактов"""
    print("\n🔍 Тест 5: Очистка ответов от артефактов")
    
    # Делаем несколько запросов и проверяем чистоту ответов
    test_queries = [
        {"query": "Как создать компонент?", "framework": "vue"},
        {"query": "Что такое Eloquent?", "framework": "laravel"},
        {"query": "Как работает v-model?", "framework": "vue"}
    ]
    
    clean_responses = 0
    for test_query in test_queries:
        response = requests.post(f"{BASE_URL}/tool/ask_rag", json=test_query)
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '')
            
            # Проверяем на артефакты
            is_clean = True
            if 'Created Question' in answer or 'Created Answer' in answer:
                is_clean = False
            if answer.count('```') % 2 != 0:  # Нечетное количество блоков кода
                is_clean = False
            if answer.endswith('```'):
                is_clean = False
            
            if is_clean:
                clean_responses += 1
                print(f"   ✅ Запрос '{test_query['query'][:30]}...' - чистый ответ")
            else:
                print(f"   ⚠️ Запрос '{test_query['query'][:30]}...' - найдены артефакты")
    
    success_rate = clean_responses / len(test_queries) * 100
    print(f"   Процент чистых ответов: {success_rate:.0f}%")
    
    return success_rate >= 80  # Минимум 80% чистых ответов

def main():
    print("🧪 Тестирование исправлений критических проблем")
    print("=" * 50)
    
    # Проверяем доступность сервера
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ HTTP-MCP сервер недоступен!")
            return
    except:
        print("❌ Не удалось подключиться к HTTP-MCP серверу на порту 8200")
        return
    
    # Запускаем тесты
    tests = [
        test_long_response,
        test_json_error_handling,
        test_path_validation,
        test_model_availability,
        test_response_cleaning
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   ❌ Ошибка в тесте: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{len(tests)} тестов пройдено")
    
    if passed == len(tests):
        print("✅ Все исправления работают корректно!")
    else:
        print("⚠️ Некоторые проблемы требуют дополнительного внимания")

if __name__ == "__main__":
    main()
