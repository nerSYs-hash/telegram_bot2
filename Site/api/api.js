// Базовый URL нашего FastAPI
const API_URL = "http://127.0.0.1:8000";

export const API = {
    // Функция авторизации
    async authUser(tgData) {
        try {
            const response = await fetch(`${API_URL}/api/auth/telegram`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(tgData)
            });
            return await response.json();
        } catch (error) {
            console.error("Ошибка API:", error);
            return { status: "error", message: "Сервер бэкенда не отвечает" };
        }
    },

    // Получить курс пульса
    async getMarketRate() {
        const response = await fetch(`${API_URL}/api/market/rate`);
        return await response.json();
    }
};
