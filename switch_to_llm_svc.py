#!/usr/bin/env python3
"""
Скрипт для переключения MemoAI на использование llm-svc
"""

import os
import shutil
import sys
from pathlib import Path

def backup_original_agent():
    """Создание резервной копии оригинального agent.py"""
    agent_path = Path("backend/agent.py")
    backup_path = Path("backend/agent_original.py")
    
    if agent_path.exists() and not backup_path.exists():
        shutil.copy2(agent_path, backup_path)
        print("✅ Создана резервная копия: backend/agent_original.py")
        return True
    return False

def switch_to_llm_svc():
    """Переключение на llm-svc"""
    agent_original = Path("backend/agent.py")
    agent_llm_svc = Path("backend/agent_llm_svc.py")
    
    if not agent_llm_svc.exists():
        print("❌ Файл backend/agent_llm_svc.py не найден!")
        return False
    
    # Создаем резервную копию
    backup_original_agent()
    
    # Заменяем agent.py на версию с llm-svc
    shutil.copy2(agent_llm_svc, agent_original)
    print("✅ Переключено на llm-svc версию agent.py")
    return True

def switch_to_original():
    """Переключение на оригинальную версию"""
    agent_original = Path("backend/agent.py")
    agent_backup = Path("backend/agent_original.py")
    
    if not agent_backup.exists():
        print("❌ Резервная копия backend/agent_original.py не найдена!")
        return False
    
    # Восстанавливаем оригинальную версию
    shutil.copy2(agent_backup, agent_original)
    print("✅ Восстановлена оригинальная версия agent.py")
    return True

def check_llm_svc_config():
    """Проверка конфигурации llm-svc"""
    config_path = Path("llm-svc/config/config.yml")
    
    if not config_path.exists():
        print("❌ Файл конфигурации llm-svc не найден!")
        print("   Создайте файл llm-svc/config/config.yml")
        return False
    
    print("✅ Конфигурация llm-svc найдена")
    return True

def check_models_directory():
    """Проверка директории с моделями"""
    models_path = Path("models")
    
    if not models_path.exists():
        print("⚠️  Директория models/ не найдена!")
        print("   Создайте директорию и поместите туда ваши .gguf модели")
        return False
    
    # Ищем .gguf файлы
    gguf_files = list(models_path.glob("*.gguf"))
    if not gguf_files:
        print("⚠️  В директории models/ не найдено .gguf файлов!")
        print("   Поместите ваши модели в формате .gguf в директорию models/")
        return False
    
    print(f"✅ Найдено {len(gguf_files)} .gguf файлов в models/:")
    for file in gguf_files:
        print(f"   - {file.name}")
    
    return True

def main():
    """Основная функция"""
    print("🔄 Скрипт переключения MemoAI на llm-svc")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python switch_to_llm_svc.py enable   - Включить llm-svc")
        print("  python switch_to_llm_svc.py disable  - Отключить llm-svc")
        print("  python switch_to_llm_svc.py check    - Проверить конфигурацию")
        return
    
    command = sys.argv[1].lower()
    
    if command == "enable":
        print("🔧 Включение llm-svc...")
        
        # Проверяем конфигурацию
        if not check_llm_svc_config():
            return
        
        if not check_models_directory():
            print("⚠️  Продолжаем без проверки моделей...")
        
        # Переключаемся на llm-svc
        if switch_to_llm_svc():
            print("\n✅ Переключение на llm-svc завершено!")
            print("\n📋 Следующие шаги:")
            print("1. Отредактируйте llm-svc/config/config.yml")
            print("2. Укажите правильный путь к вашей модели")
            print("3. Запустите: docker-compose up -d")
            print("4. Или запустите llm-svc локально: cd llm-svc && python -m app.main")
    
    elif command == "disable":
        print("🔧 Отключение llm-svc...")
        
        if switch_to_original():
            print("\n✅ Переключение на оригинальную версию завершено!")
            print("\n📋 Теперь вы можете использовать локальные модели")
    
    elif command == "check":
        print("🔍 Проверка конфигурации...")
        
        check_llm_svc_config()
        check_models_directory()
        
        # Проверяем наличие необходимых файлов
        required_files = [
            "backend/llm_client.py",
            "backend/agent_llm_svc.py",
            "llm-svc/config/config.yml"
        ]
        
        print("\n📁 Проверка файлов интеграции:")
        for file in required_files:
            if Path(file).exists():
                print(f"✅ {file}")
            else:
                print(f"❌ {file}")
    
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()
