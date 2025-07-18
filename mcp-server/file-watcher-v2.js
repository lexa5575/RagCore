import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import { EventEmitter } from 'events';

export class FileWatcherV2 extends EventEmitter {
  constructor(projectRoot = process.env.WORKSPACE_FOLDER || process.cwd(), memoryBankManager) {
    super();
    this.projectRoot = projectRoot;
    this.memoryBankManager = memoryBankManager;
    this.watchedFiles = new Map();
    this.fsWatchers = new Map(); // Нативные fs.watch() экземпляры
    this.isWatching = false;
    this.changeBuffer = new Map(); // Буфер для группировки изменений
    this.bufferTimeout = null;
    this.bufferDelay = 500; // Группировка изменений в течение 500мс
    
    // НОВАЯ СИСТЕМА БАТЧИНГА - раз в минуту вместо спама
    this.changesBatch = []; // Буфер изменений для батчинга
    this.batchTimer = null;
    this.batchInterval = 60000; // 1 минута
    this.lastBatchTime = Date.now();
    
    console.error(`🚀 FileWatcherV2 constructor called - Real-time file watching with smart batching enabled`);
    
    // ПРИНУДИТЕЛЬНАЯ ОЧИСТКА СОСТОЯНИЯ при инициализации
    this.forceReset();
    
    // Абсолютные пути Memory Bank для полного игнорирования
    this.memoryBankPaths = [
      path.join(this.projectRoot, 'memory-bank'),
      path.join(this.projectRoot, '${workspaceFolder}', 'memory-bank')
    ];
    
    // Игнорируемые файлы и папки (расширенный список)
    this.ignoredPatterns = [
      /node_modules/,
      /\.git/,
      /\.vscode/,
      /\.idea/,
      /dist/,
      /build/,
      /coverage/,
      /\.DS_Store/,
      /\.env/,
      /\.log$/,
      /\.tmp$/,
      /chroma_storage/,
      /embedding_cache/,
      /__pycache__/,
      /\.pyc$/,
      /\.swp$/,
      /\.swo$/,
      /~$/,
      /\.backup$/,
      /\.bak$/
    ];

    // Конфигурация для анализа содержимого
    this.contentAnalysisConfig = {
      maxFileSize: 1024 * 1024, // 1MB максимум для анализа содержимого
      enableDiffAnalysis: true,
      enableSemanticAnalysis: true
    };
  }

  // Запуск отслеживания с реальным временем
  async startWatching() {
    if (this.isWatching) {
      return { success: false, message: 'File Watcher V2 уже запущен' };
    }

    try {
      console.log('🚀 Starting File Watcher V2 with real-time monitoring...');
      
      // Инициализируем список файлов
      await this.scanProject();
      
      // Запускаем нативное отслеживание файловой системы
      await this.setupRealTimeWatching();
      
      this.isWatching = true;
      
      console.log('✅ File Watcher V2 started with real-time monitoring');
      return { 
        success: true, 
        message: 'File Watcher V2 started successfully with real-time monitoring',
        watchedFiles: this.watchedFiles.size,
        realTimeWatchers: this.fsWatchers.size
      };
    } catch (error) {
      console.error('❌ File Watcher V2 startup error:', error);
      return { 
        success: false, 
        message: `Startup error: ${error.message}` 
      };
    }
  }

  // Настройка реального времени отслеживания
  async setupRealTimeWatching() {
    const watchDirectory = async (dirPath) => {
      try {
        // Проверяем что директория не игнорируется
        const relativePath = path.relative(this.projectRoot, dirPath);
        if (this.shouldIgnore(relativePath)) {
          return;
        }

        // Создаем fs.watch для директории
        const watcher = fsSync.watch(dirPath, { recursive: false }, (eventType, filename) => {
          if (filename) {
            const fullPath = path.join(dirPath, filename);
            this.handleFileSystemEvent(eventType, fullPath);
          }
        });

        this.fsWatchers.set(dirPath, watcher);

        // Рекурсивно настраиваем отслеживание поддиректорий
        const files = await fs.readdir(dirPath);
        for (const file of files) {
          const fullPath = path.join(dirPath, file);
          const stats = await fs.stat(fullPath).catch(() => null);
          
          if (stats && stats.isDirectory()) {
            await watchDirectory(fullPath);
          }
        }
      } catch (error) {
        console.error(`Ошибка настройки отслеживания ${dirPath}:`, error.message);
      }
    };

    await watchDirectory(this.projectRoot);
    console.log(`👁️ Настроено реальное время отслеживание для ${this.fsWatchers.size} директорий`);
  }

