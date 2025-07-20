#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import yaml from 'js-yaml';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { MemoryBankManager } from './memory-bank-manager.js';
import { FileWatcher } from './file-watcher.js';
import { FileWatcherV2 } from './file-watcher-v2.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Конфигурация RAG сервера
const RAG_SERVER_URL = 'http://localhost:8000';

// Функция для чтения config.yaml
async function loadConfig() {
  try {
    const configPath = path.join(__dirname, '..', 'config.yaml');
    const configFile = await fs.readFile(configPath, 'utf8');
    return yaml.load(configFile);
  } catch (error) {
    console.error('Ошибка чтения config.yaml:', error.message);
    return null;
  }
}

// Кэш проектных экземпляров для изоляции между проектами
const projectInstances = new Map();

// Функция для получения или создания экземпляров для конкретного проекта
function getProjectInstances(workingDirectory) {
  // Нормализуем путь
  const normalizedPath = workingDirectory.replace(/\\/g, '/');
  
  if (!projectInstances.has(normalizedPath)) {
    console.error(`🏗️ Создание новых экземпляров для проекта: ${normalizedPath}`);
    
    const memoryBankManager = new MemoryBankManager(normalizedPath);
    const fileWatcher = new FileWatcherV2(normalizedPath, memoryBankManager); // Используем V2!
    
    projectInstances.set(normalizedPath, {
      memoryBankManager,
      fileWatcher,
      lastUsed: Date.now()
    });
  } else {
    // Обновляем время последнего использования
    projectInstances.get(normalizedPath).lastUsed = Date.now();
  }
  
  return projectInstances.get(normalizedPath);
}

// Глобальная переменная для хранения текущего проекта (может быть установлена вручную)
let manualProjectPath = null;

// Функция для определения рабочей директории из запроса
function getWorkingDirectory(request) {
  console.error(`🔍 === ДЕТАЛЬНАЯ ДИАГНОСТИКА getWorkingDirectory ===`);
  
  // Логируем все доступные данные
  console.error(`📋 request.params:`, JSON.stringify(request.params, null, 2));
  console.error(`📋 request.meta:`, JSON.stringify(request.meta, null, 2));
  console.error(`📋 process.env.WORKSPACE_FOLDER:`, process.env.WORKSPACE_FOLDER);
  console.error(`📋 process.env.PWD:`, process.env.PWD);
  console.error(`📋 process.cwd():`, process.cwd());
  console.error(`📋 manualProjectPath:`, manualProjectPath);
  
  let workingDir = null;
  let source = 'unknown';
  
  // 1. Приоритет: Ручно установленный путь проекта
  if (manualProjectPath) {
    workingDir = manualProjectPath;
    source = 'manual';
  }
  
  // 2. Из мета-информации запроса (если Cline передает)
  if (!workingDir && request.meta && request.meta.workingDirectory) {
    workingDir = request.meta.workingDirectory;
    source = 'request.meta.workingDirectory';
  }
  
  // 3. Из других возможных мета-полей
  if (!workingDir && request.meta) {
    const possibleFields = ['projectPath', 'cwd', 'workspace', 'rootPath'];
    for (const field of possibleFields) {
      if (request.meta[field]) {
        workingDir = request.meta[field];
        source = `request.meta.${field}`;
        break;
      }
    }
  }
  
  // 4. Из переменных окружения
  if (!workingDir && process.env.WORKSPACE_FOLDER) {
    workingDir = process.env.WORKSPACE_FOLDER;
    source = 'process.env.WORKSPACE_FOLDER';
    // Исправляем проблему с ${workspaceFolder}
    if (workingDir.includes('${workspaceFolder}')) {
      workingDir = process.cwd();
      source = 'process.cwd() (fallback from ${workspaceFolder})';
    }
  }
  
  // 5. Из PWD переменной
  if (!workingDir && process.env.PWD) {
    workingDir = process.env.PWD;
    source = 'process.env.PWD';
  }
  
  // 6. Fallback на текущую директорию
  if (!workingDir) {
    workingDir = process.cwd();
    source = 'process.cwd() (fallback)';
  }
  
  console.error(`🎯 Определена рабочая директория: ${workingDir}`);
  console.error(`📍 Источник: ${source}`);
  console.error(`🔍 === КОНЕЦ ДИАГНОСТИКИ ===`);
  
  return workingDir;
}

