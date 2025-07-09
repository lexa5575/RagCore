#!/usr/bin/env python3
"""
Тесты для системы управления сессиями RAG сервера
"""

import os
import tempfile
import unittest
from unittest.mock import patch
import time
from session_manager import (
    SessionManager, Session, Message, KeyMoment, CompressedPeriod,
    KeyMomentType, SessionStatus, auto_detect_key_moments
)

class TestSessionManager(unittest.TestCase):
    """Тесты для SessionManager"""
    
    def setUp(self):
        """Подготовка к тестам"""
        # Создаем временный файл базы данных
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        
        # Инициализируем SessionManager с временной базой
        self.session_manager = SessionManager(
            db_path=self.temp_db.name,
            max_messages=10  # Маленький лимит для тестирования сжатия
        )
        
    def tearDown(self):
        """Очистка после тестов"""
        # Удаляем временный файл базы данных
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_create_session(self):
        """Тест создания сессии"""
        project_name = "test_project"
        session_id = self.session_manager.create_session(project_name)
        
        # Проверяем, что session_id не пустой
        self.assertIsNotNone(session_id)
        self.assertNotEqual(session_id, "")
        
        # Проверяем, что сессия создалась
        session = self.session_manager.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.project_name, project_name)
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertEqual(len(session.messages), 0)
        self.assertEqual(len(session.key_moments), 0)
    
    def test_get_latest_session(self):
        """Тест получения последней сессии проекта"""
        project_name = "test_project"
        
        # Создаем несколько сессий
        session_id1 = self.session_manager.create_session(project_name)
        time.sleep(0.1)  # Небольшая задержка для разных timestamp
        session_id2 = self.session_manager.create_session(project_name)
        
        # Получаем последнюю сессию
        latest_session_id = self.session_manager.get_latest_session(project_name)
        
        # Должна вернуться последняя созданная сессия
        self.assertEqual(latest_session_id, session_id2)
    
    def test_add_message(self):
        """Тест добавления сообщения"""
        session_id = self.session_manager.create_session("test_project")
        
        # Добавляем сообщение
        success = self.session_manager.add_message(
            session_id,
            "user",
            "Тестовое сообщение",
            actions=["test_action"],
            files=["test_file.py"],
            metadata={"test": "data"}
        )
        
        self.assertTrue(success)
        
        # Проверяем, что сообщение добавилось
        session = self.session_manager.get_session(session_id)
        self.assertEqual(len(session.messages), 1)
        
        message = session.messages[0]
        self.assertEqual(message.role, "user")
        self.assertEqual(message.content, "Тестовое сообщение")
        self.assertEqual(message.actions, ["test_action"])
        self.assertEqual(message.files_involved, ["test_file.py"])
        self.assertEqual(message.metadata, {"test": "data"})
    
    def test_add_key_moment(self):
        """Тест добавления ключевого момента"""
        session_id = self.session_manager.create_session("test_project")
        
        # Добавляем ключевой момент
        success = self.session_manager.add_key_moment(
            session_id,
            KeyMomentType.FEATURE_COMPLETED,
            "Тестовая функция",
            "Реализована тестовая функция",
            importance=8,
            files=["test_feature.py"],
            context="Контекст тестирования"
        )
        
        self.assertTrue(success)
        
        # Проверяем, что ключевой момент добавился
        session = self.session_manager.get_session(session_id)
        self.assertEqual(len(session.key_moments), 1)
        
        key_moment = session.key_moments[0]
        self.assertEqual(key_moment.type, KeyMomentType.FEATURE_COMPLETED)
        self.assertEqual(key_moment.title, "Тестовая функция")
        self.assertEqual(key_moment.summary, "Реализована тестовая функция")
        self.assertEqual(key_moment.importance, 8)
        self.assertEqual(key_moment.files_involved, ["test_feature.py"])
        self.assertEqual(key_moment.context, "Контекст тестирования")
    
    def test_session_compression(self):
        """Тест сжатия сессии при превышении лимита сообщений"""
        session_id = self.session_manager.create_session("test_project")
        
        # Добавляем много сообщений (больше чем max_messages)
        for i in range(15):
            self.session_manager.add_message(
                session_id,
                "user" if i % 2 == 0 else "assistant",
                f"Сообщение {i}",
                actions=[f"action_{i}"],
                files=[f"file_{i}.py"]
            )
        
        # Проверяем, что произошло сжатие
        session = self.session_manager.get_session(session_id)
        
        # Должно остаться не больше max_messages сообщений
        self.assertLessEqual(len(session.messages), self.session_manager.max_messages)
        
        # Должна появиться сжатая история
        self.assertGreater(len(session.compressed_history), 0)
        
        # Проверяем содержимое сжатой истории
        compressed_period = session.compressed_history[0]
        self.assertGreater(compressed_period.message_count, 0)
        self.assertNotEqual(compressed_period.summary, "")
    
    def test_get_session_context(self):
        """Тест получения контекста сессии"""
        session_id = self.session_manager.create_session("test_project")
        
        # Добавляем сообщения и ключевые моменты
        self.session_manager.add_message(session_id, "user", "Тестовый вопрос")
        self.session_manager.add_message(session_id, "assistant", "Тестовый ответ")
        self.session_manager.add_key_moment(
            session_id,
            KeyMomentType.BREAKTHROUGH,
            "Важное открытие",
            "Найден важный паттерн"
        )
        
        # Получаем контекст
        context = self.session_manager.get_session_context(session_id)
        
        self.assertIsNotNone(context)
        self.assertEqual(context['project_name'], "test_project")
        self.assertEqual(len(context['recent_messages']), 2)
        self.assertEqual(len(context['key_moments']), 1)
        self.assertIn('stats', context)
    
    def test_archive_session(self):
        """Тест архивирования сессии"""
        session_id = self.session_manager.create_session("test_project")
        
        # Архивируем сессию
        success = self.session_manager.archive_session(session_id)
        self.assertTrue(success)
        
        # Проверяем, что статус изменился
        session = self.session_manager.get_session(session_id)
        self.assertEqual(session.status, SessionStatus.ARCHIVED)
    
    def test_cleanup_old_sessions(self):
        """Тест очистки старых сессий"""
        # Создаем сессии
        session_id1 = self.session_manager.create_session("old_project")
        session_id2 = self.session_manager.create_session("new_project")
        
        # Имитируем старую сессию изменяя timestamp в базе данных напрямую
        import sqlite3
        conn = sqlite3.connect(self.session_manager.db_path)
        cursor = conn.cursor()
        old_timestamp = time.time() - (40 * 24 * 60 * 60)  # 40 дней назад
        cursor.execute('UPDATE sessions SET last_used = ? WHERE id = ?', (old_timestamp, session_id1))
        conn.commit()
        conn.close()
        
        # Запускаем очистку
        archived_count, deleted_count = self.session_manager.cleanup_old_sessions(30)
        
        # Проверяем, что старая сессия была заархивирована
        self.assertEqual(archived_count, 1)
        
        # Проверяем статус новой сессии
        new_session = self.session_manager.get_session(session_id2)
        self.assertEqual(new_session.status, SessionStatus.ACTIVE)
    
    def test_get_stats(self):
        """Тест получения статистики"""
        # Создаем несколько сессий
        self.session_manager.create_session("project1")
        self.session_manager.create_session("project2")
        session_id = self.session_manager.create_session("project3")
        self.session_manager.archive_session(session_id)
        
        # Получаем статистику
        stats = self.session_manager.get_stats()
        
        self.assertIn('total_sessions', stats)
        self.assertIn('unique_projects', stats)
        self.assertIn('status_distribution', stats)
        
        self.assertEqual(stats['total_sessions'], 3)
        self.assertEqual(stats['unique_projects'], 3)
        self.assertEqual(stats['status_distribution']['active'], 2)
        self.assertEqual(stats['status_distribution']['archived'], 1)