  // Обработка событий файловой системы
  handleFileSystemEvent(eventType, fullPath) {
    try {
      const relativePath = path.relative(this.projectRoot, fullPath);
      
      // Игнорируем файлы по паттернам
      if (this.shouldIgnore(relativePath)) {
        return;
      }

      // Добавляем в буфер для группировки изменений
      const changeKey = `${eventType}:${fullPath}`;
      this.changeBuffer.set(changeKey, {
        eventType,
        fullPath,
        relativePath,
        timestamp: Date.now()
      });

      // Сбрасываем таймер буфера
      if (this.bufferTimeout) {
        clearTimeout(this.bufferTimeout);
      }

      // Устанавливаем новый таймер для обработки буфера
      this.bufferTimeout = setTimeout(() => {
        this.processBufferedChanges();
      }, this.bufferDelay);

    } catch (error) {
      console.error('Ошибка обработки события файловой системы:', error);
    }
  }

  // Обработка буферизованных изменений
  async processBufferedChanges() {
    if (this.changeBuffer.size === 0) {
      return;
    }

    console.log(`⚡ Обработка ${this.changeBuffer.size} буферизованных изменений`);
    
    const changes = [];
    const bufferedChanges = Array.from(this.changeBuffer.values());
    this.changeBuffer.clear();

    for (const bufferedChange of bufferedChanges) {
      const change = await this.analyzeFileChange(bufferedChange);
      if (change) {
        changes.push(change);
      }
    }

    if (changes.length > 0) {
      await this.processChanges(changes);
    }
  }

  // Анализ изменения файла с детальным содержимым
  async analyzeFileChange(bufferedChange) {
    const { eventType, fullPath, relativePath } = bufferedChange;

    try {
      const stats = await fs.stat(fullPath).catch(() => null);
      const existingFile = this.watchedFiles.get(fullPath);

      if (!stats) {
        // Файл удален
        if (existingFile) {
          this.watchedFiles.delete(fullPath);
          return {
            type: 'deleted',
            path: relativePath,
            fullPath,
            timestamp: new Date().toISOString(),
            previousContent: existingFile.content || null
          };
        }
        return null;
      }

      if (stats.isDirectory()) {
        // Новая директория - настраиваем отслеживание
        if (!this.fsWatchers.has(fullPath)) {
          await this.setupDirectoryWatching(fullPath);
        }
        return null;
      }

      // Анализ файла
      const currentMtime = stats.mtime.getTime();
      const currentSize = stats.size;

      if (!existingFile) {
        // Новый файл
        const content = await this.readFileContent(fullPath, stats.size);
        const fileInfo = {
          path: relativePath,
          size: currentSize,
          mtime: currentMtime,
          exists: true,
          content: content
        };
        
        this.watchedFiles.set(fullPath, fileInfo);
        
        return {
          type: 'created',
          path: relativePath,
          fullPath,
          size: currentSize,
          timestamp: new Date().toISOString(),
          content: content,
          contentPreview: this.generateContentPreview(content)
        };
      }

      // Файл изменен
      if (currentMtime !== existingFile.mtime || currentSize !== existingFile.size) {
        const newContent = await this.readFileContent(fullPath, stats.size);
        const oldContent = existingFile.content || '';
        
        // Генерируем diff анализ
        const diffAnalysis = this.generateDiffAnalysis(oldContent, newContent);
        
        // Обновляем информацию о файле
        this.watchedFiles.set(fullPath, {
          ...existingFile,
          size: currentSize,
          mtime: currentMtime,
          content: newContent
        });

        return {
          type: 'modified',
          path: relativePath,
          fullPath,
          oldSize: existingFile.size,
          newSize: currentSize,
          timestamp: new Date().toISOString(),
          content: newContent,
          previousContent: oldContent,
          diffAnalysis: diffAnalysis,
          contentPreview: this.generateContentPreview(newContent)
        };
      }

      return null;
    } catch (error) {
      console.error(`Ошибка анализа изменения файла ${fullPath}:`, error);
      return null;
    }
  }

