# Документация фреймворков / Framework Documentation

[🇷🇺 Русский](#русский) | [🇺🇸 English](#english)

---

## Русский

Эта папка содержит документацию различных фреймворков, которая используется RAG сервером для ответов на вопросы.

### 📁 Структура папок

- `alpine_docs/` - Документация Alpine.js
- `filament_docs/` - Документация Filament PHP
- `laravel_docs/` - Документация Laravel
- `tailwindcss_docs/` - Документация Tailwind CSS
- `vue_docs/` - Документация Vue.js

### 🚀 Первоначальная настройка

После клонирования репозитория документация **НЕ ВКЛЮЧЕНА** в git, так как она занимает много места и у каждого разработчика может быть разная версия.

#### Скачивание всей документации:
```bash
python update_docs.py --all
```

#### Скачивание конкретного фреймворка:
```bash
python update_docs.py --framework vue
python update_docs.py --framework laravel
python update_docs.py --framework filament
python update_docs.py --framework alpine
python update_docs.py --framework tailwindcss
```

### 📊 Статистика документации

После скачивания документации вы можете проверить статистику:

```bash
# Запустить RAG сервер
python rag_server.py

# В другом терминале проверить статистику
curl http://localhost:8000/stats
curl http://localhost:8000/frameworks
```

### 🔄 Обновление документации

Документация обновляется автоматически при запуске скриптов. Для принудительного обновления:

```bash
python update_docs.py --framework vue --force
```

### ⚠️ Важные замечания

1. **Размер**: Полная документация всех фреймворков может занимать несколько сотен мегабайт
2. **Версии**: Скрипты скачивают последние версии документации
3. **Интернет**: Для скачивания требуется стабильное интернет-соединение
4. **Время**: Первоначальное скачивание может занять несколько минут

### 🛠️ Разработка

Если вы добавляете поддержку нового фреймворка:

1. Добавьте логику скачивания в `update_docs.py`
2. Обновите `services/framework_detector.py`
3. Добавьте новую папку в `.gitignore`
4. Обновите этот README.md

---

## English

This folder contains documentation for various frameworks used by the RAG server to answer questions.

### 📁 Folder Structure

- `alpine_docs/` - Alpine.js Documentation
- `filament_docs/` - Filament PHP Documentation
- `laravel_docs/` - Laravel Documentation
- `tailwindcss_docs/` - Tailwind CSS Documentation
- `vue_docs/` - Vue.js Documentation

### 🚀 Initial Setup

After cloning the repository, documentation is **NOT INCLUDED** in git, as it takes up a lot of space and each developer may have a different version.

#### Download all documentation:
```bash
python update_docs.py --all
```

#### Download specific framework:
```bash
python update_docs.py --framework vue
python update_docs.py --framework laravel
python update_docs.py --framework filament
python update_docs.py --framework alpine
python update_docs.py --framework tailwindcss
```

### 📊 Documentation Statistics

After downloading documentation, you can check statistics:

```bash
# Start RAG server
python rag_server.py

# In another terminal check statistics
curl http://localhost:8000/stats
curl http://localhost:8000/frameworks
```

### 🔄 Updating Documentation

Documentation is updated automatically when running scripts. For forced update:

```bash
python update_docs.py --framework vue --force
```

### ⚠️ Important Notes

1. **Size**: Full documentation of all frameworks can take several hundred megabytes
2. **Versions**: Scripts download the latest versions of documentation
3. **Internet**: Stable internet connection required for downloading
4. **Time**: Initial download may take several minutes

### 🛠️ Development

If you're adding support for a new framework:

1. Add download logic to `update_docs.py`
2. Update `services/framework_detector.py`
3. Add new folder to `.gitignore`
4. Update this README.md