// Функция для установки проекта вручную
function setManualProjectPath(path) {
  manualProjectPath = path;
  console.error(`🔧 Установлен ручной путь проекта: ${path}`);
}

// Очистка неиспользуемых экземпляров (каждые 30 минут)
setInterval(() => {
  const now = Date.now();
  const thirtyMinutes = 30 * 60 * 1000;
  
  for (const [path, instances] of projectInstances.entries()) {
    if (now - instances.lastUsed > thirtyMinutes) {
      console.error(`🧹 Очистка неиспользуемых экземпляров для: ${path}`);
      
      // Останавливаем File Watcher если он активен
      if (instances.fileWatcher.isWatching) {
        instances.fileWatcher.stopWatching();
      }
      
      projectInstances.delete(path);
    }
  }
}, 30 * 60 * 1000);

// Создаем MCP сервер
const server = new Server(
  {
    name: 'enhanced-rag-assistant',
    version: '2.0.0',
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

// Определяем инструменты
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // RAG инструменты (существующие)
      {
        name: 'ask_rag',
        description: 'Задать вопрос RAG серверу и получить ответ на основе документации',
        inputSchema: {
          type: 'object',
          properties: {
            question: {
              type: 'string',
              description: 'Вопрос пользователя',
            },
            framework: {
              type: 'string',
              description: 'Фреймворк для фильтрации (vue, laravel, alpine, filament, inertia, tailwindcss)',
              enum: ['vue', 'laravel', 'alpine', 'filament', 'inertia', 'tailwindcss'],
            },
            model: {
              type: 'string',
              description: 'Модель LLM для ответа (qwen или deepseek)',
              enum: ['qwen', 'deepseek'],
            },
            max_results: {
              type: 'number',
              description: 'Максимальное количество результатов (1-20)',
              minimum: 1,
              maximum: 20,
              default: 5,
            },
          },
          required: ['question'],
        },
      },
      {
        name: 'list_frameworks',
        description: 'Получить список доступных фреймворков с описаниями',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_rag_stats',
        description: 'Получить статистику базы данных RAG',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'list_models',
        description: 'Получить список доступных LLM моделей',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      
      // Memory Bank инструменты (новые)
      {
        name: 'memory_bank_init',
        description: 'Инициализировать Memory Bank в текущем проекте',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'memory_bank_status',
        description: 'Получить статус Memory Bank и информацию о файлах',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'memory_bank_read',
        description: 'Прочитать файл из Memory Bank',
        inputSchema: {
          type: 'object',
          properties: {
            filename: {
              type: 'string',
              description: 'Имя файла для чтения (например: tasks.md, progress.md, activeContext.md)',
            },
          },
          required: ['filename'],
        },
      },
      {
        name: 'memory_bank_write',
        description: 'Записать или обновить файл в Memory Bank',
        inputSchema: {
          type: 'object',
          properties: {
            filename: {
              type: 'string',
              description: 'Имя файла для записи',
            },
            content: {
              type: 'string',
              description: 'Содержимое файла',
            },
          },
          required: ['filename', 'content'],
        },
      },
      {
        name: 'memory_bank_search',
        description: 'Поиск в Memory Bank по ключевым словам',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Поисковый запрос',
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'memory_bank_archive',
        description: 'Архивировать завершенную задачу',
        inputSchema: {
          type: 'object',
          properties: {
            taskId: {
              type: 'string',
              description: 'Идентификатор задачи',
            },
            summary: {
              type: 'string',
              description: 'Краткое описание задачи',
            },
            completedWork: {
              type: 'string',
              description: 'Описание выполненной работы',
            },
            keyDecisions: {
              type: 'string',
              description: 'Ключевые решения',
            },
            lessonsLearned: {
              type: 'string',
              description: 'Извлеченные уроки',
            },
            filesModified: {
              type: 'string',
              description: 'Измененные файлы',
            },
            timeSpent: {
              type: 'string',
              description: 'Затраченное время',
            },
          },
          required: ['taskId'],
        },
      },
      
      // File Watcher инструменты
      {
        name: 'file_watcher_start',
        description: 'Запустить отслеживание изменений файлов',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'file_watcher_stop',
        description: 'Остановить отслеживание изменений файлов',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'file_watcher_stats',
        description: 'Получить статистику File Watcher',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      
      // Инструмент для управления проектом
      {
        name: 'set_project_path',
        description: 'Установить путь к проекту вручную для правильной работы File Watcher и Memory Bank',
        inputSchema: {
          type: 'object',
          properties: {
            path: {
              type: 'string',
              description: 'Полный путь к папке проекта (например: /Users/username/Projects/my-project)',
            },
          },
          required: ['path'],
        },
      },
      {
        name: 'get_current_project',
        description: 'Получить информацию о текущем проекте и доступных проектах в кэше',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});

// Обработчик вызова инструментов
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      // RAG инструменты
      case 'ask_rag': {
        const { question, framework, model, max_results = 5 } = args;
        
        const response = await axios.post(`${RAG_SERVER_URL}/ask`, {
          question,
          framework,
          model,
          max_results,
        });

        const data = response.data;
        
        let formattedAnswer = data.answer;
        
        if (data.sources && data.sources.length > 0) {
          formattedAnswer += '\n\n📚 Источники:';
          data.sources.forEach((source, index) => {
            formattedAnswer += `\n${index + 1}. [${source.framework}] ${source.source}`;
            if (source.heading) {
              formattedAnswer += ` - ${source.heading}`;
            }
          });
        }
        
        if (data.framework_detected) {
          formattedAnswer += `\n\n🎯 Определен фреймворк: ${data.framework_detected}`;
        }
        
        return {
          content: [
            {
              type: 'text',
              text: formattedAnswer,
            },
          ],
        };
      }

      case 'list_frameworks': {
        let frameworks = {};
        let source = 'unknown';
        
        // Сначала пытаемся прочитать из локального config.yaml
        try {
          const config = await loadConfig();
          if (config && config.frameworks) {
            frameworks = config.frameworks;
            source = 'config.yaml';
          }
        } catch (error) {
          console.error('Ошибка чтения локального config.yaml:', error.message);
        }
        
        // Если локальный config не содержит фреймворки, обращаемся к RAG серверу
        if (Object.keys(frameworks).length === 0) {
          try {
            const response = await axios.get(`${RAG_SERVER_URL}/frameworks`);
            frameworks = response.data;
            source = 'RAG server';
          } catch (error) {
            return {
              content: [
                {
                  type: 'text',
                  text: `❌ Не удалось получить список фреймворков:\n- Локальный config.yaml недоступен или пуст\n- RAG сервер недоступен: ${error.message}`,
                },
              ],
            };
          }
        }
        
        let text = `📦 Доступные фреймворки (источник: ${source}):\n\n`;
        
        for (const [key, info] of Object.entries(frameworks)) {
          text += `**${info.name || key}** (${key})\n`;
          text += `${info.description || 'Описание отсутствует'}\n`;
          text += `Тип: ${info.type || 'не указан'}\n`;
          text += `Статус: ${info.enabled ? '✅ Включен' : '❌ Отключен'}\n\n`;
        }
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      case 'get_rag_stats': {
        const response = await axios.get(`${RAG_SERVER_URL}/stats`);
        const stats = response.data;
        
        let text = '📊 Статистика RAG базы данных:\n\n';
        text += `📚 Всего документов: ${stats.total_documents}\n`;
        text += `💾 Размер кэша: ${stats.cache_size}\n\n`;
        
        if (stats.frameworks) {
          text += '📈 Распределение по фреймворкам:\n';
          for (const [framework, count] of Object.entries(stats.frameworks)) {
            text += `  • ${framework}: ${count} документов\n`;
          }
        }
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      case 'list_models': {
        const response = await axios.get(`${RAG_SERVER_URL}/models`);
        const modelsData = response.data;
        
        let text = '🤖 Доступные LLM модели:\n\n';
        
        for (const [key, info] of Object.entries(modelsData.models)) {
          text += `**${info.name}** (${key})\n`;
          text += `Максимум токенов: ${info.max_tokens}\n`;
          text += `Температура: ${info.temperature}\n\n`;
        }
        
        text += `Модель по умолчанию: **${modelsData.default}**\n`;
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      // Memory Bank инструменты
      case 'memory_bank_init': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        const result = await memoryBankManager.initializeMemoryBank();
        
        return {
          content: [
            {
              type: 'text',
              text: result.success 
                ? `✅ ${result.message}\n📁 Путь: ${result.path}\n🎯 Проект: ${workingDir}`
                : `❌ ${result.message}`,
            },
          ],
        };
      }

      case 'memory_bank_status': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        // Автоматическая инициализация при первом обращении
        const ensureResult = await memoryBankManager.ensureMemoryBankExists();
        if (!ensureResult.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${ensureResult.message}`,
              },
            ],
          };
        }

        const status = await memoryBankManager.getMemoryBankStatus();
        
        let text = '📊 Статус Memory Bank:\n\n';
        
        if (ensureResult.created) {
          text += `🆕 Memory Bank автоматически создан для проекта\n`;
        } else {
          text += `✅ Используется существующий Memory Bank\n`;
        }
        
        text += `📁 Путь: ${status.path}\n`;
        text += `🎯 Проект: ${workingDir}\n\n`;
        
        text += '📄 Файлы:\n';
        status.files.forEach(file => {
          text += `  • ${file.name} (${file.lines} строк, изменен: ${new Date(file.modified).toLocaleString('ru-RU')})\n`;
        });
        
        if (status.directories.length > 0) {
          text += '\n📂 Папки:\n';
          status.directories.forEach(dir => {
            text += `  • ${dir.name}/ (${dir.files} файлов)\n`;
          });
        }
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      case 'memory_bank_read': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        // Автоматическая инициализация при первом обращении
        const ensureResult = await memoryBankManager.ensureMemoryBankExists();
        if (!ensureResult.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${ensureResult.message}`,
              },
            ],
          };
        }

        const { filename } = args;
        const result = await memoryBankManager.readMemoryBankFile(filename);
        
        let responseText = '';
        if (ensureResult.created) {
          responseText += `🆕 Memory Bank автоматически создан для проекта\n\n`;
        }
        
        responseText += result.success 
          ? `📄 **${filename}**\n🎯 Проект: ${workingDir}\n\n${result.content}`
          : `❌ ${result.message}`;
        
        return {
          content: [
            {
              type: 'text',
              text: responseText,
            },
          ],
        };
      }

      case 'memory_bank_write': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        // Автоматическая инициализация при первом обращении
        const ensureResult = await memoryBankManager.ensureMemoryBankExists();
        if (!ensureResult.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${ensureResult.message}`,
              },
            ],
          };
        }

        const { filename, content } = args;
        const result = await memoryBankManager.writeMemoryBankFile(filename, content);
        
        let responseText = '';
        if (ensureResult.created) {
          responseText += `🆕 Memory Bank автоматически создан для проекта\n\n`;
        }
        
        responseText += result.success 
          ? `✅ ${result.message}\n🎯 Проект: ${workingDir}`
          : `❌ ${result.message}`;
        
        return {
          content: [
            {
              type: 'text',
              text: responseText,
            },
          ],
        };
      }

      case 'memory_bank_search': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        // Автоматическая инициализация при первом обращении
        const ensureResult = await memoryBankManager.ensureMemoryBankExists();
        if (!ensureResult.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${ensureResult.message}`,
              },
            ],
          };
        }

        const { query } = args;
        const result = await memoryBankManager.searchMemoryBank(query);
        
        if (!result.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${result.message}`,
              },
            ],
          };
        }

        let text = '';
        if (ensureResult.created) {
          text += `🆕 Memory Bank автоматически создан для проекта\n\n`;
        }
        
        text += `🔍 Результаты поиска для "${query}":\n`;
        text += `🎯 Проект: ${workingDir}\n`;
        text += `Найдено: ${result.total} совпадений\n\n`;
        
        if (result.results.length === 0) {
          text += 'Совпадений не найдено.';
        } else {
          result.results.forEach((match, index) => {
            text += `**${index + 1}. ${match.file}** (строка ${match.line})\n`;
            text += `${match.content}\n\n`;
          });
        }
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      case 'memory_bank_archive': {
        const workingDir = getWorkingDirectory(request);
        const { memoryBankManager } = getProjectInstances(workingDir);
        
        // Автоматическая инициализация при первом обращении
        const ensureResult = await memoryBankManager.ensureMemoryBankExists();
        if (!ensureResult.success) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ ${ensureResult.message}`,
              },
            ],
          };
        }

        const { taskId, ...taskData } = args;
        const result = await memoryBankManager.archiveTask(taskId, taskData);
        
        let responseText = '';
        if (ensureResult.created) {
          responseText += `🆕 Memory Bank автоматически создан для проекта\n\n`;
        }
        
        responseText += result.success 
          ? `✅ Задача "${taskId}" архивирована успешно\n🎯 Проект: ${workingDir}`
          : `❌ ${result.message}`;
        
        return {
          content: [
            {
              type: 'text',
              text: responseText,
            },
          ],
        };
      }

      // File Watcher инструменты
      case 'file_watcher_start': {
        const workingDir = getWorkingDirectory(request);
        const { fileWatcher } = getProjectInstances(workingDir);
        
        const result = await fileWatcher.startWatching();
        
        return {
          content: [
            {
              type: 'text',
              text: result.success 
                ? `✅ ${result.message}\n📁 Отслеживается файлов: ${result.watchedFiles}\n🎯 Проект: ${workingDir}`
                : `❌ ${result.message}`,
            },
          ],
        };
      }

      case 'file_watcher_stop': {
        const workingDir = getWorkingDirectory(request);
        const { fileWatcher } = getProjectInstances(workingDir);
        
        const result = fileWatcher.stopWatching();
        
        return {
          content: [
            {
              type: 'text',
              text: result.success 
                ? `✅ ${result.message}\n🎯 Проект: ${workingDir}`
                : `❌ ${result.message}`,
            },
          ],
        };
      }

      case 'file_watcher_stats': {
        const workingDir = getWorkingDirectory(request);
        const { fileWatcher } = getProjectInstances(workingDir);
        
        const stats = fileWatcher.getStats();
        
        let text = '📊 Статистика File Watcher V2:\n\n';
        text += `🔍 Статус: ${stats.isWatching ? 'Активен' : 'Остановлен'}\n`;
        text += `📁 Отслеживается файлов: ${stats.watchedFiles}\n`;
        text += `🎯 Проект: ${workingDir}\n\n`;
        
        // Показываем новые возможности V2
        if (stats.version === '2.0') {
          text += `🚀 **File Watcher V2 - Революционные возможности:**\n`;
          text += `👁️ Реальное время отслеживание: ${stats.realTimeWatchers || 0} директорий\n`;
          text += `⚡ Буферизованные изменения: ${stats.bufferedChanges || 0}\n`;
          text += `🔧 Возможности: ${stats.features ? stats.features.join(', ') : 'real-time, content-analysis'}\n\n`;
        } else {
          text += `⏱️ Интервал проверки: ${stats.pollInterval || 'N/A'}мс\n`;
        }
        
        text += `🚫 Игнорируемых паттернов: ${stats.ignoredPatterns}\n`;
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      // Инструменты управления проектом
      case 'set_project_path': {
        const { path } = args;
        
        try {
          // Проверяем что путь существует
          const fs = await import('fs/promises');
          const stats = await fs.stat(path);
          
          if (!stats.isDirectory()) {
            return {
              content: [
                {
                  type: 'text',
                  text: `❌ Указанный путь не является папкой: ${path}`,
                },
              ],
            };
          }
          
          // Устанавливаем новый путь проекта
          setManualProjectPath(path);
          
          let text = `✅ Путь проекта установлен успешно!\n\n`;
          text += `🎯 Новый проект: ${path}\n`;
          text += `📋 Теперь File Watcher и Memory Bank будут работать с этим проектом\n\n`;
          text += `💡 Рекомендуется:\n`;
          text += `1. Остановить File Watcher если он был активен\n`;
          text += `2. Запустить File Watcher заново для нового проекта\n`;
          text += `3. Проверить статус Memory Bank для нового проекта`;
          
          return {
            content: [
              {
                type: 'text',
                text,
              },
            ],
          };
        } catch (error) {
          return {
            content: [
              {
                type: 'text',
                text: `❌ Ошибка при установке пути проекта: ${error.message}\n\nУбедитесь что путь существует и доступен для чтения.`,
              },
            ],
          };
        }
      }

      case 'get_current_project': {
        const workingDir = getWorkingDirectory(request);
        
        let text = '📊 Информация о текущем проекте:\n\n';
        text += `🎯 Текущий проект: ${workingDir}\n`;
        text += `📍 Источник определения: ${manualProjectPath ? 'Установлен вручную' : 'Автоматическое определение'}\n\n`;
        
        text += '💾 Кэшированные проекты:\n';
        if (projectInstances.size === 0) {
          text += '  • Нет кэшированных проектов\n';
        } else {
          for (const [path, instances] of projectInstances.entries()) {
            const lastUsedDate = new Date(instances.lastUsed).toLocaleString('ru-RU');
            const isActive = instances.fileWatcher.isWatching ? '🟢 Активен' : '⚪ Остановлен';
            text += `  • ${path}\n`;
            text += `    File Watcher: ${isActive}\n`;
            text += `    Последнее использование: ${lastUsedDate}\n\n`;
          }
        }
        
        text += '🔧 Доступные действия:\n';
        text += '• Используйте `set_project_path` для смены проекта\n';
        text += '• Используйте `file_watcher_stats` для проверки текущего состояния\n';
        text += '• Используйте `memory_bank_status` для проверки Memory Bank';
        
        return {
          content: [
            {
              type: 'text',
              text,
            },
          ],
        };
      }

      default:
        throw new Error(`Неизвестный инструмент: ${name}`);
    }
  } catch (error) {
    let errorMessage = `Ошибка при выполнении ${name}: `;
    
    if (error.response) {
      errorMessage += `${error.response.status} - ${error.response.statusText}`;
      if (error.response.data && error.response.data.detail) {
        errorMessage += `\n${error.response.data.detail}`;
      }
    } else if (error.request) {
      errorMessage += 'RAG сервер не отвечает. Убедитесь, что он запущен на http://localhost:8000';
    } else {
      errorMessage += error.message;
    }
    
    return {
      content: [
        {
          type: 'text',
          text: errorMessage,
        },
      ],
      isError: true,
    };
  }
});

