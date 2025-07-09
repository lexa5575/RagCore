#!/usr/bin/env python3
"""
Система управления сессиями для RAG сервера с sliding window и ключевыми моментами
Подобно Cursor/Cline - умная память для контекста проектов
"""

import sqlite3
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@dataclass
class Message:
    """Отдельное сообщение в сессии"""
    id: str
    timestamp: float
    role: str  # user/assistant
    content: str
    actions: List[str]  # действия, которые были выполнены
    files_involved: List[str]  # файлы, которые были затронуты
    metadata: Dict[str, Any]  # дополнительная информация

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(**data)

@dataclass
class KeyMoment:
    """Важное событие в сессии"""
    id: str
    timestamp: float
    type: KeyMomentType
    title: str
    summary: str
    importance: int  # 1-10
    files_involved: List[str]
    context: str  # контекст вокруг момента
    related_messages: List[str]  # ID связанных сообщений

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyMoment':
        data['type'] = KeyMomentType(data['type'])
        return cls(**data)

@dataclass
class CompressedPeriod:
    """Сжатая история старых сообщений"""
    id: str
    start_time: float
    end_time: float
    summary: str
    key_achievements: List[str]
    files_involved: List[str]
    message_count: int
    key_moments: List[str]  # ID ключевых моментов из этого периода

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompressedPeriod':
        return cls(**data)

@dataclass
class Session:
    """Сессия работы с проектом"""
    id: str
    project_name: str
    created_at: float
    last_used: float
    status: SessionStatus
    
    # Sliding window - последние 200 сообщений
    messages: List[Message]
    
    # Ключевые моменты (сохраняются всегда)
    key_moments: List[KeyMoment]
    
    # Сжатая история старых сообщений
    compressed_history: List[CompressedPeriod]
    
    # Метаданные
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'project_name': self.project_name,
            'created_at': self.created_at,
            'last_used': self.last_used,
            'status': self.status.value,
            'messages': [msg.to_dict() for msg in self.messages],
            'key_moments': [km.to_dict() for km in self.key_moments],
            'compressed_history': [cp.to_dict() for cp in self.compressed_history],
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        return cls(
            id=data['id'],
            project_name=data['project_name'],
            created_at=data['created_at'],
            last_used=data['last_used'],
            status=SessionStatus(data['status']),
            messages=[Message.from_dict(msg) for msg in data['messages']],
            key_moments=[KeyMoment.from_dict(km) for km in data['key_moments']],
            compressed_history=[CompressedPeriod.from_dict(cp) for cp in data['compressed_history']],
            metadata=data['metadata']
        )