class TestAutoDetectKeyMoments(unittest.TestCase):
    """Тесты для автоматического обнаружения ключевых моментов"""
    
    def test_detect_error_solved(self):
        """Тест обнаружения решения ошибки"""
        content = "Fixed the bug in the authentication system"
        actions = ["fix_code"]
        files = ["auth.py"]
        
        moments = auto_detect_key_moments(content, actions, files)
        
        # Должен обнаружить момент решения ошибки
        self.assertGreater(len(moments), 0)
        moment_types = [moment[0] for moment in moments]
        self.assertIn(KeyMomentType.ERROR_SOLVED, moment_types)
    
    def test_detect_file_created(self):
        """Тест обнаружения создания файла"""
        content = "Created new user service"
        actions = ["create", "write"]
        files = ["user_service.py"]
        
        moments = auto_detect_key_moments(content, actions, files)
        
        # Должен обнаружить момент создания файла
        self.assertGreater(len(moments), 0)
        moment_types = [moment[0] for moment in moments]
        self.assertIn(KeyMomentType.FILE_CREATED, moment_types)
    
    def test_detect_feature_completed(self):
        """Тест обнаружения завершения функции"""
        content = "Successfully implemented the payment processing feature"
        actions = ["implement"]
        files = ["payment.py"]
        
        moments = auto_detect_key_moments(content, actions, files)
        
        # Должен обнаружить момент завершения функции
        self.assertGreater(len(moments), 0)
        moment_types = [moment[0] for moment in moments]
        self.assertIn(KeyMomentType.FEATURE_COMPLETED, moment_types)
    
    def test_detect_config_changed(self):
        """Тест обнаружения изменения конфигурации"""
        content = "Updated database configuration settings"
        actions = ["update_config"]
        files = ["config.yaml"]
        
        moments = auto_detect_key_moments(content, actions, files)
        
        # Должен обнаружить момент изменения конфигурации
        self.assertGreater(len(moments), 0)
        moment_types = [moment[0] for moment in moments]
        self.assertIn(KeyMomentType.CONFIG_CHANGED, moment_types)
    
    def test_no_moments_detected(self):
        """Тест отсутствия обнаруженных моментов"""
        content = "Just a regular message"
        actions = ["regular_action"]
        files = []
        
        moments = auto_detect_key_moments(content, actions, files)
        
        # Не должно быть обнаружено моментов
        self.assertEqual(len(moments), 0)


