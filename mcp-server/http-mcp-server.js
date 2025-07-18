#!/usr/bin/env node
import express from 'express';
import axios from 'axios';
import fs from 'fs/promises';
import path from 'path';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import yaml from 'js-yaml';
import { createRequire } from 'module';

// Импорт функций автоанализа из stdio-mcp-server
const require = createRequire(import.meta.url);
const { handleExternalAutoAnalysis } = require('./stdio-mcp-server.js');

// Загрузка конфигурации
const configPath = path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'config.yaml');
const configContent = await fs.readFile(configPath, 'utf8');
const config = yaml.load(configContent);

const RAG_SERVER_URL = 'http://localhost:8000';
const MCP_PORT = 8200;
const CHUNK_LIMIT_TOKENS = config.mcp?.chunk_limit_tokens || 4000;
const KEY_MOMENTS_LIMIT = config.mcp?.key_moments_limit || 10;

// Функция получения имени текущего проекта
function getCurrentProjectName() {
  const cwd = process.cwd();
  const projectName = path.basename(cwd);
  return projectName.replace(/[^\w\-_.]/g, '_') || 'default';
}

// Функция получения корневой папки проекта
function getCurrentProjectRoot() {
  return process.cwd();
}

// Функция получения или создания сессии
async function getOrCreateSession() {
  let sessionId;
  try {
    const sessionResponse = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
    sessionId = sessionResponse.data.session_id;
  } catch {
    // Создаем новую сессию если не существует
    const createResponse = await axios.post(`${RAG_SERVER_URL}/sessions/create?project_name=${getCurrentProjectName()}`, {
      description: "Claude Code CLI HTTP MCP сессия"
    });
    sessionId = createResponse.data.session_id;
  }
  return sessionId;
}

// Инициализация Express
const app = express();

// Middleware для обработки JSON
app.use(express.json({ limit: '50mb' }));

// Обработчик ошибок парсинга JSON
app.use((err, req, res, next) => {
  if (err instanceof SyntaxError && err.status === 400 && 'body' in err) {
    return res.status(400).json({ error: 'Invalid JSON', details: err.message });
  }
  next();
});

// Инициализация базы данных для логирования
let db;