class SessionManager:
    """Основной класс управления сессиями"""
    
    def __init__(self, db_path: str = "session_storage.db", max_messages: int = 200):
        self.db_path = db_path
        self.max_messages = max_messages
        self.compression_threshold = 50  # убираем старые 50 сообщений при сжатии
        self._init_database()

    def _init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создание таблицы сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used REAL NOT NULL,
                status TEXT NOT NULL,
                data TEXT NOT NULL
            )
        ''')
        
        # Создание индексов
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project_name ON sessions(project_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_last_used ON sessions(last_used)')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def create_session(self, project_name: str) -> str:
        """Создание новой сессии для проекта"""
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        session = Session(
            id=session_id,
            project_name=project_name,
            created_at=current_time,
            last_used=current_time,
            status=SessionStatus.ACTIVE,
            messages=[],
            key_moments=[],
            compressed_history=[],
            metadata={}
        )
        
        self._save_session(session)
        logger.info(f"Created new session {session_id} for project {project_name}")
        return session_id

    def get_latest_session(self, project_name: str) -> Optional[str]:
        """Получение последней сессии проекта"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM sessions 
            WHERE project_name = ? AND status = ?
            ORDER BY last_used DESC 
            LIMIT 1
        ''', (project_name, SessionStatus.ACTIVE.value))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None

    def get_session(self, session_id: str) -> Optional[Session]:
        """Получение сессии по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT data FROM sessions WHERE id = ?', (session_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            data = json.loads(result[0])
            return Session.from_dict(data)
        return None

    def _save_session(self, session: Session):
        """Сохранение сессии в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sessions 
            (id, project_name, created_at, last_used, status, data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session.id,
            session.project_name,
            session.created_at,
            session.last_used,
            session.status.value,
            json.dumps(session.to_dict())
        ))
        
        conn.commit()
        conn.close()

    def add_message(self, session_id: str, role: str, content: str, 
                   actions: List[str] = None, files: List[str] = None,
                   metadata: Dict[str, Any] = None) -> bool:
        """Добавление сообщения в сессию"""
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        message = Message(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            role=role,
            content=content,
            actions=actions or [],
            files_involved=files or [],
            metadata=metadata or {}
        )

        session.messages.append(message)
        session.last_used = time.time()

        # Проверяем, нужно ли сжатие
        if len(session.messages) > self.max_messages:
            self._compress_session(session)

        self._save_session(session)
        logger.info(f"Added message to session {session_id}")
        return True

    def add_key_moment(self, session_id: str, moment_type: KeyMomentType, 
                      title: str, summary: str, importance: int = None,
                      files: List[str] = None, context: str = "",
                      related_messages: List[str] = None) -> bool:
        """Добавление ключевого момента"""
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        # Автоматическое определение важности по типу
        if importance is None:
            importance = MOMENT_IMPORTANCE.get(moment_type, 5)

        key_moment = KeyMoment(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            type=moment_type,
            title=title,
            summary=summary,
            importance=importance,
            files_involved=files or [],
            context=context,
            related_messages=related_messages or []
        )

        session.key_moments.append(key_moment)
        session.last_used = time.time()

        # Сортируем ключевые моменты по важности и времени
        session.key_moments.sort(key=lambda x: (-x.importance, -x.timestamp))

        self._save_session(session)
        logger.info(f"Added key moment '{title}' to session {session_id}")
        return True

    def _compress_session(self, session: Session):
        """Сжатие сессии - удаление старых сообщений с сохранением ключевых моментов"""
        if len(session.messages) <= self.max_messages:
            return

        # Сортируем сообщения по времени
        session.messages.sort(key=lambda x: x.timestamp)

        # Берем старые сообщения для сжатия
        messages_to_compress = session.messages[:self.compression_threshold]
        session.messages = session.messages[self.compression_threshold:]

        if not messages_to_compress:
            return

        # Создаем сжатый период
        start_time = messages_to_compress[0].timestamp
        end_time = messages_to_compress[-1].timestamp
        
        # Генерируем сводку
        summary = self._generate_summary(messages_to_compress)
        key_achievements = self._extract_achievements(messages_to_compress)
        files_involved = list(set(
            file for msg in messages_to_compress for file in msg.files_involved
        ))

        # Ключевые моменты из этого периода
        period_key_moments = [
            km.id for km in session.key_moments 
            if start_time <= km.timestamp <= end_time
        ]

        compressed_period = CompressedPeriod(
            id=str(uuid.uuid4()),
            start_time=start_time,
            end_time=end_time,
            summary=summary,
            key_achievements=key_achievements,
            files_involved=files_involved,
            message_count=len(messages_to_compress),
            key_moments=period_key_moments
        )

        session.compressed_history.append(compressed_period)
        
        # Сортируем сжатую историю по времени
        session.compressed_history.sort(key=lambda x: x.start_time)

        logger.info(f"Compressed {len(messages_to_compress)} messages from session {session.id}")

    def _generate_summary(self, messages: List[Message]) -> str:
        """Генерация сводки для сжатого периода"""
        if not messages:
            return ""

        # Простая сводка на основе ролей и действий
        user_messages = [msg for msg in messages if msg.role == "user"]
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]
        
        all_actions = []
        for msg in messages:
            all_actions.extend(msg.actions)
        
        unique_actions = list(set(all_actions))
        
        summary_parts = []
        
        if user_messages:
            summary_parts.append(f"Обработано {len(user_messages)} запросов пользователя")
        
        if assistant_messages:
            summary_parts.append(f"Дано {len(assistant_messages)} ответов")
        
        if unique_actions:
            summary_parts.append(f"Выполнены действия: {', '.join(unique_actions[:5])}")
        
        return "; ".join(summary_parts)

    def _extract_achievements(self, messages: List[Message]) -> List[str]:
        """Извлечение ключевых достижений из сообщений"""
        achievements = []
        
        for msg in messages:
            # Ищем паттерны достижений в контенте
            content_lower = msg.content.lower()
            
            if any(word in content_lower for word in ["completed", "finished", "done", "success"]):
                achievements.append(f"Завершено: {msg.content[:100]}...")
            
            if any(word in content_lower for word in ["created", "added", "implemented"]):
                achievements.append(f"Создано: {msg.content[:100]}...")
                
            if any(word in content_lower for word in ["fixed", "resolved", "solved"]):
                achievements.append(f"Исправлено: {msg.content[:100]}...")
        
        return achievements[:10]  # Максимум 10 достижений

    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получение полного контекста сессии для Claude"""
        session = self.get_session(session_id)
        if not session:
            return None

        # Сортируем ключевые моменты по важности
        top_key_moments = sorted(
            session.key_moments, 
            key=lambda x: (-x.importance, -x.timestamp)
        )[:20]  # Топ 20 ключевых моментов

        # Последние сообщения
        recent_messages = sorted(session.messages, key=lambda x: x.timestamp)[-50:]

        # Сжатая история
        compressed_summary = []
        for period in session.compressed_history:
            compressed_summary.append({
                'period': f"{datetime.fromtimestamp(period.start_time).strftime('%Y-%m-%d %H:%M')} - {datetime.fromtimestamp(period.end_time).strftime('%Y-%m-%d %H:%M')}",
                'summary': period.summary,
                'achievements': period.key_achievements,
                'files': period.files_involved
            })

        return {
            'session_id': session.id,
            'project_name': session.project_name,
            'created_at': datetime.fromtimestamp(session.created_at).isoformat(),
            'last_used': datetime.fromtimestamp(session.last_used).isoformat(),
            'status': session.status.value,
            'recent_messages': [msg.to_dict() for msg in recent_messages],
            'key_moments': [km.to_dict() for km in top_key_moments],
            'compressed_history': compressed_summary,
            'metadata': session.metadata,
            'stats': {
                'total_messages': len(session.messages),
                'total_key_moments': len(session.key_moments),
                'compressed_periods': len(session.compressed_history)
            }
        }

    def get_project_sessions(self, project_name: str) -> List[Dict[str, Any]]:
        """Получение всех сессий проекта"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, created_at, last_used, status FROM sessions 
            WHERE project_name = ?
            ORDER BY last_used DESC
        ''', (project_name,))
        
        results = cursor.fetchall()
        conn.close()
        
        sessions = []
        for row in results:
            sessions.append({
                'id': row[0],
                'created_at': datetime.fromtimestamp(row[1]).isoformat(),
                'last_used': datetime.fromtimestamp(row[2]).isoformat(),
                'status': row[3]
            })
        
        return sessions

    def archive_session(self, session_id: str) -> bool:
        """Архивирование сессии"""
        session = self.get_session(session_id)
        if not session:
            return False

        session.status = SessionStatus.ARCHIVED
        session.last_used = time.time()
        self._save_session(session)
        
        logger.info(f"Archived session {session_id}")
        return True

    def cleanup_old_sessions(self, days_threshold: int = 30):
        """Автоочистка старых сессий"""
        threshold_time = time.time() - (days_threshold * 24 * 60 * 60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Архивируем старые активные сессии
        cursor.execute('''
            UPDATE sessions 
            SET status = ?
            WHERE last_used < ? AND status = ?
        ''', (SessionStatus.ARCHIVED.value, threshold_time, SessionStatus.ACTIVE.value))
        
        archived_count = cursor.rowcount
        
        # Удаляем очень старые архивированные сессии
        very_old_threshold = time.time() - (90 * 24 * 60 * 60)  # 3 месяца
        cursor.execute('''
            DELETE FROM sessions 
            WHERE last_used < ? AND status = ?
        ''', (very_old_threshold, SessionStatus.ARCHIVED.value))
        
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cleanup completed: archived {archived_count}, deleted {deleted_count} sessions")
        return archived_count, deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики системы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT status, COUNT(*) FROM sessions GROUP BY status')
        status_counts = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(DISTINCT project_name) FROM sessions')
        unique_projects = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sessions')
        total_sessions = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_sessions': total_sessions,
            'unique_projects': unique_projects,
            'status_distribution': status_counts,
            'database_path': self.db_path
        }

# Вспомогательные функции для интеграции с RAG сервером
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