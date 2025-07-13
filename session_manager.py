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
    files_involved: List[str]  # Пути к файлам (старое поле)
    context: str  # контекст вокруг момента
    related_messages: List[str]  # ID связанных сообщений
    
    # Новые поля для улучшенной привязки файлов
    file_snapshots: List[str]  # ID снимков файлов
    code_snippets: List[str]   # ID фрагментов кода
    project_context: Dict[str, Any]  # Контекст проекта на момент события

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyMoment':
        data['type'] = KeyMomentType(data['type'])
        
        # Обратная совместимость - добавляем новые поля если их нет
        if 'file_snapshots' not in data:
            data['file_snapshots'] = []
        if 'code_snippets' not in data:
            data['code_snippets'] = []
        if 'project_context' not in data:
            data['project_context'] = {}
            
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
class FileSnapshot:
    """Снимок файла на момент взаимодействия"""
    id: str
    file_path: str
    content: str
    content_hash: str  # SHA-256 хеш содержимого
    language: str  # Определенный язык программирования
    size_bytes: int
    timestamp: float
    encoding: str  # UTF-8, ASCII и т.д.
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileSnapshot':
        return cls(**data)

@dataclass  
class CodeSnippet:
    """Фрагмент кода из файла"""
    id: str
    file_snapshot_id: str  # Связь со снимком файла
    content: str
    language: str
    start_line: int
    end_line: int
    context_before: str  # Несколько строк до фрагмента
    context_after: str   # Несколько строк после фрагмента
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeSnippet':
        return cls(**data)

