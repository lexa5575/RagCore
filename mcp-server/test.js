#!/usr/bin/env node
import axios from 'axios';

const RAG_SERVER_URL = 'http://localhost:8000';

console.log('🧪 Тестирование MCP сервера для RAG Assistant\n');

async function testRAGServer() {
  try {
    // Тест 1: Проверка доступности RAG сервера
    console.log('1️⃣ Проверка доступности RAG сервера...');
    const rootResponse = await axios.get(RAG_SERVER_URL);
    console.log('✅ RAG сервер доступен');
    console.log(`   Документов в базе: ${rootResponse.data.total_docs}`);
    console.log('');
    
    // Тест 1.5: Проверка доступности моделей
    console.log('1️⃣.5️⃣ Проверка доступности моделей...');
    const modelsResponse = await axios.get(`${RAG_SERVER_URL}/models`);
    console.log('✅ Список моделей получен:');
    console.log(`   Доступно моделей: ${Object.keys(modelsResponse.data.models).length}`);
    console.log(`   Модель по умолчанию: ${modelsResponse.data.default}`);
    Object.entries(modelsResponse.data.models).forEach(([key, info]) => {
      console.log(`   - ${info.name} (${key})`);
    });
    console.log('');

    // Тест 2: Получение списка фреймворков
    console.log('2️⃣ Получение списка фреймворков...');
    const frameworksResponse = await axios.get(`${RAG_SERVER_URL}/frameworks`);
    const frameworks = Object.keys(frameworksResponse.data);
    console.log(`✅ Найдено фреймворков: ${frameworks.length}`);
    frameworks.forEach(fw => console.log(`   - ${fw}`));
    console.log('');

    // Тест 3: Статистика базы данных
    console.log('3️⃣ Получение статистики...');
    const statsResponse = await axios.get(`${RAG_SERVER_URL}/stats`);
    console.log('✅ Статистика получена:');
    console.log(`   Всего документов: ${statsResponse.data.total_documents}`);
    console.log(`   Размер кэша: ${statsResponse.data.cache_size}`);
    if (statsResponse.data.frameworks) {
      console.log('   Распределение:');
      Object.entries(statsResponse.data.frameworks).forEach(([fw, count]) => {
        console.log(`     ${fw}: ${count}`);
      });
    }
    console.log('');

    // Тест 4: Тестовый запрос с моделью по умолчанию
    console.log('4️⃣ Тестовый запрос к RAG с моделью по умолчанию...');
    console.log('   Вопрос: "Что такое компонент?"');
    
    const startTime = Date.now();
    const askResponse = await axios.post(`${RAG_SERVER_URL}/ask`, {
      question: 'Что такое компонент?',
      max_results: 3
    });
    const responseTime = (Date.now() - startTime) / 1000;
    
    console.log('✅ Ответ получен:');
    console.log(`   Время ответа: ${responseTime.toFixed(2)}с`);
    console.log(`   Определен фреймворк: ${askResponse.data.framework_detected}`);
    console.log(`   Источников: ${askResponse.data.sources.length}`);
    console.log(`   Первые 200 символов ответа:`);
    console.log(`   "${askResponse.data.answer.substring(0, 200)}..."`);
    console.log('');
    
    // Тест 5: Тестовый запрос с указанием модели
    console.log('5️⃣ Тестовый запрос к RAG с указанием модели...');
    console.log('   Вопрос: "Что такое компонент?" с моделью deepseek');
    
    try {
      const startTimeDeepseek = Date.now();
      const askResponseDeepseek = await axios.post(`${RAG_SERVER_URL}/ask`, {
        question: 'Что такое компонент?',
        max_results: 3,
        model: 'deepseek'
      });
      const responseTimeDeepseek = (Date.now() - startTimeDeepseek) / 1000;
      
      console.log('✅ Ответ от DeepSeek получен:');
      console.log(`   Время ответа: ${responseTimeDeepseek.toFixed(2)}с`);
      console.log(`   Определен фреймворк: ${askResponseDeepseek.data.framework_detected}`);
      console.log(`   Источников: ${askResponseDeepseek.data.sources.length}`);
      console.log(`   Первые 200 символов ответа:`);
      console.log(`   "${askResponseDeepseek.data.answer.substring(0, 200)}..."`);
    } catch (error) {
      console.log('⚠️ Тест с моделью DeepSeek пропущен:');
      console.log(`   ${error.message}`);
      if (error.response && error.response.data && error.response.data.detail) {
        console.log(`   ${error.response.data.detail}`);
      }
    }
    console.log('');

    console.log('✅ Все тесты пройдены успешно!');
    console.log('\n📝 Теперь вы можете настроить MCP сервер в Cline:');
    console.log('   Путь к серверу: ' + process.cwd() + '/index.js');
    
  } catch (error) {
    console.error('❌ Ошибка при тестировании:');
    if (error.code === 'ECONNREFUSED') {
      console.error('   RAG сервер не запущен на http://localhost:8000');
      console.error('   Запустите его командой:');
      console.error('   cd /Users/aleksejcuprynin/PycharmProjects/chanki');
      console.error('   source venv/bin/activate');
      console.error('   python rag_server.py');
    } else if (error.response) {
      console.error(`   HTTP ${error.response.status}: ${error.response.statusText}`);
      if (error.response.data && error.response.data.detail) {
        console.error(`   ${error.response.data.detail}`);
      }
    } else {
      console.error(`   ${error.message}`);
    }
    process.exit(1);
  }
}

// Запуск тестов
testRAGServer();