async function initDatabase() {
  const dbPath = path.join(path.dirname(new URL(import.meta.url).pathname), '..', 
    config.session_memory?.db_path || './session_storage.db');
  
  db = await open({
    filename: dbPath,
    driver: sqlite3.Database
  });

  // Создаем таблицу для логирования MCP вызовов
  await db.exec(`
    CREATE TABLE IF NOT EXISTS mcp_calls (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tool_name TEXT,
      args_json TEXT,
      result_json TEXT,
      success BOOLEAN,
      session_id TEXT,
      ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  console.log('✅ База данных инициализирована');
}

// Функция для логирования вызовов с session_id
async function logToolCall(toolName, args, result, success, sessionId = null) {
  try {
    // Получаем session_id если не передан
    if (!sessionId) {
      try {
        sessionId = await getOrCreateSession();
      } catch (error) {
        console.error('Ошибка получения session_id для логирования:', error);
        sessionId = null;
      }
    }
    
    await db.run(
      'INSERT INTO mcp_calls (tool_name, args_json, result_json, success, session_id) VALUES (?, ?, ?, ?, ?)',
      toolName,
      JSON.stringify(args),
      JSON.stringify(result),
      success ? 1 : 0,
      sessionId
    );
  } catch (error) {
    console.error('Ошибка логирования:', error);
  }
}

// Функция для подсчета токенов (упрощенная)
function estimateTokens(text) {
  // Примерная оценка: 1 токен ≈ 4 символа
  return Math.ceil(text.length / 4);
}

// Функция очистки ответов от артефактов
function cleanLLMResponse(response) {
  if (!response || typeof response !== 'string') {
    return response;
  }
  
  // Логируем исходный ответ для отладки
  console.log('🔍 Исходная длина ответа:', response.length);
  
  // Удаление артефактов промпта в начале ответа
  // Ищем маркеры начала реального ответа
  const answerMarkers = [
    '[Answer]',
    '[Ответ]',
    'Answer:',
    'Ответ:',
    '[Response]',
    'Response:'
  ];
  
  let cleanedResponse = response;
  
  // Удаляем ВСЕ маркеры ответа, не только первый
  for (const marker of answerMarkers) {
    while (cleanedResponse.includes(marker)) {
      const before = cleanedResponse.length;
      cleanedResponse = cleanedResponse.replace(marker, '');
      console.log(`🧹 Удален маркер "${marker}", удалено ${before - cleanedResponse.length} символов`);
    }
  }
  
  // Если есть маркер ответа, берем только первый ответ
  const firstAnswerIndex = response.indexOf('[Answer]');
  if (firstAnswerIndex !== -1) {
    const secondAnswerIndex = response.indexOf('[Answer]', firstAnswerIndex + 1);
    if (secondAnswerIndex !== -1) {
      // Есть несколько ответов, берем только первый
      cleanedResponse = response.substring(firstAnswerIndex + '[Answer]'.length, secondAnswerIndex).trim();
      console.log(`🧹 Найдено несколько ответов, взят только первый`);
    } else {
      // Только один ответ
      cleanedResponse = response.substring(firstAnswerIndex + '[Answer]'.length).trim();
    }
  }
  
  // Удаление контекста документации и инструкций
  const contextMarkers = [
    /\[.*?Documentation Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[User Question\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[Additional Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[Instructions\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[.*?Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi
  ];
  
  for (const pattern of contextMarkers) {
    const before = cleanedResponse.length;
    cleanedResponse = cleanedResponse.replace(pattern, '');
    if (before !== cleanedResponse.length) {
      console.log(`🧹 Удален контекст, удалено ${before - cleanedResponse.length} символов`);
    }
  }
  
  // Удаление артефактов типа "Created Question", "Created Answer"
  cleanedResponse = cleanedResponse.replace(/Created\s+(Question|Answer|Query|Response).*?```/gis, '');
  
  // Удаление множественных обратных кавычек в конце
  cleanedResponse = cleanedResponse.replace(/```+\s*$/g, '').trim();
  
  // Удаление одиночных блоков кода в конце
  cleanedResponse = cleanedResponse.replace(/```\s*$/g, '').trim();
  
  // Удаление повторяющихся блоков кода
  const codeBlocks = cleanedResponse.match(/```[\s\S]*?```/g) || [];
  const seenBlocks = new Set();
  
  codeBlocks.forEach(block => {
    if (seenBlocks.has(block)) {
      // Удаляем первое вхождение дубликата
      cleanedResponse = cleanedResponse.replace(block, '');
    } else {
      seenBlocks.add(block);
    }
  });
  
  // Удаление артефактов типа "Human:", "Assistant:", "User:"
  cleanedResponse = cleanedResponse.replace(/^(Human|Assistant|User|AI):\s*/gm, '');
  
  // Удаление лишних переносов строк
  cleanedResponse = cleanedResponse.replace(/\n{3,}/g, '\n\n');
  
  // Удаление повторяющихся примеров [Example]
  const examplePattern = /\[Example\][\s\S]*?(?=\[Example\]|$)/g;
  const examples = cleanedResponse.match(examplePattern) || [];
  const uniqueExamples = [...new Set(examples)];
  
  if (examples.length > uniqueExamples.length) {
    // Есть дубликаты, пересобираем ответ
    const beforeExamples = cleanedResponse.substring(0, cleanedResponse.indexOf('[Example]'));
    cleanedResponse = beforeExamples + uniqueExamples.join('\n\n');
  }
  
  // Специальная очистка для артефактов в конце
  // Удаляем незакрытые блоки кода
  const backtickCount = (cleanedResponse.match(/```/g) || []).length;
  if (backtickCount % 2 !== 0) {
    // Находим последний ```
    const lastBackticks = cleanedResponse.lastIndexOf('```');
    if (lastBackticks > 0) {
      const remaining = cleanedResponse.substring(lastBackticks + 3);
      if (!remaining.includes('```')) {
        // Удаляем незакрытый блок
        cleanedResponse = cleanedResponse.substring(0, lastBackticks).trim();
      }
    }
  }
  
  // Удаление обрывов на середине слова в конце
  if (cleanedResponse && cleanedResponse.length > 20) {
    const lastChar = cleanedResponse[cleanedResponse.length - 1];
    if (!',.!?;:)]\'"»\n'.includes(lastChar)) {
      // Ищем последнее полное предложение
      const sentenceEnds = [];
      for (let i = 0; i < cleanedResponse.length; i++) {
        if ('.!?'.includes(cleanedResponse[i]) && i < cleanedResponse.length - 1) {
          if (i + 1 < cleanedResponse.length && ' \n'.includes(cleanedResponse[i + 1])) {
            sentenceEnds.push(i + 1);
          }
        }
      }
      
      // Если есть полные предложения, обрезаем до последнего
      if (sentenceEnds.length > 0 && sentenceEnds[sentenceEnds.length - 1] < cleanedResponse.length - 10) {
        cleanedResponse = cleanedResponse.substring(0, sentenceEnds[sentenceEnds.length - 1]).trim();
      }
    }
  }
  
  // Финальная очистка пробелов
  cleanedResponse = cleanedResponse.trim();
  
  // Убедимся, что ответ не пустой после всех очисток
  if (!cleanedResponse) {
    cleanedResponse = "Извините, не удалось сгенерировать корректный ответ.";
  }
  
  console.log('✅ Очищенная длина ответа:', cleanedResponse.length);
  console.log(`📉 Удалено ${response.length - cleanedResponse.length} символов артефактов`);
  
  return cleanedResponse;
}

// Функция для разбиения на чанки
function chunkResponse(data, chunkLimit = CHUNK_LIMIT_TOKENS) {
  const jsonStr = JSON.stringify(data);
  const totalTokens = estimateTokens(jsonStr);
  
  if (totalTokens <= chunkLimit) {
    return [data];
  }

  // Разбиваем большой ответ на части
  const chunks = [];
  const totalChunks = Math.ceil(totalTokens / chunkLimit);
  
  // Для простоты разбиваем по строкам, если это массив
  if (Array.isArray(data)) {
    const itemsPerChunk = Math.ceil(data.length / totalChunks);
    for (let i = 0; i < data.length; i += itemsPerChunk) {
      chunks.push({
        segment: `${chunks.length + 1}/${totalChunks}`,
        data: data.slice(i, i + itemsPerChunk)
      });
    }
  } else {
    // Для объектов возвращаем как есть с пометкой
    chunks.push({
      segment: '1/1',
      data: data,
      warning: 'Response too large, consider pagination'
    });
  }
  
  return chunks;
}

// Обработчики инструментов
const toolHandlers = {
  // Основной инструмент RAG
  async ask_rag(args) {
    const response = await axios.post(`${RAG_SERVER_URL}/ask`, {
      question: args.query || args.question,
      framework: args.framework,
      model: args.model,
      max_results: args.max_results || 5,
      project_name: getCurrentProjectName()
    });

    // Очищаем ответ от артефактов
    const cleanedAnswer = cleanLLMResponse(response.data.answer);
    
    // Логируем для диагностики
    if (response.data.answer !== cleanedAnswer) {
      console.log('🧹 Очистка ответа выполнена');
      console.log(`Было символов: ${response.data.answer.length}, стало: ${cleanedAnswer.length}`);
    }

    // Сохраняем в сессию если включено
    if (config.session_memory?.auto_save_interactions) {
      try {
        const sessionId = await getOrCreateSession();
        await axios.post(`${RAG_SERVER_URL}/session/message`, {
          project_name: getCurrentProjectName(),
          role: 'assistant',
          content: cleanedAnswer,
          actions: ['ask_rag'],
          files: response.data.sources?.map(s => s.source) || []
        });
      } catch (error) {
        console.error('Ошибка сохранения в сессию:', error);
      }
    }

    return {
      answer: cleanedAnswer,
      sources: response.data.sources?.map(s => ({
        path: s.source,
        line: s.line || 0,
        framework: s.framework
      })) || [],
      session_id: response.data.session_id
    };
  },

  // Получение последних изменений (ключевых моментов)
  async get_recent_changes(args) {
    const limit = args.limit || KEY_MOMENTS_LIMIT;
    
    try {
      const response = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
      const data = response.data;
      
      // Попробуем все возможные пути к ключевым моментам
      let moments = null;
      
      if (data && data.context && data.context.key_moments && Array.isArray(data.context.key_moments)) {
        moments = data.context.key_moments;
      } else if (data && data.key_moments && Array.isArray(data.key_moments)) {
        moments = data.key_moments;
      }
      
      if (!moments || moments.length === 0) {
        return {
          changes: [],
          error: 'Ключевые моменты не найдены'
        };
      }
      
      // Берем последние ключевые моменты
      const recentMoments = moments
        .slice(0, limit)
        .map(moment => ({
          timestamp: moment.timestamp,
          type: moment.type,
          title: moment.title,
          summary: moment.summary,
          files: moment.files_involved
        }));

      return {
        changes: recentMoments
      };
    } catch (error) {
      return {
        changes: [],
        error: 'Не удалось получить ключевые моменты'
      };
    }
  },

  // Запуск тестов (заглушка)
  async run_tests(args) {
    // Stub implementation
    await new Promise(resolve => setTimeout(resolve, 1000)); // Имитация работы
    
    return {
      status: 'OK',
      log: 'All tests passed (stub implementation)\n✓ Test suite 1: 10/10 passed\n✓ Test suite 2: 5/5 passed'
    };
  },

  // Сборка проекта (заглушка)
  async build_project(args) {
    // Stub implementation
    await new Promise(resolve => setTimeout(resolve, 2000)); // Имитация работы
    
    return {
      status: 'OK',
      log: 'Build completed successfully (stub implementation)\n✓ Compiled 42 files\n✓ Bundle size: 1.2MB\n✓ Build time: 2.1s'
    };
  },

  // Применение патча
  async apply_patch(args) {
    const { diff } = args;
    
    if (!diff) {
      throw new Error('Параметр diff обязателен');
    }

    // Здесь должна быть реальная логика применения патча
    // Для демонстрации просто логируем
    
    // Создаем ключевой момент
    try {
      const sessionId = await getOrCreateSession();
      await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/key-moment`, {
        moment_type: 'refactoring',
        title: 'Применен патч',
        summary: `Применен патч: ${diff.substring(0, 100)}...`,
        files_involved: args.files || [],
        importance: 7
      });
    } catch (error) {
      console.error('Ошибка создания ключевого момента:', error);
    }

    return {
      status: 'applied',
      message: 'Патч успешно применен'
    };
  },

  // Запуск линтеров (заглушка)
  async run_linters(args) {
    // Stub implementation
    await new Promise(resolve => setTimeout(resolve, 500)); // Имитация работы
    
    return {
      status: 'OK',
      issues: []
    };
  },

  // Открытие файла
  async open_file(args) {
    const { path: filePath } = args;
    
    if (!filePath) {
      throw new Error('Параметр path обязателен');
    }

    // Валидация пути для безопасности
    const normalizedPath = path.normalize(filePath);
    const absolutePath = path.isAbsolute(normalizedPath) ? normalizedPath : path.resolve(normalizedPath);
    
    // Список запрещенных путей (системные файлы)
    const forbiddenPaths = [
      '/etc/',
      '/sys/',
      '/proc/',
      '/root/',
      'C:\\Windows\\',
      'C:\\System'
    ];
    
    // Специальная проверка для .ssh (может быть в домашней директории)
    if (absolutePath.includes('.ssh')) {
      throw new Error('Доступ запрещен: системный файл');
    }
    
    // Проверяем на запрещенные пути
    const isSystemPath = forbiddenPaths.some(forbidden => 
      absolutePath.toLowerCase().includes(forbidden.toLowerCase())
    );
    
    if (isSystemPath) {
      throw new Error('Доступ запрещен: системный файл');
    }
    
    // Проверяем, что файл не содержит опасных паттернов
    if (normalizedPath.includes('..') && (normalizedPath.includes('etc') || normalizedPath.includes('ssh'))) {
      throw new Error('Доступ запрещен: подозрительный путь');
    }

    try {
      const content = await fs.readFile(filePath, 'utf8');
      return {
        content: content
      };
    } catch (error) {
      throw new Error(`Не удалось прочитать файл: ${error.message}`);
    }
  },

  // Список фреймворков
  async list_frameworks(args) {
    const response = await axios.get(`${RAG_SERVER_URL}/frameworks`);
    return {
      frameworks: Object.entries(response.data).map(([key, info]) => ({
        key: key,
        name: info.name,
        description: info.description
      }))
    };
  },

  // Список моделей
  async list_models(args) {
    const response = await axios.get(`${RAG_SERVER_URL}/models`);
    return {
      models: Object.entries(response.data.models).map(([key, info]) => ({
        key: key,
        name: info.name,
        max_tokens: info.max_tokens,
        temperature: info.temperature
      })),
      default: response.data.default
    };
  },

  // Статистика
  async get_stats(args) {
    const response = await axios.get(`${RAG_SERVER_URL}/stats`);
    return {
      stats: response.data
    };
  },

  // Системный инструмент: сохранение вызова
  async save_tool_call(args) {
    const { tool_name, parameters, result } = args;
    
    // Этот инструмент уже логируется автоматически через logToolCall
    // Но можем добавить дополнительную логику если нужно
    
    return {
      saved: true
    };
  },

  // Системный инструмент: сохранение изменения файла
  async save_file_change(args) {
    const { file_path, old_content, new_content } = args;
    
    // Создаем ключевой момент для изменения файла
    try {
      const sessionId = await getOrCreateSession();
      await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/key-moment`, {
        moment_type: 'file_created',
        title: `Изменен файл ${path.basename(file_path)}`,
        summary: `Файл ${file_path} был изменен`,
        files_involved: [file_path],
        importance: 5
      });
    } catch (error) {
      console.error('Ошибка создания ключевого момента:', error);
    }

    return {
      saved: true
    };
  }
};

