#!/usr/bin/env python3
"""
Скрипт миграции конфигурации backend
Переводит старые настройки из settings.json в новый config.yml
"""

import json
import yaml
import os
from pathlib import Path

def migrate_settings_to_config():
    """Миграция настроек из settings.json в config.yml"""
    
    # Пути к файлам
    settings_path = "settings.json"
    config_path = "config/config.yml"
    
    # Проверяем существование старого файла
    if not os.path.exists(settings_path):
        print(f"Файл {settings_path} не найден. Миграция не требуется.")
        return
    
    # Загружаем старые настройки
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            old_settings = json.load(f)
        print(f"Загружены настройки из {settings_path}")
    except Exception as e:
        print(f"Ошибка загрузки {settings_path}: {e}")
        return
    
    # Загружаем новую конфигурацию
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            new_config = yaml.safe_load(f)
        print(f"Загружена конфигурация из {config_path}")
    except Exception as e:
        print(f"Ошибка загрузки {config_path}: {e}")
        return
    
    # Мигрируем настройки
    migrated = False
    
    # Мигрируем настройки голоса
    if "voice_speaker" in old_settings:
        new_config["microservices"]["llm_svc"]["tts"]["default_speaker"] = old_settings["voice_speaker"]
        migrated = True
        print(f"Мигрирован voice_speaker: {old_settings['voice_speaker']}")
    
    # Мигрируем настройки транскрипции
    if "transcription_engine" in old_settings:
        if old_settings["transcription_engine"] == "whisperx":
            # WhisperX заменяется на Vosk в микросервисе
            print("WhisperX заменен на Vosk в микросервисе")
        migrated = True
    
    if "transcription_language" in old_settings:
        new_config["microservices"]["llm_svc"]["transcription"]["default_language"] = old_settings["transcription_language"]
        migrated = True
        print(f"Мигрирован transcription_language: {old_settings['transcription_language']}")
    
    # Мигрируем настройки темы (если нужно)
    if "theme" in old_settings:
        # Тема обычно настраивается на фронтенде
        print(f"Настройка темы '{old_settings['theme']}' должна быть перенесена на фронтенд")
    
    # Сохраняем обновленную конфигурацию
    if migrated:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True, indent=2)
            print(f"Конфигурация обновлена в {config_path}")
        except Exception as e:
            print(f"Ошибка сохранения {config_path}: {e}")
    else:
        print("Нет настроек для миграции")

def backup_old_settings():
    """Создание резервной копии старых настроек"""
    settings_path = "settings.json"
    backup_path = "settings.json.backup"
    
    if os.path.exists(settings_path):
        try:
            import shutil
            shutil.copy2(settings_path, backup_path)
            print(f"Создана резервная копия: {backup_path}")
        except Exception as e:
            print(f"Ошибка создания резервной копии: {e}")

if __name__ == "__main__":
    print("=== Миграция конфигурации astrachat Backend ===")
    print()
    
    # Создаем резервную копию
    backup_old_settings()
    
    # Выполняем миграцию
    migrate_settings_to_config()
    
    print()
    print("Миграция завершена!")
    print("Теперь backend будет использовать config.yml вместо settings.json")
    print("Старые настройки сохранены в settings.json.backup")


