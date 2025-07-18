import fs from 'fs/promises';
import path from 'path';
import { EventEmitter } from 'events';

export class FileWatcher extends EventEmitter {
  constructor(projectRoot = process.env.WORKSPACE_FOLDER || process.cwd(), memoryBankManager) {
    super();
    this.projectRoot = projectRoot;
    this.memoryBankManager = memoryBankManager;
    this.watchedFiles = new Map();
    this.isWatching = false;
    this.watchInterval = null;
    this.pollInterval = 2000; // Проверка каждые 2 секунды
    
    console.error(`🏗️ FileWatcher constructor called with ${this.watchedFiles.size} files`);
    
    // ПРИНУДИТЕЛЬНАЯ ОЧИСТКА СОСТОЯНИЯ при инициализации
    this.forceReset();
    
    // Игнорируемые файлы и папки
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
      /\.pyc$/
    ];
  }

  // Запуск отслеживания
  async startWatching() {
    if (this.isWatching) {
      return { success: false, message: 'File Watcher уже запущен' };
    }

    try {
      console.log('🔍 Starting File Watcher...');
      
      // Инициализируем список файлов
      await this.scanProject();
      
      // Запускаем периодическую проверку
      this.watchInterval = setInterval(() => {
        this.checkForChanges();
      }, this.pollInterval);
      
      this.isWatching = true;
      
      console.log('✅ File Watcher started');
      return { 
        success: true, 
        message: 'File Watcher started successfully',
        watchedFiles: this.watchedFiles.size
      };
    } catch (error) {
      console.error('❌ File Watcher startup error:', error);
      return { 
        success: false, 
        message: `Startup error: ${error.message}` 
      };
    }
  }

  // Остановка отслеживания
  stopWatching() {
    if (!this.isWatching) {
      return { success: false, message: 'File Watcher не запущен' };
    }

    if (this.watchInterval) {
      clearInterval(this.watchInterval);
      this.watchInterval = null;
    }

    this.isWatching = false;
    this.watchedFiles.clear(); // Очищаем список отслеживаемых файлов
    console.log('🛑 File Watcher остановлен');
    
    return { 
      success: true, 
      message: 'File Watcher остановлен успешно' 
    };
  }

  // Сканирование проекта
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
            // Сохраняем информацию о файле
            this.watchedFiles.set(fullPath, {
              path: relativeFilePath,
              size: stats.size,
              mtime: stats.mtime.getTime(),
              exists: true
            });
          }
        }
      } catch (error) {
        console.error(`Ошибка сканирования ${dirPath}:`, error.message);
      }
    };

    await scanDirectory(this.projectRoot);
    console.log(`📁 Проект просканирован: ${this.watchedFiles.size} файлов`);
  }

  // Проверка изменений
  async checkForChanges() {
    try {
      const changes = [];
      
      // Проверяем существующие файлы
      for (const [fullPath, fileInfo] of this.watchedFiles.entries()) {
        try {
          const stats = await fs.stat(fullPath);
          const currentMtime = stats.mtime.getTime();
          const currentSize = stats.size;
          
          // Проверяем изменения
          if (currentMtime !== fileInfo.mtime || currentSize !== fileInfo.size) {
            const changeType = this.detectChangeType(fileInfo, { size: currentSize, mtime: currentMtime });
            
            changes.push({
              type: 'modified',
              path: fileInfo.path,
              fullPath,
              changeType,
              oldSize: fileInfo.size,
              newSize: currentSize,
              timestamp: new Date().toISOString()
            });
            
            // Обновляем информацию о файле
            this.watchedFiles.set(fullPath, {
              ...fileInfo,
              size: currentSize,
              mtime: currentMtime
            });
          }
        } catch (error) {
          if (error.code === 'ENOENT') {
            // Файл удален
            changes.push({
              type: 'deleted',
              path: fileInfo.path,
              fullPath,
              timestamp: new Date().toISOString()
            });
            
            this.watchedFiles.delete(fullPath);
          }
        }
      }
      
      // Проверяем новые файлы (упрощенная версия)
      await this.checkForNewFiles(changes);
      
      // Обрабатываем изменения
      if (changes.length > 0) {
        await this.processChanges(changes);
      }
      
    } catch (error) {
      console.error('Ошибка проверки изменений:', error);
    }
  }

  // Проверка новых файлов
  async checkForNewFiles(changes) {
    // Простая проверка - сканируем только корневую папку для новых файлов
    try {
      const files = await fs.readdir(this.projectRoot);
      
      for (const file of files) {
        const fullPath = path.join(this.projectRoot, file);
        
        if (this.shouldIgnore(file)) {
          continue;
        }
        
        if (!this.watchedFiles.has(fullPath)) {
          try {
            const stats = await fs.stat(fullPath);
            
            if (stats.isFile()) {
              changes.push({
                type: 'created',
                path: file,
                fullPath,
                size: stats.size,
                timestamp: new Date().toISOString()
              });
              
              // Добавляем в отслеживаемые файлы
              this.watchedFiles.set(fullPath, {
                path: file,
                size: stats.size,
                mtime: stats.mtime.getTime(),
                exists: true
              });
            }
          } catch (error) {
            // Игнорируем ошибки доступа
          }
        }
      }
    } catch (error) {
      console.error('Ошибка проверки новых файлов:', error);
    }
  }

  // Определение типа изменения
  detectChangeType(oldInfo, newInfo) {
    if (newInfo.size > oldInfo.size) {
      return 'content_added';
    } else if (newInfo.size < oldInfo.size) {
      return 'content_removed';
    } else {
      return 'content_modified';
    }
  }

  // Обработка изменений
  async processChanges(changes) {
    console.log(`📝 Обнаружено ${changes.length} изменений`);
    
    for (const change of changes) {
      console.log(`  ${change.type}: ${change.path}`);
      
      // Генерируем событие
      this.emit('fileChange', change);
      
      // Определяем ключевые моменты
      const keyMoments = await this.detectKeyMoments(change);
      
      if (keyMoments.length > 0) {
        console.log(`  🔑 Обнаружено ${keyMoments.length} ключевых моментов`);
        
        for (const moment of keyMoments) {
          this.emit('keyMoment', moment);
          await this.saveKeyMomentToMemoryBank(moment, change);
        }
      }
      
      // Обновляем Memory Bank
      await this.updateMemoryBankProgress(change);
    }
  }

  // Определение ключевых моментов
  async detectKeyMoments(change) {
    const moments = [];
    
    try {
      // Анализируем тип файла и изменения
      const fileExt = path.extname(change.path).toLowerCase();
      const fileName = path.basename(change.path);
      
      // Создание нового файла
      if (change.type === 'created') {
        moments.push({
          type: 'FILE_CREATED',
          title: `Создан файл ${fileName}`,
          description: `Новый файл: ${change.path}`,
          file: change.path,
          timestamp: change.timestamp
        });
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
      
      // Изменения в коде
      if (this.isCodeFile(fileExt)) {
        if (change.changeType === 'content_added') {
          moments.push({
            type: 'CODE_ADDED',
            title: `Добавлен код в ${fileName}`,
            description: `Расширен файл: ${change.path} (+${change.newSize - change.oldSize} байт)`,
            file: change.path,
            timestamp: change.timestamp
          });
        }
      }
      
    } catch (error) {
      console.error('Ошибка определения ключевых моментов:', error);
    }
    
    return moments;
  }

  // Сохранение ключевого момента в Memory Bank
  async saveKeyMomentToMemoryBank(moment, change) {
    try {
      if (!this.memoryBankManager) {
        return;
      }

      // Читаем текущий progress.md
      const progressResult = await this.memoryBankManager.readMemoryBankFile('progress.md');
      
      if (progressResult.success) {
        const timestamp = new Date().toLocaleString('ru-RU');
        const newEntry = `\n## ${moment.title}\n**Время:** ${timestamp}\n**Описание:** ${moment.description}\n**Файл:** ${change.path}\n`;
        
        const updatedContent = progressResult.content + newEntry;
        
        await this.memoryBankManager.writeMemoryBankFile('progress.md', updatedContent);
        console.log(`💾 Ключевой момент сохранен в Memory Bank: ${moment.title}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения в Memory Bank:', error);
    }
  }

  // Обновление прогресса в Memory Bank
  async updateMemoryBankProgress(change) {
    try {
      if (!this.memoryBankManager) {
        return;
      }

      // Читаем activeContext.md
      const contextResult = await this.memoryBankManager.readMemoryBankFile('activeContext.md');
      
      if (contextResult.success) {
        const timestamp = new Date().toLocaleString('ru-RU');
        const changeInfo = `\n**${timestamp}:** ${change.type} - ${change.path}`;
        
        // Добавляем информацию об изменении в секцию "Working On"
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
    } catch (error) {
      console.error('Ошибка обновления контекста:', error);
    }
  }

  // Проверка игнорируемых файлов
  shouldIgnore(filePath) {
    return this.ignoredPatterns.some(pattern => pattern.test(filePath));
  }

  // Проверка конфигурационных файлов
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

  // Проверка файлов кода
  isCodeFile(extension) {
    const codeExtensions = [
      '.js', '.ts', '.jsx', '.tsx',
      '.py', '.php', '.java', '.c', '.cpp',
      '.html', '.css', '.scss', '.sass',
      '.vue', '.svelte', '.md', '.mdx'
    ];
    
    return codeExtensions.includes(extension);
  }

  // Принудительная очистка состояния при инициализации
  forceReset() {
    console.error(`🔧 FileWatcher.forceReset() called - принудительная очистка при инициализации`);
    
    if (this.watchInterval) {
      clearInterval(this.watchInterval);
      this.watchInterval = null;
    }
    
    this.isWatching = false;
    this.watchedFiles.clear();
    
    console.error(`✅ FileWatcher forceReset complete - состояние очищено`);
  }

  // Полная очистка состояния
  reset() {
    console.error(`🔄 FileWatcher.reset() called - clearing all state`);
    
    if (this.watchInterval) {
      clearInterval(this.watchInterval);
      this.watchInterval = null;
    }
    
    this.isWatching = false;
    this.watchedFiles.clear();
    
    console.error(`✅ FileWatcher reset complete - watchedFiles.size: ${this.watchedFiles.size}`);
    
    return {
      success: true,
      message: 'FileWatcher state reset successfully'
    };
  }

  // Получение статистики
  getStats() {
    console.error(`🔍 FileWatcher.getStats() called:`);
    console.error(`  - isWatching: ${this.isWatching}`);
    console.error(`  - watchedFiles.size: ${this.watchedFiles.size}`);
    console.error(`  - watchInterval: ${this.watchInterval}`);
    console.error(`  - Map contents:`, Array.from(this.watchedFiles.keys()).slice(0, 3));
    
    // Если File Watcher остановлен, но файлы все еще отслеживаются - это проблема
    if (!this.isWatching && this.watchedFiles.size > 0) {
      console.error(`⚠️ ПРОБЛЕМА: File Watcher остановлен, но watchedFiles содержит ${this.watchedFiles.size} файлов!`);
      console.error(`🔧 Автоматическая очистка...`);
      this.watchedFiles.clear();
      console.error(`✅ Очистка завершена - watchedFiles.size: ${this.watchedFiles.size}`);
    }
    
    return {
      isWatching: this.isWatching,
      watchedFiles: this.watchedFiles.size,
      pollInterval: this.pollInterval,
      ignoredPatterns: this.ignoredPatterns.length
    };
  }
}
