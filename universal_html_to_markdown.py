#!/usr/bin/env python3
"""
Universal HTML to Markdown Converter for RAG Systems
Универсальный конвертер HTML в Markdown для RAG систем

Поддерживает различные фреймворки и типы документации
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import argparse

from bs4 import BeautifulSoup, Tag, NavigableString
import html2text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурации для разных фреймворков
FRAMEWORK_CONFIGS = {
    'tailwindcss': {
        'name': 'Tailwind CSS',
        'html_path': 'tailwindcss.com/docs',
        'output_path': 'tailwindcss_docs',
        'content_selectors': ['main', '[role="main"]', '.prose', 'article', 'body'],
        'remove_selectors': [
            'nav', 'header', 'footer', 'aside',
            '.navigation', '.nav', '.navbar', '.sidebar',
            '.breadcrumb', '.breadcrumbs', '.toc',
            '.search', '.social', '.advertisement',
            'script', 'style', 'noscript'
        ],
        'title_selectors': ['h1', 'title', '.page-title', '.main-title'],
        'skip_files': ['index.html', 'search.html', '404.html', 'sitemap.html'],
        'code_languages': {
            '@apply': 'css',
            '@tailwind': 'css',
            '@layer': 'css',
            'class=': 'html',
            'className=': 'jsx'
        }
    },
    'vue': {
        'name': 'Vue.js',
        'html_path': 'vue_docs_html',
        'output_path': 'vue_docs_converted',
        'content_selectors': ['.content', 'main', 'article', '.documentation'],
        'remove_selectors': [
            'nav', 'header', 'footer', '.sidebar',
            '.nav-links', '.page-nav', '.edit-link'
        ],
        'title_selectors': ['h1', '.page-title'],
        'skip_files': ['index.html'],
        'code_languages': {
            'export default': 'javascript',
            '<template>': 'vue',
            'import': 'javascript'
        }
    },
    'laravel': {
        'name': 'Laravel',
        'html_path': 'laravel_docs_html',
        'output_path': 'laravel_docs_converted',
        'content_selectors': ['.documentation-body', '.content', 'main'],
        'remove_selectors': [
            '.documentation-nav', '.page-nav', 'nav',
            'header', 'footer', '.version-switcher'
        ],
        'title_selectors': ['h1', '.page-title'],
        'skip_files': ['index.html'],
        'code_languages': {
            '<?php': 'php',
            'artisan': 'bash',
            'composer': 'bash',
            'Route::': 'php'
        }
    },
    'alpine': {
        'name': 'Alpine.js',
        'html_path': 'alpinejs.dev',
        'output_path': 'alpine_docs',
        'content_selectors': ['main', '.content', 'article', '.prose', 'body'],
        'remove_selectors': [
            'nav', 'header', 'footer', 'aside',
            '.navigation', '.nav', '.navbar', '.sidebar',
            '.breadcrumb', '.breadcrumbs', '.toc',
            '.search', '.social', '.advertisement',
            'script', 'style', 'noscript'
        ],
        'title_selectors': ['h1', 'title', '.page-title', '.main-title'],
        'skip_files': ['index.html', 'robots.txt', 'login.html', 'forgot-password.html'],
        'code_languages': {
            'x-data': 'javascript',
            'x-show': 'javascript',
            'x-if': 'javascript',
            'x-for': 'javascript',
            'x-model': 'javascript',
            'x-on:': 'javascript',
            '@click': 'javascript',
            'Alpine.': 'javascript'
        }
    }
}

class UniversalHTMLConverter:
    """Универсальный конвертер HTML в Markdown для разных фреймворков"""
    
    def __init__(self, framework: str, custom_config: Optional[Dict] = None):
        """
        Инициализация конвертера
        
        Args:
            framework: Название фреймворка
            custom_config: Кастомная конфигурация (опционально)
        """
        if framework not in FRAMEWORK_CONFIGS and not custom_config:
            raise ValueError(f"Фреймворк {framework} не поддерживается. Доступные: {list(FRAMEWORK_CONFIGS.keys())}")
        
        self.framework = framework
        self.config = custom_config or FRAMEWORK_CONFIGS[framework]
        
        self.html_docs_path = Path(self.config['html_path'])
        self.output_path = Path(self.config['output_path'])
        
        # Создаем выходную папку
        self.output_path.mkdir(exist_ok=True)
        
        # Настройка html2text
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.ignore_emphasis = False
        self.h.body_width = 0
        self.h.unicode_snob = True
        self.h.escape_snob = True
        
        # Статистика конвертации
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total_files': 0
        }
        
        logger.info(f"Инициализирован универсальный конвертер для {self.config['name']}")
        logger.info(f"HTML документы: {self.html_docs_path}")
        logger.info(f"Выходная папка: {self.output_path}")
    
    def find_html_files(self) -> List[Path]:
        """Находит все HTML файлы в папке документации"""
        if not self.html_docs_path.exists():
            logger.error(f"Папка с HTML файлами не найдена: {self.html_docs_path}")
            return []
        
        html_files = list(self.html_docs_path.glob("*.html"))
        
        # Фильтруем служебные файлы
        filtered_files = []
        skip_patterns = self.config.get('skip_files', [])
        
        for file_path in html_files:
            if file_path.name not in skip_patterns:
                filtered_files.append(file_path)
        
        logger.info(f"Найдено {len(filtered_files)} HTML файлов для конвертации")
        return filtered_files
    
    def extract_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Извлекает основной контент из HTML"""
        content_selectors = self.config.get('content_selectors', ['main', 'body'])
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                logger.debug(f"Найден контент с селектором: {selector}")
                return content
        
        # Если не нашли специальный контейнер, берем body
        body = soup.find('body')
        if body:
            self._remove_navigation_elements(body)
            return body
        
        logger.warning("Не удалось найти основной контент")
        return None
    
    def _remove_navigation_elements(self, content: Tag):
        """Удаляет навигационные элементы из контента"""
        remove_selectors = self.config.get('remove_selectors', [])
        
        for selector in remove_selectors:
            elements = content.select(selector)
            for element in elements:
                element.decompose()
    
    def clean_html_content(self, content: Tag) -> Tag:
        """Очищает HTML контент перед конвертацией"""
        # Удаляем комментарии
        for comment in content.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
        
        # Удаляем пустые параграфы
        for p in content.find_all('p'):
            if not p.get_text(strip=True):
                p.decompose()
        
        # Очищаем атрибуты, оставляя только важные
        important_attrs = ['href', 'src', 'alt', 'title', 'class']
        
        for tag in content.find_all():
            if hasattr(tag, 'attrs'):
                new_attrs = {}
                for attr, value in tag.attrs.items():
                    if attr in important_attrs:
                        new_attrs[attr] = value
                tag.attrs = new_attrs
        
        return content
    
    def enhance_code_blocks(self, content: Tag) -> Tag:
        """Улучшает блоки кода для лучшей конвертации"""
        code_blocks = content.find_all(['pre', 'code'])
        
        for block in code_blocks:
            if block.name == 'pre':
                code_tag = block.find('code')
                if code_tag:
                    classes = code_tag.get('class', [])
                    if not any('language-' in cls or 'lang-' in cls for cls in classes):
                        text = code_tag.get_text()
                        lang = self._detect_code_language(text)
                        if lang:
                            code_tag['class'] = classes + [f'language-{lang}']
        
        return content
    
    def _detect_code_language(self, code_text: str) -> Optional[str]:
        """Определяет язык программирования по содержимому кода"""
        code_lower = code_text.lower().strip()
        
        # Используем конфигурацию фреймворка для определения языка
        code_languages = self.config.get('code_languages', {})
        
        for keyword, language in code_languages.items():
            if keyword.lower() in code_lower:
                return language
        
        # Общие паттерны
        if code_lower.startswith('<') and '>' in code_lower:
            return 'html'
        elif code_lower.startswith('$') or code_lower.startswith('npm '):
            return 'bash'
        elif any(keyword in code_lower for keyword in ['function', 'const ', 'let ', 'var ']):
            return 'javascript'
        
        return None
    
    def convert_html_to_markdown(self, html_content: str, file_path: Path) -> str:
        """Конвертирует HTML в Markdown"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Извлекаем заголовок страницы
            title = self._extract_page_title(soup, file_path)
            
            # Извлекаем основной контент
            main_content = self.extract_main_content(soup)
            if not main_content:
                logger.warning(f"Не удалось извлечь контент из {file_path.name}")
                return ""
            
            # Очищаем контент
            main_content = self.clean_html_content(main_content)
            main_content = self.enhance_code_blocks(main_content)
            
            # Конвертируем в markdown
            markdown_content = self.h.handle(str(main_content))
            
            # Добавляем заголовок страницы
            if title:
                markdown_content = f"# {title}\n\n{markdown_content}"
            
            # Постобработка markdown
            markdown_content = self._post_process_markdown(markdown_content)
            
            return markdown_content
            
        except Exception as e:
            logger.error(f"Ошибка конвертации {file_path.name}: {e}")
            return ""
    
    def _extract_page_title(self, soup: BeautifulSoup, file_path: Path) -> str:
        """Извлекает заголовок страницы"""
        title_selectors = self.config.get('title_selectors', ['h1', 'title'])
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and title != self.config['name']:
                    return title
        
        # Если не нашли заголовок, создаем из имени файла
        title = file_path.stem.replace('-', ' ').title()
        return title
    
    def _post_process_markdown(self, markdown: str) -> str:
        """Постобработка markdown контента"""
        # Удаляем лишние пустые строки
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # Исправляем заголовки
        markdown = re.sub(r'^#{7,}', '######', markdown, flags=re.MULTILINE)
        
        # Улучшаем блоки кода
        markdown = re.sub(r'```\n\n```', '```\n```', markdown)
        
        # Удаляем HTML комментарии
        markdown = re.sub(r'<!--.*?-->', '', markdown, flags=re.DOTALL)
        
        # Очищаем начало и конец
        markdown = markdown.strip()
        
        return markdown
    
    def generate_output_filename(self, html_file: Path) -> str:
        """Генерирует имя выходного markdown файла"""
        base_name = html_file.stem
        clean_name = re.sub(r'[^\w\-]', '-', base_name)
        clean_name = re.sub(r'-+', '-', clean_name)
        clean_name = clean_name.strip('-')
        return f"{clean_name}.md"
    
    def convert_file(self, html_file: Path) -> bool:
        """Конвертирует один HTML файл в Markdown"""
        try:
            logger.debug(f"Обрабатываем файл: {html_file.name}")
            
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            markdown_content = self.convert_html_to_markdown(html_content, html_file)
            
            if not markdown_content.strip():
                logger.warning(f"Пустой контент после конвертации: {html_file.name}")
                self.stats['skipped'] += 1
                return False
            
            output_filename = self.generate_output_filename(html_file)
            output_file = self.output_path / output_filename
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.debug(f"✅ Сохранен: {output_filename}")
            self.stats['processed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке {html_file.name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def convert_all(self) -> Dict:
        """Конвертирует все HTML файлы в Markdown"""
        logger.info(f"🚀 Начинаем конвертацию HTML → Markdown для {self.config['name']}")
        
        html_files = self.find_html_files()
        self.stats['total_files'] = len(html_files)
        
        if not html_files:
            logger.warning("HTML файлы не найдены")
            return self.stats
        
        for html_file in html_files:
            self.convert_file(html_file)
        
        # Выводим статистику
        logger.info("📊 Статистика конвертации:")
        logger.info(f"   Всего файлов: {self.stats['total_files']}")
        logger.info(f"   Обработано: {self.stats['processed']}")
        logger.info(f"   Пропущено: {self.stats['skipped']}")
        logger.info(f"   Ошибок: {self.stats['errors']}")
        
        if self.stats['processed'] > 0:
            logger.info(f"✅ Конвертация завершена! Markdown файлы сохранены в: {self.output_path}")
        else:
            logger.warning("❌ Ни один файл не был успешно конвертирован")
        
        return self.stats

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Универсальный конвертер HTML документации в Markdown")
    parser.add_argument('framework', choices=list(FRAMEWORK_CONFIGS.keys()),
                       help='Фреймворк для конвертации')
    parser.add_argument('--input', '-i', type=str,
                       help='Путь к HTML файлам (переопределяет конфигурацию)')
    parser.add_argument('--output', '-o', type=str,
                       help='Путь для сохранения markdown файлов (переопределяет конфигурацию)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Подробный вывод')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Создаем кастомную конфигурацию если нужно
        custom_config = None
        if args.input or args.output:
            custom_config = FRAMEWORK_CONFIGS[args.framework].copy()
            if args.input:
                custom_config['html_path'] = args.input
            if args.output:
                custom_config['output_path'] = args.output
        
        # Создаем конвертер
        converter = UniversalHTMLConverter(
            framework=args.framework,
            custom_config=custom_config
        )
        
        # Запускаем конвертацию
        stats = converter.convert_all()
        
        # Возвращаем код завершения
        if stats['processed'] > 0:
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
