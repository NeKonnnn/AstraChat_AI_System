-- Скрипт для установки расширения pgvector в базу данных
-- Выполните этот скрипт в pgAdmin4 или psql после сборки pgvector

-- Проверка версии PostgreSQL
SELECT version();

-- Создание расширения (если еще не создано)
CREATE EXTENSION IF NOT EXISTS vector;

-- Проверка установки расширения
SELECT 
    extname AS "Расширение",
    extversion AS "Версия",
    extrelocatable AS "Перемещаемое"
FROM pg_extension 
WHERE extname = 'vector';

-- Тест создания векторного типа
SELECT '[1,2,3]'::vector AS test_vector;

-- Если все работает, вы увидите:
-- Расширение: vector
-- Версия: 0.8.1 (или другая)
-- test_vector: [1,2,3]










































































