// API base URL. Override with VITE_MINI_APP_API_BASE in .env (local dev or prod).
export const API_BASE: string =
  (import.meta.env.VITE_MINI_APP_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000';
