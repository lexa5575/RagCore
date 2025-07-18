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

// Конфигурация RAG сервера
const RAG_SERVER_URL = 'http://localhost:8000';

// Создаем MCP сервер
const server = new Server(
  {
    name: 'rag-assistant',
    version: '1.0.0',
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
        name: 'get_stats',
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
    ],
  };
});

// Обработчик вызова инструментов
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'ask_rag': {
        const { question, framework, model, max_results = 5 } = args;
        
        // Отправляем запрос к RAG серверу
        const response = await axios.post(`${RAG_SERVER_URL}/ask`, {
          question,
          framework,
          model,
          max_results,
        });

        const data = response.data;
        
        // Форматируем ответ
        let formattedAnswer = data.answer;
        
        // Добавляем информацию об источниках
        if (data.sources && data.sources.length > 0) {
          formattedAnswer += '\n\n📚 Источники:';
          data.sources.forEach((source, index) => {
            formattedAnswer += `\n${index + 1}. [${source.framework}] ${source.source}`;
            if (source.heading) {
              formattedAnswer += ` - ${source.heading}`;
            }
          });
        }
        
        // Добавляем информацию о фреймворке
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
        const response = await axios.get(`${RAG_SERVER_URL}/frameworks`);
        const frameworks = response.data;
        
        let text = '📦 Доступные фреймворки:\n\n';
        
        for (const [key, info] of Object.entries(frameworks)) {
          text += `**${info.name}** (${key})\n`;
          text += `${info.description}\n`;
          text += `Тип: ${info.type}\n\n`;
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

      case 'get_stats': {
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
        
        text += `Модель по умолчанию: **${modelsData.default}**\n\n`;
        text += `Для использования конкретной модели, укажите параметр model при вызове ask_rag:\n`;
        text += `Например: "Используй ask_rag с model="deepseek" чтобы узнать что такое компонент"`;
        
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
    // Обработка ошибок
    let errorMessage = `Ошибка при выполнении ${name}: `;
    
    if (error.response) {
      // Ошибка от RAG сервера
      errorMessage += `${error.response.status} - ${error.response.statusText}`;
      if (error.response.data && error.response.data.detail) {
        errorMessage += `\n${error.response.data.detail}`;
      }
    } else if (error.request) {
      // Нет ответа от сервера
      errorMessage += 'RAG сервер не отвечает. Убедитесь, что он запущен на http://localhost:8000';
    } else {
      // Другая ошибка
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
      {
        uri: 'rag://frameworks',
        name: 'Список фреймворков',
        description: 'Информация о доступных фреймворках в RAG базе',
        mimeType: 'application/json',
      },
      {
        uri: 'rag://stats',
        name: 'Статистика базы данных',
        description: 'Статистика документов в RAG базе',
        mimeType: 'application/json',
      },
      {
        uri: 'rag://models',
        name: 'Список моделей',
        description: 'Информация о доступных LLM моделях',
        mimeType: 'application/json',
      },
    ],
  };
});

// Обработчик чтения ресурсов
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  try {
    switch (uri) {
      case 'rag://frameworks': {
        const response = await axios.get(`${RAG_SERVER_URL}/frameworks`);
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

      case 'rag://stats': {
        const response = await axios.get(`${RAG_SERVER_URL}/stats`);
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

      case 'rag://models': {
        const response = await axios.get(`${RAG_SERVER_URL}/models`);
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

      default:
        throw new Error(`Неизвестный ресурс: ${uri}`);
    }
  } catch (error) {
    throw new Error(`Ошибка при чтении ресурса ${uri}: ${error.message}`);
  }
});

// Запуск сервера
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.error('RAG MCP server started');
}

main().catch((error) => {
  console.error('Server startup error:', error);
  process.exit(1);
});
