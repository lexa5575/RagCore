#!/usr/bin/env node

/**
 * 🤖 STDIO MCP Server для Claude Code CLI
 * Обеспечивает автоматическую интеграцию с RAG системой
 * Все HTTP запросы идут к существующему RAG серверу на порту 8000
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from 'axios';
import fs from 'fs/promises';
import path from 'path';
import yaml from 'js-yaml';

// Загрузка конфигурации
const configPath = path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'config.yaml');
const configContent = await fs.readFile(configPath, 'utf8');
const config = yaml.load(configContent);

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

// Функция получения или создания сессии для текущего проекта
async function getOrCreateSession() {
  try {
    // Пытаемся получить последнюю сессию проекта
    const sessionResponse = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
    return sessionResponse.data.session_id;
  } catch (error) {
    // Если не найдена, создаем новую сессию
    try {
      const createResponse = await axios.post(`${RAG_SERVER_URL}/sessions/create`, {
        project_name: getCurrentProjectName()
      });
      return createResponse.data.session_id;
    } catch (createError) {
      throw new Error(`Не удалось создать сессию: ${createError.message}`);
    }
  }
}

// Конфигурация
const RAG_SERVER_URL = process.env.RAG_SERVER_URL || 'http://localhost:8000';
const CHUNK_LIMIT_TOKENS = config.mcp?.chunk_limit_tokens || 4000;
const KEY_MOMENTS_LIMIT = config.mcp?.key_moments_limit || 10;

// Инициализация сервера
const server = new Server(
  {
    name: "rag-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Функция очистки ответов RAG (та же логика из HTTP сервера)
function cleanRAGResponse(response) {
  if (!response || typeof response !== 'string') {
    return response;
  }
  
  // Удаляем артефакты промпта
  let cleanedResponse = response;
  
  // Удаление маркеров ответа
  const answerMarkers = [
    '[Answer]',
    '[Ответ]',
    'Answer:',
    'Ответ:',
    '[Response]',
    'Response:'
  ];
  
  for (const marker of answerMarkers) {
    while (cleanedResponse.includes(marker)) {
      cleanedResponse = cleanedResponse.replace(marker, '');
    }
  }
  
  // Если есть маркер ответа, берем только первый ответ
  const firstAnswerIndex = response.indexOf('[Answer]');
  if (firstAnswerIndex !== -1) {
    const secondAnswerIndex = response.indexOf('[Answer]', firstAnswerIndex + 1);
    if (secondAnswerIndex !== -1) {
      cleanedResponse = response.substring(firstAnswerIndex + '[Answer]'.length, secondAnswerIndex).trim();
    } else {
      cleanedResponse = response.substring(firstAnswerIndex + '[Answer]'.length).trim();
    }
  }
  
  // Удаление контекста документации
  const contextMarkers = [
    /\[.*?Documentation Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[User Question\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[Additional Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[Instructions\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi,
    /\[.*?Context\][\s\S]*?(?=\[Answer\]|\[Ответ\]|Answer:|Ответ:|$)/gi
  ];
  
  for (const pattern of contextMarkers) {
    cleanedResponse = cleanedResponse.replace(pattern, '');
  }
  
  // Удаление множественных обратных кавычек
  cleanedResponse = cleanedResponse.replace(/```+\s*$/g, '').trim();
  
  // Удаление артефактов типа "Human:", "Assistant:", "User:"
  cleanedResponse = cleanedResponse.replace(/^(Human|Assistant|User|AI):\s*/gm, '');
  
  // Удаление лишних переносов строк
  cleanedResponse = cleanedResponse.replace(/\n{3,}/g, '\n\n');
  
  // Финальная очистка
  cleanedResponse = cleanedResponse.trim();
  
  if (!cleanedResponse) {
    cleanedResponse = "Извините, не удалось сгенерировать корректный ответ.";
  }
  
  return cleanedResponse;
}

// 🤖 Автодетекция ключевых моментов (портирована из session_manager.py)
const KEY_MOMENT_TYPES = {
  ERROR_SOLVED: "error_solved",
  FEATURE_COMPLETED: "feature_completed", 
  CONFIG_CHANGED: "config_changed",
  BREAKTHROUGH: "breakthrough",
  FILE_CREATED: "file_created",
  DEPLOYMENT: "deployment",
  IMPORTANT_DECISION: "important_decision",
  REFACTORING: "refactoring",
  TEST_ADDED: "test_added"
};

const MOMENT_IMPORTANCE = {
  [KEY_MOMENT_TYPES.BREAKTHROUGH]: 9,
  [KEY_MOMENT_TYPES.ERROR_SOLVED]: 8,
  [KEY_MOMENT_TYPES.DEPLOYMENT]: 8,
  [KEY_MOMENT_TYPES.FEATURE_COMPLETED]: 7,
  [KEY_MOMENT_TYPES.IMPORTANT_DECISION]: 7,
  [KEY_MOMENT_TYPES.CONFIG_CHANGED]: 6,
  [KEY_MOMENT_TYPES.REFACTORING]: 6,
  [KEY_MOMENT_TYPES.TEST_ADDED]: 6,
  [KEY_MOMENT_TYPES.FILE_CREATED]: 5,
};

