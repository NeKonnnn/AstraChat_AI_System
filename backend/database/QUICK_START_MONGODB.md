# 🚀 Быстрый старт MongoDB для MemoAI

## Вариант 1: Локальная установка (5 минут)

### 1. Скачайте MongoDB
```
https://www.mongodb.com/try/download/community
```
- Version: **7.0.x**
- Platform: **Windows**
- Package: **msi**

### 2. Установите
- Запустите `.msi` файл
- Выберите **Complete**
- ✅ Оставьте галочку **Install MongoDB as a Service**
- Нажмите **Install**

### 3. Проверьте
Откройте PowerShell:
```powershell
Get-Service MongoDB
mongosh
```

### 4. Настройте проект
Создайте `.env` в корне проекта:
```env
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=memoai
MONGODB_USER=admin
MONGODB_PASSWORD=password
```

### 5. Протестируйте
```powershell
python test_mongodb_connection.py
```

---

## Вариант 2: Docker (1 минута)

### 1. Запустите MongoDB
```powershell
docker-compose up -d mongodb
```

### 2. Проверьте
```powershell
docker ps
```

### 3. Готово! ✅

---

## Запуск проекта

### Локально:
```powershell
.\venv_312\Scripts\activate
cd backend
python main.py
```

### Docker:
```powershell
docker-compose up -d
```

---

## Проблемы?

📖 Подробная инструкция: **MONGODB_SETUP_WINDOWS.md**

### Частые ошибки:

**MongoDB не запускается:**
```powershell
net start MongoDB
```

**Порт занят:**
```powershell
netstat -ano | findstr :27017
```

**Зависимости не установлены:**
```powershell
pip install motor pymongo
```

---

## Готово! 🎉

Теперь MemoAI работает с MongoDB!




