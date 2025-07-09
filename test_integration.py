#!/usr/bin/env python3
"""
Тестирование интеграции Session Manager с RAG сервером
"""

import requests
import json
import time
from typing import Dict, Any

class RAGServerTest:
    """Тестирование интегрированного RAG сервера"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def test_server_status(self) -> Dict[str, Any]:
        """Тестирование статуса сервера"""
        print("🔍 Тестирование статуса сервера...")
        
        response = self.session.get(f"{self.base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Сервер работает: {data['message']}")
            print(f"🧠 Session Memory: {'включен' if data['session_memory']['enabled'] else 'отключен'}")
            return data
        else:
            print(f"❌ Сервер недоступен: {response.status_code}")
            return {}
    
    def test_create_session(self, project_name: str) -> str:
        """Тестирование создания сессии"""
        print(f"🆕 Создание сессии для проекта: {project_name}")
        
        response = self.session.post(
            f"{self.base_url}/sessions/create",
            params={"project_name": project_name}
        )
        
        if response.status_code == 200:
            data = response.json()
            session_id = data['session_id']
            print(f"✅ Сессия создана: {session_id}")
            return session_id
        else:
            print(f"❌ Ошибка создания сессии: {response.status_code}")
            return None
    
    def test_ask_with_memory(self, session_id: str, question: str, 
                           project_name: str = None) -> Dict[str, Any]:
        """Тестирование запроса с памятью"""
        print(f"💬 Запрос с памятью: {question}")
        
        payload = {
            "question": question,
            "framework": "laravel",
            "project_name": project_name,
            "session_id": session_id,
            "use_memory": True,
            "save_to_memory": True
        }
        
        response = self.session.post(
            f"{self.base_url}/ask",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Ответ получен (время: {data['response_time']:.2f}s)")
            print(f"🧠 Использована память: {data['session_context_used']}")
            print(f"🔑 Ключевых моментов: {len(data['key_moments_detected'])}")
            return data
        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
            return {}
    
    def test_ide_ask(self, session_id: str, question: str, 
                    file_path: str = None, project_path: str = None) -> Dict[str, Any]:
        """Тестирование IDE запроса"""
        print(f"🖥️ IDE запрос: {question}")
        
        payload = {
            "question": question,
            "file_path": file_path,
            "project_path": project_path,
            "session_id": session_id,
            "use_memory": True,
            "save_to_memory": True,
            "quick_mode": False
        }
        
        response = self.session.post(
            f"{self.base_url}/ide/ask",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ IDE ответ получен (время: {data['response_time']:.2f}s)")
            print(f"🔧 Фреймворк: {data['framework_detected']}")
            return data
        else:
            print(f"❌ Ошибка IDE запроса: {response.status_code}")
            return {}
    
    def test_session_info(self, session_id: str) -> Dict[str, Any]:
        """Тестирование получения информации о сессии"""
        print(f"📋 Получение информации о сессии: {session_id}")
        
        response = self.session.get(f"{self.base_url}/sessions/{session_id}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Информация получена:")
            print(f"   📂 Проект: {data['project_name']}")
            print(f"   💬 Сообщений: {data['stats']['total_messages']}")
            print(f"   🔑 Ключевых моментов: {data['stats']['total_key_moments']}")
            return data
        else:
            print(f"❌ Ошибка получения информации: {response.status_code}")
            return {}
    
    def test_add_key_moment(self, session_id: str) -> bool:
        """Тестирование добавления ключевого момента"""
        print("🔑 Добавление ключевого момента...")
        
        payload = {
            "moment_type": "feature_completed",
            "title": "Интеграция Session Manager",
            "summary": "Успешно интегрирована система памяти с RAG сервером",
            "importance": 8,
            "files": ["rag_server.py", "session_manager.py"],
            "context": "Тестирование интеграции"
        }
        
        response = self.session.post(
            f"{self.base_url}/sessions/{session_id}/key-moment",
            params=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Ключевой момент добавлен: {data['message']}")
            return True
        else:
            print(f"❌ Ошибка добавления момента: {response.status_code}")
            return False
    
    def test_session_stats(self) -> Dict[str, Any]:
        """Тестирование статистики сессий"""
        print("📊 Получение статистики сессий...")
        
        response = self.session.get(f"{self.base_url}/sessions/stats")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Статистика получена:")
            print(f"   📁 Всего сессий: {data['total_sessions']}")
            print(f"   🔀 Уникальных проектов: {data['unique_projects']}")
            return data
        else:
            print(f"❌ Ошибка получения статистики: {response.status_code}")
            return {}
    
    def run_integration_test(self):
        """Запуск полного теста интеграции"""
        print("🚀 Запуск полного теста интеграции Session Manager + RAG Server")
        print("=" * 70)
        
        # 1. Проверка статуса сервера
        server_status = self.test_server_status()
        if not server_status:
            print("❌ Сервер недоступен, прерываем тест")
            return
        
        print("\n" + "=" * 70)
        
        # 2. Создание сессии
        project_name = "test_integration_project"
        session_id = self.test_create_session(project_name)
        if not session_id:
            print("❌ Не удалось создать сессию, прерываем тест")
            return
        
        print("\n" + "=" * 70)
        
        # 3. Несколько запросов для накопления контекста
        questions = [
            "Как создать модель в Laravel?",
            "Как добавить валидацию к модели?",
            "Как создать контроллер для этой модели?",
            "Как настроить маршруты для CRUD операций?"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n--- Запрос {i}/4 ---")
            response = self.test_ask_with_memory(session_id, question, project_name)
            if response:
                print(f"📝 Ответ: {response['answer'][:150]}...")
            time.sleep(1)  # Небольшая пауза между запросами
        
        print("\n" + "=" * 70)
        
        # 4. IDE запрос
        self.test_ide_ask(
            session_id,
            "Как исправить ошибку валидации?",
            file_path="/path/to/project/app/Models/User.php",
            project_path="/path/to/project"
        )
        
        print("\n" + "=" * 70)
        
        # 5. Добавление ключевого момента
        self.test_add_key_moment(session_id)
        
        print("\n" + "=" * 70)
        
        # 6. Получение информации о сессии
        self.test_session_info(session_id)
        
        print("\n" + "=" * 70)
        
        # 7. Статистика сессий
        self.test_session_stats()
        
        print("\n" + "=" * 70)
        print("✅ Тест интеграции завершен успешно!")

def main():
    """Основная функция"""
    tester = RAGServerTest()
    
    try:
        tester.run_integration_test()
    except KeyboardInterrupt:
        print("\n⏹️ Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка во время теста: {e}")

if __name__ == "__main__":
    main()