// Определяем ресурсы
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      // RAG ресурсы
      {
        uri: 'rag://frameworks',
        name: 'Список фреймворков',
        description: 'Информация о доступных фреймворках в RAG базе',
        mimeType: 'application/json',
      },
      {
        uri: 'rag://stats',
        name: 'Статистика RAG базы данных',
        description: 'Статистика документов в RAG базе',
        mimeType: 'application/json',
      },
      {
        uri: 'rag://models',
        name: 'Список моделей',
        description: 'Информация о доступных LLM моделях',
        mimeType: 'application/json',
      },
      
      // Memory Bank ресурсы
      {
        uri: 'memory://status',
        name: 'Статус Memory Bank',
        description: 'Информация о состоянии Memory Bank',
        mimeType: 'application/json',
      },
      {
        uri: 'memory://tasks',
        name: 'Активные задачи',
        description: 'Содержимое файла tasks.md',
        mimeType: 'text/markdown',
      },
      {
        uri: 'memory://progress',
        name: 'Прогресс проекта',
        description: 'Содержимое файла progress.md',
        mimeType: 'text/markdown',
      },
      {
        uri: 'memory://context',
        name: 'Активный контекст',
        description: 'Содержимое файла activeContext.md',
        mimeType: 'text/markdown',
      },
    ],
  };
});