function autoDetectKeyMoments(toolName, args, content = "", files = []) {
  const moments = [];
  const contentLower = content.toLowerCase();
  const toolNameLower = toolName.toLowerCase();
  
  // Анализ типов файлов для контекста
  const fileTypes = files.map(file => {
    const ext = file.split('.').pop()?.toLowerCase();
    if (['js', 'ts', 'jsx', 'tsx'].includes(ext)) return 'javascript';
    if (['py'].includes(ext)) return 'python';
    if (['yaml', 'yml'].includes(ext)) return 'config';
    if (['json'].includes(ext)) return 'config';
    if (['md'].includes(ext)) return 'documentation';
    if (['test.js', 'spec.js', 'test.ts', 'spec.ts'].some(t => file.includes(t))) return 'test';
    return ext || 'unknown';
  });
  
  // Размер контента для определения масштаба изменений
  const contentSize = content.length;
  const isLargeChange = contentSize > 1000;
  const isMediumChange = contentSize > 300;
  
  // Обнаружение решения ошибок (русские и английские слова)
  const errorKeywords = [
    // Английские
    "error", "fix", "fixed", "solved", "resolved", "bug", "issue", "problem", 
    "debug", "debugged", "patch", "patched", "hotfix", "bugfix", "correction",
    "trouble", "troubleshoot", "repair", "repaired", "broken", "crash", "failed",
    // Русские
    "ошибка", "исправлен", "решен", "решена", "исправлена", "починен", "починена",
    "баг", "проблема", "устранен", "устранена", "фикс", "исправление", "отладка",
    "отлажен", "патч", "хотфикс", "багфикс", "коррекция", "неисправность",
    "сломан", "сломана", "падение", "крах", "провал", "сбой"
  ];
  
  if (errorKeywords.some(word => contentLower.includes(word))) {
    const fileContext = fileTypes.length > 0 ? ` в ${fileTypes.join(', ')} файлах` : '';
    const scaleContext = isLargeChange ? ' (крупное исправление)' : isMediumChange ? ' (среднее исправление)' : '';
    
    moments.push({
      type: KEY_MOMENT_TYPES.ERROR_SOLVED,
      title: `Решение ошибки${fileContext}${scaleContext}`,
      summary: `Исправлена ошибка через ${toolName}${fileContext}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.ERROR_SOLVED] + (isLargeChange ? 1 : 0),
      files: files
    });
  }
  
  // Обнаружение создания файлов
  const creationActions = [
    // Английские
    "create", "created", "write", "wrote", "written", "add", "added", "new file", 
    "generate", "generated", "build", "built", "make", "made", "initialize", "init",
    // Русские  
    "создать", "создан", "создана", "написать", "написал", "написана", "добавить",
    "добавлен", "добавлена", "новый файл", "генерировать", "сгенерирован", "построить",
    "построен", "сделать", "сделан", "инициализация", "инициализирован"
  ];
  if ((creationActions.some(action => toolNameLower.includes(action) || contentLower.includes(action)) && files.length > 0) ||
      (toolName === "open_file" && args.path && contentLower.includes("создан"))) {
    const fileName = files[0] || args.path || "";
    const fileType = fileTypes[0] || fileName.split('.').pop() || 'файл';
    const scaleContext = isLargeChange ? ' (крупный файл)' : '';
    
    moments.push({
      type: KEY_MOMENT_TYPES.FILE_CREATED,
      title: `Создание ${fileType} файла${scaleContext}`,
      summary: `Создан ${fileType} файл ${fileName} через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.FILE_CREATED] + (fileType === 'test' ? 1 : 0),
      files: files.length > 0 ? files : (args.path ? [args.path] : [])
    });
  }
  
  // Обнаружение завершения функций (русские и английские слова)
  const completionKeywords = [
    // Английские
    "completed", "finished", "done", "implemented", "ready", "success", "successful",
    "accomplish", "accomplished", "achieve", "achieved", "feature", "functionality",
    "working", "works", "functional", "delivered", "deploy", "deployed",
    // Русские
    "завершен", "завершена", "готов", "готова", "выполнен", "выполнена",
    "реализован", "реализована", "закончен", "закончена", "сделан", "сделана",
    "достигнут", "достигнута", "функция", "функциональность", "работает",
    "рабочий", "функционал", "доставлен", "доставлена", "развернут", "развернута"
  ];
  
  if (completionKeywords.some(word => contentLower.includes(word))) {
    moments.push({
      type: KEY_MOMENT_TYPES.FEATURE_COMPLETED,
      title: "Завершение функции",
      summary: `Реализована функция через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.FEATURE_COMPLETED],
      files: files
    });
  }
  
  // Обнаружение изменений конфигурации (русские и английские слова)
  const configKeywords = [
    // Английские
    "config", "configuration", "settings", "yaml", "json", "env", "environment",
    "setup", "options", "preferences", "properties", "variables", "constants",
    "parameters", "configure", "configured", "setup", "initialized",
    // Русские
    "конфигурация", "настройки", "настройка", "конфиг", "параметры", "переменные",
    "константы", "опции", "предпочтения", "свойства", "настроен", "настроена",
    "сконфигурирован", "сконфигурирована", "установка", "инициализация"
  ];
  
  if ((configKeywords.some(word => contentLower.includes(word)) && files.length > 0) ||
      (files.some(file => file.includes('.yaml') || file.includes('.json') || file.includes('.config')))) {
    moments.push({
      type: KEY_MOMENT_TYPES.CONFIG_CHANGED,
      title: "Изменение конфигурации",
      summary: `Обновлена конфигурация через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.CONFIG_CHANGED],
      files: files
    });
  }
  
  // Обнаружение рефакторинга (русские и английские слова)
  const refactoringKeywords = [
    // Английские
    "refactor", "refactored", "refactoring", "restructure", "restructured", 
    "optimize", "optimized", "optimization", "improve", "improved", "improvement",
    "enhance", "enhanced", "enhancement", "redesign", "redesigned", "rewrite", "rewritten",
    "cleanup", "clean", "simplified", "streamline", "streamlined", "modernize", "modernized",
    // Русские
    "рефакторинг", "рефакторил", "рефакторила", "рефакторить", "оптимизирован", "оптимизирована",
    "переработан", "переработана", "реструктуризация", "улучшен", "улучшена", "улучшение",
    "усовершенствован", "усовершенствована", "переписан", "переписана", "очистка", "очищен",
    "упрощен", "упрощена", "модернизирован", "модернизирована", "обновлен", "обновлена"
  ];
  
  if (refactoringKeywords.some(word => contentLower.includes(word))) {
    moments.push({
      type: KEY_MOMENT_TYPES.REFACTORING,
      title: "Рефакторинг кода",
      summary: `Проведен рефакторинг через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.REFACTORING],
      files: files
    });
  }
  
  // Обнаружение важных решений (русские и английские слова)
  const decisionKeywords = [
    // Английские
    "decided", "decision", "choice", "selected", "approach",
    // Русские
    "решил", "решила", "решение", "выбор", "подход", "стратегия",
    "принято решение", "выбран", "выбрана"
  ];
  
  if (decisionKeywords.some(word => contentLower.includes(word))) {
    moments.push({
      type: KEY_MOMENT_TYPES.IMPORTANT_DECISION,
      title: "Важное решение",
      summary: `Принято решение через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.IMPORTANT_DECISION],
      files: files
    });
  }
  
  // Обнаружение добавления тестов (русские и английские слова)
  const testKeywords = [
    // Английские
    "test", "tests", "testing", "spec", "specs", "unit test", "integration test",
    "test case", "test suite", "assert", "assertion", "mock", "mocked", "stub",
    "coverage", "jest", "mocha", "cypress", "playwright", "vitest", "karma",
    // Русские
    "тест", "тесты", "тестирование", "спек", "спеки", "юнит тест", "интеграционный тест",
    "тестовый случай", "набор тестов", "утверждение", "мок", "заглушка", "покрытие"
  ];
  
  if ((testKeywords.some(word => contentLower.includes(word)) && files.length > 0) ||
      (files.some(file => file.includes('.test.') || file.includes('.spec.') || 
       file.includes('test/') || file.includes('tests/') || file.includes('__tests__/')))) {
    moments.push({
      type: KEY_MOMENT_TYPES.TEST_ADDED,
      title: "Добавлен тест",
      summary: `Добавлен тест через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.TEST_ADDED],
      files: files
    });
  }
  
  return moments;
}

// Автоматическое сохранение обнаруженных ключевых моментов
async function autoSaveKeyMoments(toolName, args, content = "", files = []) {
  try {
    const detectedMoments = autoDetectKeyMoments(toolName, args, content, files);
    
    if (detectedMoments.length === 0) {
      return detectedMoments; // Возвращаем пустой массив
    }
    
    // Создаем или получаем текущую сессию
    const sessionId = await getOrCreateSession();
    
    // Сохраняем каждый обнаруженный ключевой момент
    for (const moment of detectedMoments) {
      try {
        await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/key-moment`, {
          moment_type: moment.type,
          title: moment.title,
          summary: moment.summary,
          files_involved: moment.files || [],
          importance: moment.importance
        });
        
        console.error(`🎯 Автосохранен ключевой момент: ${moment.title} (${moment.type})`);
      } catch (error) {
        console.error(`❌ Ошибка автосохранения момента ${moment.title}:`, error.message);
      }
    }
    
    return detectedMoments;
    
  } catch (error) {
    console.error(`❌ Ошибка автодетекции ключевых моментов:`, error.message);
    return [];
  }
}

// API endpoint для внешнего автоанализа (от Claude File Watcher)
async function handleExternalAutoAnalysis(analysisData) {
  try {
    const { tool_name, args, content, files } = analysisData;
    
    console.error(`🔍 Внешний автоанализ: ${tool_name} для ${files.join(', ')}`);
    
    // Выполняем автодетекцию
    const detectedMoments = await autoSaveKeyMoments(tool_name, args || {}, content, files);
    
    return {
      success: true,
      moments_detected: detectedMoments.length,
      moments: detectedMoments.map(m => ({
        type: m.type,
        title: m.title,
        importance: m.importance
      }))
    };
    
  } catch (error) {
    console.error(`❌ Ошибка внешнего автоанализа:`, error.message);
    return {
      success: false,
      moments_detected: 0,
      error: error.message
    };
  }
}

