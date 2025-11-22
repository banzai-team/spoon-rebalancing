"""
Точка входа для запуска API сервера
"""
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Запуск API сервера на http://{host}:{port}")
    print(f"📚 Документация API: http://{host}:{port}/docs")
    print(f"🔍 Альтернативная документация: http://{host}:{port}/redoc")
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

