"""
Модуль для управления контекстными промптами моделей
Позволяет сохранять, загружать и применять контекстные промпты для каждой модели
"""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

def merge_context_prompt_into_system(
    system_prompt: Optional[str],
    model_path: Optional[str] = None,
    custom_prompt_id: Optional[str] = None,
    manager: Optional["ContextPromptManager"] = None,
) -> Optional[str]:
    """Добавляет глобальный/модельный промпт из Настройки → Модели к системным инструкциям."""
    mgr = manager or context_prompt_manager
    context_block = ""
    if mgr:
        try:
            if model_path:
                context_block = (mgr.get_effective_prompt(model_path, custom_prompt_id) or "").strip()
            else:
                context_block = (mgr.get_global_prompt() or "").strip()
        except Exception:
            context_block = ""

    extra = (system_prompt or "").strip()
    if context_block and extra:
        return f"{context_block}\n\n{extra}"
    if context_block:
        return context_block
    return extra or None


class ContextPromptManager:
    """Менеджер контекстных промптов для моделей"""
    
    def __init__(self):
        backend_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(backend_dir)
        # Канонический путь — рядом с settings.json; legacy — корень репозитория
        self.prompts_file = os.path.join(backend_dir, "context_prompts.json")
        self._legacy_prompts_file = os.path.join(project_root, "context_prompts.json")
        self.settings_file = os.path.join(backend_dir, "settings.json")
        
        # Загружаем существующие промпты
        self.context_prompts = self.load_context_prompts()
        self._migrate_legacy_prompts_file()
    
    def _read_prompts_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None

    def _prompts_payload_nonempty(self, data: Optional[Dict[str, Any]]) -> bool:
        if not data:
            return False
        if str(data.get("global_prompt") or "").strip():
            return True
        model_prompts = data.get("model_prompts") or {}
        if isinstance(model_prompts, dict) and any(str(v or "").strip() for v in model_prompts.values()):
            return True
        custom_prompts = data.get("custom_prompts") or {}
        return isinstance(custom_prompts, dict) and len(custom_prompts) > 0

    def _migrate_legacy_prompts_file(self) -> None:
        """Если промпты лежат только в корне репозитория — переносим в backend/context_prompts.json."""
        legacy = self._read_prompts_file(self._legacy_prompts_file)
        if not legacy or not self._prompts_payload_nonempty(legacy):
            return
        current = self.context_prompts or {}
        if self._prompts_payload_nonempty(current):
            return
        self.context_prompts = legacy
        self.save_context_prompts()

    def load_context_prompts(self) -> Dict[str, Any]:
        """Загрузка контекстных промптов из файла"""
        default_prompts = {
            "global_prompt": "",
            "model_prompts": {},
            "custom_prompts": {},
        }
        try:
            for candidate in (self.prompts_file, self._legacy_prompts_file):
                data = self._read_prompts_file(candidate)
                if data is not None:
                    return data
            self.save_context_prompts(default_prompts)
            return default_prompts
        except Exception as e:
            print(f"Ошибка при загрузке контекстных промптов: {e}")
            return default_prompts
    
    def save_context_prompts(self, prompts: Optional[Dict[str, Any]] = None) -> bool:
        """Сохранение контекстных промптов в файл"""
        try:
            if prompts is None:
                prompts = self.context_prompts
            
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump(prompts, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении контекстных промптов: {e}")
            return False
    
    def get_global_prompt(self) -> str:
        """Получение глобального промпта"""
        return self.context_prompts.get("global_prompt", "")
    
    def set_global_prompt(self, prompt: str) -> bool:
        """Установка глобального промпта"""
        self.context_prompts["global_prompt"] = prompt
        return self.save_context_prompts()
    
    def get_model_prompt(self, model_path: str) -> str:
        """Получение промпта для конкретной модели"""
        model_prompts = self.context_prompts.get("model_prompts", {})
        return model_prompts.get(model_path, self.get_global_prompt())
    
    def set_model_prompt(self, model_path: str, prompt: str) -> bool:
        """Установка промпта для конкретной модели"""
        if "model_prompts" not in self.context_prompts:
            self.context_prompts["model_prompts"] = {}
        
        self.context_prompts["model_prompts"][model_path] = prompt
        return self.save_context_prompts()
    
    def get_custom_prompt(self, prompt_id: str) -> Optional[str]:
        """Получение пользовательского промпта по ID"""
        custom_prompts = self.context_prompts.get("custom_prompts", {})
        return custom_prompts.get(prompt_id)
    
    def set_custom_prompt(self, prompt_id: str, prompt: str, description: str = "") -> bool:
        """Создание/обновление пользовательского промпта"""
        if "custom_prompts" not in self.context_prompts:
            self.context_prompts["custom_prompts"] = {}
        
        self.context_prompts["custom_prompts"][prompt_id] = {
            "prompt": prompt,
            "description": description,
            "created_at": self._get_current_timestamp()
        }
        return self.save_context_prompts()
    
    def delete_custom_prompt(self, prompt_id: str) -> bool:
        """Удаление пользовательского промпта"""
        if "custom_prompts" in self.context_prompts and prompt_id in self.context_prompts["custom_prompts"]:
            del self.context_prompts["custom_prompts"][prompt_id]
            return self.save_context_prompts()
        return False
    
    def get_all_custom_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Получение всех пользовательских промптов"""
        return self.context_prompts.get("custom_prompts", {})
    
    def get_effective_prompt(self, model_path: str, custom_prompt_id: Optional[str] = None) -> str:
        """Получение эффективного промпта для модели с учетом приоритетов"""
        # 1. Если указан пользовательский промпт, используем его
        if custom_prompt_id:
            custom_prompt = self.get_custom_prompt(custom_prompt_id)
            if custom_prompt:
                return custom_prompt.get("prompt", self.get_global_prompt())
        
        # 2. Если есть промпт для конкретной модели, используем его
        model_prompt = self.get_model_prompt(model_path)
        if model_prompt != self.get_global_prompt():
            return model_prompt
        
        # 3. Иначе используем глобальный промпт
        return self.get_global_prompt()
    
    def get_models_list(self) -> List[Dict[str, Any]]:
        """Получение списка всех моделей с их промптами"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    models = settings.get("models", [])
                    
                    # Добавляем информацию о промптах для каждой модели
                    for model in models:
                        model_path = model.get("path", "")
                        model["context_prompt"] = self.get_model_prompt(model_path)
                        model["has_custom_prompt"] = model_path in self.context_prompts.get("model_prompts", {})
                    
                    return models
            return []
        except Exception as e:
            print(f"Ошибка при получении списка моделей: {e}")
            return []
    
    def _get_current_timestamp(self) -> str:
        """Получение текущей временной метки"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def export_prompts(self, file_path: str) -> bool:
        """Экспорт всех промптов в файл"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.context_prompts, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка при экспорте промптов: {e}")
            return False
    
    def import_prompts(self, file_path: str) -> bool:
        """Импорт промптов из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_prompts = json.load(f)
            
            # Валидация структуры
            if not isinstance(imported_prompts, dict):
                return False
            
            # Обновляем промпты
            self.context_prompts.update(imported_prompts)
            return self.save_context_prompts()
        except Exception as e:
            print(f"Ошибка при импорте промптов: {e}")
            return False

# Создаем глобальный экземпляр менеджера
context_prompt_manager = ContextPromptManager()
