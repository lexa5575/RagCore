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
  REFACTORING: "refactoring"
};

const MOMENT_IMPORTANCE = {
  [KEY_MOMENT_TYPES.BREAKTHROUGH]: 9,
  [KEY_MOMENT_TYPES.ERROR_SOLVED]: 8,
  [KEY_MOMENT_TYPES.DEPLOYMENT]: 8,
  [KEY_MOMENT_TYPES.FEATURE_COMPLETED]: 7,
  [KEY_MOMENT_TYPES.IMPORTANT_DECISION]: 7,
  [KEY_MOMENT_TYPES.CONFIG_CHANGED]: 6,
  [KEY_MOMENT_TYPES.REFACTORING]: 6,
  [KEY_MOMENT_TYPES.FILE_CREATED]: 5,
};

function autoDetectKeyMoments(toolName, args, content = "", files = []) {
  const moments = [];
  const contentLower = content.toLowerCase();
  const toolNameLower = toolName.toLowerCase();
  
  // Обнаружение решения ошибок (русские и английские слова)
  const errorKeywords = [
    // Английские
    "error", "fix", "solved", "resolved", "bug", "issue", "problem",
    // Русские
    "ошибка", "исправлен", "решен", "решена", "исправлена", "починен", "починена",
    "баг", "проблема", "устранен", "устранена", "фикс", "исправление"
  ];
  
  if (errorKeywords.some(word => contentLower.includes(word))) {
    moments.push({
      type: KEY_MOMENT_TYPES.ERROR_SOLVED,
      title: "Решение ошибки",
      summary: `Обнаружено и исправлено через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.ERROR_SOLVED],
      files: files
    });
  }
  
  // Обнаружение создания файлов
  const creationActions = ["create", "write", "add", "создать", "написать", "добавить"];
  if ((creationActions.some(action => toolNameLower.includes(action) || contentLower.includes(action)) && files.length > 0) ||
      (toolName === "open_file" && args.path && contentLower.includes("создан"))) {
    moments.push({
      type: KEY_MOMENT_TYPES.FILE_CREATED,
      title: `Создание файла ${files[0] || args.path || ""}`,
      summary: `Создан файл ${files[0] || args.path || ""} через ${toolName}: ${content.substring(0, 200)}...`,
      importance: MOMENT_IMPORTANCE[KEY_MOMENT_TYPES.FILE_CREATED],
      files: files.length > 0 ? files : (args.path ? [args.path] : [])
    });
  }
  
  // Обнаружение завершения функций (русские и английские слова)
  const completionKeywords = [
    // Английские
    "completed", "finished", "done", "implemented", "ready", "success",
    // Русские
    "завершен", "завершена", "готов", "готова", "выполнен", "выполнена",
    "реализован", "реализована", "закончен", "закончена", "сделан", "сделана"
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
    "config", "settings", "yaml", "json", "configuration",
    // Русские
    "конфигурация", "настройки", "настройка", "конфиг", "параметры"
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
    "refactor", "refactored", "restructure", "optimize", "optimized",
    // Русские
    "рефакторинг", "рефакторил", "рефакторила", "оптимизирован", "оптимизирована",
    "переработан", "переработана", "реструктуризация", "улучшен", "улучшена"
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
  
  return moments;
}

// Автоматическое сохранение обнаруженных ключевых моментов
async function autoSaveKeyMoments(toolName, args, content = "", files = []) {
  try {
    const detectedMoments = autoDetectKeyMoments(toolName, args, content, files);
    
    if (detectedMoments.length === 0) {
      return; // Нет ключевых моментов для сохранения
    }
    
    // Создаем или получаем текущую сессию
    let sessionId;
    try {
      const sessionResponse = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
      sessionId = sessionResponse.data.session_id;
    } catch {
      // Создаем новую сессию если не существует
      const createResponse = await axios.post(`${RAG_SERVER_URL}/sessions/create?project_name=${getCurrentProjectName()}`, {
        description: "Claude Code CLI автосессия"
      });
      sessionId = createResponse.data.session_id;
    }
    
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
    
  } catch (error) {
    console.error(`❌ Ошибка автодетекции ключевых моментов:`, error.message);
  }
}

// Функция для логирования вызовов в RAG систему
async function logToolCall(toolName, args, result, success) {
  try {
    // Используем существующий endpoint для добавления сообщения в сессию
    await axios.post(`${RAG_SERVER_URL}/session/message`, {
      project_name: "${getCurrentProjectName()}",
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
        const response = await axios.post(`${RAG_SERVER_URL}/ask`, {
          question: args.query,
          framework: args.framework,
          max_results: args.max_results || 5,
        });

        const cleanedAnswer = cleanRAGResponse(response.data.answer);
        
        result = {
          answer: cleanedAnswer,
          sources: response.data.sources?.map(s => ({
            path: s.source,
            framework: s.framework,
            heading: s.heading || ''
          })) || [],
          session_id: response.data.session_id,
          framework_detected: response.data.framework_detected,
          total_docs: response.data.total_docs,
          response_time: response.data.response_time
        };
        
        await logToolCall(name, args, result, true);
        
        // 🤖 Автоанализ ответа RAG на ключевые моменты
        await autoSaveKeyMoments(name, args, `${args.query} ${cleanedAnswer}`, []);
        
        return {
          content: [
            {
              type: "text",
              text: `📚 **RAG Ответ:**\n\n${cleanedAnswer}\n\n🎯 **Фреймворк:** ${response.data.framework_detected}\n📊 **Найдено документов:** ${response.data.total_docs}\n⚡ **Время ответа:** ${Math.round(response.data.response_time)}мс\n\n🔗 **Источники:**\n${response.data.sources?.map(s => `- **${s.framework}**: ${s.source}${s.heading ? ` (${s.heading})` : ''}`).join('\n') || 'Нет источников'}`,
            },
          ],
        };
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
          let sessionId;
          try {
            const sessionResponse = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
            sessionId = sessionResponse.data.session_id;
          } catch {
            // Создаем новую сессию если не существует
            const createResponse = await axios.post(`${RAG_SERVER_URL}/sessions/create?project_name=${getCurrentProjectName()}`, {
              description: "Claude Code CLI сессия"
            });
            sessionId = createResponse.data.session_id;
          }
          
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
          let sessionId;
          try {
            const sessionResponse = await axios.get(`${RAG_SERVER_URL}/sessions/latest?project_name=${getCurrentProjectName()}`);
            sessionId = sessionResponse.data.session_id;
          } catch {
            const createResponse = await axios.post(`${RAG_SERVER_URL}/sessions/create?project_name=${getCurrentProjectName()}`, {
              description: "Claude Code CLI автосессия"
            });
            sessionId = createResponse.data.session_id;
          }
          
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
          const response = await axios.get(`${RAG_SERVER_URL}/file-snapshots/search`, {
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
          const projectRoot = args.project_root || process.cwd();
          
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
          
          const response = await axios.get(`${RAG_SERVER_URL}/memory-bank/context`, {
            params: {
              context_type: contextType,
              project_root: process.cwd()
            }
          });
          
          // Правильно извлекаем данные из нового формата ответа
          const contextData = response.data.context;
          const filesCount = response.data.files_count;
          
          let content = "";
          let filename = "";
          
          if (contextType === "project") {
            content = contextData["project-context"] || "Контекст проекта не найден";
            filename = "project-context.md";
          } else if (contextType === "active") {
            content = contextData["active-context"] || "Активный контекст не найден";  
            filename = "active-context.md";
          } else if (contextType === "progress") {
            content = contextData["progress"] || "Прогресс не найден";
            filename = "progress.md";
          } else if (contextType === "decisions") {
            content = contextData["decisions"] || "Решения не найдены";
            filename = "decisions.md";
          } else if (contextType === "patterns") {
            content = contextData["code-patterns"] || "Паттерны кода не найдены";
            filename = "code-patterns.md";
          }
          
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
            project_root: process.cwd(),
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
            project_root: process.cwd(),
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
              project_root: process.cwd()
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
          const response = await axios.get(`${RAG_SERVER_URL}/code-symbols/search`, {
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

main().catch(console.error);