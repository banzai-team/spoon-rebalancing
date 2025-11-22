FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install uv

# Копирование pyproject.toml и установка зависимостей
# Делаем это отдельно для лучшего кеширования Docker слоев
COPY pyproject.toml .
RUN uv pip install --system .

# Копирование кода приложения
COPY . .

# Открываем порт
EXPOSE 8000

# Команда по умолчанию
CMD ["python", "portfolio_rebalancer_api.py"]