  // Чтение содержимого файла с ограничениями
  async readFileContent(filePath, fileSize) {
    try {
      // Проверяем размер файла
      if (fileSize > this.contentAnalysisConfig.maxFileSize) {
        return `[Файл слишком большой для анализа: ${fileSize} байт]`;
      }

      // Проверяем что это текстовый файл
      if (!this.isTextFile(filePath)) {
        return `[Бинарный файл: ${path.extname(filePath)}]`;
      }

      const content = await fs.readFile(filePath, 'utf8');
      return content;
    } catch (error) {
      return `[Ошибка чтения файла: ${error.message}]`;
    }
  }

  // Проверка текстового файла
  isTextFile(filePath) {
    const textExtensions = [
      '.js', '.ts', '.jsx', '.tsx', '.py', '.php', '.java', '.c', '.cpp',
      '.html', '.css', '.scss', '.sass', '.vue', '.svelte', '.md', '.mdx',
      '.json', '.yaml', '.yml', '.xml', '.txt', '.csv', '.sql', '.sh',
      '.env', '.gitignore', '.dockerfile', '.conf', '.ini', '.cfg'
    ];
    
    const ext = path.extname(filePath).toLowerCase();
    return textExtensions.includes(ext) || !ext; // файлы без расширения тоже считаем текстовыми
  }

  // Генерация превью содержимого
  generateContentPreview(content) {
    if (!content || typeof content !== 'string') {
      return null;
    }

    const lines = content.split('\n');
    const preview = {
      totalLines: lines.length,
      firstLines: lines.slice(0, 5).join('\n'),
      lastLines: lines.length > 10 ? lines.slice(-3).join('\n') : null,
      isEmpty: content.trim().length === 0,
      hasCode: this.detectCodePatterns(content)
    };

    return preview;
  }

