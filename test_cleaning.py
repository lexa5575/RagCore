#!/usr/bin/env python3
"""
Тест для проверки очистки артефактов
"""

import requests
import json

# Тестовый запрос
response = requests.post("http://127.0.0.1:8200/tool/ask_rag", json={
    "query": "Что такое ref в Vue?",
    "framework": "vue",
    "max_results": 2
})

if response.status_code == 200:
    data = response.json()
    answer = data.get('answer', '')
    
    print("=" * 80)
    print("ПОЛНЫЙ ОТВЕТ:")
    print("=" * 80)
    print(answer)
    print("=" * 80)
    print(f"\nДлина ответа: {len(answer)} символов")
    
    # Проверяем наличие артефактов
    artifacts = [
        '[VUE]',
        '[LARAVEL]',
        '[Documentation Context]',
        '[User Question]',
        '[Additional Context]',
        '[Instructions]',
        '[Answer]',
        'description.md',
        '# What\'s Next?',
        '# Routing',
        '# State Management',
        '# Performance Optimization',
        '# Conclusion'
    ]
    
    found_artifacts = []
    for artifact in artifacts:
        if artifact in answer:
            count = answer.count(artifact)
            found_artifacts.append(f"{artifact} (найдено {count} раз)")
    
    if found_artifacts:
        print("\n🔴 НАЙДЕНЫ АРТЕФАКТЫ:")
        for artifact in found_artifacts:
            print(f"  - {artifact}")
    else:
        print("\n✅ Артефакты не найдены")
    
    # Проверяем, где начинается мусор
    if '[VUE]' in answer:
        first_vue_index = answer.find('[VUE]')
        print(f"\n🔍 Первый артефакт '[VUE]' найден на позиции: {first_vue_index}")
        print(f"Текст до артефакта ({first_vue_index} символов):")
        print("-" * 40)
        print(answer[:first_vue_index])
        print("-" * 40)
else:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)
