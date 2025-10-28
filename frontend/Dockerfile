# Multi-stage build для React приложения
FROM node:20-alpine as build

# Установка рабочей директории
WORKDIR /app

# Установка build arguments ДО копирования
ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_WS_URL=ws://localhost:8000

# Установка переменных окружения
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_WS_URL=$REACT_APP_WS_URL

# Копирование package.json и package-lock.json
COPY package*.json ./

# Установка зависимостей (включая dev dependencies для сборки)
RUN npm ci
# Копирование исходного кода
COPY . .

# Сборка приложения (ENV переменные уже установлены выше)
RUN npm run build

# Production стадия
FROM nginx:alpine

# Копирование собранного приложения
COPY --from=build /app/build /usr/share/nginx/html

# Копирование конфигурации nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открытие порта
EXPOSE 3000

# Команда запуска
CMD ["nginx", "-g", "daemon off;"]