  // Детекция паттернов кода
  detectCodePatterns(content) {
    const codePatterns = [
      /function\s+\w+\s*\(/,
      /class\s+\w+/,
      /import\s+.*from/,
      /export\s+(default\s+)?/,
      /const\s+\w+\s*=/,
      /let\s+\w+\s*=/,
      /var\s+\w+\s*=/,
      /def\s+\w+\s*\(/,
      /public\s+class/,
      /private\s+\w+/
    ];

    return codePatterns.some(pattern => pattern.test(content));
  }

  // Генерация diff анализа
  generateDiffAnalysis(oldContent, newContent) {
    if (!oldContent || !newContent) {
      return null;
    }

    const oldLines = oldContent.split('\n');
    const newLines = newContent.split('\n');
    
    const analysis = {
      linesAdded: Math.max(0, newLines.length - oldLines.length),
      linesRemoved: Math.max(0, oldLines.length - newLines.length),
      charactersAdded: Math.max(0, newContent.length - oldContent.length),
      charactersRemoved: Math.max(0, oldContent.length - newContent.length),
      significantChanges: this.detectSignificantChanges(oldContent, newContent)
    };

    return analysis;
  }

  // Детекция значимых изменений
  detectSignificantChanges(oldContent, newContent) {
    const changes = [];

    // Детекция новых функций
    const oldFunctions = this.extractFunctions(oldContent);
    const newFunctions = this.extractFunctions(newContent);
    
    for (const func of newFunctions) {
      if (!oldFunctions.includes(func)) {
        changes.push({ type: 'function_added', name: func });
      }
    }

    for (const func of oldFunctions) {
      if (!newFunctions.includes(func)) {
        changes.push({ type: 'function_removed', name: func });
      }
    }

    // Детекция новых импортов
    const oldImports = this.extractImports(oldContent);
    const newImports = this.extractImports(newContent);
    
    for (const imp of newImports) {
      if (!oldImports.includes(imp)) {
        changes.push({ type: 'import_added', name: imp });
      }
    }

    return changes;
  }

  // Извлечение функций из кода
  extractFunctions(content) {
    const functions = [];
    const patterns = [
      /function\s+(\w+)\s*\(/g,
      /const\s+(\w+)\s*=\s*\(/g,
      /(\w+)\s*:\s*function\s*\(/g,
      /def\s+(\w+)\s*\(/g
    ];

    for (const pattern of patterns) {
      let match;
      while ((match = pattern.exec(content)) !== null) {
        functions.push(match[1]);
      }
    }

    return functions;
  }

  // Извлечение импортов из кода
  extractImports(content) {
    const imports = [];
    const patterns = [
      /import\s+.*from\s+['"]([^'"]+)['"]/g,
      /import\s+['"]([^'"]+)['"]/g,
      /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g
    ];

    for (const pattern of patterns) {
      let match;
      while ((match = pattern.exec(content)) !== null) {
        imports.push(match[1]);
      }
    }

    return imports;
  }

  // Настройка отслеживания новой директории
  async setupDirectoryWatching(dirPath) {
    try {
      const watcher = fsSync.watch(dirPath, { recursive: false }, (eventType, filename) => {
        if (filename) {
          const fullPath = path.join(dirPath, filename);
          this.handleFileSystemEvent(eventType, fullPath);
        }
      });

      this.fsWatchers.set(dirPath, watcher);
      console.log(`👁️ Настроено отслеживание новой директории: ${dirPath}`);
    } catch (error) {
      console.error(`Ошибка настройки отслеживания директории ${dirPath}:`, error);
    }
  }

  // Остановка отслеживания
  stopWatching() {
    if (!this.isWatching) {
      return { success: false, message: 'File Watcher V2 не запущен' };
    }

    // Останавливаем все fs.watch экземпляры
    for (const [dirPath, watcher] of this.fsWatchers.entries()) {
      try {
        watcher.close();
      } catch (error) {
        console.error(`Ошибка закрытия watcher для ${dirPath}:`, error);
      }
    }
    this.fsWatchers.clear();

    // Очищаем буферы
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
      this.bufferTimeout = null;
    }
    this.changeBuffer.clear();

    // Очищаем батч
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }
    this.changesBatch = [];

    this.isWatching = false;
    this.watchedFiles.clear();
    
    console.log('🛑 File Watcher V2 остановлен');
    
    return { 
      success: true, 
      message: 'File Watcher V2 остановлен успешно' 
    };
  }

  // Сканирование проекта (улучшенная версия)
  async scanProject() {
    const scanDirectory = async (dirPath, relativePath = '') => {
      try {
        const files = await fs.readdir(dirPath);
        
        for (const file of files) {
          const fullPath = path.join(dirPath, file);
          const relativeFilePath = path.join(relativePath, file);
          
          // Проверяем игнорируемые паттерны
          if (this.shouldIgnore(relativeFilePath)) {
            continue;
          }

          const stats = await fs.stat(fullPath);
          
          if (stats.isDirectory()) {
            await scanDirectory(fullPath, relativeFilePath);
          } else {
            // Читаем содержимое файла для анализа
            const content = await this.readFileContent(fullPath, stats.size);
            
            // Сохраняем расширенную информацию о файле
            this.watchedFiles.set(fullPath, {
              path: relativeFilePath,
              size: stats.size,
              mtime: stats.mtime.getTime(),
              exists: true,
              content: content,
              contentPreview: this.generateContentPreview(content)
            });
          }
        }
      } catch (error) {
        console.error(`Ошибка сканирования ${dirPath}:`, error.message);
      }
    };

    await scanDirectory(this.projectRoot);
    console.log(`📁 Проект просканирован: ${this.watchedFiles.size} файлов с анализом содержимого`);
  }

  // НОВАЯ СИСТЕМА БАТЧИНГА - добавляем изменения в буфер вместо немедленной записи
  async processChanges(changes) {
    console.log(`📝 Обнаружено ${changes.length} изменений - добавляем в батч`);
    
    for (const change of changes) {
      console.log(`  ${change.type}: ${change.path}`);
      if (change.diffAnalysis && change.diffAnalysis.significantChanges.length > 0) {
        console.log(`    Значимые изменения: ${change.diffAnalysis.significantChanges.length}`);
      }
      
      // Генерируем событие
      this.emit('fileChange', change);
      
      // Добавляем в батч вместо немедленной записи в Memory Bank
      this.addToBatch(change);
    }
  }

  // Добавление изменения в батч
  addToBatch(change) {
    this.changesBatch.push(change);
    console.log(`📦 Добавлено в батч: ${change.path} (всего в батче: ${this.changesBatch.length})`);
    
    // Сбрасываем таймер батча
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
    }

    // Устанавливаем новый таймер на 1 минуту
    this.batchTimer = setTimeout(() => {
      this.processBatch();
    }, this.batchInterval);
  }

  // Обработка батча изменений - раз в минуту
  async processBatch() {
    if (this.changesBatch.length === 0) {
      return;
    }

    console.log(`📊 Обработка батча: ${this.changesBatch.length} изменений`);
    
    // Генерируем сводку батча
    const summary = this.generateBatchSummary(this.changesBatch);
    
    // Записываем одну сводку вместо множества записей
    await this.writeMemoryBankSummary(summary);
    
    // Очищаем батч
    this.changesBatch = [];
    this.lastBatchTime = Date.now();
  }

  // Генерация сводки батча
  generateBatchSummary(changes) {
    const summary = {
      timestamp: new Date().toLocaleString('ru-RU'),
      totalChanges: changes.length,
      created: changes.filter(c => c.type === 'created'),
      modified: changes.filter(c => c.type === 'modified'),
      deleted: changes.filter(c => c.type === 'deleted'),
      significantChanges: [],
      keyMoments: []
    };

    // Анализируем значимые изменения
    for (const change of changes) {
      if (change.diffAnalysis?.significantChanges?.length > 0) {
        summary.significantChanges.push(...change.diffAnalysis.significantChanges.map(sc => ({
          ...sc,
          file: change.path
        })));
      }
    }

    return summary;
  }

  // Запись сводки в Memory Bank
  async writeMemoryBankSummary(summary) {
    try {
      if (!this.memoryBankManager) {
        return;
      }

      const timestamp = summary.timestamp;
      
      // Генерируем красивую markdown сводку
      let markdownSummary = `\n## 📊 Сводка изменений - ${timestamp}\n`;
      
      if (summary.totalChanges > 0) {
        markdownSummary += `**Всего изменений:** ${summary.totalChanges}\n\n`;
        
        if (summary.created.length > 0) {
          markdownSummary += `**Создано файлов:** ${summary.created.length}\n`;
          summary.created.slice(0, 3).forEach(c => {
            markdownSummary += `  - ${c.path}`;
            if (c.contentPreview?.hasCode) {
              markdownSummary += ` (${c.contentPreview.totalLines} строк кода)`;
            }
            markdownSummary += `\n`;
          });
          if (summary.created.length > 3) {
            markdownSummary += `  - ... и еще ${summary.created.length - 3}\n`;
          }
          markdownSummary += `\n`;
        }
        
        if (summary.modified.length > 0) {
          markdownSummary += `**Изменено файлов:** ${summary.modified.length}\n`;
          summary.modified.slice(0, 3).forEach(c => {
            markdownSummary += `  - ${c.path}`;
            if (c.diffAnalysis) {
              markdownSummary += ` (+${c.diffAnalysis.linesAdded}/-${c.diffAnalysis.linesRemoved})`;
            }
            markdownSummary += `\n`;
          });
          if (summary.modified.length > 3) {
            markdownSummary += `  - ... и еще ${summary.modified.length - 3}\n`;
          }
          markdownSummary += `\n`;
        }

        if (summary.deleted.length > 0) {
          markdownSummary += `**Удалено файлов:** ${summary.deleted.length}\n`;
          summary.deleted.slice(0, 3).forEach(c => {
            markdownSummary += `  - ${c.path}\n`;
          });
          if (summary.deleted.length > 3) {
            markdownSummary += `  - ... и еще ${summary.deleted.length - 3}\n`;
          }
          markdownSummary += `\n`;
        }
        
        if (summary.significantChanges.length > 0) {
          markdownSummary += `**Значимые изменения:**\n`;
          summary.significantChanges.slice(0, 5).forEach(sc => {
            markdownSummary += `  - ${this.getChangeTitle({ type: sc.type })}: ${sc.name} в ${sc.file}\n`;
          });
          if (summary.significantChanges.length > 5) {
            markdownSummary += `  - ... и еще ${summary.significantChanges.length - 5}\n`;
          }
          markdownSummary += `\n`;
        }
      } else {
        markdownSummary += `Изменений не обнаружено.\n\n`;
      }
      
      markdownSummary += `---\n`;

      // Записываем в activeContext.md
      const contextResult = await this.memoryBankManager.readMemoryBankFile('activeContext.md');
      if (contextResult.success) {
        let updatedContent = contextResult.content;
        
        if (updatedContent.includes('## Working On')) {
          updatedContent = updatedContent.replace(
            '## Working On',
            `## Working On${markdownSummary}`
          );
        } else {
          updatedContent += `\n## Recent Changes${markdownSummary}`;
        }
        
        await this.memoryBankManager.writeMemoryBankFile('activeContext.md', updatedContent);
        console.log(`💾 Сводка батча записана в Memory Bank: ${summary.totalChanges} изменений`);
      }
    } catch (error) {
      console.error('Ошибка записи сводки батча:', error);
    }
  }

  // Группировка изменений по типам
  groupChangesByType(changes) {
    const grouped = {
      created: changes.filter(c => c.type === 'created'),
      modified: changes.filter(c => c.type === 'modified'),
      deleted: changes.filter(c => c.type === 'deleted')
    };

    return grouped;
  }

  // Улучшенная детекция ключевых моментов
  async detectKeyMomentsV2(change) {
    const moments = [];
    
    try {
      const fileExt = path.extname(change.path).toLowerCase();
      const fileName = path.basename(change.path);
      
      // Создание нового файла с анализом содержимого
      if (change.type === 'created') {
        const moment = {
          type: 'FILE_CREATED',
          title: `Создан файл ${fileName}`,
          description: `Новый файл: ${change.path}`,
          file: change.path,
          timestamp: change.timestamp,
          details: {
            size: change.size,
            hasCode: change.contentPreview?.hasCode || false,
            lines: change.contentPreview?.totalLines || 0
          }
        };

        if (change.contentPreview?.hasCode) {
          moment.title = `Создан код файл ${fileName}`;
          moment.description += ` (${change.contentPreview.totalLines} строк кода)`;
        }

        moments.push(moment);
      }
      
      // Удаление файла
      if (change.type === 'deleted') {
        moments.push({
          type: 'FILE_DELETED',
          title: `Удален файл ${fileName}`,
          description: `Файл удален: ${change.path}`,
          file: change.path,
          timestamp: change.timestamp
        });
      }
      
      // Изменения с анализом diff
      if (change.type === 'modified' && change.diffAnalysis) {
        const { significantChanges, linesAdded, linesRemoved } = change.diffAnalysis;
        
        if (significantChanges.length > 0) {
          for (const sigChange of significantChanges) {
            moments.push({
              type: `CODE_${sigChange.type.toUpperCase()}`,
              title: `${this.getChangeTitle(sigChange)} в ${fileName}`,
              description: `${sigChange.type}: ${sigChange.name} в файле ${change.path}`,
              file: change.path,
              timestamp: change.timestamp,
              details: {
                changeType: sigChange.type,
                name: sigChange.name,
                linesAdded,
                linesRemoved
              }
            });
          }
        } else if (linesAdded > 5 || linesRemoved > 5) {
          moments.push({
            type: 'SIGNIFICANT_EDIT',
            title: `Значительные изменения в ${fileName}`,
            description: `Изменен файл: ${change.path} (+${linesAdded}/-${linesRemoved} строк)`,
            file: change.path,
            timestamp: change.timestamp,
            details: { linesAdded, linesRemoved }
          });
        }
      }
      
      // Изменения в конфигурационных файлах
      if (this.isConfigFile(fileName)) {
        moments.push({
          type: 'CONFIG_CHANGED',
          title: `Изменена конфигурация ${fileName}`,
          description: `Обновлен конфигурационный файл: ${change.path}`,
          file: change.path,
          timestamp: change.timestamp
        });
      }
      
    } catch (error) {
      console.error('Ошибка определения ключевых моментов V2:', error);
    }
    
    return moments;
  }

  // Получение заголовка для типа изменения
  getChangeTitle(sigChange) {
    const titles = {
      'function_added': 'Добавлена функция',
      'function_removed': 'Удалена функция',
      'import_added': 'Добавлен импорт',
      'import_removed': 'Удален импорт'
    };
    
    return titles[sigChange.type] || 'Изменение';
  }

  // Улучшенное сохранение в Memory Bank
  async saveKeyMomentToMemoryBankV2(moment, change) {
    try {
      if (!this.memoryBankManager) {
        return;
      }

      // Читаем текущий progress.md
      const progressResult = await this.memoryBankManager.readMemoryBankFile('progress.md');
      
      if (progressResult.success) {
        const timestamp = new Date().toLocaleString('ru-RU');
        let newEntry = `\n## ${moment.title}\n**Время:** ${timestamp}\n**Описание:** ${moment.description}\n**Файл:** ${change.path}\n`;
        
        // Добавляем детали если есть
        if (moment.details) {
          newEntry += `**Детали:** ${JSON.stringify(moment.details, null, 2)}\n`;
        }
        
        const updatedContent = progressResult.content + newEntry;
        
        await this.memoryBankManager.writeMemoryBankFile('progress.md', updatedContent);
        console.log(`💾 Ключевой момент V2 сохранен в Memory Bank: ${moment.title}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения в Memory Bank V2:', error);
    }
  }

  // Улучшенное обновление прогресса в Memory Bank
  async updateMemoryBankProgressV2(change, groupedChanges) {
    try {
      if (!this.memoryBankManager) {
        return;
      }

      // Читаем activeContext.md
      const contextResult = await this.memoryBankManager.readMemoryBankFile('activeContext.md');
      
      if (contextResult.success) {
        const timestamp = new Date().toLocaleString('ru-RU');
        
        // Создаем умную сводку вместо простого лога
        let changeInfo = `\n**${timestamp}:** `;
        
        if (change.type === 'created' && change.contentPreview?.hasCode) {
          changeInfo += `Создан код файл ${change.path} (${change.contentPreview.totalLines} строк)`;
        } else if (change.type === 'modified' && change.diffAnalysis) {
          const { linesAdded, linesRemoved, significantChanges } = change.diffAnalysis;
          if (significantChanges.length > 0) {
            changeInfo += `Изменен ${change.path}: ${significantChanges.map(c => c.type).join(', ')}`;
          } else {
            changeInfo += `Изменен ${change.path} (+${linesAdded}/-${linesRemoved} строк)`;
          }
        } else {
          changeInfo += `${change.type} - ${change.path}`;
        }
        
        // Проверяем на дублирование записей
        if (!contextResult.content.includes(changeInfo.trim())) {
          let updatedContent = contextResult.content;
          
          if (updatedContent.includes('## Working On')) {
            updatedContent = updatedContent.replace(
              '## Working On',
              `## Working On${changeInfo}`
            );
          } else {
            updatedContent += `\n## Recent Changes${changeInfo}`;
          }
          
          await this.memoryBankManager.writeMemoryBankFile('activeContext.md', updatedContent);
        }
      }
    } catch (error) {
      console.error('Ошибка обновления контекста V2:', error);
    }
  }

  // Улучшенный метод игнорирования с абсолютными путями для Memory Bank
  shouldIgnore(filePath) {
    // Проверяем абсолютные пути Memory Bank
    const fullPath = path.resolve(this.projectRoot, filePath);
    
    for (const mbPath of this.memoryBankPaths) {
      if (fullPath.startsWith(mbPath)) {
        console.log(`🚫 Игнорируем Memory Bank файл: ${filePath}`);
        return true; // Полностью игнорируем Memory Bank
      }
    }
    
    // Проверяем остальные паттерны
    return this.ignoredPatterns.some(pattern => pattern.test(filePath));
  }

  isConfigFile(fileName) {
    const configFiles = [
      'package.json', 'package-lock.json', 'yarn.lock',
      'composer.json', 'composer.lock',
      'requirements.txt', 'Pipfile', 'poetry.lock',
      'config.yaml', 'config.yml', 'config.json',
      '.env', '.env.example',
      'webpack.config.js', 'vite.config.js',
      'tsconfig.json', 'jsconfig.json',
      'tailwind.config.js', 'postcss.config.js'
    ];
    
    return configFiles.includes(fileName.toLowerCase());
  }

  isCodeFile(extension) {
    const codeExtensions = [
      '.js', '.ts', '.jsx', '.tsx',
      '.py', '.php', '.java', '.c', '.cpp',
      '.html', '.css', '.scss', '.sass',
      '.vue', '.svelte', '.md', '.mdx'
    ];
    
    return codeExtensions.includes(extension);
  }

  forceReset() {
    console.error(`🔧 FileWatcherV2.forceReset() called - принудительная очистка при инициализации`);
    
    // Останавливаем все watchers
    for (const [dirPath, watcher] of this.fsWatchers.entries()) {
      try {
        watcher.close();
      } catch (error) {
        // Игнорируем ошибки при закрытии
      }
    }
    this.fsWatchers.clear();

    // Очищаем буферы
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
      this.bufferTimeout = null;
    }
    this.changeBuffer.clear();

    // Очищаем батч
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }
    this.changesBatch = [];
    