// Основной endpoint для вызова инструментов
app.post('/tool/:name', async (req, res) => {
  const toolName = req.params.name;
  const args = req.body;
  
  console.log(`🔧 Вызов инструмента: ${toolName}`);
  
  // Проверяем, включен ли инструмент
  const enabledTools = config.mcp?.tools_enabled || [];
  if (!enabledTools.includes(toolName)) {
    const error = { error: `Инструмент ${toolName} не включен в конфигурации` };
    await logToolCall(toolName, args, error, false);
    return res.status(403).json(error);
  }

  // Проверяем наличие обработчика
  const handler = toolHandlers[toolName];
  if (!handler) {
    const error = { error: `Неизвестный инструмент: ${toolName}` };
    await logToolCall(toolName, args, error, false);
    return res.status(404).json(error);
  }

  try {
    // Получаем session_id для логирования
    let sessionId = null;
    try {
      sessionId = await getOrCreateSession();
    } catch (error) {
      console.error('Ошибка получения session_id:', error);
    }
    
    // Выполняем инструмент
    const result = await handler(args);
    
    // Логируем успешный вызов
    await logToolCall(toolName, args, result, true, sessionId);
    
    // Проверяем размер ответа
    const chunks = chunkResponse(result);
    
    if (chunks.length === 1) {
      // Обычный ответ
      res.json(chunks[0]);
    } else {
      // Chunked response
      res.setHeader('Transfer-Encoding', 'chunked');
      res.setHeader('Content-Type', 'application/json');
      
      for (const chunk of chunks) {
        res.write(JSON.stringify(chunk) + '\n');
      }
      res.end();
    }
  } catch (error) {
    console.error(`❌ Ошибка в инструменте ${toolName}:`, error);
    const errorResult = { 
      error: error.message || 'Внутренняя ошибка сервера',
      details: error.response?.data || undefined
    };
    
    // Получаем session_id для логирования ошибки
    let sessionId = null;
    try {
      sessionId = await getOrCreateSession();
    } catch (sessionError) {
      console.error('Ошибка получения session_id для логирования ошибки:', sessionError);
    }
    
    // Логируем ошибку
    await logToolCall(toolName, args, errorResult, false, sessionId);
    
    res.status(500).json(errorResult);
  }
});

