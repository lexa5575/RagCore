import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class MemoryBankManager {
  constructor(projectRoot = process.env.WORKSPACE_FOLDER || process.cwd()) {
    // Исправляем проблему с ${workspaceFolder} - используем реальный путь
    if (projectRoot && projectRoot.includes('${workspaceFolder}')) {
      projectRoot = process.cwd();
    }
    this.projectRoot = projectRoot;
    this.memoryBankPath = path.join(projectRoot, 'memory-bank');
  }

  // Умная автоматическая инициализация Memory Bank
  async ensureMemoryBankExists() {
    try {
      const hasBank = await this.hasMemoryBank();
      
      if (!hasBank) {
        console.log(`🧠 Auto-initializing Memory Bank for project: ${this.projectRoot}`);
        const result = await this.initializeMemoryBank();
        
        if (result.success) {
          console.log(`✅ Memory Bank auto-created at: ${result.path}`);
          return {
            success: true,
            created: true,
            message: `Memory Bank auto-initialized for project`,
            path: result.path
          };
        } else {
          console.error(`❌ Failed to auto-initialize Memory Bank: ${result.message}`);
          return {
            success: false,
            created: false,
            message: result.message
          };
        }
      } else {
        // Memory Bank уже существует - используем его
        return {
          success: true,
          created: false,
          message: 'Using existing Memory Bank',
          path: this.memoryBankPath
        };
      }
    } catch (error) {
      console.error(`❌ Error in ensureMemoryBankExists: ${error.message}`);
      return {
        success: false,
        created: false,
        message: `Auto-initialization failed: ${error.message}`
      };
    }
  }

  // Проверка существования Memory Bank
  async hasMemoryBank() {
    try {
      const stats = await fs.stat(this.memoryBankPath);
      return stats.isDirectory();
    } catch (error) {
      return false;
    }
  }

  // Инициализация Memory Bank структуры
  async initializeMemoryBank() {
    try {
      // Создаем основную папку
      await fs.mkdir(this.memoryBankPath, { recursive: true });
      
      // Создаем подпапки
      await fs.mkdir(path.join(this.memoryBankPath, 'creative'), { recursive: true });
      await fs.mkdir(path.join(this.memoryBankPath, 'reflection'), { recursive: true });
      await fs.mkdir(path.join(this.memoryBankPath, 'archive'), { recursive: true });

      // Создаем основные файлы
      const files = {
        'projectbrief.md': this.getProjectBriefTemplate(),
        'tasks.md': this.getTasksTemplate(),
        'activeContext.md': this.getActiveContextTemplate(),
        'progress.md': this.getProgressTemplate(),
        'productContext.md': this.getProductContextTemplate(),
        'systemPatterns.md': this.getSystemPatternsTemplate(),
        'techContext.md': this.getTechContextTemplate(),
        'style-guide.md': this.getStyleGuideTemplate()
      };

      for (const [filename, content] of Object.entries(files)) {
        const filePath = path.join(this.memoryBankPath, filename);
        await fs.writeFile(filePath, content, 'utf8');
      }

      return {
        success: true,
        message: 'Memory Bank инициализирован успешно',
        path: this.memoryBankPath
      };
    } catch (error) {
      return {
        success: false,
        message: `Ошибка инициализации Memory Bank: ${error.message}`,
        error: error.message
      };
    }
  }

  // Чтение файла Memory Bank
  async readMemoryBankFile(filename) {
    try {
      const filePath = path.join(this.memoryBankPath, filename);
      const content = await fs.readFile(filePath, 'utf8');
      return {
        success: true,
        content,
        filename,
        path: filePath
      };
    } catch (error) {
      return {
        success: false,
        message: `Ошибка чтения файла ${filename}: ${error.message}`,
        error: error.message
      };
    }
  }

  // Запись в файл Memory Bank
  async writeMemoryBankFile(filename, content) {
    try {
      const filePath = path.join(this.memoryBankPath, filename);
      await fs.writeFile(filePath, content, 'utf8');
      return {
        success: true,
        message: `Файл ${filename} обновлен успешно`,
        filename,
        path: filePath
      };
    } catch (error) {
      return {
        success: false,
        message: `Ошибка записи файла ${filename}: ${error.message}`,
        error: error.message
      };
    }
  }

  // Получение статуса Memory Bank
  async getMemoryBankStatus() {
    try {
      const hasBank = await this.hasMemoryBank();
      if (!hasBank) {
        return {
          exists: false,
          message: 'Memory Bank не инициализирован'
        };
      }

      const files = await fs.readdir(this.memoryBankPath);
      const status = {
        exists: true,
        path: this.memoryBankPath,
        files: [],
        directories: []
      };

      for (const file of files) {
        const filePath = path.join(this.memoryBankPath, file);
        const stats = await fs.stat(filePath);
        
        if (stats.isDirectory()) {
          const subFiles = await fs.readdir(filePath);
          status.directories.push({
            name: file,
            files: subFiles.length
          });
        } else {
          const content = await fs.readFile(filePath, 'utf8');
          status.files.push({
            name: file,
            size: stats.size,
            modified: stats.mtime,
            lines: content.split('\n').length
          });
        }
      }

      return status;
    } catch (error) {
      return {
        exists: false,
        error: error.message
      };
    }
  }

  // Поиск в Memory Bank
  async searchMemoryBank(query) {
    try {
      const hasBank = await this.hasMemoryBank();
      if (!hasBank) {
        return {
          success: false,
          message: 'Memory Bank не инициализирован'
        };
      }

      const results = [];
      const searchInDirectory = async (dirPath, relativePath = '') => {
        const files = await fs.readdir(dirPath);
        
        for (const file of files) {
          const filePath = path.join(dirPath, file);
          const stats = await fs.stat(filePath);
          
          if (stats.isDirectory()) {
            await searchInDirectory(filePath, path.join(relativePath, file));
          } else if (file.endsWith('.md')) {
            const content = await fs.readFile(filePath, 'utf8');
            const lines = content.split('\n');
            
            lines.forEach((line, index) => {
              if (line.toLowerCase().includes(query.toLowerCase())) {
                results.push({
                  file: path.join(relativePath, file),
                  line: index + 1,
                  content: line.trim(),
                  context: lines.slice(Math.max(0, index - 1), index + 2)
                });
              }
            });
          }
        }
      };

      await searchInDirectory(this.memoryBankPath);

      return {
        success: true,
        query,
        results,
        total: results.length
      };
    } catch (error) {
      return {
        success: false,
        message: `Ошибка поиска: ${error.message}`,
        error: error.message
      };
    }
  }

  // Архивирование задачи
  async archiveTask(taskId, taskData) {
    try {
      // Убеждаемся что Memory Bank существует
      await this.ensureMemoryBankExists();
      
      // Убеждаемся что папка archive существует
      const archiveDir = path.join(this.memoryBankPath, 'archive');
      await fs.mkdir(archiveDir, { recursive: true });
      
      const timestamp = new Date().toISOString().split('T')[0];
      const archiveFilename = `archive-${taskId}-${timestamp}.md`;
      const archiveContent = this.getArchiveTemplate(taskId, taskData);
      
      // Записываем файл напрямую в папку archive
      const archiveFilePath = path.join(archiveDir, archiveFilename);
      await fs.writeFile(archiveFilePath, archiveContent, 'utf8');
      
      // Очищаем tasks.md после архивирования
      await this.writeMemoryBankFile('tasks.md', this.getTasksTemplate());
      
      return {
        success: true,
        message: `Задача "${taskId}" архивирована успешно`,
        filename: archiveFilename,
        path: archiveFilePath
      };
    } catch (error) {
      return {
        success: false,
        message: `Ошибка архивирования: ${error.message}`,
        error: error.message
      };
    }
  }

  // Шаблоны файлов
  getProjectBriefTemplate() {
    return `# Project Brief

## Project Overview
[Краткое описание проекта]

## Goals and Objectives
- [Цель 1]
- [Цель 2]

## Key Stakeholders
- [Заинтересованная сторона 1]
- [Заинтересованная сторона 2]

## Success Criteria
- [Критерий успеха 1]
- [Критерий успеха 2]

## Timeline
- Start Date: [Дата начала]
- Target Completion: [Целевая дата завершения]

---
*Создано: ${new Date().toISOString()}*
`;
  }

  getTasksTemplate() {
    return `# Active Tasks

## Current Task
[Описание текущей задачи]

## Task Checklist
- [ ] [Подзадача 1]
- [ ] [Подзадача 2]
- [ ] [Подзадача 3]

## Components
- [Компонент 1]
- [Компонент 2]

## Notes
[Заметки и важные моменты]

---
*Обновлено: ${new Date().toISOString()}*
`;
  }

  getActiveContextTemplate() {
    return `# Active Context

## Current Focus
[Текущий фокус разработки]

## Working On
- [Что делаем сейчас]

## Next Steps
1. [Следующий шаг 1]
2. [Следующий шаг 2]

## Blockers
- [Блокер 1]
- [Блокер 2]

---
*Обновлено: ${new Date().toISOString()}*
`;
  }

  getProgressTemplate() {
    return `# Progress Tracking

## Completed
- [x] [Завершенная задача 1]
- [x] [Завершенная задача 2]

## In Progress
- [ ] [Задача в работе 1]
- [ ] [Задача в работе 2]

## Planned
- [ ] [Запланированная задача 1]
- [ ] [Запланированная задача 2]

## Metrics
- Progress: [X]%
- Time Spent: [X] hours
- Estimated Remaining: [X] hours

---
*Обновлено: ${new Date().toISOString()}*
`;
  }

  getProductContextTemplate() {
    return `# Product Context

## Product Vision
[Видение продукта]

## Target Users
- [Целевая аудитория 1]
- [Целевая аудитория 2]

## Key Features
- [Ключевая функция 1]
- [Ключевая функция 2]

## Business Requirements
- [Бизнес-требование 1]
- [Бизнес-требование 2]

---
*Создано: ${new Date().toISOString()}*
`;
  }

  getSystemPatternsTemplate() {
    return `# System Patterns

## Architecture Patterns
- [Паттерн архитектуры 1]
- [Паттерн архитектуры 2]

## Design Patterns
- [Паттерн дизайна 1]
- [Паттерн дизайна 2]

## Coding Standards
- [Стандарт кодирования 1]
- [Стандарт кодирования 2]

## Best Practices
- [Лучшая практика 1]
- [Лучшая практика 2]

---
*Создано: ${new Date().toISOString()}*
`;
  }

  getTechContextTemplate() {
    return `# Technical Context

## Technology Stack
- Frontend: [Технология фронтенда]
- Backend: [Технология бэкенда]
- Database: [База данных]
- Infrastructure: [Инфраструктура]

## Dependencies
- [Зависимость 1]
- [Зависимость 2]

## Development Environment
- [Требование к среде 1]
- [Требование к среде 2]

## Deployment
- [Информация о развертывании]

---
*Создано: ${new Date().toISOString()}*
`;
  }

  getStyleGuideTemplate() {
    return `# Style Guide

## Code Style
- [Правило стиля кода 1]
- [Правило стиля кода 2]

## Naming Conventions
- [Соглашение об именовании 1]
- [Соглашение об именовании 2]

## Documentation Standards
- [Стандарт документации 1]
- [Стандарт документации 2]

## Review Guidelines
- [Руководство по ревью 1]
- [Руководство по ревью 2]

---
*Создано: ${new Date().toISOString()}*
`;
  }

  getArchiveTemplate(taskId, taskData) {
    return `# Archive: ${taskId}

## Task Summary
${taskData.summary || '[Краткое описание задачи]'}

## Completed Work
${taskData.completedWork || '[Описание выполненной работы]'}

## Key Decisions
${taskData.keyDecisions || '[Ключевые решения]'}

## Lessons Learned
${taskData.lessonsLearned || '[Извлеченные уроки]'}

## Files Modified
${taskData.filesModified || '[Измененные файлы]'}

## Time Spent
${taskData.timeSpent || '[Затраченное время]'}

---
*Архивировано: ${new Date().toISOString()}*
`;
  }
}
