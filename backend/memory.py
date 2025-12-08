from backend.config.config import MEMORY_PATH
import json
import os
import uuid

# Формируем полные пути к файлам
MEMORY_FILE = os.path.join(MEMORY_PATH, "dialog_history.txt")
DIALOG_FILE = os.path.join(MEMORY_PATH, "dialog_history_dialog.json")

# Глобальная переменная для текущего ID диалога (для совместимости с MongoDB версией)
current_conversation_id = None


def get_or_create_conversation_id():
    """Получение или создание ID текущего диалога (для совместимости с MongoDB версией)"""
    global current_conversation_id
    if current_conversation_id is None:
        current_conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    return current_conversation_id


def reset_conversation():
    """Сброс текущего диалога (начало нового) (для совместимости с MongoDB версией)"""
    global current_conversation_id
    current_conversation_id = None

async def save_to_memory(role, message):
    """Сохраняет сообщение в память в простом формате"""
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{role}: {message}\n")

async def save_dialog_entry(role, content, metadata=None):
    """Сохраняет сообщение в формате диалога для передачи в модель"""
    import datetime
    
    # Загружаем существующую историю или создаем новую
    dialog_history = []
    if os.path.exists(DIALOG_FILE):
        try:
            with open(DIALOG_FILE, "r", encoding="utf-8") as f:
                dialog_history = json.load(f)
        except:
            dialog_history = []
    
    # Добавляем новое сообщение с временной меткой
    dialog_history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().isoformat()  # Полный формат ISO для API
    })
    
    # Сохраняем обновленную историю
    try:
        with open(DIALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(dialog_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении истории диалога: {e}")

async def load_history():
    """Загружает простую историю в текстовом формате"""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

async def load_dialog_history():
    """Загружает историю диалога в формате для передачи в модель"""
    if os.path.exists(DIALOG_FILE):
        try:
            with open(DIALOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

async def clear_dialog_history():
    """Очищает историю диалога"""
    if os.path.exists(DIALOG_FILE):
        os.remove(DIALOG_FILE)
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    return "История диалога очищена"

async def get_recent_dialog_history(max_entries=None):
    """Возвращает последние N сообщений из истории диалога
    
    Args:
        max_entries: Максимальное количество сообщений. Если None, возвращает всю историю (неограниченная память)
    """
    history = await load_dialog_history()
    
    # Если max_entries не указан, возвращаем всю историю (неограниченная память)
    if max_entries is None:
        return history
    
    # Ограничиваем количество сообщений
    return history[-max_entries:] if len(history) > max_entries else history