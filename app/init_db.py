"""
Скрипт для инициализации базы данных
"""
import os
import sys
from database import init_db, get_database_url

def main():
    """Инициализирует БД"""
    print("🔧 Инициализация базы данных...")
    print(f"📊 Подключение к: {get_database_url().replace(os.getenv('DB_PASSWORD', 'postgres'), '***')}")
    
    try:
        init_db()
        print("✅ База данных успешно инициализирована!")
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

