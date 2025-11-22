# Docker Setup для Portfolio Rebalancer

Инструкции по запуску приложения с использованием Docker и PostgreSQL.

## Требования

- Docker и Docker Compose
- API ключ для LLM провайдера (OpenRouter, OpenAI и т.д.)

## Быстрый старт

### 1. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
# LLM настройки
LLM_PROVIDER=openrouter
LLM_MODEL=x-ai/grok-4.1-fast:free
OPENROUTER_API_KEY=your-api-key-here

# Настройки БД (опционально, есть значения по умолчанию)
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=portfolio_rebalancer
```

### 2. Запуск с Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f api

# Остановка
docker-compose down

# Остановка с удалением данных БД
docker-compose down -v
```

### 3. Инициализация базы данных

База данных автоматически инициализируется при первом запуске API сервера. Если нужно инициализировать вручную:

```bash
# В контейнере
docker-compose exec api python init_db.py

# Или локально (если PostgreSQL запущен локально)
python init_db.py
```

## Структура сервисов

### PostgreSQL
- **Порт**: 5432
- **База данных**: portfolio_rebalancer
- **Пользователь**: postgres
- **Пароль**: postgres (измените в production!)

### API Server
- **Порт**: 8000
- **Документация**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## Разработка

### Локальная разработка без Docker

Если вы хотите запускать только PostgreSQL в Docker, а API локально:

```bash
# Запустить только PostgreSQL
docker-compose up -d postgres

# Настроить переменные окружения для локального подключения
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=portfolio_rebalancer

# Запустить API локально
python portfolio_rebalancer_api.py
```

### Подключение к БД

```bash
# Через Docker
docker-compose exec postgres psql -U postgres -d portfolio_rebalancer

# Локально (если PostgreSQL запущен локально)
psql -h localhost -U postgres -d portfolio_rebalancer
```

## Миграции

В текущей версии используется автоматическое создание таблиц через SQLAlchemy. Для production рекомендуется использовать Alembic для миграций:

```bash
# Установка Alembic
pip install alembic

# Инициализация
alembic init alembic

# Создание миграции
alembic revision --autogenerate -m "Initial migration"

# Применение миграций
alembic upgrade head
```

## Резервное копирование

### Создание бэкапа

```bash
docker-compose exec postgres pg_dump -U postgres portfolio_rebalancer > backup.sql
```

### Восстановление из бэкапа

```bash
docker-compose exec -T postgres psql -U postgres portfolio_rebalancer < backup.sql
```

## Troubleshooting

### Проблема: API не может подключиться к БД

1. Проверьте, что PostgreSQL запущен:
   ```bash
   docker-compose ps
   ```

2. Проверьте логи PostgreSQL:
   ```bash
   docker-compose logs postgres
   ```

3. Проверьте переменные окружения:
   ```bash
   docker-compose exec api env | grep DB_
   ```

### Проблема: Таблицы не создаются

1. Убедитесь, что БД инициализирована:
   ```bash
   docker-compose exec api python init_db.py
   ```

2. Проверьте логи API:
   ```bash
   docker-compose logs api
   ```

### Проблема: Порт уже занят

Измените порты в `docker-compose.yml`:

```yaml
services:
  postgres:
    ports:
      - "5433:5432"  # Измените 5432 на 5433
  api:
    ports:
      - "8001:8000"  # Измените 8000 на 8001
```

## Production рекомендации

1. **Безопасность**:
   - Измените пароли БД
   - Используйте секреты Docker или переменные окружения
   - Настройте firewall

2. **Производительность**:
   - Настройте пул соединений PostgreSQL
   - Используйте connection pooling в SQLAlchemy
   - Настройте индексы в БД

3. **Мониторинг**:
   - Добавьте логирование
   - Настройте health checks
   - Используйте мониторинг БД

4. **Масштабирование**:
   - Используйте managed PostgreSQL (AWS RDS, Google Cloud SQL)
   - Настройте репликацию
   - Используйте load balancer для API