// Функция для логирования вызовов в RAG систему
async function logToolCall(toolName, args, result, success) {
  try {
    // Получаем session_id для добавления сообщения
    const sessionId = await getOrCreateSession();
    
    // Используем правильный endpoint для добавления сообщения в сессию
    await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/message`, {
      role: "assistant",
      content: `MCP Tool: ${toolName} - ${success ? 'Success' : 'Failed'}`,
      actions: [toolName],
      files: result?.files || []
    }).catch(() => {}); // Игнорируем ошибки логирования
  } catch (error) {
    // Логирование не критично, просто выводим в консоль
    console.error(`📝 Лог инструмента ${toolName}: ${success ? 'Success' : 'Failed'}`);
  }
}

// Определение инструментов
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "ask_rag",
        description: "Получить ответ от RAG системы на технические вопросы по Laravel, Vue.js, Filament и др. Автоматически сохраняет контекст в сессию.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Вопрос или запрос для RAG системы",
            },
            framework: {
              type: "string",
              description: "Фреймворк для поиска: laravel, vue, filament, alpine, inertia, tailwindcss",
              enum: ["laravel", "vue", "filament", "alpine", "inertia", "tailwindcss"],
            },
            max_results: {
              type: "number",
              description: "Максимальное количество результатов (по умолчанию 5)",
              default: 5,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "list_frameworks",
        description: "Получить список доступных фреймворков в RAG системе с количеством документов",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "get_stats",
        description: "Получить статистику документов и использования RAG системы",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "get_recent_changes",
        description: "Получить последние ключевые моменты из текущей сессии",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "number",
              description: "Количество моментов для получения (по умолчанию 10)",
              default: 10,
            },
          },
        },
      },
      {
        name: "save_key_moment",
        description: "Сохранить важный момент в текущую сессию (например, решение проблемы, важное изменение кода)",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Краткое название ключевого момента",
            },
            summary: {
              type: "string", 
              description: "Подробное описание того, что произошло",
            },
            type: {
              type: "string",
              description: "Тип момента",
              enum: ["error_solved", "feature_completed", "config_changed", "breakthrough", "file_created", "deployment", "important_decision", "refactoring"],
              default: "feature_completed"
            },
            files: {
              type: "array",
              items: { type: "string" },
              description: "Список затронутых файлов",
              default: []
            },
            importance: {
              type: "number",
              description: "Важность от 1 до 10",
              minimum: 1,
              maximum: 10,
              default: 5
            }
          },
          required: ["title", "summary"],
        },
      },
      {
        name: "open_file",
        description: "Безопасно открыть и прочитать файл из проекта с автосохранением снимка",
        inputSchema: {
          type: "object",
          properties: {
            path: {
              type: "string",
              description: "Путь к файлу для чтения",
            },
          },
          required: ["path"],
        },
      },
      {
        name: "search_files",
        description: "Поиск по содержимому сохраненных файлов в проекте",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Поисковый запрос по содержимому файлов",
            },
            language: {
              type: "string",
              description: "Фильтр по языку программирования (python, javascript, etc.)",
              default: "",
            },
            limit: {
              type: "number",
              description: "Максимальное количество результатов",
              default: 10,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "get_file_history",
        description: "Получить историю изменений конкретного файла",
        inputSchema: {
          type: "object",
          properties: {
            file_path: {
              type: "string",
              description: "Путь к файлу для получения истории",
            },
          },
          required: ["file_path"],
        },
      },
      {
        name: "init_memory_bank",
        description: "Инициализировать Memory Bank структуру для проекта",
        inputSchema: {
          type: "object",
          properties: {
            project_root: {
              type: "string",
              description: "Корневая папка проекта (по умолчанию текущая)",
              default: "",
            },
          },
        },
      },
      {
        name: "get_memory_context",
        description: "Получить текущий контекст из Memory Bank",
        inputSchema: {
          type: "object",
          properties: {
            context_type: {
              type: "string",
              description: "Тип контекста: project, active, progress, decisions, patterns",
              enum: ["project", "active", "progress", "decisions", "patterns"],
              default: "active",
            },
          },
        },
      },
      {
        name: "update_active_context",
        description: "Обновить активный контекст сессии",
        inputSchema: {
          type: "object",
          properties: {
            session_state: {
              type: "string",
              description: "Описание текущего состояния сессии",
            },
            tasks: {
              type: "array",
              items: { type: "string" },
              description: "Список текущих задач",
              default: [],
            },
            decisions: {
              type: "array",
              items: { type: "string" },
              description: "Список недавних решений",
              default: [],
            },
          },
          required: ["session_state"],
        },
      },
      {
        name: "log_decision",
        description: "Зафиксировать важное решение в Memory Bank",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Название решения",
            },
            context: {
              type: "string",
              description: "Контекст и причины решения",
            },
            decision: {
              type: "string",
              description: "Принятое решение",
            },
            consequences: {
              type: "string",
              description: "Последствия и влияние решения",
            },
          },
          required: ["title", "context", "decision"],
        },
      },
      {
        name: "search_memory_bank",
        description: "Поиск по содержимому Memory Bank файлов",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Поисковый запрос",
            },
          },
          required: ["query"],
        },
      },
      {
        name: "search_symbols",
        description: "Поиск по символам кода (функции, классы, переменные) с AST-анализом",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Поисковый запрос по названию или сигнатуре символа",
            },
            symbol_type: {
              type: "string",
              description: "Тип символа: function, class, variable, import",
              default: "",
            },
            language: {
              type: "string",
              description: "Язык программирования: python, javascript, typescript",
              default: "",
            },
            limit: {
              type: "number",
              description: "Максимальное количество результатов",
              default: 20,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "enhance_prompt",
        description: "Анализ и улучшение пользовательских промтов через локальную LLM",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Пользовательский промт для анализа и улучшения",
            },
            force_enhance: {
              type: "boolean",
              description: "Принудительное улучшение даже для хороших промтов",
              default: false,
            },
            analysis_only: {
              type: "boolean", 
              description: "Только анализ без улучшения",
              default: false,
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "analyze_prompt",
        description: "Анализ промта на необходимость улучшения без обращения к LLM",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Пользовательский промт для анализа",
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "process_prompt_with_triggers",
        description: "Обработка промта с поддержкой триггера улучшения (добавьте ??? в конец промта)",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Пользовательский промт. Добавьте ??? в конец для автоматического улучшения",
            },
            project_context: {
              type: "object",
              description: "Контекст проекта для улучшения",
              default: {},
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "smart_process_prompt",
        description: "Интеллектуальная обработка промта с автоматическим улучшением",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Пользовательский промт для интеллектуальной обработки",
            },
            threshold: {
              type: "number",
              description: "Порог для автоматического улучшения (0.0-1.0)",
              default: 0.3,
            },
            max_time: {
              type: "number",
              description: "Максимальное время обработки в секундах",
              default: 5.0,
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "should_process_prompt",
        description: "Проверка нужно ли обрабатывать промт автоматически",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Пользовательский промт для проверки",
            },
            threshold: {
              type: "number",
              description: "Порог качества промта (0.0-1.0)",
              default: 0.3,
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "get_session_summary",
        description: "Получить краткий обзор последней работы в проекте",
        inputSchema: {
          type: "object",
          properties: {
            days_back: {
              type: "number",
              description: "Количество дней назад для обзора",
              default: 1,
            },
          },
        },
      },
      {
        name: "get_project_status",
        description: "Получить текущее состояние проекта с полной статистикой",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "get_recent_work",
        description: "Получить хронологию работы за последние N дней",
        inputSchema: {
          type: "object",
          properties: {
            days_back: {
              type: "number",
              description: "Количество дней для анализа",
              default: 3,
            },
          },
        },
      },
      {
        name: "initialize_context",
        description: "Автоматическая инициализация контекста для нового Claude",
        inputSchema: {
          type: "object",
          properties: {
            include_code_examples: {
              type: "boolean",
              description: "Включать ли примеры кода в контекст",
              default: true,
            },
          },
        },
      },
      {
        name: "search_project_memory",
        description: "Поиск по памяти проекта (код, решения, ключевые моменты)",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Поисковый запрос"
            },
            content_type: {
              type: "string",
              description: "Тип контента: code, decision, key_moment, session"
            },
            session_id: {
              type: "string",
              description: "ID сессии для фильтрации"
            },
            min_importance: {
              type: "number",
              description: "Минимальная важность (0-10)",
              default: 0
            },
            limit: {
              type: "number",
              description: "Максимальное количество результатов",
              default: 5
            }
          },
          required: ["query"]
        }
      },
      {
        name: "add_project_memory",
        description: "Добавление записи в память проекта",
        inputSchema: {
          type: "object",
          properties: {
            content_type: {
              type: "string",
              description: "Тип контента: code, decision, key_moment, session"
            },
            title: {
              type: "string",
              description: "Заголовок записи"
            },
            content: {
              type: "string",
              description: "Содержимое записи"
            },
            session_id: {
              type: "string",
              description: "ID сессии (необязательно)"
            },
            file_path: {
              type: "string",
              description: "Путь к файлу (необязательно)"
            },
            importance: {
              type: "number",
              description: "Важность записи (1-10)",
              default: 5
            },
            metadata: {
              type: "object",
              description: "Дополнительные метаданные"
            }
          },
          required: ["content_type", "title", "content"]
        }
      },
    ],
  };
});

// Обработчик вызова инструментов
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;
    
    switch (name) {
      case "ask_rag": {
        // Получаем или создаем сессию для проекта
        const sessionId = await getOrCreateSession();
        
        try {
          // Определяем параметры поиска
          const searchParams = {
            query: args.query,
            framework: args.framework || null,
            include_project_memory: true,  // Всегда включаем память проекта
            include_framework_docs: true,  // Всегда включаем документацию
            limit_per_source: args.max_results || 3
          };
          
          // Используем новый unified RAG endpoint
          const response = await axios.post(`${RAG_SERVER_URL}/unified-rag/search`, searchParams);
          
          if (response.status === 200) {
            const data = response.data;
            
            // Форматируем ответ с разделением по источникам
            let answer = `# 🎯 Ответ по запросу: "${args.query}"\n\n`;
            
            // Добавляем результаты из документации фреймворков
            if (data.framework_docs && data.framework_docs.length > 0) {
              answer += `## 📚 Документация фреймворков\n\n`;
              data.framework_docs.forEach((doc, i) => {
                const framework = doc.metadata.framework || 'unknown';
                const title = doc.metadata.title || `Документ ${i+1}`;
                const relevance = (doc.relevance_score * 100).toFixed(1);
                
                answer += `### ${i+1}. [${framework.toUpperCase()}] ${title} (${relevance}%)\n`;
                answer += `${doc.content.substring(0, 800)}...\n\n`;
              });
            }
            
            // Добавляем результаты из проектной памяти
            if (data.project_memory && data.project_memory.length > 0) {
              answer += `## 🧠 Память проекта\n\n`;
              data.project_memory.forEach((memory, i) => {
                const contentType = memory.metadata.content_type || 'unknown';
                const title = memory.metadata.title || `Запись ${i+1}`;
                const relevance = (memory.relevance_score * 100).toFixed(1);
                const importance = memory.metadata.importance || 5;
                
                answer += `### ${i+1}. [${contentType.toUpperCase()}] ${title} (${relevance}%, важность: ${importance})\n`;
                answer += `${memory.content.substring(0, 600)}...\n\n`;
              });
            }
            
            // Добавляем общую статистику
            answer += `## 📊 Статистика поиска\n`;
            answer += `- Общая релевантность: ${(data.combined_score * 100).toFixed(1)}%\n`;
            answer += `- Найдено в документации: ${data.framework_docs.length}\n`;
            answer += `- Найдено в памяти проекта: ${data.project_memory.length}\n`;
            answer += `- Всего результатов: ${data.total_results}\n`;
            
            if (data.total_results === 0) {
              answer = `Не найдено релевантной информации по запросу "${args.query}".\n\nПопробуйте:
- Переформулировать запрос
- Использовать более общие термины
- Указать конкретный фреймворк (framework: "laravel", "vue", "filament")`;
            }
            
            // Сохраняем взаимодействие в сессию
            await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/message`, {
              role: "user",
              content: `RAG Query: ${args.query}`,
              actions: ["ask_rag"],
              files: []
            }).catch(() => {}); // Игнорируем ошибки логирования
            
            await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/message`, {
              role: "assistant", 
              content: answer,
              actions: ["ask_rag"],
              files: data.framework_docs.concat(data.project_memory).map(r => r.metadata.file_path || "").filter(Boolean)
            }).catch(() => {});
            
            const cleanedAnswer = cleanRAGResponse(answer);
            
            await logToolCall(name, args, { answer: cleanedAnswer, sources: data.total_results }, true);
            
            // 🤖 Автоанализ ответа RAG на ключевые моменты
            await autoSaveKeyMoments(name, args, `${args.query} ${cleanedAnswer}`, []);
            
            return {
              content: [
                {
                  type: "text",
                  text: cleanedAnswer,
                },
              ],
            };
          } else {
            throw new Error(`RAG сервер вернул статус ${response.status}`);
          }
        } catch (error) {
          console.error(`❌ Ошибка запроса к unified RAG: ${error.message}`);
          await logToolCall(name, args, { error: error.message }, false);
          
          return {
            content: [
              {
                type: "text", 
                text: `Ошибка обращения к RAG системе: ${error.message}`,
              },
            ],
          };
        }
      }

      case "list_frameworks": {
        const response = await axios.get(`${RAG_SERVER_URL}/frameworks`);
        const statsResponse = await axios.get(`${RAG_SERVER_URL}/stats`);
        
        const frameworks = Object.entries(response.data).map(([key, info]) => {
          const docCount = statsResponse.data.frameworks[key.toUpperCase()] || 0;
          return `- **${key}**: ${info.name} - ${info.description} (${docCount} документов)`;
        }).join('\n');
        
        result = { frameworks: response.data, stats: statsResponse.data.frameworks };
        await logToolCall(name, args, result, true);
        
        return {
          content: [
            {
              type: "text",
              text: `📋 **Доступные фреймворки:**\n\n${frameworks}\n\n📊 **Всего документов:** ${statsResponse.data.total_documents}`,
            },
          ],
        };
      }

      case "get_stats": {
        const response = await axios.get(`${RAG_SERVER_URL}/stats`);
        const stats = response.data;
        
        const frameworkStats = Object.entries(stats.frameworks || {})
          .map(([key, count]) => `- **${key}**: ${count} документов`)
          .join('\n');
        
        result = stats;
        await logToolCall(name, args, result, true);
        
        return {
          content: [
            {
              type: "text",
              text: `📊 **Статистика RAG системы:**\n\n**Всего документов:** ${stats.total_documents || 0}\n\n**По фреймворкам:**\n${frameworkStats}\n\n**Размер кэша:** ${stats.cache_size || 0}`,
            },
          ],
        };
      }

      case "get_recent_changes": {
        try {
          // ПРОСТОЙ ТЕСТ - показываем что функция вызывается
          const testMessage = `🔄 **ТЕСТ: Функция get_recent_changes вызвана!**\n\nВремя: ${new Date().toLocaleString()}\nURL: ${RAG_SERVER_URL}\nПроект: ${getCurrentProjectName()}`;
          
          const response = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
          const data = response.data;
          
          // Попробуем все возможные пути к ключевым моментам
          let moments = null;
          let source = "";
          
          if (data && data.context && data.context.key_moments && Array.isArray(data.context.key_moments)) {
            moments = data.context.key_moments;
            source = "data.context.key_moments";
          } else if (data && data.key_moments && Array.isArray(data.key_moments)) {
            moments = data.key_moments;
            source = "data.key_moments";
          }
          
          if (!moments || moments.length === 0) {
            return {
              content: [{
                type: "text",
                text: `${testMessage}\n\n❌ **Проблема:** Ключевые моменты не найдены\n\n**Структура ответа:**\n- Поля в data: ${Object.keys(data || {}).join(', ')}\n- context существует: ${!!(data && data.context)}\n- Поля в context: ${data && data.context ? Object.keys(data.context).join(', ') : 'нет'}`
              }]
            };
          }
          
          // Форматируем первые несколько моментов
          const formatted = moments.slice(0, args.limit || 5).map((m, i) => 
            `${i+1}. **${m.title || 'Без названия'}** (${m.type || 'unknown'})\n   ${(m.summary || '').substring(0, 100)}...`
          ).join('\n\n');
          
          return {
            content: [{
              type: "text", 
              text: `${testMessage}\n\n✅ **Успех!** Найдено ${moments.length} ключевых моментов\n**Источник:** ${source}\n\n**Последние моменты:**\n\n${formatted}`
            }]
          };
          
        } catch (error) {
          return {
            content: [{
              type: "text",
              text: `🔄 **ТЕСТ: Функция get_recent_changes вызвана!**\n\n❌ **Ошибка:** ${error.message}\n\n**Детали:**\n- URL: ${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}\n- Время: ${new Date().toLocaleString()}`
            }]
          };
        }
      }

      case "save_key_moment": {
        try {
          // Создаем или получаем текущую сессию
          const sessionId = await getOrCreateSession();
          
          // Сохраняем ключевой момент
          const momentResponse = await axios.post(`${RAG_SERVER_URL}/sessions/${sessionId}/key-moment`, {
            moment_type: args.type || 'feature_completed',
            title: args.title,
            summary: args.summary,
            files_involved: args.files || [],
            importance: args.importance || 5
          });
          
          result = { saved: true, session_id: sessionId };
          await logToolCall(name, args, result, true);
          
          // 🤖 Автоанализ описания ключевого момента на дополнительные моменты
          await autoSaveKeyMoments(name, args, `${args.title} ${args.summary}`, args.files || []);
          
          return {
            content: [
              {
                type: "text",
                text: `✅ **Ключевой момент сохранен**\n\n**Название:** ${args.title}\n**Тип:** ${args.type || 'feature_completed'}\n**Описание:** ${args.summary}\n**Сессия:** ${sessionId}`,
              },
            ],
          };
        } catch (error) {
          return {
            content: [
              {
                type: "text",
                text: `❌ **Ошибка сохранения ключевого момента**\n\n${error.message}`,
              },
            ],
          };
        }
      }

      case "open_file": {
        const filePath = args.path;
        
        if (!filePath) {
          throw new Error('Параметр path обязателен');
        }

        // Валидация пути для безопасности (та же логика из HTTP сервера)
        const normalizedPath = path.normalize(filePath);
        const absolutePath = path.isAbsolute(normalizedPath) ? normalizedPath : path.resolve(normalizedPath);
        
        // Список запрещенных путей
        const forbiddenPaths = [
          '/etc/',
          '/sys/', 
          '/proc/',
          '/root/',
          'C:\\Windows\\',
          'C:\\System'
        ];
        
        if (absolutePath.includes('.ssh') || 
            forbiddenPaths.some(forbidden => absolutePath.toLowerCase().includes(forbidden.toLowerCase())) ||
            (normalizedPath.includes('..') && (normalizedPath.includes('etc') || normalizedPath.includes('ssh')))) {
          throw new Error('Доступ запрещен: системный файл');
        }

        try {
          const content = await fs.readFile(filePath, 'utf8');
          
          // Получаем/создаем сессию для сохранения снимка файла
          const sessionId = await getOrCreateSession();
          
          // Сохраняем снимок файла через новый API
          try {
            const snapshotResponse = await axios.post(`${RAG_SERVER_URL}/file-snapshots/save`, {
              session_id: sessionId,
              file_path: filePath,
              content: content
            });
            
            console.error(`📸 Снимок файла сохранен: ${snapshotResponse.data.snapshot_id}`);
          } catch (snapshotError) {
            console.error(`⚠️ Не удалось сохранить снимок файла: ${snapshotError.message}`);
          }
          
          result = { content, path: filePath };
          await logToolCall(name, args, result, true);
          
          // 🤖 Автоанализ содержимого файла на ключевые моменты
          await autoSaveKeyMoments(name, args, content, [filePath]);
          
          return {
            content: [
              {
                type: "text",
                text: `📁 **Файл:** ${filePath}\n\n\`\`\`\n${content}\n\`\`\``,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Не удалось прочитать файл: ${error.message}`);
        }
      }

      case "search_files": {
        try {
          // Получаем session_id для текущего проекта
          const sessionId = await getOrCreateSession();
          
          const response = await axios.get(`${RAG_SERVER_URL}/sessions/${sessionId}/search/files`, {
            params: {
              query: args.query,
              language: args.language || "",
              limit: args.limit || 10
            }
          });
          
          const results = response.data.results;
          const totalFound = response.data.total_found;
          
          let resultText = `🔍 **Поиск по файлам:** "${args.query}"\n\n`;
          resultText += `📊 **Найдено:** ${totalFound} результатов\n\n`;
          
          if (args.language) {
            resultText += `🏷️ **Фильтр по языку:** ${args.language}\n\n`;
          }
          
          if (results.length === 0) {
            resultText += "❌ Ничего не найдено";
          } else {
            resultText += "📂 **Результаты:**\n\n";
            results.forEach((result, index) => {
              resultText += `${index + 1}. **${result.file_path}** (${result.language})\n`;
              resultText += `   ${result.content_preview.substring(0, 100)}...\n\n`;
            });
          }
          
          result = { query: args.query, results, total_found: totalFound };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка поиска по файлам: ${error.message}`);
        }
      }

      case "get_file_history": {
        try {
          // Кодируем путь для URL
          const encodedPath = encodeURIComponent(args.file_path);
          const response = await axios.get(`${RAG_SERVER_URL}/file-snapshots/history/${encodedPath}`);
          
          const history = response.data.history;
          const totalVersions = response.data.total_versions;
          
          let resultText = `📚 **История файла:** ${args.file_path}\n\n`;
          resultText += `📊 **Всего версий:** ${totalVersions}\n\n`;
          
          if (history.length === 0) {
            resultText += "❌ История не найдена";
          } else {
            resultText += "🗂️ **Версии:**\n\n";
            history.forEach((version, index) => {
              const date = new Date(version.timestamp * 1000).toLocaleString();
              resultText += `${index + 1}. **${version.content_hash.substring(0, 8)}** (${version.size_bytes} байт) - ${date}\n`;
            });
          }
          
          result = { file_path: args.file_path, history, total_versions: totalVersions };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка получения истории файла: ${error.message}`);
        }
      }

      case "init_memory_bank": {
        try {
          const projectRoot = args.project_root || getCurrentProjectRoot();
          
          const response = await axios.post(`${RAG_SERVER_URL}/memory-bank/init`, {
            project_root: projectRoot
          });
          
          result = { initialized: true, project_root: projectRoot };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: `🏦 **Memory Bank инициализирован**\n\n**Проект:** ${projectRoot}\n**Создано файлов:** ${response.data.files_created || 5}\n\n📂 **Структура:**\n- project-context.md - Контекст проекта\n- active-context.md - Активный контекст сессии\n- progress.md - Трекинг прогресса\n- decisions.md - Лог важных решений\n- code-patterns.md - Паттерны кода`,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка инициализации Memory Bank: ${error.message}`);
        }
      }

      case "get_memory_context": {
        try {
          const contextType = args.context_type || "active";
          
          // Используем текущий проект
          const projectRoot = getCurrentProjectRoot();
          
          const response = await axios.get(`${RAG_SERVER_URL}/memory-bank/context`, {
            params: {
              context_type: contextType,
              project_root: projectRoot
            }
          });
          
          // Извлекаем данные из правильного формата ответа API
          const content = response.data.content || "Контекст не найден";
          const filename = response.data.filename || `${contextType}.md`;
          
          result = { context_type: contextType, content, filename };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: `🏦 **Memory Bank - ${contextType.toUpperCase()}**\n\n📁 **Файл:** ${filename}\n\n---\n\n${content}`,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка получения контекста Memory Bank: ${error.message}`);
        }
      }

      case "update_active_context": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/memory-bank/update-active-context`, {
            project_root: getCurrentProjectRoot(),
            session_state: args.session_state,
            tasks: args.tasks || [],
            decisions: args.decisions || []
          });
          
          result = { updated: true, session_state: args.session_state };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: `🔄 **Активный контекст обновлен**\n\n**Состояние сессии:** ${args.session_state}\n**Задач:** ${(args.tasks || []).length}\n**Решений:** ${(args.decisions || []).length}`,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка обновления активного контекста: ${error.message}`);
        }
      }

      case "log_decision": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/memory-bank/add-decision`, {
            project_root: getCurrentProjectRoot(),
            title: args.title,
            context: args.context,
            decision: args.decision,
            consequences: args.consequences || ""
          });
          
          result = { logged: true, title: args.title };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: `📝 **Решение зафиксировано**\n\n**Название:** ${args.title}\n**Контекст:** ${args.context}\n**Решение:** ${args.decision}\n${args.consequences ? `**Последствия:** ${args.consequences}` : ''}`,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка фиксации решения: ${error.message}`);
        }
      }

      case "search_memory_bank": {
        try {
          const response = await axios.get(`${RAG_SERVER_URL}/memory-bank/search`, {
            params: {
              query: args.query,
              project_root: getCurrentProjectRoot()
            }
          });
          
          const results = response.data.results;
          const totalFound = response.data.total_found;
          
          let resultText = `🔍 **Поиск в Memory Bank:** "${args.query}"\n\n`;
          resultText += `📊 **Найдено:** ${totalFound} результатов\n\n`;
          
          if (results.length === 0) {
            resultText += "❌ Ничего не найдено";
          } else {
            resultText += "📂 **Результаты:**\n\n";
            results.forEach((result, index) => {
              resultText += `${index + 1}. **${result.filename}**\n`;
              resultText += `   ${result.preview.substring(0, 150)}...\n\n`;
            });
          }
          
          result = { query: args.query, results, total_found: totalFound };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка поиска в Memory Bank: ${error.message}`);
        }
      }

      case "search_symbols": {
        try {
          // Получаем session_id для текущего проекта
          const sessionId = await getOrCreateSession();
          
          const response = await axios.get(`${RAG_SERVER_URL}/sessions/${sessionId}/search/symbols`, {
            params: {
              query: args.query,
              symbol_type: args.symbol_type || "",
              language: args.language || "",
              limit: args.limit || 20
            }
          });
          
          const results = response.data.results;
          const totalFound = response.data.total_found;
          
          let resultText = `🔍 **Поиск символов:** "${args.query}"\n\n`;
          resultText += `📊 **Найдено:** ${totalFound} символов\n\n`;
          
          if (args.symbol_type) {
            resultText += `🏷️ **Тип:** ${args.symbol_type}\n`;
          }
          if (args.language) {
            resultText += `💻 **Язык:** ${args.language}\n`;
          }
          if (args.symbol_type || args.language) {
            resultText += '\n';
          }
          
          if (results.length === 0) {
            resultText += "❌ Символы не найдены";
          } else {
            resultText += "🎯 **Найденные символы:**\n\n";
            results.forEach((symbol, index) => {
              const typeEmoji = symbol.symbol_type === 'function' ? '🔧' : 
                              symbol.symbol_type === 'class' ? '📦' : 
                              symbol.symbol_type === 'variable' ? '📝' : '📥';
              
              resultText += `${index + 1}. ${typeEmoji} **${symbol.name}** (${symbol.symbol_type})\n`;
              resultText += `   📁 ${symbol.file_path}:${symbol.start_line}\n`;
              resultText += `   ⚡ \`${symbol.signature.substring(0, 80)}${symbol.signature.length > 80 ? '...' : ''}\`\n`;
              
              if (symbol.docstring && symbol.docstring.trim()) {
                resultText += `   📖 ${symbol.docstring.substring(0, 100)}${symbol.docstring.length > 100 ? '...' : ''}\n`;
              }
              
              resultText += '\n';
            });
          }
          
          result = { query: args.query, results, total_found: totalFound };
          await logToolCall(name, args, result, true);
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
        } catch (error) {
          throw new Error(`Ошибка поиска символов: ${error.message}`);
        }
      }

      case "enhance_prompt": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/prompt/enhance`, {
            prompt: args.prompt,
            project_context: { project_root: getCurrentProjectRoot() },
            force_enhance: args.force_enhance || false
          });
          
          const enhanced = response.data;
          result = enhanced;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `✨ **Промт улучшен!**\n\n`;
          resultText += `**Исходный промт:**\n${enhanced.original_prompt}\n\n`;
          resultText += `**Улучшенный промт:**\n${enhanced.enhanced_prompt}\n\n`;
          resultText += `**Улучшения:** ${enhanced.improvements.join(', ')}\n`;
          resultText += `**Время обработки:** ${enhanced.processing_time.toFixed(2)}с`;
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка улучшения промта: ${error.message}`);
        }
      }

      case "analyze_prompt": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/prompt/analyze`, {
            prompt: args.prompt,
            project_context: { project_root: getCurrentProjectRoot() }
          });
          
          const analysis = response.data;
          result = analysis;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `🔍 **Анализ промта:**\n\n`;
          resultText += `**Промт:** ${args.prompt}\n\n`;
          resultText += `**Нужно улучшение:** ${analysis.needs_enhancement ? '✅ Да' : '❌ Нет'}\n`;
          resultText += `**Уверенность:** ${(analysis.confidence * 100).toFixed(1)}%\n`;
          resultText += `**Намерение:** ${analysis.estimated_intent}\n`;
          
          if (analysis.issues && analysis.issues.length > 0) {
            resultText += `**Проблемы:**\n`;
            analysis.issues.forEach((issue, i) => {
              resultText += `${i + 1}. ${issue}\n`;
            });
          }
          
          if (analysis.suggested_context && analysis.suggested_context.length > 0) {
            resultText += `**Рекомендуемый контекст:** ${analysis.suggested_context.join(', ')}`;
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка анализа промта: ${error.message}`);
        }
      }

      case "process_prompt_with_triggers": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/smart/process`, {
            prompt: args.prompt,
            context: args.project_context || { project_root: getCurrentProjectRoot() },
            project_context: { project_name: getCurrentProjectName(), project_root: getCurrentProjectRoot() }
          });
          
          const processing = response.data;
          result = processing;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ с детальной информацией о триггерах
          let resultText = `🚀 **Обработка промта с триггерами:**\n\n`;
          
          if (processing.was_enhanced) {
            resultText += `✨ **Промт был улучшен!**\n\n`;
            resultText += `**Исходный промт:**\n${processing.original_prompt}\n\n`;
            resultText += `**Улучшенный промт:**\n${processing.final_prompt}\n\n`;
            
            if (processing.metadata.trigger_used) {
              resultText += `**Использован триггер:** ${processing.metadata.trigger_used}\n`;
            }
            
            if (processing.metadata.improvements) {
              resultText += `**Улучшения:** ${processing.metadata.improvements.join(', ')}\n`;
            }
            
            resultText += `**Причина:** ${processing.reasoning}\n`;
            resultText += `**Время обработки:** ${processing.processing_time.toFixed(3)}с\n`;
            resultText += `**Уверенность:** ${(processing.confidence * 100).toFixed(1)}%\n`;
            
          } else {
            // Проверяем есть ли триггер в metadata
            if (processing.metadata && processing.metadata.trigger_used) {
              resultText += `🎯 **Триггер обнаружен, но промт не улучшен**\n\n`;
              resultText += `**Исходный промт:** ${processing.original_prompt}\n\n`;
              resultText += `**Очищенный промт:** ${processing.final_prompt}\n\n`;
              resultText += `**Использован триггер:** ${processing.metadata.trigger_used}\n`;
              resultText += `**Причина:** ${processing.reasoning}\n`;
              
              if (processing.metadata.improvements) {
                resultText += `**Анализ:** ${processing.metadata.improvements.join(', ')}\n`;
              }
            } else {
              resultText += `📝 **Промт оставлен без изменений**\n\n`;
              resultText += `**Промт:** ${processing.final_prompt}\n\n`;
              resultText += `**Причина:** ${processing.reasoning}\n`;
              
              resultText += `\n💡 **Триггер для улучшения:**\n`;
              resultText += `• Добавьте **???** в конец промта для автоматического улучшения\n`;
            }
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка обработки промта с триггерами: ${error.message}`);
        }
      }

      case "smart_process_prompt": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/smart/process`, {
            prompt: args.prompt,
            threshold: args.threshold || 0.3,
            max_time: args.max_time || 5.0,
            context: { project_root: getCurrentProjectRoot() },
            project_context: { project_name: getCurrentProjectName(), project_root: getCurrentProjectRoot() }
          });
          
          const processed = response.data;
          result = processed;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `🧠 **Smart Processing результат:**\n\n`;
          resultText += `**Исходный промт:**\n${processed.original_prompt}\n\n`;
          
          if (processed.was_enhanced) {
            resultText += `**✨ Улучшенный промт:**\n${processed.final_prompt}\n\n`;
            resultText += `**Уверенность:** ${(processed.confidence * 100).toFixed(1)}%\n`;
            resultText += `**Время обработки:** ${processed.processing_time.toFixed(3)}с\n`;
            resultText += `**Причина улучшения:** ${processed.reasoning}`;
            
            if (processed.metadata && processed.metadata.improvements) {
              resultText += `\n**Улучшения:** ${processed.metadata.improvements.join(', ')}`;
            }
          } else {
            resultText += `**❌ Улучшение не требуется**\n`;
            resultText += `**Причина:** ${processed.reasoning}\n`;
            resultText += `**Уверенность:** ${(processed.confidence * 100).toFixed(1)}%`;
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка smart processing: ${error.message}`);
        }
      }

      case "should_process_prompt": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/smart/should_process`, {
            prompt: args.prompt,
            threshold: args.threshold || 0.3,
            context: { project_root: getCurrentProjectRoot() }
          });
          
          const assessment = response.data;
          result = assessment;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `🔍 **Оценка промта:**\n\n`;
          resultText += `**Промт:** ${args.prompt}\n\n`;
          resultText += `**Нужно обработать:** ${assessment.should_process ? '✅ Да' : '❌ Нет'}\n`;
          resultText += `**Оценка качества:** ${(assessment.quality_score * 100).toFixed(1)}% (${assessment.assessment})\n`;
          resultText += `**Длина промта:** ${assessment.prompt_length} символов\n`;
          resultText += `**Причина:** ${assessment.reason}`;
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка проверки промта: ${error.message}`);
        }
      }

      case "get_session_summary": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/sessions/summary`, {
            days_back: args.days_back || 1,
          });
          
          const summary = response.data;
          result = summary;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `📊 **Обзор работы за ${summary.period}:**\n\n`;
          
          // Ключевые моменты
          if (summary.key_moments && summary.key_moments.total > 0) {
            resultText += `🔥 **Ключевые моменты:** ${summary.key_moments.total}\n`;
            resultText += `📈 **Важность:** ${summary.key_moments.total_importance} баллов\n`;
            
            if (summary.key_moments.by_type && Object.keys(summary.key_moments.by_type).length > 0) {
              resultText += `**По типам:**\n`;
              Object.entries(summary.key_moments.by_type).forEach(([type, moments]) => {
                resultText += `  • ${type}: ${moments.length} шт.\n`;
              });
            }
            resultText += `\n`;
          }
          
          // Файлы
          if (summary.files_changed && summary.files_changed.count > 0) {
            resultText += `📁 **Файлы изменены:** ${summary.files_changed.count}\n`;
            if (summary.files_changed.list.length > 0) {
              resultText += `**Основные:**\n`;
              summary.files_changed.list.slice(0, 5).forEach(file => {
                resultText += `  • ${file}\n`;
              });
            }
            resultText += `\n`;
          }
          
          // Продуктивность
          if (summary.productivity_score !== undefined) {
            resultText += `⚡ **Продуктивность:** ${summary.productivity_score}/100\n\n`;
          }
          
          // Последняя активность
          if (summary.recent_activity && summary.recent_activity.length > 0) {
            resultText += `💬 **Последняя активность:**\n`;
            summary.recent_activity.slice(0, 3).forEach(activity => {
              resultText += `  • ${activity.role}: ${activity.content}\n`;
            });
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка получения session summary: ${error.message}`);
        }
      }

      case "get_project_status": {
        try {
          const response = await axios.get(`${RAG_SERVER_URL}/sessions/project/status`);
          
          const status = response.data;
          result = status;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `🏗️ **Статус проекта:**\n\n`;
          
          // Описание проекта
          if (status.project_info && status.project_info.context) {
            resultText += `📋 **Описание:**\n${status.project_info.context}\n\n`;
          }
          
          // Технологии
          if (status.project_info && status.project_info.technologies && Object.keys(status.project_info.technologies).length > 0) {
            resultText += `💻 **Технологии:**\n`;
            Object.entries(status.project_info.technologies).forEach(([tech, count]) => {
              resultText += `  • ${tech}: ${count} файлов\n`;
            });
            resultText += `\n`;
          }
          
          // Статистика разработки
          if (status.development_stats) {
            resultText += `📊 **Статистика разработки:**\n`;
            resultText += `  • Ключевые моменты: ${status.development_stats.total_moments}\n`;
            resultText += `  • Файлы: ${status.development_stats.total_files}\n`;
            resultText += `  • Сообщения: ${status.development_stats.total_messages}\n\n`;
          }
          
          // Последняя активность
          if (status.last_activity) {
            const daysSince = status.days_since_last_activity;
            let activityMsg = '';
            if (daysSince < 1) {
              activityMsg = 'Сегодня';
            } else if (daysSince < 2) {
              activityMsg = 'Вчера';
            } else {
              activityMsg = `${daysSince.toFixed(1)} дней назад`;
            }
            resultText += `⏰ **Последняя активность:** ${activityMsg}\n\n`;
          }
          
          // Активные файлы
          if (status.project_info && status.project_info.active_files && status.project_info.active_files.length > 0) {
            resultText += `📁 **Активные файлы:**\n`;
            status.project_info.active_files.slice(0, 5).forEach(file => {
              resultText += `  • ${file.file_path} (${file.activity_count} изменений)\n`;
            });
          }
          
          // Последние решения
          if (status.recent_decisions && status.recent_decisions.length > 0) {
            resultText += `\n🧠 **Последние решения:**\n`;
            status.recent_decisions.slice(0, 3).forEach(decision => {
              resultText += `  • ${decision.title}\n`;
            });
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка получения project status: ${error.message}`);
        }
      }

      case "get_recent_work": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/sessions/work/recent`, {
            days_back: args.days_back || 3,
          });
          
          const work = response.data;
          result = work;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `📅 **Хронология работы за ${work.period}:**\n\n`;
          
          // Общая статистика
          if (work.summary) {
            resultText += `📊 **Общая статистика:**\n`;
            resultText += `  • Активных дней: ${work.summary.total_days_active}\n`;
            resultText += `  • Ключевых моментов: ${work.summary.total_moments}\n`;
            resultText += `  • Файлов изменено: ${work.summary.total_files_changed}\n`;
            resultText += `  • Средняя интенсивность: ${work.summary.avg_daily_intensity}%\n`;
            if (work.summary.most_productive_day) {
              resultText += `  • Самый продуктивный день: ${work.summary.most_productive_day}\n`;
            }
            resultText += `\n`;
          }
          
          // Хронология по дням
          if (work.timeline && work.timeline.length > 0) {
            resultText += `📖 **Хронология по дням:**\n\n`;
            work.timeline.forEach((day, index) => {
              if (index < 5) { // Показываем первые 5 дней
                resultText += `**${day.date}**\n`;
                if (day.intensity.intensity_score > 0) {
                  resultText += `  ⚡ Интенсивность: ${day.intensity.intensity_score}%\n`;
                }
                
                if (day.moments && day.moments.length > 0) {
                  resultText += `  🔥 Ключевые моменты:\n`;
                  day.moments.slice(0, 3).forEach(moment => {
                    resultText += `    • ${moment.title}\n`;
                  });
                }
                
                if (day.files_changed && day.files_changed.length > 0) {
                  resultText += `  📁 Файлы: ${day.files_changed.slice(0, 3).map(f => f.file_path).join(', ')}\n`;
                }
                
                resultText += `\n`;
              }
            });
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка получения recent work: ${error.message}`);
        }
      }

      case "initialize_context": {
        try {
          const response = await axios.post(`${RAG_SERVER_URL}/sessions/context/initialize`, {
            include_code_examples: args.include_code_examples !== false,
          });
          
          const context = response.data;
          result = context;
          await logToolCall(name, args, result, true);
          
          // Форматированный ответ
          let resultText = `${context.welcome_message}\n\n`;
          
          // Обзор проекта
          if (context.project_overview) {
            resultText += `🏗️ **Обзор проекта:**\n`;
            if (context.project_overview.description) {
              resultText += `${context.project_overview.description}\n\n`;
            }
            
            if (context.project_overview.technologies && Object.keys(context.project_overview.technologies).length > 0) {
              resultText += `💻 **Технологии:**\n`;
              Object.entries(context.project_overview.technologies).forEach(([tech, count]) => {
                resultText += `  • ${tech}: ${count} файлов\n`;
              });
              resultText += `\n`;
            }
          }
          
          // Последняя активность
          if (context.recent_activity && context.recent_activity.last_work) {
            resultText += `⏰ **Последняя работа:** ${context.recent_activity.last_work.date}\n`;
            if (context.recent_activity.productivity_score > 0) {
              resultText += `⚡ **Продуктивность:** ${context.recent_activity.productivity_score}%\n`;
            }
            resultText += `\n`;
          }
          
          // Ключевые решения
          if (context.key_decisions && context.key_decisions.length > 0) {
            resultText += `🧠 **Ключевые решения:**\n`;
            context.key_decisions.slice(0, 3).forEach(decision => {
              resultText += `  • ${decision.title}\n`;
            });
            resultText += `\n`;
          }
          
          // Активные файлы
          if (context.active_files && context.active_files.length > 0) {
            resultText += `📁 **Активные файлы:**\n`;
            context.active_files.slice(0, 3).forEach(file => {
              resultText += `  • ${file.file_path} (${file.language})\n`;
            });
            resultText += `\n`;
          }
          
          // Рекомендации
          if (context.recommendations && context.recommendations.length > 0) {
            resultText += `💡 **Рекомендации:**\n`;
            context.recommendations.forEach(rec => {
              resultText += `  • ${rec}\n`;
            });
          }
          
          return {
            content: [
              {
                type: "text",
                text: resultText,
              },
            ],
          };
          
        } catch (error) {
          throw new Error(`Ошибка инициализации контекста: ${error.message}`);
        }
      }

      case "search_project_memory": {
        try {
          const searchParams = {
            query: args.query,
            content_type: args.content_type || null,
            session_id: args.session_id || null,
            min_importance: args.min_importance || 0,
            limit: args.limit || 5
          };
          
          const response = await axios.get(`${RAG_SERVER_URL}/unified-rag/search-memory`, {
            params: searchParams
          });
          
          if (response.status === 200) {
            const data = response.data;
            
            let result = `# 🧠 Поиск по памяти проекта: "${args.query}"\n\n`;
            
            if (data.results && data.results.length > 0) {
              data.results.forEach((memory, i) => {
                const contentType = memory.metadata.content_type || 'unknown';
                const title = memory.metadata.title || `Запись ${i+1}`;
                const relevance = (memory.relevance_score * 100).toFixed(1);
                const importance = memory.metadata.importance || 5;
                const sessionId = memory.metadata.session_id || 'unknown';
                
                result += `## ${i+1}. [${contentType.toUpperCase()}] ${title}\n`;
                result += `**Релевантность:** ${relevance}% | **Важность:** ${importance} | **Сессия:** ${sessionId}\n\n`;
                result += `${memory.content}\n\n---\n\n`;
              });
              
              result += `**Всего найдено:** ${data.total_found} записей`;
            } else {
              result += `Записи не найдены по запросу "${args.query}".`;
            }
            
            await logToolCall(name, args, { found: data.total_found }, true);
            
            return {
              content: [
                {
                  type: "text",
                  text: result,
                },
              ],
            };
          } else {
            throw new Error(`Статус ${response.status}`);
          }
        } catch (error) {
          console.error(`❌ Ошибка поиска по памяти проекта: ${error.message}`);
          await logToolCall(name, args, { error: error.message }, false);
          
          return {
            content: [
              {
                type: "text",
                text: `Ошибка поиска по памяти проекта: ${error.message}`,
              },
            ],
          };
        }
      }

      case "add_project_memory": {
        try {
          const sessionId = await getOrCreateSession();
          
          const memoryData = {
            content_type: args.content_type,
            title: args.title,
            content: args.content,
            session_id: args.session_id || sessionId,
            file_path: args.file_path || "",
            importance: args.importance || 5,
            metadata: args.metadata || {}
          };
          
          const response = await axios.post(`${RAG_SERVER_URL}/unified-rag/add-project-memory`, memoryData);
          
          if (response.status === 200) {
            const data = response.data;
            
            await logToolCall(name, args, data, true);
            
            return {
              content: [
                {
                  type: "text",
                  text: `✅ Запись добавлена в память проекта\n\n**ID:** ${data.memory_id}\n**Тип:** ${data.content_type}\n**Заголовок:** ${data.title}`,
                },
              ],
            };
          } else {
            throw new Error(`Статус ${response.status}`);
          }
        } catch (error) {
          console.error(`❌ Ошибка добавления в память проекта: ${error.message}`);
          await logToolCall(name, args, { error: error.message }, false);
          
          return {
            content: [
              {
                type: "text",
                text: `Ошибка добавления в память проекта: ${error.message}`,
              },
            ],
          };
        }
      }

      default:
        throw new Error(`Неизвестный инструмент: ${name}`);
    }
  } catch (error) {
    console.error(`Ошибка выполнения инструмента ${name}:`, error.message);
    
    await logToolCall(name, args, { error: error.message }, false);
    
    // 🤖 Автоанализ ошибки на ключевые моменты (решение проблем)
    await autoSaveKeyMoments(name, args, `Ошибка в ${name}: ${error.message}`, []);
    
    return {
      content: [
        {
          type: "text",
          text: `❌ **Ошибка выполнения ${name}:**\n\n${error.message}\n\n🔧 **Проверьте:**\n- RAG сервер запущен на ${RAG_SERVER_URL}\n- Параметры запроса корректны`,
        },
      ],
      isError: true,
    };
  }
});

// Запуск сервера
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.error("🚀 STDIO MCP Server запущен для Claude Code CLI - ВЕРСИЯ 3.0 С MEMORY BANK!");
  console.error(`📊 RAG Backend: ${RAG_SERVER_URL}`);
  console.error("🔧 RAG инструменты: ask_rag, list_frameworks, get_stats, get_recent_changes, save_key_moment");
  console.error("📁 FileSnapshot: open_file, search_files, get_file_history");
  console.error("🏦 Memory Bank: init_memory_bank, get_memory_context, update_active_context, log_decision, search_memory_bank");
  console.error("🤖 Автоматическое сохранение ключевых моментов АКТИВНО");
  console.error("🎯 Детекция: ошибки, файлы, конфигурации, рефакторинг, решения");
  console.error("🔥 NEW: Memory Bank система по примеру Cursor/Cline!");
}

// Обработка ошибок
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  process.exit(1);
});

// Экспорт функций для использования в HTTP сервере
export {
  autoDetectKeyMoments,
  autoSaveKeyMoments,
  handleExternalAutoAnalysis,
  KEY_MOMENT_TYPES,
  MOMENT_IMPORTANCE
};

// Запуск только если файл вызывается напрямую
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}