    this.isWatching = false;
    this.watchedFiles.clear();
    
    console.error(`✅ FileWatcherV2 forceReset complete - состояние очищено`);
  }

  getStats() {
    console.error(`🔍 FileWatcherV2.getStats() called:`);
    console.error(`  - isWatching: ${this.isWatching}`);
    console.error(`  - watchedFiles.size: ${this.watchedFiles.size}`);
    console.error(`  - fsWatchers.size: ${this.fsWatchers.size}`);
    console.error(`  - changeBuffer.size: ${this.changeBuffer.size}`);
    
    return {
      isWatching: this.isWatching,
      watchedFiles: this.watchedFiles.size,
      realTimeWatchers: this.fsWatchers.size,
      bufferedChanges: this.changeBuffer.size,
      ignoredPatterns: this.ignoredPatterns.length,
      version: '2.0',
      features: ['real-time', 'content-analysis', 'diff-analysis', 'semantic-analysis'],
      // Для совместимости со старым кодом
      pollInterval: null // V2 не использует polling
    };
  }

  // Метод для получения детальной информации о файле
  getFileDetails(filePath) {
    const fullPath = path.resolve(this.projectRoot, filePath);
    const fileInfo = this.watchedFiles.get(fullPath);
    
    if (!fileInfo) {
      return null;
    }

    return {
      ...fileInfo,
      fullPath,
      isTextFile: this.isTextFile(fullPath),
      isCodeFile: this.isCodeFile(path.extname(filePath)),
      isConfigFile: this.isConfigFile(path.basename(filePath))
    };
  }

  // Метод для получения статистики по типам файлов
  getFileTypeStats() {
    const stats = {
      total: this.watchedFiles.size,
      textFiles: 0,
      codeFiles: 0,
      configFiles: 0,
      binaryFiles: 0,
      extensions: new Map()
    };

    for (const [fullPath, fileInfo] of this.watchedFiles.entries()) {
      const ext = path.extname(fullPath).toLowerCase();
      const fileName = path.basename(fullPath);
      
      // Подсчет по расширениям
      stats.extensions.set(ext, (stats.extensions.get(ext) || 0) + 1);
      
      // Подсчет по типам
      if (this.isTextFile(fullPath)) {
        stats.textFiles++;
      } else {
        stats.binaryFiles++;
      }
      
      if (this.isCodeFile(ext)) {
        stats.codeFiles++;
      }
      
      if (this.isConfigFile(fileName)) {
        stats.configFiles++;
      }
    }

    return stats;
  }
}
