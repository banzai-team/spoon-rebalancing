"""
Скрипт для инициализации базы данных с использованием миграций Alembic
"""
import os
import sys
from app.db import get_database_url
from alembic.config import Config
from alembic import command

def main():
    """Инициализирует БД с помощью миграций"""
    print("🔧 Инициализация базы данных...")
    print(f"📊 Подключение к: {get_database_url().replace(os.getenv('DB_PASSWORD', 'postgres'), '***')}")
    
    try:
        # Настройка Alembic
        alembic_cfg = Config("alembic.ini")
        
        # Применяем миграции
        print("📦 Применение миграций...")
        command.upgrade(alembic_cfg, "head")
        
        print("✅ База данных успешно инициализирована!")
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