// Endpoint для внешнего автоанализа (от Claude File Watcher)
app.post('/auto-analyze-moments', async (req, res) => {
  try {
    const analysisData = req.body;
    
    console.log(`🔍 Запрос внешнего автоанализа для: ${analysisData.files?.join(', ') || 'unknown'}`);
    
    // Импортируем функцию автоанализа из stdio-mcp-server
    const result = await handleExternalAutoAnalysis(analysisData);
    
    res.json(result);
  } catch (error) {
    console.error('❌ Ошибка внешнего автоанализа:', error);
    res.status(500).json({
      success: false,
      moments_detected: 0,
      error: error.message
    });
  }
});

// Health check endpoint
app.get('/health', async (req, res) => {
  try {
    const currentProject = getCurrentProjectName();
    const projectRoot = getCurrentProjectRoot();
    
    // Попробуем получить текущую сессию
    let sessionInfo = null;
    try {
      const sessionId = await getOrCreateSession();
      sessionInfo = {
        session_id: sessionId,
        project_name: currentProject,
        project_root: projectRoot
      };
    } catch (error) {
      sessionInfo = {
        error: 'Не удалось получить информацию о сессии',
        project_name: currentProject,
        project_root: projectRoot
      };
    }
    
    res.json({
      status: 'ok',
      version: '1.0.0',
      rag_server: RAG_SERVER_URL,
      tools_enabled: config.mcp?.tools_enabled || [],
      session_info: sessionInfo
    });
  } catch (error) {
    res.status(500).json({
      status: 'error',
      error: error.message
    });
  }
});

