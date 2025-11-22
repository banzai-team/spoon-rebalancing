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

# Копирование pyproject.toml
COPY pyproject.toml .

# Копирование всего кода приложения
COPY . .

# Установка зависимостей и пакета
RUN uv pip install --system .

# Открываем порт
EXPOSE 8000

# Команда по умолчанию
CMD ["python", "run.py"]

