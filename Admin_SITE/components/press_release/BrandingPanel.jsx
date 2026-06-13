import { useState, useEffect } from 'react';
import { Palette, Save, CheckCircle2 } from 'lucide-react';
import { makeApi } from './useApi';
import Button from '../shared/Button';

export default function BrandingPanel({ token, onChange, compact = false }) {
  const api = makeApi(token);
  
  const [config, setConfig] = useState({
    enabled: false,
    sign: '©',
    text: '',
    show_year: true,
    modules: {
      horoscope: false,
      anketa: false,
      press_release: false
    }
  });
  
  const [savedAt, setSavedAt] = useState(0);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      const d = await api.getBranding();
      if (d?.global_signature) {
        setConfig(JSON.parse(d.global_signature));
      } else {
        // Fallback for legacy signature
        if (d?.signature && config.text === '') {
           setConfig(prev => ({ ...prev, text: d.signature.replace(/<[^>]*>?/gm, '') }));
        }
      }
    } catch (e) {}
  };

  useEffect(() => { refresh(); }, []);

  const handleSave = async () => {
    setBusy(true);
    try {
      await api.setBranding('global_signature', JSON.stringify(config));
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(0), 1500);
      onChange?.();
    } catch (e) {
      alert('Ошибка: ' + (e?.detail || e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  const updateConfig = (updates) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  const toggleModule = (mod) => {
    setConfig(prev => ({
      ...prev,
      modules: { ...prev.modules, [mod]: !prev.modules[mod] }
    }));
  };

  const wrapperCls = compact
    ? 'space-y-3'
    : 'bg-sff rounded-3xl border border-bd shadow-sm p-5 space-y-4';

  return (
    <div className={wrapperCls}>
      {!compact && (
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-7 h-7 rounded-xl bg-[color-mix(in_oklab,var(--pink)_16%,transparent)] flex items-center justify-center">
            <Palette size={14} className="text-pink" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xs font-black uppercase tracking-widest text-tx">Глобальный брендинг</h2>
            <p className="text-[10px] text-lbl mt-0.5">
              Единая подпись для публикаций в каналах сообщества
            </p>
          </div>
          {savedAt > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-black text-ok">
              <CheckCircle2 size={12}/> сохранено
            </span>
          )}
        </div>
      )}

      {compact && savedAt > 0 && (
        <div className="flex justify-end">
          <span className="flex items-center gap-1 text-[10px] font-black text-ok">
            <CheckCircle2 size={12}/> сохранено
          </span>
        </div>
      )}

      <div className="space-y-3">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={config.enabled}
            onChange={(e) => updateConfig({ enabled: e.target.checked })}
            className="w-4 h-4 accent-amber-500" />
          <span className="text-[11px] font-bold text-tx">Включить глобальную подпись</span>
        </label>

        {config.enabled && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] font-bold text-lbl uppercase tracking-widest mb-1.5">Значок</div>
                <input
                  value={config.sign}
                  onChange={(e) => updateConfig({ sign: e.target.value })}
                  placeholder="©"
                  className="w-full px-3 py-2 bg-sf2 border border-bd rounded-lg text-xs font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--pink)_50%,transparent)]"
                />
              </div>
              <div>
                <div className="text-[10px] font-bold text-lbl uppercase tracking-widest mb-1.5">Текст</div>
                <input
                  value={config.text}
                  onChange={(e) => updateConfig({ text: e.target.value })}
                  placeholder="Pulse Community"
                  className="w-full px-3 py-2 bg-sf2 border border-bd rounded-lg text-xs font-bold focus:outline-none focus:border-[color-mix(in_oklab,var(--pink)_50%,transparent)]"
                />
              </div>
            </div>

            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={config.show_year}
                  onChange={(e) => updateConfig({ show_year: e.target.checked })}
                  className="w-4 h-4 accent-amber-500" />
                <span className="text-[11px] font-bold text-tx">Добавлять год</span>
              </label>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-tx">Стиль шрифта:</span>
                <select
                  value={config.font_style || 'normal'}
                  onChange={(e) => updateConfig({ font_style: e.target.value })}
                  className="bg-sf2 border border-bd rounded-lg text-[11px] font-bold px-2 py-1 outline-none focus:border-pink-500 text-tx"
                >
                  <option value="normal">Обычный</option>
                  <option value="bold">Жирный</option>
                  <option value="italic">Курсив</option>
                  <option value="mono">Моноширинный</option>
                </select>
              </div>
            </div>

            <div className="pt-2 border-t border-bd space-y-2">
              <div className="text-[10px] font-bold text-lbl uppercase tracking-widest">Применять в модулях:</div>
              <div className="flex gap-4">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={config.modules.press_release}
                    onChange={() => toggleModule('press_release')}
                    className="w-3.5 h-3.5 accent-pink" />
                  <span className="text-[11px] text-tx">Пресс-релизы</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={config.modules.anketa}
                    onChange={() => toggleModule('anketa')}
                    className="w-3.5 h-3.5 accent-pink" />
                  <span className="text-[11px] text-tx">Анкеты</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={config.modules.horoscope}
                    onChange={() => toggleModule('horoscope')}
                    className="w-3.5 h-3.5 accent-pink" />
                  <span className="text-[11px] text-tx">Гороскопы</span>
                </label>
              </div>
            </div>
            
            <div className="bg-sf2 border border-bd rounded-lg px-3 py-2 mt-2">
              <div className="text-[9px] font-black uppercase tracking-widest text-lbl mb-1">Превью</div>
              <div className={`text-xs text-tx ${config.font_style === 'bold' ? 'font-bold' : config.font_style === 'italic' ? 'italic' : config.font_style === 'mono' ? 'font-mono text-[11px]' : ''}`}>
                {[config.sign, config.text, config.show_year ? new Date().getFullYear() : ''].filter(Boolean).join(' ')}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="pt-2">
        <Button variant="primary" size="sm" icon={Save} block disabled={busy} onClick={handleSave}>
          Сохранить настройки
        </Button>
      </div>
    </div>
  );
}