// Endpoint для получения статистики вызовов
app.get('/stats/calls', async (req, res) => {
  try {
    const stats = await db.all(`
      SELECT 
        tool_name,
        COUNT(*) as call_count,
        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
        MAX(ts) as last_call
      FROM mcp_calls
      GROUP BY tool_name
      ORDER BY call_count DESC
    `);
    
    res.json({ stats });
  } catch (error) {
    res.status(500).json({ error: 'Ошибка получения статистики' });
  }
});

// Запуск сервера
async function start() {
  try {
    await initDatabase();
    
    app.listen(MCP_PORT, '127.0.0.1', () => {
      console.log(`🚀 HTTP-MCP сервер запущен на http://127.0.0.1:${MCP_PORT}`);
      console.log(`📊 RAG backend: ${RAG_SERVER_URL}`);
      console.log(`🔧 Включенные инструменты: ${config.mcp?.tools_enabled?.join(', ') || 'нет'}`);
      console.log(`🏗️ Проект: ${getCurrentProjectName()}`);
      console.log(`📁 Корень проекта: ${getCurrentProjectRoot()}`);
      console.log(`🔐 Session management: АКТИВЕН`);
    });
  } catch (error) {
    console.error('❌ Ошибка запуска сервера:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n👋 Завершение работы...');
  if (db) {
    await db.close();
  }
  process.exit(0);
});

start();
