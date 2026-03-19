# webapp.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

# Инициализируем FastAPI
app = FastAPI(title="Pulse Mini App API")

# Разрешаем CORS (чтобы браузер не блокировал запросы)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальная переменная для БД (мы её передадим при старте из main.py)
db = None

def setup_webapp(database):
    global db
    db = database

# 1. Отдача самого сайта (HTML)
@app.get("/")
async def serve_index():
    # Ищем файл в той же папке, где лежит webapp.py
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "index.html"))
    
    # Если файла нет - выведем понятную ошибку прямо в браузер
    if not os.path.exists(html_path):
        return HTMLResponse(
            content=f"<h2>Ошибка!</h2><p>Файл <b>index.html</b> не найден.</p><p>Python ищет его здесь: <br><code>{html_path}</code></p><p>Положи файл index.html в эту папку!</p>", 
            status_code=404
        )
        
    # Если файл есть, отдаем его правильно (FastAPI сам проставит нужные заголовки)
    return FileResponse(html_path)

# 2. API: Получение данных для дашборда (Главная страница)
@app.get("/api/dashboard/{user_id}")
async def get_dashboard(user_id: int):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Собираем данные из твоей БД
    exchange_rate = db.get_exchange_rate()
    bank_balance = db.get_bank_balance()
    is_owner = user['is_owner'] or user['is_admin']
    
    return {
        "user": {
            "id": user['user_id'],
            "name": user['first_name'],
            "balance": user['balance'],
            "is_owner": is_owner
        },
        "economy": {
            "exchange_rate": exchange_rate,
            "bank_balance": bank_balance,
            "rub_equivalent": round(user['balance'] * exchange_rate, 2)
        }
    }

# 3. API: Перевод пульсов (Пример обработки POST запроса)
class TransferRequest(BaseModel):
    sender_id: int
    target_username: str
    amount: float

@app.post("/api/transfer")
async def transfer_pulses(data: TransferRequest):
    sender = db.get_user(data.sender_id)
    if not sender or sender['balance'] < data.amount:
        return {"success": False, "message": "Недостаточно средств"}
    
    # Ищем получателя (убираем @ если есть)
    target_uname = data.target_username.replace("@", "")
    db.cursor.execute('SELECT * FROM users WHERE username = ?', (target_uname,))
    target_user = db.cursor.fetchone()
    
    if not target_user:
        return {"success": False, "message": "Пользователь не найден"}
        
    if target_user['user_id'] == data.sender_id:
        return {"success": False, "message": "Нельзя перевести самому себе"}

    # Списываем и начисляем
    db.update_user_balance(data.sender_id, data.amount, 'subtract')
    db.update_user_balance(target_user['user_id'], data.amount, 'add')
    
    # Записываем транзакцию
    db.add_transaction(
        data.sender_id, 
        target_user['user_id'], 
        data.amount, 
        'transfer', 
        'Перевод из Mini App'
    )
    
    return {"success": True, "message": "Перевод успешно выполнен!"}