@dataclass
class CodeSymbol:
    """AST символ из кода (функция, класс, переменная)"""
    id: str
    file_snapshot_id: str  # Связь со снимком файла
    symbol_type: str       # function, class, variable, import, etc.
    name: str             # Имя символа
    full_name: str        # Полное имя с namespace
    signature: str        # Сигнатура функции или определение
    docstring: str        # Документация
    start_line: int
    end_line: int
    language: str
    parent_symbol_id: Optional[str]  # Для вложенных символов
    visibility: str       # public, private, protected
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeSymbol':
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
        
        # Создание таблицы снимков файлов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_snapshots (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                language TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                encoding TEXT NOT NULL,
                session_id TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        # Создание таблицы фрагментов кода  
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS code_snippets (
                id TEXT PRIMARY KEY,
                file_snapshot_id TEXT NOT NULL,
                content TEXT NOT NULL,
                language TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                context_before TEXT NOT NULL,
                context_after TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (file_snapshot_id) REFERENCES file_snapshots (id)
            )
        ''')
        
        # Создание таблицы AST символов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS code_symbols (
                id TEXT PRIMARY KEY,
                file_snapshot_id TEXT NOT NULL,
                symbol_type TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                signature TEXT NOT NULL,
                docstring TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                language TEXT NOT NULL,
                parent_symbol_id TEXT,
                visibility TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (file_snapshot_id) REFERENCES file_snapshots (id),
                FOREIGN KEY (parent_symbol_id) REFERENCES code_symbols (id)
            )
        ''')
        
        # Создание индексов для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_snapshots_path ON file_snapshots(file_path)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_snapshots_hash ON file_snapshots(content_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_snippets_language ON code_snippets(language)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_symbols_name ON code_symbols(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_symbols_type ON code_symbols(symbol_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_symbols_language ON code_symbols(language)')
        
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
        try:
            session = self.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return False

        try:
            # Автоматическое определение важности по типу
            if importance is None:
                importance = MOMENT_IMPORTANCE.get(moment_type, 5)

            logger.info(f"Creating key moment: title='{title}', type={moment_type}, importance={importance}")

            key_moment = KeyMoment(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                type=moment_type,
                title=title,
                summary=summary,
                importance=importance,
                files_involved=files or [],
                context=context,
                related_messages=related_messages or [],
                # Новые поля для расширенной функциональности
                file_snapshots=[],
                code_snippets=[],
                project_context={}
            )

            logger.info(f"Key moment created successfully, adding to session")

            session.key_moments.append(key_moment)
            session.last_used = time.time()

            # Сортируем ключевые моменты по важности и времени
            session.key_moments.sort(key=lambda x: (-x.importance, -x.timestamp))

            logger.info(f"Saving session with {len(session.key_moments)} key moments")
            self._save_session(session)
            logger.info(f"Added key moment '{title}' to session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error in add_key_moment: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

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

    def save_file_snapshot(self, session_id: str, file_path: str, content: str, language: str = "") -> str:
        """Сохранение снимка файла"""
        import hashlib
        
        # Создаем хеш содержимого
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Проверяем, есть ли уже такой снимок
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM file_snapshots 
            WHERE file_path = ? AND content_hash = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (file_path, content_hash))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing[0]  # Возвращаем существующий ID
        
        # Создаем новый снимок
        snapshot_id = str(uuid.uuid4())
        current_time = time.time()
        
        # Определяем язык программирования если не указан
        if not language:
            language = self._detect_language(file_path)
        
        cursor.execute('''
            INSERT INTO file_snapshots 
            (id, file_path, content, content_hash, language, size_bytes, timestamp, encoding, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot_id, file_path, content, content_hash, language,
            len(content.encode('utf-8')), current_time, 'utf-8', session_id
        ))
        
        conn.commit()
        conn.close()
        
        # Автоматический парсинг AST символов для поддерживаемых языков
        if language in ['python', 'javascript', 'typescript']:
            try:
                self.parse_ast_symbols(snapshot_id, content, language, file_path)
                logger.info(f"AST symbols parsed for {file_path}")
            except Exception as e:
                logger.warning(f"Failed to parse AST for {file_path}: {e}")
        
        logger.info(f"File snapshot saved: {file_path} ({content_hash[:8]})")
        
        return snapshot_id

    def create_code_snippet(self, file_snapshot_id: str, content: str, start_line: int, 
                           end_line: int, context_before: str = "", context_after: str = "") -> str:
        """Создание фрагмента кода"""
        snippet_id = str(uuid.uuid4())
        current_time = time.time()
        
        # Получаем информацию о снимке файла
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT language FROM file_snapshots WHERE id = ?', (file_snapshot_id,))
        result = cursor.fetchone()
        language = result[0] if result else ""
        
        cursor.execute('''
            INSERT INTO code_snippets 
            (id, file_snapshot_id, content, language, start_line, end_line, 
             context_before, context_after, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snippet_id, file_snapshot_id, content, language, start_line, end_line,
            context_before, context_after, current_time
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Code snippet created: lines {start_line}-{end_line}")
        
        return snippet_id

    def search_file_content(self, query: str, language: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        """Поиск по содержимому файлов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        base_query = '''
            SELECT fs.id, fs.file_path, fs.language, fs.timestamp, 
                   SUBSTR(fs.content, 1, 500) as content_preview
            FROM file_snapshots fs
            WHERE fs.content LIKE ?
        '''
        
        params = [f'%{query}%']
        
        if language:
            base_query += ' AND fs.language = ?'
            params.append(language)
            
        base_query += ' ORDER BY fs.timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        
        formatted_results = []
        for row in results:
            formatted_results.append({
                'snapshot_id': row[0],
                'file_path': row[1], 
                'language': row[2],
                'timestamp': row[3],
                'content_preview': row[4]
            })
        
        conn.close()
        return formatted_results

    def get_file_history(self, file_path: str) -> List[Dict[str, Any]]:
        """Получение истории изменений файла"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, content_hash, size_bytes, timestamp
            FROM file_snapshots 
            WHERE file_path = ?
            ORDER BY timestamp DESC
        ''', (file_path,))
        
        results = cursor.fetchall()
        history = []
        
        for row in results:
            history.append({
                'snapshot_id': row[0],
                'content_hash': row[1],
                'size_bytes': row[2], 
                'timestamp': row[3]
            })
            
        conn.close()
        return history

    def _detect_language(self, file_path: str) -> str:
        """Определение языка программирования по расширению файла"""
        extension = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript', 
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.php': 'php',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.vue': 'vue',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.sql': 'sql',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.md': 'markdown'
        }
        
        return language_map.get(extension, 'text')

    def parse_ast_symbols(self, file_snapshot_id: str, content: str, language: str, file_path: str) -> List[str]:
        """Парсинг AST символов из кода"""
        symbols = []
        
        try:
            if language == 'python':
                symbols = self._parse_python_ast(file_snapshot_id, content, file_path)
            elif language in ['javascript', 'typescript']:
                symbols = self._parse_javascript_ast(file_snapshot_id, content, file_path)
            # Дополнительные языки можно добавить позже
        except Exception as e:
            logger.warning(f"Ошибка парсинга AST для {file_path}: {e}")
        
        return symbols

    def _parse_python_ast(self, file_snapshot_id: str, content: str, file_path: str) -> List[str]:
        """Парсинг Python AST"""
        symbols = []
        
        try:
            import ast
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                symbol_id = str(uuid.uuid4())
                current_time = time.time()
                
                if isinstance(node, ast.FunctionDef):
                    # Извлекаем сигнатуру функции
                    args = [arg.arg for arg in node.args.args]
                    signature = f"def {node.name}({', '.join(args)})"
                    
                    # Извлекаем docstring
                    docstring = ast.get_docstring(node) or ""
                    
                    symbol = CodeSymbol(
                        id=symbol_id,
                        file_snapshot_id=file_snapshot_id,
                        symbol_type="function",
                        name=node.name,
                        full_name=node.name,  # TODO: добавить namespace
                        signature=signature,
                        docstring=docstring,
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno),
                        language='python',
                        parent_symbol_id=None,  # TODO: обработать вложенные функции
                        visibility='public' if not node.name.startswith('_') else 'private',
                        timestamp=current_time
                    )
                    
                    self._save_code_symbol(symbol)
                    symbols.append(symbol_id)
                    
                elif isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node) or ""
                    
                    symbol = CodeSymbol(
                        id=symbol_id,
                        file_snapshot_id=file_snapshot_id,
                        symbol_type="class",
                        name=node.name,
                        full_name=node.name,
                        signature=f"class {node.name}",
                        docstring=docstring,
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno),
                        language='python',
                        parent_symbol_id=None,
                        visibility='public' if not node.name.startswith('_') else 'private',
                        timestamp=current_time
                    )
                    
                    self._save_code_symbol(symbol)
                    symbols.append(symbol_id)
                    
        except SyntaxError as e:
            logger.warning(f"Ошибка синтаксиса в Python файле {file_path}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге Python AST: {e}")
            
        return symbols

    def _parse_javascript_ast(self, file_snapshot_id: str, content: str, file_path: str) -> List[str]:
        """Парсинг JavaScript AST (базовый regex-based)"""
        symbols = []
        
        try:
            import re
            lines = content.split('\n')
            
            # Простые регексы для функций и классов
            function_pattern = r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\('
            arrow_function_pattern = r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
            class_pattern = r'^(?:export\s+)?class\s+(\w+)'
            
            for i, line in enumerate(lines, 1):
                line = line.strip()
                symbol_id = str(uuid.uuid4())
                current_time = time.time()
                
                # Функции
                func_match = re.match(function_pattern, line)
                arrow_match = re.match(arrow_function_pattern, line)
                class_match = re.match(class_pattern, line)
                
                if func_match:
                    name = func_match.group(1)
                    symbol = CodeSymbol(
                        id=symbol_id,
                        file_snapshot_id=file_snapshot_id,
                        symbol_type="function",
                        name=name,
                        full_name=name,
                        signature=line[:100],  # Первые 100 символов
                        docstring="",
                        start_line=i,
                        end_line=i,  # TODO: найти конец функции
                        language='javascript',
                        parent_symbol_id=None,
                        visibility='public',
                        timestamp=current_time
                    )
                    self._save_code_symbol(symbol)
                    symbols.append(symbol_id)
                    
                elif arrow_match:
                    name = arrow_match.group(1)
                    symbol = CodeSymbol(
                        id=symbol_id,
                        file_snapshot_id=file_snapshot_id,
                        symbol_type="function",
                        name=name,
                        full_name=name,
                        signature=line[:100],
                        docstring="",
                        start_line=i,
                        end_line=i,
                        language='javascript',
                        parent_symbol_id=None,
                        visibility='public',
                        timestamp=current_time
                    )
                    self._save_code_symbol(symbol)
                    symbols.append(symbol_id)
                    
                elif class_match:
                    name = class_match.group(1)
                    symbol = CodeSymbol(
                        id=symbol_id,
                        file_snapshot_id=file_snapshot_id,
                        symbol_type="class",
                        name=name,
                        full_name=name,
                        signature=line[:100],
                        docstring="",
                        start_line=i,
                        end_line=i,
                        language='javascript',
                        parent_symbol_id=None,
                        visibility='public',
                        timestamp=current_time
                    )
                    self._save_code_symbol(symbol)
                    symbols.append(symbol_id)
                    
        except Exception as e:
            logger.error(f"Ошибка при парсинге JavaScript AST: {e}")
            
        return symbols

    def _save_code_symbol(self, symbol: CodeSymbol):
        """Сохранение символа в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO code_symbols 
            (id, file_snapshot_id, symbol_type, name, full_name, signature, docstring,
             start_line, end_line, language, parent_symbol_id, visibility, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol.id, symbol.file_snapshot_id, symbol.symbol_type, symbol.name,
            symbol.full_name, symbol.signature, symbol.docstring, symbol.start_line,
            symbol.end_line, symbol.language, symbol.parent_symbol_id,
            symbol.visibility, symbol.timestamp
        ))
        
        conn.commit()
        conn.close()

    def search_symbols(self, query: str, symbol_type: str = "", language: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """Поиск по символам кода"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        base_query = '''
            SELECT cs.id, cs.name, cs.full_name, cs.symbol_type, cs.signature, 
                   cs.docstring, cs.start_line, cs.end_line, cs.language, cs.visibility,
                   fs.file_path
            FROM code_symbols cs
            JOIN file_snapshots fs ON cs.file_snapshot_id = fs.id
            WHERE (cs.name LIKE ? OR cs.signature LIKE ? OR cs.docstring LIKE ?)
        '''
        
        params = [f'%{query}%', f'%{query}%', f'%{query}%']
        
        if symbol_type:
            base_query += ' AND cs.symbol_type = ?'
            params.append(symbol_type)
            
        if language:
            base_query += ' AND cs.language = ?'
            params.append(language)
            
        base_query += ' ORDER BY cs.timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        
        formatted_results = []
        for row in results:
            formatted_results.append({
                'symbol_id': row[0],
                'name': row[1],
                'full_name': row[2],
                'symbol_type': row[3],
                'signature': row[4],
                'docstring': row[5],
                'start_line': row[6],
                'end_line': row[7],
                'language': row[8],
                'visibility': row[9],
                'file_path': row[10]
            })
        
        conn.close()
        return formatted_results

class MemoryBankManager:
    """Управление Memory Bank файлами по примеру Cursor/Cline"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.memory_bank_dir = self.project_root / "memory-bank"
        self._ensure_memory_bank_structure()
    
    def _ensure_memory_bank_structure(self):
        """Создание структуры Memory Bank"""
        self.memory_bank_dir.mkdir(exist_ok=True)
        
        # Создаем основные файлы Memory Bank
        memory_files = {
            "project-context.md": self._get_project_context_template(),
            "active-context.md": self._get_active_context_template(),
            "progress.md": self._get_progress_template(),
            "decisions.md": self._get_decisions_template(),
            "code-patterns.md": self._get_code_patterns_template()
        }
        
        for filename, template in memory_files.items():
            file_path = self.memory_bank_dir / filename
            if not file_path.exists():
                file_path.write_text(template, encoding='utf-8')
                logger.info(f"Создан Memory Bank файл: {filename}")
    
    def _get_project_context_template(self) -> str:
        """Шаблон для project-context.md"""
        return """# Project Context

## Technical Stack
- **Language**: 
- **Framework**: 
- **Database**: 
- **Tools**: 

## Architecture Principles
- 
- 
- 

## Development Guidelines
- 
- 
- 

## Key Dependencies
- 
- 
- 

## Environment Setup
```bash
# Add setup commands here
```

## Important Notes
- 
- 
- 

---
*Последнее обновление: автоматически*
"""

    def _get_active_context_template(self) -> str:
        """Шаблон для active-context.md"""
        return """# Active Context

## Current Session State
- **Focus**: 
- **Working on**: 
- **Last action**: 

## Ongoing Tasks
- [ ] 
- [ ] 
- [ ] 

## Recent Decisions
- 
- 
- 

## Open Questions
- 
- 
- 

## Next Steps
1. 
2. 
3. 

---
*Последнее обновление: автоматически*
"""

    def _get_progress_template(self) -> str:
        """Шаблон для progress.md"""
        return """# Progress Tracking

## Current Phase
**Phase**: 
**Status**: 
**Progress**: 0%

## Milestones
- [ ] **Milestone 1**: 
- [ ] **Milestone 2**: 
- [ ] **Milestone 3**: 

## Completed Work
- ✅ 
- ✅ 
- ✅ 

## In Progress
- 🔄 
- 🔄 
- 🔄 

## Blockers
- ❌ 
- ❌ 
- ❌ 

## Metrics
- **Lines of code**: 
- **Files modified**: 
- **Tests added**: 

---
*Последнее обновление: автоматически*
"""

    def _get_decisions_template(self) -> str:
        """Шаблон для decisions.md"""
        return """# Decision Log

## Architecture Decisions

### [ADR-001] Decision Title
**Date**: 
**Status**: Accepted/Rejected/Superseded
**Context**: 
**Decision**: 
**Consequences**: 

### [ADR-002] Decision Title  
**Date**: 
**Status**: 
**Context**: 
**Decision**: 
**Consequences**: 

## Technical Choices

### Framework Selection
**Choice**: 
**Reasoning**: 
**Alternatives considered**: 

### Database Design
**Choice**: 
**Reasoning**: 
**Alternatives considered**: 

## Pattern Decisions
- 
- 
- 

---
*Последнее обновление: автоматически*
"""

    def _get_code_patterns_template(self) -> str:
        """Шаблон для code-patterns.md"""
        return """# Code Patterns

## Established Patterns

### Error Handling
```python
# Example pattern
try:
    # code
except SpecificError as e:
    logger.error(f"Error: {e}")
    raise
```

### API Response Format
```json
{
  "success": true,
  "data": {},
  "error": null,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### File Organization
```
src/
├── components/
├── services/
├── utils/
└── types/
```

## Naming Conventions
- **Functions**: camelCase / snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Files**: kebab-case / snake_case

## Code Style Guidelines
- 
- 
- 

## Testing Patterns
```python
# Test pattern example
def test_function_name():
    # Arrange
    
    # Act
    
    # Assert
```

---
*Последнее обновление: автоматически*
"""

    def update_active_context(self, session_state: str, ongoing_tasks: List[str], recent_decisions: List[str]):
        """Обновление активного контекста"""
        active_context_path = self.memory_bank_dir / "active-context.md"
        
        content = f"""# Active Context

## Current Session State
{session_state}

## Ongoing Tasks
{chr(10).join([f"- [ ] {task}" for task in ongoing_tasks])}

## Recent Decisions
{chr(10).join([f"- {decision}" for decision in recent_decisions])}

## Next Steps
1. [Автоматически определяется из контекста]
2. [Обновляется при каждом ключевом моменте]

---
*Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        active_context_path.write_text(content, encoding='utf-8')
        logger.info("Обновлен active-context.md")

    def update_progress(self, completed_work: List[str], in_progress: List[str], blockers: List[str]):
        """Обновление прогресса"""
        progress_path = self.memory_bank_dir / "progress.md"
        
        content = f"""# Progress Tracking

## Completed Work
{chr(10).join([f"- ✅ {work}" for work in completed_work])}

## In Progress  
{chr(10).join([f"- 🔄 {work}" for work in in_progress])}

## Blockers
{chr(10).join([f"- ❌ {blocker}" for blocker in blockers])}

---
*Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        progress_path.write_text(content, encoding='utf-8')
        logger.info("Обновлен progress.md")

    def add_decision(self, title: str, context: str, decision: str, consequences: str):
        """Добавление нового решения"""
        decisions_path = self.memory_bank_dir / "decisions.md"
        
        if decisions_path.exists():
            content = decisions_path.read_text(encoding='utf-8')
        else:
            content = self._get_decisions_template()
        
        # Добавляем новое решение после заголовка
        new_decision = f"""
### [ADR-{datetime.now().strftime('%Y%m%d-%H%M')}] {title}
**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status**: Accepted
**Context**: {context}
**Decision**: {decision}
**Consequences**: {consequences}
"""
        
        # Вставляем после "## Architecture Decisions"
        insertion_point = content.find("## Architecture Decisions") + len("## Architecture Decisions")
        updated_content = content[:insertion_point] + new_decision + content[insertion_point:]
        
        decisions_path.write_text(updated_content, encoding='utf-8')
        logger.info(f"Добавлено решение: {title}")

    def get_memory_bank_context(self) -> Dict[str, str]:
        """Получение полного контекста Memory Bank"""
        context = {}
        
        for md_file in self.memory_bank_dir.glob("*.md"):
            try:
                context[md_file.stem] = md_file.read_text(encoding='utf-8')
            except Exception as e:
                logger.error(f"Ошибка чтения {md_file}: {e}")
                context[md_file.stem] = ""
        
        return context

    def search_memory_bank(self, query: str) -> List[Dict[str, str]]:
        """Поиск по содержимому Memory Bank"""
        results = []
        query_lower = query.lower()
        
        for md_file in self.memory_bank_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                if query_lower in content.lower():
                    # Найдем контекст вокруг найденного текста
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context_lines = lines[start:end]
                            
                            results.append({
                                'file': md_file.name,
                                'line_number': i + 1,
                                'context': '\n'.join(context_lines),
                                'match_line': line.strip()
                            })
                            break
            except Exception as e:
                logger.error(f"Ошибка поиска в {md_file}: {e}")
        
        return results

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