class TestDataModels(unittest.TestCase):
    """Тесты для моделей данных"""
    
    def test_message_serialization(self):
        """Тест сериализации/десериализации сообщения"""
        message = Message(
            id="test_id",
            timestamp=time.time(),
            role="user",
            content="Test content",
            actions=["action1", "action2"],
            files_involved=["file1.py", "file2.py"],
            metadata={"key": "value"}
        )
        
        # Сериализуем в словарь
        message_dict = message.to_dict()
        
        # Десериализуем обратно
        reconstructed_message = Message.from_dict(message_dict)
        
        # Проверяем, что все поля совпадают
        self.assertEqual(message.id, reconstructed_message.id)
        self.assertEqual(message.timestamp, reconstructed_message.timestamp)
        self.assertEqual(message.role, reconstructed_message.role)
        self.assertEqual(message.content, reconstructed_message.content)
        self.assertEqual(message.actions, reconstructed_message.actions)
        self.assertEqual(message.files_involved, reconstructed_message.files_involved)
        self.assertEqual(message.metadata, reconstructed_message.metadata)
    
    def test_key_moment_serialization(self):
        """Тест сериализации/десериализации ключевого момента"""
        key_moment = KeyMoment(
            id="test_id",
            timestamp=time.time(),
            type=KeyMomentType.BREAKTHROUGH,
            title="Test breakthrough",
            summary="Test summary",
            importance=9,
            files_involved=["file1.py"],
            context="Test context",
            related_messages=["msg1", "msg2"]
        )
        
        # Сериализуем в словарь
        moment_dict = key_moment.to_dict()
        
        # Десериализуем обратно
        reconstructed_moment = KeyMoment.from_dict(moment_dict)
        
        # Проверяем, что все поля совпадают
        self.assertEqual(key_moment.id, reconstructed_moment.id)
        self.assertEqual(key_moment.timestamp, reconstructed_moment.timestamp)
        self.assertEqual(key_moment.type, reconstructed_moment.type)
        self.assertEqual(key_moment.title, reconstructed_moment.title)
        self.assertEqual(key_moment.summary, reconstructed_moment.summary)
        self.assertEqual(key_moment.importance, reconstructed_moment.importance)
        self.assertEqual(key_moment.files_involved, reconstructed_moment.files_involved)
        self.assertEqual(key_moment.context, reconstructed_moment.context)
        self.assertEqual(key_moment.related_messages, reconstructed_moment.related_messages)


def run_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов системы управления сессиями...")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тестовые классы
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestAutoDetectKeyMoments))
    suite.addTests(loader.loadTestsFromTestCase(TestDataModels))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Выводим результат
    if result.wasSuccessful():
        print("\n✅ Все тесты прошли успешно!")
        return True
    else:
        print(f"\n❌ Провалилось тестов: {len(result.failures + result.errors)}")
        return False


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)