// Обработчик чтения ресурсов
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  try {
    // RAG ресурсы
    if (uri.startsWith('rag://')) {
      const endpoint = uri.replace('rag://', '');
      const response = await axios.get(`${RAG_SERVER_URL}/${endpoint}`);
      
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(response.data, null, 2),
          },
        ],
      };
    }
    
    // Memory Bank ресурсы
    if (uri.startsWith('memory://')) {
      const resource = uri.replace('memory://', '');
      const workingDir = getWorkingDirectory(request);
      const { memoryBankManager } = getProjectInstances(workingDir);
      
      switch (resource) {
        case 'status': {
          await memoryBankManager.ensureMemoryBankExists();
          const status = await memoryBankManager.getMemoryBankStatus();
          
          // Добавляем информацию о проекте в статус
          status.workingDirectory = workingDir;
          
          return {
            contents: [
              {
                uri,
                mimeType: 'application/json',
                text: JSON.stringify(status, null, 2),
              },
            ],
          };
        }
        
        case 'tasks': {
          // Автоматическая инициализация при обращении к ресурсу
          await memoryBankManager.ensureMemoryBankExists();
          const result = await memoryBankManager.readMemoryBankFile('tasks.md');
          
          let content = result.success ? result.content : `Ошибка: ${result.message}`;
          content += `\n\n---\n🎯 Проект: ${workingDir}`;
          
          return {
            contents: [
              {
                uri,
                mimeType: 'text/markdown',
                text: content,
              },
            ],
          };
        }
        
        case 'progress': {
          // Автоматическая инициализация при обращении к ресурсу
          await memoryBankManager.ensureMemoryBankExists();
          const result = await memoryBankManager.readMemoryBankFile('progress.md');
          
          let content = result.success ? result.content : `Ошибка: ${result.message}`;
          content += `\n\n---\n🎯 Проект: ${workingDir}`;
          
          return {
            contents: [
              {
                uri,
                mimeType: 'text/markdown',
                text: content,
              },
            ],
          };
        }
        
        case 'context': {
          // Автоматическая инициализация при обращении к ресурсу
          await memoryBankManager.ensureMemoryBankExists();
          const result = await memoryBankManager.readMemoryBankFile('activeContext.md');
          
          let content = result.success ? result.content : `Ошибка: ${result.message}`;
          content += `\n\n---\n🎯 Проект: ${workingDir}`;
          
          return {
            contents: [
              {
                uri,
                mimeType: 'text/markdown',
                text: content,
              },
            ],
          };
        }
        
        default:
          throw new Error(`Неизвестный ресурс Memory Bank: ${resource}`);
      }
    }

    throw new Error(`Неизвестный ресурс: ${uri}`);
  } catch (error) {
    throw new Error(`Ошибка при чтении ресурса ${uri}: ${error.message}`);
  }
});

// Обработчики событий File Watcher теперь создаются динамически для каждого проекта
// в функции getProjectInstances()

// Запуск сервера
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.error('🚀 Enhanced RAG + Memory Bank MCP server started');
  console.error('📚 RAG functions: ask_rag, list_frameworks, get_rag_stats, list_models');
  console.error('🧠 Memory Bank functions: memory_bank_*, file_watcher_*');
}

main().catch((error) => {
  console.error('Server startup error:', error);
  process.exit(1);
});
