import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Bot, Copy, ArrowRight, X, Info } from 'lucide-react';

function InfoModal({ open, onClose }) {
  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-[32px] bg-white shadow-2xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <div className="text-lg font-black text-gray-900">Инструкция по генерации</div>
            <div className="text-sm text-gray-500 mt-1">Промпт формируется на основе стека и задачи.</div>
          </div>
          <button onClick={onClose} className="p-2 rounded-2xl text-gray-500 hover:bg-gray-100 transition">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5 text-sm text-gray-700">
          <p>Если поле "Стек" заполнено, результат будет содержать его в явном виде.</p>
          <p>Если поле "Стек" пустое, в итоговом промпте будет передана только задача.</p>
          <p>Для быстрого запуска используйте <span className="font-black">Ctrl+Enter</span> или <span className="font-black">Cmd+Enter</span>.</p>
          <div className="rounded-3xl bg-gray-50 border border-gray-200 p-4 text-xs leading-relaxed text-gray-600">
            <div className="font-black text-gray-900 mb-2">Структура результата:</div>
            <div>system: Ты переводишь описание задачи разработчика в промпт для Claude Code.</div>
            <div>Стек: {`{stack}`}</div>
            <div>Задача: {`{input}`}</div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function copyToClipboard(text) {
  if (!text) return Promise.reject(new Error('Нет текста для копирования'));
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      resolve();
    } catch (err) {
      reject(err);
    } finally {
      document.body.removeChild(textarea);
    }
  });
}

function buildPrompt(stack, input) {
  const normalizedStack = stack.trim();
  const normalizedInput = input.trim();
  const prefix = 'system: Ты переводишь описание задачи разработчика в промпт для Claude Code.';
  const stackPart = normalizedStack ? `Стек: ${normalizedStack}` : '';
  const taskPart = `Задача: ${normalizedInput}`;

  return [prefix, stackPart, taskPart].filter(Boolean).join('\n');
}

export default function PromptTranslator() {
  const [stack, setStack] = useState('');
  const [task, setTask] = useState('');
  const [output, setOutput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [showInfo, setShowInfo] = useState(false);

  const resetState = () => {
    setStack('');
    setTask('');
    setOutput('');
    setError('');
    setCopied(false);
  };

  const generatePrompt = useCallback(async () => {
    const normalizedTask = task.trim();
    if (!normalizedTask) return;
    setError('');
    setIsLoading(true);
    setCopied(false);

    try {
      const result = buildPrompt(stack, normalizedTask);
      await new Promise((resolve) => setTimeout(resolve, 220));
      setOutput(result);
    } catch (e) {
      setError('Не удалось сформировать промпт. Попробуйте ещё раз.');
    } finally {
      setIsLoading(false);
    }
  }, [stack, task]);

  const handleCopy = async () => {
    if (!output) return;
    try {
      await copyToClipboard(output);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Ошибка копирования в буфер обмена');
    }
  };

  const handleKeyDown = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      generatePrompt();
    }
  };

  useEffect(() => {
    if (!task.trim()) {
      setCopied(false);
    }
  }, [task]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-[2.5rem] border border-gray-100 shadow-sm p-6">
        <div className="flex items-start justify-between gap-3 mb-5">
          <div>
            <div className="text-xl font-black text-gray-900">Claude Code prompt helper</div>
            <div className="text-sm text-gray-500 mt-1">Преобразуй задачу в структурированный промпт для Claude Code.</div>
          </div>
          <button onClick={() => setShowInfo(true)} className="inline-flex items-center gap-2 rounded-3xl border border-gray-200 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-100 transition">
            <Info size={16} /> Инструкция
          </button>
        </div>

        <div className="grid gap-4">
          <label className="space-y-2 text-sm font-semibold text-gray-700">
            Стек (input, необязательно)
            <input
              value={stack}
              onChange={(e) => setStack(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Next.js + TypeScript + Tailwind + Supabase"
              className="w-full rounded-3xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          </label>

          <label className="space-y-2 text-sm font-semibold text-gray-700">
            Задача
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Опиши задачу понятно: пример — 'Напиши X на React с TypeScript, Tailwind и Supabase, кнопка закрывает модалку, результат в JSON.'"
              rows={8}
              className="w-full rounded-[32px] border border-gray-200 bg-gray-50 px-4 py-4 text-sm text-gray-900 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 resize-none"
            />
          </label>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={generatePrompt}
                disabled={!task.trim() || isLoading}
                className="inline-flex items-center gap-2 rounded-3xl bg-blue-600 px-5 py-3 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
              >
                {isLoading ? 'Генерируем...' : 'Сгенерировать промпт'}
              </button>
              <button
                type="button"
                onClick={resetState}
                className="inline-flex items-center gap-2 rounded-3xl border border-gray-200 bg-white px-5 py-3 text-sm font-black text-gray-700 transition hover:bg-gray-50"
              >
                Очистить
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span>Ctrl/Cmd + Enter для отправки</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1">Итерация</span>
            </div>
          </div>

          {error && (
            <div className="rounded-3xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>
      </div>

      {output && (
        <div className="bg-white rounded-[2.5rem] border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between gap-3 px-6 py-5 border-b border-gray-100">
            <div>
              <div className="text-sm font-black text-gray-900">Промпт для Claude Code</div>
              <div className="text-xs text-gray-500">Скопируй и вставь в API-запрос.</div>
            </div>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-2 rounded-3xl bg-blue-600 px-4 py-2 text-sm font-black text-white transition hover:bg-blue-700"
            >
              <Copy size={14} /> {copied ? 'Скопировано ✓' : 'Скопировать'}
            </button>
          </div>
          <div className="px-6 py-5 bg-slate-950 text-white text-sm font-medium leading-relaxed whitespace-pre-wrap break-words">
            {output}
          </div>
        </div>
      )}

      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} />
    </div>
  );
}
