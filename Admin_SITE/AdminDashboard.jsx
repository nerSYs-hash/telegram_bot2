import React, { useState, useMemo, useEffect, useCallback } from 'react';
import EconomyPage from './components/economy/EconomyPage';
import { createPortal } from 'react-dom';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Brush
} from 'recharts';
import { 
  Home, Users, Settings, Send, Power, Menu, X, Calendar, Heart, 
  ShieldAlert, ScrollText, PieChart, Trash2, PlusCircle, AlertOctagon, 
  CheckCircle2, Info, Edit, ShieldBan, Clock, MessageSquareX, 
  Zap, Bot, Sparkles, Loader2, Download, FileSpreadsheet,
  FileText, TrendingUp, TrendingDown, Activity, ChevronRight,
  Wallet, Ghost, MessageCircle, UserSearch, UserCheck,
  ChevronDown, ChevronUp, Globe, User, Image as ImageIcon, Video, Smile, Link2,
  Flame, HeartHandshake, Dices, Coins, ShieldCheck, UserMinus, Percent,
  Megaphone, PartyPopper, Wrench, Bug,
  GripVertical, Play, Square, Copy, Search, Check, RotateCcw, Ban,
  Crown, AtSign, Hash, Plug, LogOut
} from 'lucide-react';

const UserAvatar = React.memo(({ userId, name = '', size = 36 }) => {
  const [err, setErr] = React.useState(false);
  const initials = (name || '?').replace(/^@/, '').slice(0, 1).toUpperCase();
  const px = `${size}px`;
  if (!userId || err) {
    return (
      <div className="rounded-full bg-gradient-to-tr from-blue-500 to-indigo-500 flex items-center justify-center text-white font-black flex-shrink-0 select-none"
           style={{ width: px, height: px, fontSize: Math.round(size * 0.42) }}>
        {initials}
      </div>
    );
  }
  return (
    <img src={`/api/user/${userId}/avatar`} alt="" onError={() => setErr(true)}
         className="rounded-full object-cover flex-shrink-0 border-2 border-white shadow-sm"
         style={{ width: px, height: px }}/>
  );
});

// ═══════════════════════════════════════════
//  СПИСОК ОБНОВЛЕНИЙ — добавляй сюда при каждом релизе
//  type: 'new' | 'fix' | 'improve'
// ═══════════════════════════════════════════
const UPDATES = [
  {
    version: 'V1.12.9',
    date: '20 апреля 2026',
    title: '📝 Полноэкранный редактор триггеров',
    items: [
      { type: 'new',     tag: 'triggers', text: 'Редактор триггера переработан в полноэкранную страницу вместо всплывающего модала' },
      { type: 'improve', tag: 'triggers', text: 'Шапка в стиле ChatKeeper: кнопки «Сохранить», «···» (меню) и «Удалить» всегда видны' },
      { type: 'fix',     tag: 'triggers', text: 'Старый 4-шаговый мастер полностью удалён — никаких конфликтов с новым редактором' },
    ],
  },
  {
    version: 'V1.12.7',
    date: '19 апреля 2026',
    title: '🗂 Новый редактор условий и действий',
    items: [
      { type: 'new',     tag: 'triggers', text: 'Редактор триггера: раздельные блоки условий и действий с drag & drop сортировкой' },
      { type: 'new',     tag: 'triggers', text: 'Список триггеров: переключатель активен/неактивен, поиск, копирование, контекстное меню' },
    ],
  },
  {
    version: 'V1.12.6',
    date: '18 апреля 2026',
    title: '🏷 Журнал: хештеги и управление администраторами',
    items: [
      { type: 'new',     tag: 'journal',  text: 'Все 15 хештегов событий поддерживаются в фильтрах журнала' },
      { type: 'new',     tag: 'site',     text: 'Блок управления администраторами — назначение и снятие прямо из панели' },
    ],
  },
  {
    version: 'V1.12.5',
    date: '17 апреля 2026',
    title: '🧹 Чистка интерфейса и точная статистика',
    items: [
      { type: 'fix',     tag: 'statistics', text: 'Часовой пояс UTC+3 (Москва) применяется корректно ко всем графикам и периодам' },
      { type: 'new',     tag: 'statistics', text: 'Брашер (синий ползунок) для выбора диапазона на графике статистики' },
      { type: 'improve', tag: 'site',       text: 'Удалён весь ИИ-блок (кнопки, модалки, запросы к Gemini) — интерфейс стал чище и быстрее' },
    ],
  },
  {
    version: 'V1.12.4',
    date: '16 апреля 2026',
    title: '📊 Панель: слайдер графика и баланс банка',
    items: [
      { type: 'new',     tag: 'statistics', text: 'Граф-слайдер на панели — выбирай любой временной диапазон для детального просмотра' },
      { type: 'improve', tag: 'statistics', text: 'Баланс банка берётся из живых данных, а не из заглушки' },
      { type: 'improve', tag: 'triggers',   text: 'Локализованные названия для RegEx-условий и типов действий' },
    ],
  },
  {
    version: 'V1.12.0',
    date: '15 апреля 2026',
    title: '🔤 Плейсхолдеры в сообщениях триггеров',
    items: [
      { type: 'new',     tag: 'triggers', text: 'Поддержка переменных %act_X% и %rpl_X% (25+ суффиксов) — подстановка данных о пользователе прямо в текст сообщения' },
    ],
  },
  {
    version: 'V1.11.11',
    date: '15 апреля 2026',
    title: '🔐 Авторизация через Telegram',
    items: [
      { type: 'new',     tag: 'site', text: 'Вход через Telegram Login Widget — JWT-токен, защита роутов, аватар и имя в шапке' },
      { type: 'new',     tag: 'site', text: 'auto_pin, warn_period, target — поля доступны прямо в карточках действий без лишних кликов' },
    ],
  },
  {
    version: 'V1.11.8',
    date: '21 апреля 2026',
    title: '📊 Точные данные в статистике и Excel',
    items: [
      { type: 'fix',     tag: 'statistics', text: 'Даты «За вчера» исправлены — период больше не захватывает сегодняшний день ни в чате, ни в Excel-экспорте' },
      { type: 'fix',     tag: 'statistics', text: 'Excel: разделение данных по администраторам работает корректно, лишние .00 убраны из ячеек' },
      { type: 'fix',     tag: 'statistics', text: 'Защита от пустых периодов — панель не падает, если за выбранный диапазон нет сообщений' },
    ],
  },
  {
    version: 'V1.11.7',
    date: '16 апреля 2026',
    title: '📈 Переработка источника данных статистики',
    items: [
      { type: 'improve', tag: 'statistics', text: 'Все данные статистики переведены на единый источник — цифры теперь совпадают во всех разделах панели' },
      { type: 'improve', tag: 'statistics', text: 'СДС (средняя длина сообщения) рассчитывается динамически — точнее, без накопленной погрешности' },
      { type: 'fix',     tag: 'statistics', text: 'Починена почасовая статистика: данные больше не задваиваются, ТОП-5% отображает корректные проценты' },
      { type: 'fix',     tag: 'statistics', text: 'Реакции: засчитывается только факт изменения, а не каждый клик — Индекс активности точный' },
    ],
  },
  {
    version: 'V1.11.3p',
    date: '22 апреля 2026',
    title: '✨ Анимация карточек и условие «Тип ответа»',
    items: [
      { type: 'new',     tag: 'triggers', text: 'Новое условие триггера — «Тип ответа»: 13 вариантов (реплай, первое сообщение, реакция и др.) с мультивыбором и инверсией' },
      { type: 'new',     tag: 'site',     text: 'Анимация вставки новой карточки действия — появляется с пружинящим коннектором при добавлении' },
      { type: 'improve', tag: 'triggers', text: 'Кнопка сброса условия (шестерёнка) работает через портал — больше не перекрывается другими карточками' },
    ],
  },
  {
    version: 'V1.11.3k',
    date: '16 апреля 2026',
    title: '⏱ send_delay и компактный стиль реплая',
    items: [
      { type: 'new',     tag: 'triggers', text: 'send_delay отрабатывает через JobQueue — бот не блокируется, остальные триггеры продолжают работать' },
      { type: 'improve', tag: 'triggers', text: 'Реплай на сообщение теперь в компактном стиле ChatKeeper — голубая полоса слева вместо полной цитаты' },
      { type: 'new',     tag: 'triggers', text: 'media_pos=\'reply\' — медиа и текст отправляются единым реплаем с голубой полосой' },
      { type: 'fix',     tag: 'triggers', text: '@username в действиях триггера резолвится в реального пользователя' },
    ],
  },
  {
    version: 'V1.11.3',
    date: '15 апреля 2026',
    title: '🔩 Полный ремонт системы триггеров',
    items: [
      { type: 'fix',     tag: 'triggers', text: 'Устранено 6 критических багов: conditionGroups не сохранялись, warn_count игнорировался, emoji-реакция не ставилась' },
      { type: 'fix',     tag: 'triggers', text: 'Карточка pin: pin_target + автоматическое открепление через заданное время работают корректно' },
      { type: 'fix',     tag: 'triggers', text: 'Фильтр where_fires=chat/pv реально применяется — триггер не срабатывает в неположенном месте' },
      { type: 'fix',     tag: 'triggers', text: 'HTML из WYSIWYG-редактора санитизируется под parse_mode=HTML Telegram' },
      { type: 'new',     tag: 'triggers', text: 'Медиа-пикер с выбором типа (фото / видео / GIF / стикер) и расположением (выше / ниже / реплаем)' },
      { type: 'new',     tag: 'site',     text: 'Стрелки сортировки карточек условий и действий — видимые, рабочие, с анимированным коннектором между ними' },
      { type: 'new',     tag: 'site',     text: 'Логотип Puls Chat на странице входа, в сайдбаре и favicon' },
    ],
  },
  {
    version: 'V1.11',
    date: '15 апреля 2026',
    title: '🚀 Запуск веб-панели управления',
    items: [
      { type: 'new',     tag: 'site',       text: 'Веб-сайт puls-chat.ru — теперь можно управлять ботом прямо из браузера' },
      { type: 'new',     tag: 'statistics', text: 'Статистика чата: графики активности, периоды (сегодня / неделя / месяц / год), экспорт в Excel' },
      { type: 'new',     tag: 'journal',    text: 'Журнал событий: все входы, нарушения триггеров, муты и баны в одном месте с фильтрами' },
      { type: 'new',     tag: 'triggers',   text: 'Управление триггерами: создание и редактирование через удобный 4-шаговый мастер' },
      { type: 'new',     tag: 'site',       text: 'Раздел Обновления — история изменений с тегами разделов и анимацией по клику' },
      { type: 'improve', tag: 'journal',    text: 'Ссылки в журнале кликабельны — переход прямо к сообщению в Telegram' },
      { type: 'improve', tag: 'journal',    text: 'Текст нарушения выделяется рамкой-цитатой для удобства чтения' },
      { type: 'improve', tag: 'journal',    text: 'Записи журнала хранят до 2000 символов вместо 200 — больше не обрезается' },
      { type: 'improve', tag: 'site',       text: 'Иконки в меню дёргаются при нажатии — приятная обратная связь' },
      { type: 'fix',     tag: 'site',       text: 'При обновлении страницы остаёшься на той же вкладке' },
      { type: 'fix',     tag: 'journal',    text: 'Фильтры журнала работают корректно для всех типов событий' },
    ],
  },
];

const LATEST_VERSION = UPDATES[0].version;

// ═══════════════════════════════════════════
//  LOGIN PAGE
// ═══════════════════════════════════════════
function LoginPage({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  useEffect(() => {
    window.onTelegramAuth = async (tgUser) => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tgUser),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Ошибка'); }
        const { token, is_admin, is_owner } = await res.json();
        localStorage.setItem('auth_token', token);
        onLogin({ ...tgUser, is_admin, is_owner });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    const container = document.getElementById('tg-login-btn');
    if (container && !container.querySelector('script')) {
      const s = document.createElement('script');
      s.src = 'https://telegram.org/js/telegram-widget.js?22';
      s.setAttribute('data-telegram-login', 'Pulse_On_bot');
      s.setAttribute('data-size', 'large');
      s.setAttribute('data-radius', '12');
      s.setAttribute('data-onauth', 'onTelegramAuth(user)');
      s.setAttribute('data-request-access', 'write');
      s.async = true;
      container.appendChild(s);
    }
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-blue-950 to-gray-900 px-4">
      {/* Фоновые blur-пятна */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-500 rounded-full opacity-10 blur-3xl"/>
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-500 rounded-full opacity-10 blur-3xl"/>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-blue-400 rounded-full opacity-5 blur-3xl"/>
      </div>

      <div className="relative w-full max-w-sm">
        {/* Карточка */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl">

          {/* Логотип */}
          <div className="flex flex-col items-center mb-8">
            <img src="/logo.jpg" alt="Puls Chat" className="w-24 h-24 rounded-3xl shadow-2xl shadow-blue-500/40 mb-4 object-cover"/>
            <h1 className="text-2xl font-black text-white tracking-tight">Puls Chat</h1>
            <p className="text-sm text-white/40 font-medium mt-1">Панель управления чатом</p>
          </div>

          {/* Разделитель */}
          <div className="h-px bg-white/10 mb-6"/>

          {/* Текст */}
          <div className="text-center mb-6">
            <p className="text-sm font-bold text-white/60">Войди через Telegram</p>
            <p className="text-xs text-white/30 mt-1">Доступ только для администраторов</p>
          </div>

          {/* Кнопка Telegram */}
          <div className="flex justify-center">
            {loading ? (
              <div className="flex items-center gap-2 text-white/50 text-sm font-bold">
                <Loader2 size={18} className="animate-spin"/> Входим...
              </div>
            ) : (
              <div id="tg-login-btn"/>
            )}
          </div>

          {/* Ошибка */}
          {error && (
            <div className="mt-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-2xl text-center">
              <p className="text-xs font-bold text-red-400">{error}</p>
            </div>
          )}

          {/* Подсказка */}
          <div className="mt-6 pt-5 border-t border-white/10 text-center">
            <p className="text-[10px] text-white/20 leading-relaxed">
              Используем официальный виджет Telegram.<br/>Пароли и данные нам не передаются.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

class EconomyErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(e) { return { error: e }; }
  render() {
    if (this.state.error) {
      return (
        <div className="bg-white rounded-3xl border border-red-100 p-12 text-center space-y-3">
          <div className="text-4xl">⚠️</div>
          <div className="font-black text-gray-900">Ошибка загрузки раздела Экономика</div>
          <div className="text-xs text-red-500 font-mono bg-red-50 rounded-xl p-3 text-left break-all">
            {this.state.error?.message || String(this.state.error)}
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            className="px-6 py-2 bg-blue-600 text-white rounded-xl font-black text-sm">
            Попробовать снова
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  // ── АВТОРИЗАЦИЯ ──
  const [authUser, setAuthUser]       = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) { setAuthLoading(false); return; }
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(u => { if (u) setAuthUser(u); else localStorage.removeItem('auth_token'); })
      .catch(() => localStorage.removeItem('auth_token'))
      .finally(() => setAuthLoading(false));
  }, []);

  const isAdmin = !!(authUser && (authUser.is_admin || authUser.is_owner));

  // ── ПРОФИЛЬ ──
  const [profileData, setProfileData]             = useState(null);
  const [profileLoading, setProfileLoading]       = useState(false);
  const [showConnectChat, setShowConnectChat]     = useState(false);
  const [accessesOpen, setAccessesOpen]           = useState(false);
  const fetchProfile = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    setProfileLoading(true);
    fetch('/api/admin/profile/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setProfileData(d); })
      .catch(() => {})
      .finally(() => setProfileLoading(false));
  }, []);

  // Автозагрузка профиля сразу после логина — чтобы permissions были доступны во всех вкладках
  useEffect(() => { if (authUser && !profileData) fetchProfile(); }, [authUser, profileData, fetchProfile]);

  // ── userCan(perm) — главный хелпер проверки прав на фронте ──
  const userPermissions = useMemo(
    () => new Set(profileData?.permissions || []),
    [profileData]
  );
  const userCan = useCallback((perm) => {
    if (authUser?.is_owner || profileData?.role_raw === 'developer') return true;
    return userPermissions.has(perm);
  }, [authUser, userPermissions, profileData]);

  // ── ПРАВА ДОСТУПА ──
  const [permCatalog, setPermCatalog]             = useState(null);
  const [permRoles, setPermRoles]                 = useState(null);
  const [permLoading, setPermLoading]             = useState(false);
  const [permActiveRole, setPermActiveRole]       = useState('deputy');
  const [permLocal, setPermLocal]                 = useState({ deputy: new Set(), admin: new Set() });
  const [permDirty, setPermDirty]                 = useState(false);
  const [permSelectedRes, setPermSelectedRes]     = useState(null);
  const [permSaving, setPermSaving]               = useState(false);
  const [permToast, setPermToast]                 = useState(null);

  const fetchPermissions = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    setPermLoading(true);
    Promise.all([
      fetch('/api/admin/permissions/catalog', { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null),
      fetch('/api/admin/permissions/roles',   { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null),
    ])
      .then(([catalog, roles]) => {
        if (catalog) setPermCatalog(catalog);
        if (roles) {
          setPermLocal({
            deputy: new Set(roles.deputy || []),
            admin:  new Set(roles.admin  || []),
          });
          setPermRoles(roles);
        }
        setPermDirty(false);
        if (catalog?.resources?.length) setPermSelectedRes(catalog.resources[0].key);
      })
      .catch(() => {})
      .finally(() => setPermLoading(false));
  }, []);

  const [activeTab, setActiveTab] = useState(() => window.location.hash.slice(1) || 'statistics');
  const navigateTo = (id) => {
    // Если идёт редактирование триггера — показываем подтверждение
    if (editingTrigger) {
      setLeaveTarget(id);
      setShowLeaveConfirm(true);
      return;
    }
    setActiveTab(id);
    window.location.hash = id;
    if (id === 'updates') {
      localStorage.setItem('lastSeenUpdate', LATEST_VERSION);
      setHasNewUpdate(false);
    }
  };
  const _doNavigate = (id) => {
    setActiveTab(id);
    window.location.hash = id;
    if (id === 'updates') {
      localStorage.setItem('lastSeenUpdate', LATEST_VERSION);
      setHasNewUpdate(false);
    }
  };
  const [hasNewUpdate, setHasNewUpdate] = useState(
    () => localStorage.getItem('lastSeenUpdate') !== LATEST_VERSION
  );
  const [jigglingTag, setJigglingTag] = useState(null);
  const triggerJiggle = (key) => { setJigglingTag(key); };
  const [jigglingNav, setJigglingNav] = useState(null);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showDetailedIndices, setShowDetailedIndices] = useState(false);
  const [activeIndexTooltip, setActiveIndexTooltip] = useState(null);
  const [showHealthTooltip, setShowHealthTooltip] = useState(false);

  // ================= СОСТОЯНИЯ: ТРИГГЕРЫ =================
  // editingTrigger !== null → показываем страницу редактора вместо списка
  const [editingTrigger, setEditingTrigger] = useState(null);
  const [triggers, setTriggers] = useState([]);
  const [triggersLoading, setTriggersLoading] = useState(false);
  const [showMediaPicker, setShowMediaPicker] = useState(false);
  const [showCondPickerModal, setShowCondPickerModal] = useState(false);
  const [condPickerGroupIdx, setCondPickerGroupIdx] = useState(0);
  const [condPickerSearch, setCondPickerSearch] = useState('');
  const [condPickerTab, setCondPickerTab] = useState('message');
  const [condTooltip, setCondTooltip] = useState(null);
  const [showActPickerModal, setShowActPickerModal] = useState(false);
  const [actPickerGroupIdx, setActPickerGroupIdx] = useState(0);
  const [actPickerSearch, setActPickerSearch] = useState('');
  const [actGroupSettingsIdx, setActGroupSettingsIdx] = useState(null);
  const [newActionIds, setNewActionIds] = useState(() => new Set());
  const [condChipInputs, setCondChipInputs] = useState({});
  const [condSettingsModal, setCondSettingsModal] = useState(null); // {gIdx, cIdx}
  const [condGearModal,     setCondGearModal]     = useState(null); // {gIdx, cIdx}
  const [condOpenDropdown, setCondOpenDropdown] = useState(null);   // 'type_g_c' | 'mod_g_c'
  const [actOpenDropdown, setActOpenDropdown] = useState(null);     // 'reply_g_a'
  const [showKeyboardModal, setShowKeyboardModal] = useState(false);
  const [kbModalTarget, setKbModalTarget] = useState(null);         // {gIdx, aIdx}
  const [kbButtonType, setKbButtonType] = useState(null);           // null|'link'|'trigger'|'share'|'reaction'
  const [kbNewButton, setKbNewButton] = useState({});
  const [kbReactionEmoji, setKbReactionEmoji] = useState('🌐');
  const [fmtState, setFmtState] = useState({bold:false,italic:false,underline:false,strikeThrough:false});
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [leaveTarget, setLeaveTarget] = useState(null);
  const [phDropdown, setPhDropdown] = useState(null); // ключ 'gIdx_aIdx_varIdx' | null
  const [settingHint, setSettingHint] = useState(null);      // 'key' | null
  const [settingHintPos, setSettingHintPos] = useState({x:0,y:0});
  const [customPlaceholders, setCustomPlaceholders] = useState([]);
  const [showEditorHelp, setShowEditorHelp] = useState(false);
  const [showTriggerEditMenu, setShowTriggerEditMenu] = useState(false);
  const [triggerSearch, setTriggerSearch] = useState('');
  const [showTriggerMenu, setShowTriggerMenu] = useState(false);
  const [togglingTrigger, setTogglingTrigger] = useState(null);
  const [copyingTrigger, setCopyingTrigger] = useState(null);
  const [dragId, setDragId] = useState(null);
  const [actionSettingsModal, setActionSettingsModal] = useState(null); // {gIdx, aIdx}
  const [actionSettingsPct, setActionSettingsPct] = useState(100);      // temp % в модале
  const [topics, setTopics] = useState([]);
  const [topicsLoaded, setTopicsLoaded] = useState(false);
  const [mediaUploading, setMediaUploading] = useState(false); // {gIdx,aIdx,varIdx} | false
  const [showPreview, setShowPreview] = useState(null); // {text, mediaUrl, mediaType, keyboard} | null

  useEffect(() => {
    if (document.getElementById('connector-insert-kf')) return;
    const style = document.createElement('style');
    style.id = 'connector-insert-kf';
    style.innerHTML = `
@keyframes connectorLineGrow {
  0%   { transform: scaleY(0); }
  100% { transform: scaleY(1); }
}
@keyframes connectorDotPop {
  0%   { transform: scale(0); opacity: 0; }
  60%  { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
.connector-insert .connector-line {
  transform-origin: center;
  animation: connectorLineGrow 260ms cubic-bezier(.4,0,.2,1) 120ms both;
}
.connector-insert .connector-dot-top {
  animation: connectorDotPop 220ms cubic-bezier(.34,1.56,.64,1) 380ms both;
}
.connector-insert .connector-dot-bot {
  animation: connectorDotPop 220ms cubic-bezier(.34,1.56,.64,1) 380ms both;
}
`;
    document.head.appendChild(style);
  }, []);

  const fetchTriggers = () => {
    setTriggersLoading(true);
    fetch('/api/triggers')
      .then(r => r.json())
      .then(data => { setTriggers(Array.isArray(data) ? data : []); setTriggersLoading(false); })
      .catch(() => setTriggersLoading(false));
  };

  const toggleTrigger = async (id) => {
    setTogglingTrigger(id);
    try {
      const r = await fetch(`/api/triggers/${id}/toggle`, { method: 'PATCH' });
      const data = await r.json();
      setTriggers(prev => prev.map(t => t.id === id ? { ...t, is_enabled: data.is_enabled } : t));
    } catch {}
    setTogglingTrigger(null);
  };

  const copyTrigger = async (id) => {
    setCopyingTrigger(id);
    try {
      await fetch(`/api/triggers/${id}/copy`, { method: 'POST' });
      fetchTriggers();
    } catch {}
    setCopyingTrigger(null);
  };

  // Drag & drop для активных триггеров
  const handleDragStart = (id) => setDragId(id);
  const handleDrop = (targetId) => {
    if (!dragId || dragId === targetId) return;
    setTriggers(prev => {
      const active = prev.filter(t => t.is_enabled);
      const inactive = prev.filter(t => !t.is_enabled);
      const fromIdx = active.findIndex(t => t.id === dragId);
      const toIdx   = active.findIndex(t => t.id === targetId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const reordered = [...active];
      const [moved] = reordered.splice(fromIdx, 1);
      reordered.splice(toIdx, 0, moved);
      return [...reordered, ...inactive];
    });
    setDragId(null);
  };

  useEffect(() => { fetchTriggers(); }, []);
  useEffect(() => { if (activeTab === 'journal') fetchJournal(); }, [activeTab]);

  // ================= СОСТОЯНИЯ: ШИППЕР =================
  const [shipperSettings, setShipperSettings] = useState({
    enabled: true,
    minHours: 2,
    maxHours: 5,
    mode: 'active_48',
    categories: [
      { id: 'hot18', name: '🔥 Горячие / 18+', count: 42, active: true },
      { id: 'funny', name: '😂 Смешные / Подколы', count: 28, active: true },
      { id: 'romantic', name: '💘 Милые / Романтика', count: 15, active: false }
    ]
  });

  // ================= СОСТОЯНИЯ: СИСТЕМА =================
  const [systemStats, setSystemStats] = useState({
    pulseRate: 1.42,
    bankBalance: 12500450.20,
    difficultyK: 5.0,
  });

  // ── Стафф (администраторы) ──
  const [staffList, setStaffList] = useState([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [newAdminId, setNewAdminId] = useState('');
  const [staffError, setStaffError] = useState('');
  const [staffAdding, setStaffAdding] = useState(false);
  const [staffRemoving, setStaffRemoving] = useState(null);

  const fetchStaff = () => {
    setStaffLoading(true);
    fetch('/api/staff')
      .then(r => r.json())
      .then(data => { setStaffList(Array.isArray(data) ? data : []); setStaffLoading(false); })
      .catch(() => setStaffLoading(false));
  };

  const addAdmin = async () => {
    const uid = newAdminId.trim().replace('@', '');
    if (!uid) return;
    setStaffAdding(true); setStaffError('');
    try {
      const r = await fetch('/api/staff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid }),
      });
      const data = await r.json();
      if (!r.ok) { setStaffError(data.detail || 'Ошибка'); }
      else { setNewAdminId(''); fetchStaff(); }
    } catch { setStaffError('Сетевая ошибка'); }
    setStaffAdding(false);
  };

  const removeAdmin = async (userId) => {
    setStaffRemoving(userId);
    try {
      const r = await fetch(`/api/staff/${userId}`, { method: 'DELETE' });
      const data = await r.json();
      if (!r.ok) { setStaffError(data.detail || 'Ошибка'); }
      else { fetchStaff(); }
    } catch { setStaffError('Сетевая ошибка'); }
    setStaffRemoving(null);
  };

  useEffect(() => { if (activeTab === 'system') fetchStaff(); }, [activeTab]);
  useEffect(() => { if (activeTab === 'profile') fetchProfile(); }, [activeTab, fetchProfile]);
  useEffect(() => { if (activeTab === 'permissions' && !permCatalog) fetchPermissions(); }, [activeTab, permCatalog, fetchPermissions]);

  // ================= СОСТОЯНИЯ: ЖУРНАЛ =================
  const logTags = [
    { id: 'all',          label: 'Все' },
    { id: 'trigger',      label: '#Триггер' },
    { id: 'mute',         label: '#Мут' },
    { id: 'unmute',       label: '#Размут' },
    { id: 'ban',          label: '#Бан' },
    { id: 'unban',        label: '#Разбан' },
    { id: 'kick',         label: '#Исключен' },
    { id: 'warn',         label: '#Варн' },
    { id: 'join',         label: '#Вход' },
    { id: 'leave',        label: '#Выход' },
    { id: 'blacklist',    label: '#Блокировка' },
    { id: 'admin',        label: '#Админ' },
    { id: 'survey',       label: '#Опрос' },
    { id: 'profile',      label: '#Профиль' },
    { id: 'activity',     label: '#Активность' },
    { id: 'photo',        label: '#Фото' },
  ];
  const [logFilter, setLogFilter] = useState('all');
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [expandedLogs, setExpandedLogs] = useState(new Set());
  const toggleLogExpand = (id) => setExpandedLogs(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const fetchJournal = () => {
    setLogsLoading(true);
    fetch('/api/journal')
      .then(r => r.json())
      .then(data => { setLogs(Array.isArray(data) ? data : []); setLogsLoading(false); })
      .catch(() => setLogsLoading(false));
  };

  const journalAction = async (userId, action) => {
    try {
      const r = await fetch('/api/journal/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        body: JSON.stringify({ user_id: userId, action }),
      });
      const d = await r.json();
      if (d.ok) { fetchJournal(); }
      else { alert(d.error || 'Ошибка при выполнении действия'); }
    } catch (e) { alert('Ошибка сети'); }
  };
  
  // ================= СОСТОЯНИЯ: UI-НАСТРОЙКИ (цитаты) =================
  const [quoteCfg, setQuoteCfg] = useState({
    bg: '#fff7ed', stripeMode: 'solid',
    stripe1: '#fdba74', stripe2: '#f87171',
  });
  const [quoteSaving, setQuoteSaving] = useState(false);
  useEffect(() => {
    fetch('/api/ui_settings')
      .then(r => r.json())
      .then(d => setQuoteCfg({
        bg:         d.journal_quote_bg         ?? '#fff7ed',
        stripeMode: d.journal_quote_stripe_mode ?? 'solid',
        stripe1:    d.journal_quote_stripe_color1 ?? '#fdba74',
        stripe2:    d.journal_quote_stripe_color2 ?? '#f87171',
      }))
      .catch(() => {});
  }, []);
  const [quoteSaveMsg, setQuoteSaveMsg] = React.useState('');
  const saveQuoteCfg = async () => {
    setQuoteSaving(true);
    setQuoteSaveMsg('');
    try {
      const r = await fetch('/api/ui_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
        body: JSON.stringify({
          journal_quote_bg:            quoteCfg.bg,
          journal_quote_stripe_mode:   quoteCfg.stripeMode,
          journal_quote_stripe_color1: quoteCfg.stripe1,
          journal_quote_stripe_color2: quoteCfg.stripe2,
        }),
      });
      const d = await r.json();
      setQuoteSaveMsg(d.ok ? '✓ Сохранено' : `Ошибка: ${(d.errors||[]).join(', ')}`);
    } catch (e) { setQuoteSaveMsg('Ошибка сети'); }
    setQuoteSaving(false);
    setTimeout(() => setQuoteSaveMsg(''), 3000);
  };

  // ================= СОСТОЯНИЯ: ФУНКЦИИ БОТА =================
  const [botFeatures, setBotFeatures] = useState([]);
  const [featuresLoading, setFeaturesLoading] = useState(false);
  const [togglingFeature, setTogglingFeature] = useState(null);

  const fetchFeatures = () => {
    setFeaturesLoading(true);
    fetch('/api/features')
      .then(r => r.json())
      .then(data => { setBotFeatures(Array.isArray(data) ? data : []); setFeaturesLoading(false); })
      .catch(() => setFeaturesLoading(false));
  };

  const toggleFeature = async (featureId) => {
    setTogglingFeature(featureId);
    try {
      const r = await fetch(`/api/features/${featureId}/toggle`, { method: 'POST' });
      const data = await r.json();
      setBotFeatures(prev => prev.map(f => f.id === featureId ? { ...f, enabled: data.enabled } : f));
    } catch { }
    setTogglingFeature(null);
  };

  useEffect(() => { fetchFeatures(); }, []);

  // ================= СОСТОЯНИЯ: СТАТИСТИКА =================
  const PERIODS = [
    { id: 'today',     label: 'Сегодня' },
    { id: 'yesterday', label: 'Вчера'   },
    { id: 'week',      label: 'Неделя'  },
    { id: 'month',     label: 'Месяц'   },
    { id: 'year',      label: 'Год'     },
  ];
  const [statsPeriod, setStatsPeriod] = useState('today');
  const [liveStats, setLiveStats]     = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const fetchStats = useCallback((period) => {
    setStatsLoading(true);
    fetch(`/api/stats?period=${period}`)
      .then(r => r.json())
      .then(data => { setLiveStats(data); setStatsLoading(false); })
      .catch(() => setStatsLoading(false));
  }, []);

  useEffect(() => { fetchStats('today'); }, []);

  // Предупреждение при обновлении/закрытии страницы во время редактирования триггера
  useEffect(() => {
    const h = (e) => {
      if (editingTrigger) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [editingTrigger]);

  // phDropdown закрывается через клик на оверлей fixed-модала (см. JSX ниже)

  // Отслеживаем активное форматирование для подсветки кнопок тулбара
  useEffect(() => {
    const h = () => {
      try {
        setFmtState({
          bold:         document.queryCommandState('bold'),
          italic:       document.queryCommandState('italic'),
          underline:    document.queryCommandState('underline'),
          strikeThrough:document.queryCommandState('strikeThrough'),
        });
      } catch(e){}
    };
    document.addEventListener('selectionchange', h);
    return () => document.removeEventListener('selectionchange', h);
  }, []);

  const handlePeriodChange = (period) => {
    setStatsPeriod(period);
    fetchStats(period);
    setShowDetailedIndices(false);
    setActiveIndexTooltip(null);
    setShowHealthTooltip(false);
  };

  const exportExcel = () => {
    window.open(`/api/stats/export?period=${statsPeriod}`, '_blank');
  };

  // ================= ФУНКЦИИ =================
  const openTriggerModal = (t = null) => {
    if (t) {
      // ── Условия: приоритет исходных conditionGroups из БД, иначе fallback на keywords ──
      let conditionGroups;
      if (Array.isArray(t.conditionGroups) && t.conditionGroups.length > 0) {
        conditionGroups = t.conditionGroups;
      } else {
        const chips = t.keywords ? t.keywords.split(',').map(s => s.trim()).filter(Boolean) : [];
        const conditions = chips.length > 0
          ? [{ id: 1, signal: 'message', type: 'keyword', condition: t.condition || 'contains', chips, keyword: chips[0] || '' }]
          : [];
        conditionGroups = [{ id: 1, conditions }];
      }

      // ── Действия: восстанавливаем из actions[] + action_configs{} ──
      const actionList = (t.actions || []).map((type, i) => ({
        id: i + 1,
        type,
        ...(t.action_configs || {})[type] || {},
      }));

      setEditingTrigger({
        ...t,
        conditionGroups,
        actionGroups: [{ id: 1, probability: t.probability ?? 100, actions: actionList }],
      });
    } else {
      setEditingTrigger({
        id: null, name: '', probability: 100,
        where_fires: 'all', initiator: 'all',
        fire_limit: 0, auto_pin: 0,
        conditionGroups: [{ id: 1, conditions: [] }],
        actionGroups: [{ id: 1, probability: 100, actions: [] }]
      });
    }
    setShowCondPickerModal(false);
    setShowActPickerModal(false);
    setShowTriggerEditMenu(false);
    setCondTooltip(null);
    setActGroupSettingsIdx(null);
    setCondSettingsModal(null);
    setCondOpenDropdown(null);
    setCondChipInput('');
    setShowMediaPicker(false);
    _doNavigate('triggers');  // без confirm — это открытие редактора
  };

  const saveTrigger = () => {
    // ── Условия: для обратной совместимости плющим ПЕРВУЮ keyword-карточку ──
    // (полная структура с группами/И-ИЛИ летит в condition_groups)
    const firstGroup = (editingTrigger.conditionGroups || [])[0] || {};
    const conditions = firstGroup.conditions || [];
    const firstKeywordCond = conditions.find(c => c.type === 'keyword') || conditions[0] || {};
    const keywords = (firstKeywordCond.chips && firstKeywordCond.chips.length
      ? firstKeywordCond.chips
      : (firstKeywordCond.keyword ? [firstKeywordCond.keyword] : [])
    ).join(',');
    const condition = firstKeywordCond.condition || 'contains';

    // ── Действия: собираем из всех групп ──
    const allActions = (editingTrigger.actionGroups || []).flatMap(g => g.actions || []);
    const actionTypes = allActions.map(a => a.type);
    const actionConfigs = {};
    allActions.forEach(a => {
      if (!a.type) return;
      const {id, type, ...cfg} = a;
      actionConfigs[a.type] = cfg;
    });

    const body = {
      name:                 editingTrigger.name,
      condition,
      keywords,
      probability:          editingTrigger.probability ?? 100,
      where_fires:          editingTrigger.where_fires  || 'all',
      initiator:            editingTrigger.initiator    || 'all',
      target:               editingTrigger.target       || 'nobody',
      target_user:          editingTrigger.target_user  || '',
      actions:              actionTypes,
      action_configs:       actionConfigs,
      condition_groups:     editingTrigger.conditionGroups || [],
      bot_msg_delete:       editingTrigger.bot_msg_delete       || 'no',
      bot_msg_delete_after: editingTrigger.bot_msg_delete_after || 60,
      fire_limit:           editingTrigger.fire_limit   || 0,
      auto_pin:             editingTrigger.auto_pin     || 0,
      is_enabled:           editingTrigger.is_enabled   ?? true,
    };
    const isEdit = !!editingTrigger.id;
    const url    = isEdit ? `/api/triggers/${editingTrigger.id}` : '/api/triggers';
    const method = isEdit ? 'PUT' : 'POST';
    fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(r => r.json())
      .then(() => { fetchTriggers(); setEditingTrigger(null); })
      .catch(() => setEditingTrigger(null));
  };

  const deleteTrigger = (id) => {
    fetch(`/api/triggers/${id}`, { method: 'DELETE' })
      .then(() => fetchTriggers());
  };

  const ChartTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-gray-900 text-white px-4 py-3 rounded-2xl shadow-2xl border border-gray-700">
        <p className="text-[10px] font-black text-gray-400 uppercase mb-1">{label}</p>
        <p className="text-2xl font-black leading-none">{(payload[0].value || 0).toLocaleString()}</p>
        <p className="text-[9px] text-blue-400 font-bold mt-1">сообщений</p>
      </div>
    );
  };

  const navigation = [
    { id: 'updates',     name: 'Обновления',    icon: Megaphone,   group: 'top' },
    { id: 'statistics',  name: 'Статистика',    icon: PieChart,    group: 'main' },
    { id: 'journal',     name: 'Журнал',        icon: ScrollText,  group: 'main' },
    { id: 'triggers',    name: 'Триггеры',      icon: ShieldAlert,    group: 'modules' },
    { id: 'shipper',     name: 'Шиппер',        icon: HeartHandshake, group: 'modules' },
    { id: 'economy',     name: 'Экономика',     icon: Coins,          group: 'modules' },
    { id: 'system',      name: 'Система',       icon: Settings,    group: 'main' },
    { id: 'broadcast',   name: 'Рассылка',      icon: Send,        group: 'features' },
    { id: 'permissions', name: 'Права',         icon: ShieldCheck, group: 'features', ownerOnly: true },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'statistics':
        return (
          <div className="space-y-4 pb-24">

            {/* ── Period switcher ── */}
            <div className="flex space-x-2 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-hide">
              {PERIODS.map(p => (
                <button key={p.id} onClick={() => handlePeriodChange(p.id)}
                  className={`flex-shrink-0 px-5 py-2.5 rounded-2xl font-black text-[11px] uppercase tracking-wide transition-all duration-300 ${
                    statsPeriod === p.id
                      ? 'bg-gray-900 text-white shadow-lg scale-105'
                      : 'bg-white text-gray-400 border border-gray-100'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>

            {/* ── Hero: Health index ── */}
            {(() => {
              const INDEX_META = {
                oksp:   { label: 'Общая активность',      desc: 'Среднее кол-во сообщений на одного активного участника × 10. Показывает насколько активно общается каждый.' },
                sdsp:   { label: 'Диалоговость',          desc: 'Доля сообщений с ответами (reply) от общего числа сообщений. Высокое значение = живое общение, не монологи.' },
                cho:    { label: 'Эмоциональность',       desc: 'Доля сообщений, получивших реакции. Чем больше — тем сильнее люди реагируют на контент.' },
                media:  { label: 'Медиаактивность',       desc: 'Доля медиафайлов (фото, видео, GIF) от всех сообщений. Отражает разнообразие контента.' },
                korp:   { label: 'Вовлечённость',         desc: 'Суммарный отклик (ответы + реакции) к числу сообщений. Главный показатель живости чата.' },
                kopyup: { label: 'Прирост участников',    desc: '(Вступили − Вышли) / Всего участников. Положительное значение = чат растёт.' },
              };
              const idxData = liveStats?.indices || {};
              return (
                <div className={`bg-gradient-to-br from-indigo-700 via-blue-700 to-blue-500 rounded-[3rem] p-8 text-white shadow-xl relative overflow-hidden border border-white/10 transition-all duration-500 ${statsLoading ? 'opacity-60' : 'opacity-100'}`}>
                  <div className="absolute -top-10 -right-10 opacity-10 scale-150 rotate-12"><Activity size={200} /></div>
                  <div className="relative z-10">
                    {/* Строка 1: бейдж + период */}
                    <div className="flex items-center justify-between mb-5">
                      <div className="flex items-center space-x-2 bg-white/20 px-4 py-1.5 rounded-full backdrop-blur-md">
                        <Zap size={14} className="text-yellow-300 fill-yellow-300" />
                        <span className="text-[10px] font-black uppercase tracking-widest">Индекс здоровья</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-black bg-white/10 px-3 py-1 rounded-full uppercase">
                          {liveStats?.periodLabel || 'Сегодня'}
                        </span>
                        {/* ℹ кнопка — вверху справа */}
                        <div className="relative">
                          <button
                            onClick={() => setShowHealthTooltip(v => !v)}
                            className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-xs font-black hover:bg-white/30 transition-all"
                          >ℹ</button>
                          {showHealthTooltip && (
                            <div className="absolute top-9 right-0 w-64 bg-gray-900 text-white text-xs rounded-2xl p-4 z-50 shadow-2xl">
                              <p className="font-black mb-2">Формула индекса здоровья:</p>
                              <p className="opacity-80 leading-relaxed">Общая акт.×25% + Диалоговость×15% + Эмоц.×15% + Медиа×10% + Вовлечённость×20% + Прирост×15%</p>
                              <p className="opacity-60 mt-2 text-[10px]">Каждый субиндекс — реальные данные за выбранный период.</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* Строка 2: большое число */}
                    <div className="text-8xl font-black tracking-tighter leading-none mb-6">
                      {statsLoading ? <Loader2 size={48} className="animate-spin opacity-50" /> : (liveStats?.healthIndex ?? 0)}
                      {!statsLoading && <span className="text-2xl ml-1 opacity-50">%</span>}
                    </div>
                    {/* Кнопка раскрытия субиндексов */}
                    <button onClick={() => setShowDetailedIndices(!showDetailedIndices)}
                      className="w-full flex justify-between items-center text-[10px] font-black uppercase tracking-widest border-t border-white/10 pt-4">
                      <span>Детальные показатели</span>
                      {showDetailedIndices ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    {showDetailedIndices && (
                      <div className="space-y-1 pt-3 animate-in slide-in-from-top-2 duration-300">
                        {Object.entries(INDEX_META).map(([k, meta]) => (
                          <div key={k}>
                            <div className="flex items-center justify-between py-2 px-3 rounded-xl">
                              <span className="text-xs font-bold opacity-75">{meta.label}</span>
                              <div className="flex items-center space-x-2 flex-shrink-0">
                                <span className="text-sm font-black">{idxData[k] !== undefined ? idxData[k] : '—'}</span>
                                <button
                                  onClick={() => setActiveIndexTooltip(activeIndexTooltip === k ? null : k)}
                                  className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-[10px] font-black hover:bg-white/30 transition-all flex-shrink-0"
                                >ℹ</button>
                              </div>
                            </div>
                            {activeIndexTooltip === k && (
                              <div className="mx-3 mb-2 bg-white/15 backdrop-blur-sm text-white text-[10px] rounded-xl p-3 leading-relaxed border border-white/10 animate-in slide-in-from-top-1 duration-200">
                                {meta.desc}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* ── Recharts AreaChart ── */}
            <div className={`bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest flex items-center">
                  <Activity size={14} className="mr-2 text-blue-500" /> Пульс активности
                </h3>
                <span className="text-[10px] font-black text-blue-500 bg-blue-50 px-3 py-1 rounded-full">
                  {(liveStats?.history || []).reduce((s, d) => s + d.val, 0).toLocaleString()} сообщ.
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={liveStats?.history || []} margin={{ top: 5, right: 5, left: -30, bottom: 0 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fontWeight: 900, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: '#d1d5db' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#e2e8f0', strokeWidth: 2 }} />
                  <Area type="monotone" dataKey="val" stroke="#3b82f6" strokeWidth={3}
                    fill="url(#areaGrad)" dot={false} activeDot={{ r: 6, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={600} animationEasing="ease-out" />
                  <Brush
                    dataKey="day"
                    height={38}
                    stroke="#3b82f6"
                    fill="#dbeafe"
                    travellerWidth={14}
                    tickFormatter={() => ''}
                    startIndex={Math.max(0, (liveStats?.history?.length || 0) - 10)}
                    traveller={({ x, y, width, height: h }) => (
                      <g>
                        <rect x={x} y={y + 4} width={width} height={h - 8}
                          rx={6} fill="#3b82f6" stroke="#fff" strokeWidth={2} />
                        <line x1={x + width/2} y1={y + h/2 - 5} x2={x + width/2} y2={y + h/2 + 5}
                          stroke="#fff" strokeWidth={1.5} strokeLinecap="round" />
                      </g>
                    )}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* ── Метрики 2×2 ── */}
            <div className={`grid grid-cols-2 gap-4 transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              {[
                { label: 'Сообщений',      val: (liveStats?.messages    ?? 0).toLocaleString(), color: 'text-blue-500',   bg: 'bg-blue-50',   icon: MessageSquareX },
                { label: 'Активных',       val: (liveStats?.activeUsers ?? 0).toString(),        color: 'text-indigo-500', bg: 'bg-indigo-50', icon: Users          },
                { label: 'Вступили',       val: `+${liveStats?.joined   ?? 0}`,                  color: 'text-green-500',  bg: 'bg-green-50',  icon: TrendingUp     },
                { label: 'Вышли',          val: `-${liveStats?.left     ?? 0}`,                  color: 'text-red-500',    bg: 'bg-red-50',    icon: TrendingDown   },
              ].map((m, i) => (
                <div key={i} className="bg-white p-6 rounded-[2rem] border border-gray-100 shadow-sm active:scale-95 transition-all duration-200"
                  style={{ animationDelay: `${i * 60}ms` }}>
                  <div className={`w-9 h-9 ${m.bg} rounded-2xl flex items-center justify-center mb-3`}>
                    <m.icon size={18} className={m.color} />
                  </div>
                  <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block mb-1">{m.label}</span>
                  <span className="text-3xl font-black text-gray-900 leading-none">{m.val}</span>
                </div>
              ))}
            </div>

            {/* ── Банк ── */}
            <div className={`bg-gradient-to-r from-indigo-600 to-blue-600 p-6 rounded-[2rem] text-white shadow-xl transition-all duration-500 ${statsLoading ? 'opacity-40' : 'opacity-100'}`}>
              <span className="text-[10px] font-black opacity-60 uppercase tracking-widest block mb-1 flex items-center gap-1">
                <Wallet size={10} /> Баланс банка
              </span>
              <span className="text-3xl font-black tracking-tight">
                {(liveStats?.bankBalance ?? 0).toLocaleString()} 💳
              </span>
            </div>

            {/* ── Кнопка Excel ── */}
            <button onClick={exportExcel}
              className="w-full flex items-center justify-center space-x-3 bg-white border-2 border-gray-100 text-gray-700 p-5 rounded-[2rem] font-black active:scale-95 transition-all duration-200 hover:border-green-200 hover:text-green-700 hover:bg-green-50">
              <FileSpreadsheet size={22} className="text-green-600" />
              <span>Экспорт в Excel — {PERIODS.find(p=>p.id===statsPeriod)?.label}</span>
              <Download size={18} className="text-gray-400" />
            </button>
          </div>
        );

      case 'journal':
        return (
          <div className="space-y-4 pb-24">
            <div className="flex space-x-2 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
              {logTags.map(tag => (
                <button key={tag.id} onClick={() => setLogFilter(tag.id)} className={`flex-shrink-0 px-6 py-3 rounded-2xl font-black text-[10px] uppercase border transition-all ${logFilter === tag.id ? 'bg-gray-900 text-white border-gray-900 scale-105 shadow-md' : 'bg-white text-gray-400 border-gray-100'}`}>{tag.label}</button>
              ))}
            </div>
            {logsLoading && (
              <div className="text-center py-8 text-gray-400 font-black text-sm">
                <Loader2 size={24} className="animate-spin mx-auto mb-2" /> Загрузка журнала...
              </div>
            )}
            {!logsLoading && logs.length === 0 && (
              <div className="text-center py-12 text-gray-300 font-black text-sm uppercase tracking-widest">
                Событий пока нет
              </div>
            )}
            {logs.filter(l => logFilter === 'all' || l.type === logFilter).map(log => {
              const TAG_STYLE = {
                trigger:      'bg-orange-50 text-orange-600 border border-orange-200',
                mute:         'bg-yellow-50 text-yellow-700 border border-yellow-200',
                unmute:       'bg-lime-50 text-lime-700 border border-lime-200',
                ban:          'bg-red-50 text-red-600 border border-red-200',
                unban:        'bg-blue-50 text-blue-600 border border-blue-200',
                kick:         'bg-rose-50 text-rose-600 border border-rose-200',
                warn:         'bg-amber-50 text-amber-600 border border-amber-200',
                join:         'bg-green-50 text-green-600 border border-green-200',
                leave:        'bg-gray-100 text-gray-500 border border-gray-200',
                blacklist:    'bg-slate-100 text-slate-600 border border-slate-300',
                admin:        'bg-indigo-50 text-indigo-600 border border-indigo-200',
                survey:       'bg-purple-50 text-purple-600 border border-purple-200',
                profile:      'bg-teal-50 text-teal-600 border border-teal-200',
                activity:     'bg-cyan-50 text-cyan-600 border border-cyan-200',
                photo:        'bg-pink-50 text-pink-600 border border-pink-200',
              };
              const tagStyle = TAG_STYLE[log.type] || 'bg-blue-50 text-blue-600 border border-blue-200';
              const isExpanded = expandedLogs.has(log.id);
              const hasActions = ['join','ban','mute','blacklist'].includes(log.type);
              return (
                <div key={log.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm animate-in slide-in-from-bottom-2 overflow-hidden">

                  {/* ── Шапка: аватар + имя + тег + стрелка ── */}
                  <div
                    className="flex items-center gap-2 px-3 pt-2.5 pb-2 cursor-pointer select-none"
                    onClick={() => hasActions && toggleLogExpand(log.id)}
                  >
                    <UserAvatar userId={log.user_id} name={log.user} size={34}/>
                    <div className="flex-1 min-w-0">
                      <div className="font-black text-[12px] text-gray-900 truncate leading-tight">{log.user || '—'}</div>
                      <div className="text-[9px] text-gray-400 font-mono">{log.time?.replace('T',' ')}</div>
                    </div>
                    <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest ${tagStyle}`}>{log.tag}</span>
                    {hasActions && (
                      <button className={`flex-shrink-0 p-1 rounded-lg transition-colors ${isExpanded ? 'bg-gray-100 text-gray-500' : 'text-gray-300 hover:text-gray-400'}`}>
                        {isExpanded ? <ChevronUp size={13}/> : <ChevronDown size={13}/>}
                      </button>
                    )}
                  </div>

                  {/* ── Тело: текст сообщения ── */}
                  <div className="px-3 pb-2.5"
                    style={{
                      '--q-bg':       quoteCfg.bg,
                      '--q-stripe-1': quoteCfg.stripe1,
                      '--q-stripe-2': quoteCfg.stripeMode === 'alternating' ? quoteCfg.stripe2 : quoteCfg.stripe1,
                    }}
                  >
                    <div
                      className="journal-html text-[11.5px] text-gray-600 leading-snug break-words [&_a]:text-blue-500 [&_a]:underline [&_a]:font-semibold [&_b]:font-black [&_b]:text-gray-800"
                      dangerouslySetInnerHTML={{ __html: log.text }}
                    />
                  </div>

                  {/* ── Кнопки действий — только при раскрытии ── */}
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-1.5 border-t border-gray-50 pt-2">
                      <a
                        href={`tg://user?id=${log.user_id}`}
                        className="flex items-center justify-center gap-1.5 bg-blue-600 text-white py-2.5 rounded-xl font-black text-[9px] uppercase shadow-sm shadow-blue-100 active:scale-[0.98] transition-all"
                      >
                        <MessageCircle size={12}/><span>Написать в ЛС</span>
                      </a>
                      <div className="grid grid-cols-2 gap-1.5">
                        {log.type === 'mute'      && <button onClick={() => journalAction(log.user_id, 'unmute')} className="flex items-center justify-center gap-1 bg-green-50 text-green-700 py-2 rounded-xl font-black text-[9px] uppercase border border-green-200 active:scale-95 transition-all"><UserCheck size={12}/><span>Размутить</span></button>}
                        {log.type === 'mute'      && <button onClick={() => journalAction(log.user_id, 'ban')}    className="flex items-center justify-center gap-1 bg-red-50 text-red-700 py-2 rounded-xl font-black text-[9px] uppercase border border-red-200 active:scale-95 transition-all"><Ban size={12}/><span>Забанить</span></button>}
                        {log.type === 'ban'       && <button onClick={() => journalAction(log.user_id, 'unban')}  className="flex items-center justify-center gap-1 bg-blue-50 text-blue-700 py-2 rounded-xl font-black text-[9px] uppercase border border-blue-200 active:scale-95 transition-all"><UserCheck size={12}/><span>Разбанить</span></button>}
                        {log.type === 'ban'       && <button onClick={() => journalAction(log.user_id, 'kick')}   className="flex items-center justify-center gap-1 bg-rose-50 text-rose-700 py-2 rounded-xl font-black text-[9px] uppercase border border-rose-200 active:scale-95 transition-all"><UserMinus size={12}/><span>Удалить</span></button>}
                        {log.type === 'join'      && <button onClick={() => journalAction(log.user_id, 'ban')}    className="flex items-center justify-center gap-1 bg-red-50 text-red-700 py-2 rounded-xl font-black text-[9px] uppercase border border-red-200 active:scale-95 transition-all"><Ban size={12}/><span>Забанить</span></button>}
                        {log.type === 'join'      && <button className="flex items-center justify-center gap-1 bg-indigo-50 text-indigo-700 py-2 rounded-xl font-black text-[9px] uppercase border border-indigo-200 active:scale-95 transition-all"><UserSearch size={12}/><span>Досье</span></button>}
                        {log.type === 'blacklist' && <button onClick={() => journalAction(log.user_id, 'ban')}    className="flex items-center justify-center gap-1 bg-red-50 text-red-700 py-2 rounded-xl font-black text-[9px] uppercase border border-red-200 active:scale-95 transition-all"><Ban size={12}/><span>Забанить</span></button>}
                        {log.type === 'blacklist' && <button onClick={() => journalAction(log.user_id, 'kick')}   className="flex items-center justify-center gap-1 bg-rose-50 text-rose-700 py-2 rounded-xl font-black text-[9px] uppercase border border-rose-200 active:scale-95 transition-all"><UserMinus size={12}/><span>Удалить</span></button>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );

      case 'shipper':
        return (
          <div className="space-y-6 pb-24 animate-in fade-in duration-500">
            <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm flex items-center justify-between">
              <div>
                <h3 className="font-black text-xl text-gray-900 mb-1">Модуль Шиппер</h3>
                <span className={`text-[10px] font-black uppercase tracking-widest ${shipperSettings.enabled ? 'text-green-500' : 'text-red-500'}`}>
                   {shipperSettings.enabled ? '● Активен' : '○ Отключен'}
                </span>
              </div>
              <button onClick={() => setShipperSettings({...shipperSettings, enabled: !shipperSettings.enabled})} className={`w-14 h-8 rounded-full transition-colors relative ${shipperSettings.enabled ? 'bg-green-500' : 'bg-gray-200'}`}>
                <div className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-all ${shipperSettings.enabled ? 'left-7' : 'left-1'}`} />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <h3 className="px-4 text-[10px] font-black text-gray-400 uppercase tracking-widest">Категории</h3>
              {shipperSettings.categories.map(cat => (
                <div key={cat.id} className="bg-white p-5 rounded-3xl border border-gray-100 shadow-sm flex items-center justify-between active:scale-[0.98] transition-all">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center text-xl">{cat.id === 'hot18' ? '🔥' : cat.id === 'funny' ? '😂' : '💘'}</div>
                    <span className="font-black text-gray-900">{cat.name}</span>
                  </div>
                  <ChevronRight size={20} className="text-gray-300" />
                </div>
              ))}
            </div>

            <div className="bg-gray-900 text-white rounded-[2.5rem] p-8 space-y-6">
               <div className="space-y-4">
                  <h4 className="text-[10px] font-black text-blue-400 uppercase tracking-widest flex items-center"><Dices size={14} className="mr-2"/> Режим отбора</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {['active_48', 'active_72', 'inactive', 'random'].map(m => (
                      <button key={m} onClick={() => setShipperSettings({...shipperSettings, mode: m})} className={`p-4 rounded-2xl font-black text-[9px] uppercase border transition-all ${shipperSettings.mode === m ? 'bg-blue-600 border-blue-600 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
                        {m === 'active_48' ? '48ч' : m === 'active_72' ? '72ч' : m === 'inactive' ? 'Спящие' : 'Рандом'}
                      </button>
                    ))}
                  </div>
               </div>
            </div>
          </div>
        );

      case 'system':
        return (
          <div className="space-y-6 pb-24 animate-in fade-in duration-500">
             <div className="grid grid-cols-1 gap-4">
                <div className="bg-white p-8 rounded-[2.5rem] border border-gray-100 shadow-sm flex items-center justify-between">
                   <div>
                      <span className="text-[10px] font-black text-blue-500 uppercase block mb-2">Курс Пульса</span>
                      <div className="flex items-baseline space-x-2">
                         <span className="text-5xl font-black text-gray-900">{liveStats?.pulseRate ?? systemStats.pulseRate}</span>
                         <span className="text-gray-400 font-bold uppercase text-xs"> manual</span>
                      </div>
                   </div>
                   <button className="p-5 bg-blue-50 text-blue-600 rounded-3xl"><Edit size={24}/></button>
                </div>

             </div>

             {/* ─── АДМИНИСТРАТОРЫ ─── */}
             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 space-y-4">
               <div className="flex items-center justify-between">
                 <h3 className="font-black text-gray-900 text-sm uppercase flex items-center">
                   <ShieldCheck className="mr-3 text-green-500" size={16}/> Администраторы
                 </h3>
                 <button onClick={fetchStaff} className="text-xs text-gray-400 font-bold px-3 py-1.5 bg-gray-50 rounded-xl active:scale-95 transition-all">
                   Обновить
                 </button>
               </div>

               {/* Добавить */}
               <div className="flex space-x-2">
                 <input
                   value={newAdminId}
                   onChange={e => { setNewAdminId(e.target.value); setStaffError(''); }}
                   onKeyDown={e => e.key === 'Enter' && addAdmin()}
                   placeholder="ID или @username"
                   className="flex-1 bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-sm font-bold focus:outline-none focus:border-blue-300"
                 />
                 <button
                   onClick={addAdmin}
                   disabled={staffAdding || !newAdminId.trim()}
                   className="px-5 py-3 bg-gray-900 text-white rounded-2xl font-black text-xs disabled:opacity-40 active:scale-95 transition-all flex items-center space-x-1"
                 >
                   {staffAdding ? <Loader2 size={14} className="animate-spin"/> : <PlusCircle size={14}/>}
                   <span>Добавить</span>
                 </button>
               </div>
               {staffError && <p className="text-xs text-red-500 font-bold px-1">{staffError}</p>}

               {/* Список */}
               {staffLoading ? (
                 <div className="flex items-center justify-center py-6 text-gray-400">
                   <Loader2 size={18} className="animate-spin mr-2"/> Загрузка...
                 </div>
               ) : (
                 <div className="space-y-2">
                   {staffList.length === 0 && (
                     <p className="text-center text-gray-300 font-black text-xs uppercase tracking-widest py-4">
                       Нет данных
                     </p>
                   )}
                   {staffList.map(m => (
                     <div key={m.user_id} className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                       <div>
                         <div className="font-black text-sm text-gray-900">
                           {m.username ? `@${m.username}` : `ID ${m.user_id}`}
                           {m.first_name ? ` · ${m.first_name}` : ''}
                         </div>
                         <div className="flex items-center gap-2 mt-1">
                           <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full ${m.is_owner ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                             {m.is_owner ? '👑 Владелец' : '🛡 Админ'}
                           </span>
                           <span className="text-[9px] text-gray-400 font-mono">{m.user_id}</span>
                         </div>
                       </div>
                       {!m.is_owner && (
                         <button
                           onClick={() => removeAdmin(m.user_id)}
                           disabled={staffRemoving === m.user_id}
                           className="p-2.5 bg-red-50 text-red-500 rounded-xl active:scale-95 transition-all disabled:opacity-40"
                         >
                           {staffRemoving === m.user_id
                             ? <Loader2 size={15} className="animate-spin"/>
                             : <UserMinus size={15}/>}
                         </button>
                       )}
                     </div>
                   ))}
                 </div>
               )}
             </div>

             {/* ─── УПРАВЛЕНИЕ ФУНКЦИЯМИ ─── */}
             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100">
               <div className="flex items-center justify-between mb-5">
                 <h3 className="font-black text-gray-900 text-sm uppercase flex items-center">
                   <Wrench className="mr-3 text-purple-500" size={16}/> Функции бота
                 </h3>
                 <button
                   onClick={fetchFeatures}
                   className="text-xs text-gray-400 font-bold px-3 py-1.5 bg-gray-50 rounded-xl active:scale-95 transition-all"
                 >
                   Обновить
                 </button>
               </div>

               {featuresLoading && (
                 <div className="flex items-center justify-center py-8 text-gray-400">
                   <Loader2 size={20} className="animate-spin mr-2"/> Загрузка...
                 </div>
               )}

               {!featuresLoading && (
                 <div className="space-y-2">
                   {botFeatures.map(f => (
                     <div key={f.id} className="flex items-center justify-between p-3.5 bg-gray-50 rounded-2xl">
                       <span className="font-bold text-sm text-gray-800">{f.name}</span>
                       <button
                         onClick={() => toggleFeature(f.id)}
                         disabled={togglingFeature === f.id}
                         className={`relative w-12 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${
                           f.enabled ? 'bg-green-500' : 'bg-gray-300'
                         } ${togglingFeature === f.id ? 'opacity-50' : 'active:scale-95'}`}
                       >
                         <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all duration-200 ${
                           f.enabled ? 'left-[calc(100%-1.375rem)]' : 'left-0.5'
                         }`}/>
                       </button>
                     </div>
                   ))}
                 </div>
               )}
             </div>

             {/* ─── СТИЛЬ ЦИТАТ ЖУРНАЛА ─── */}
             <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 space-y-4">
               <h3 className="font-black text-gray-900 text-sm uppercase flex items-center">
                 <ScrollText className="mr-3 text-orange-400" size={16}/> Стиль цитат журнала
               </h3>

               {/* Превью */}
               <div className="journal-html"
                 style={{
                   '--q-bg':       quoteCfg.bg,
                   '--q-stripe-1': quoteCfg.stripe1,
                   '--q-stripe-2': quoteCfg.stripeMode === 'alternating' ? quoteCfg.stripe2 : quoteCfg.stripe1,
                 }}
               >
                 <p className="text-[10px] text-gray-400 font-bold uppercase mb-1">Превью:</p>
                 <blockquote>Пример текста нарушения от пользователя — это цитата сообщения</blockquote>
               </div>

               {/* Цвет фона */}
               <div className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
                 <span className="text-sm font-bold text-gray-700">Фон цитаты</span>
                 <div className="flex items-center gap-2">
                   <input type="color" value={quoteCfg.bg} onChange={e => setQuoteCfg(p => ({...p, bg: e.target.value}))}
                     className="w-8 h-8 rounded-lg border border-gray-200 cursor-pointer p-0.5"/>
                   <span className="text-xs font-mono text-gray-400">{quoteCfg.bg}</span>
                 </div>
               </div>

               {/* Режим полоски */}
               <div className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
                 <span className="text-sm font-bold text-gray-700">Полоска</span>
                 <div className="flex gap-2">
                   {['solid', 'alternating'].map(m => (
                     <button key={m} onClick={() => setQuoteCfg(p => ({...p, stripeMode: m}))}
                       className={`px-3 py-1.5 rounded-xl text-[10px] font-black uppercase transition-all ${quoteCfg.stripeMode === m ? 'bg-gray-900 text-white' : 'bg-white text-gray-400 border border-gray-200'}`}>
                       {m === 'solid' ? 'Одноцветная' : 'Чередование'}
                     </button>
                   ))}
                 </div>
               </div>

               {/* Цвет 1 */}
               <div className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
                 <span className="text-sm font-bold text-gray-700">{quoteCfg.stripeMode === 'alternating' ? 'Цвет 1' : 'Цвет полоски'}</span>
                 <div className="flex items-center gap-2">
                   <input type="color" value={quoteCfg.stripe1} onChange={e => setQuoteCfg(p => ({...p, stripe1: e.target.value}))}
                     className="w-8 h-8 rounded-lg border border-gray-200 cursor-pointer p-0.5"/>
                   <span className="text-xs font-mono text-gray-400">{quoteCfg.stripe1}</span>
                 </div>
               </div>

               {/* Цвет 2 — только при alternating */}
               {quoteCfg.stripeMode === 'alternating' && (
                 <div className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
                   <span className="text-sm font-bold text-gray-700">Цвет 2</span>
                   <div className="flex items-center gap-2">
                     <input type="color" value={quoteCfg.stripe2} onChange={e => setQuoteCfg(p => ({...p, stripe2: e.target.value}))}
                       className="w-8 h-8 rounded-lg border border-gray-200 cursor-pointer p-0.5"/>
                     <span className="text-xs font-mono text-gray-400">{quoteCfg.stripe2}</span>
                   </div>
                 </div>
               )}

               <button
                 onClick={saveQuoteCfg}
                 disabled={quoteSaving}
                 className="w-full py-3 bg-gray-900 text-white rounded-2xl font-black text-xs uppercase tracking-wide active:scale-[0.98] transition-all disabled:opacity-50 flex items-center justify-center gap-2"
               >
                 {quoteSaving ? <Loader2 size={14} className="animate-spin"/> : <Check size={14}/>}
                 Сохранить настройки
               </button>
               {quoteSaveMsg && (
                 <p className={`text-center text-xs font-bold ${quoteSaveMsg.startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
                   {quoteSaveMsg}
                 </p>
               )}
             </div>

          </div>
        );

      case 'triggers': {
        // ── Страница редактора триггера (полный экран) ──
        if (editingTrigger) {
          const upd = (field, val) => setEditingTrigger(prev => ({...prev, [field]: val}));
          const conditionGroups = editingTrigger.conditionGroups || [{ id: 1, conditions: [] }];
          const updCond = (gIdx, cIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, conditions: g.conditions.map((c, ci) => ci !== cIdx ? c : {...c, [field]: val})
            })
          }));
          const removeCond = (gIdx, cIdx) => setEditingTrigger(prev => ({
            ...prev,
            conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, conditions: g.conditions.filter((_, ci) => ci !== cIdx)
            })
          }));
          const addConditionToGroup = (gIdx, signal, ctype = 'keyword') => {
            const newId = Date.now();
            const newCond = ctype === 'reply_type'
              ? { id: newId, signal: 'message', type: 'reply_type', chips: [], inverted: false, placeholder_key: '' }
              : ctype === 'msg_type'
              ? { id: newId, signal: 'message', type: 'msg_type', chips: [], inverted: false, placeholder_key: '' }
              : { id: newId, signal, type: 'keyword', condition: 'contains', keyword: '', chips: [], keywordMode: 'chips', inverted: false, modifier: 'nocase', placeholder_key: '' };
            setEditingTrigger(prev => ({
              ...prev,
              conditionGroups: (prev.conditionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
                ...g, conditions: [...g.conditions, newCond]
              })
            }));
            setShowCondPickerModal(false);
          };
          const chipKey = (gi, ci) => `${gi}_${ci}`;
          const getChipInput = (gi, ci) => condChipInputs[chipKey(gi, ci)] || '';
          const setChipInput = (gi, ci, val) => setCondChipInputs(prev => ({...prev, [chipKey(gi, ci)]: val}));
          const addChip = (gIdx, cIdx, text) => {
            const trimmed = text.trim();
            if (!trimmed) return;
            const chips = [...(conditionGroups[gIdx]?.conditions[cIdx]?.chips || []), trimmed];
            updCond(gIdx, cIdx, 'chips', chips);
            updCond(gIdx, cIdx, 'keyword', chips.join(', '));
            setChipInput(gIdx, cIdx, '');
          };
          const removeChip = (gIdx, cIdx, chipIdx) => {
            const chips = (conditionGroups[gIdx]?.conditions[cIdx]?.chips || []).filter((_, i) => i !== chipIdx);
            updCond(gIdx, cIdx, 'chips', chips);
            updCond(gIdx, cIdx, 'keyword', chips.join(', '));
          };
          const moveCondInGroup = (gIdx, cIdx, dir) => setEditingTrigger(prev => {
            const groups = (prev.conditionGroups||[]).map((g, gi) => {
              if (gi !== gIdx) return g;
              const conds = [...g.conditions];
              const newIdx = cIdx + dir;
              if (newIdx < 0 || newIdx >= conds.length) return g;
              [conds[cIdx], conds[newIdx]] = [conds[newIdx], conds[cIdx]];
              return {...g, conditions: conds};
            });
            return {...prev, conditionGroups: groups};
          });
          const addCondGroup = () => setEditingTrigger(prev => ({
            ...prev, conditionGroups: [...(prev.conditionGroups||[]), { id: Date.now(), conditions: [] }]
          }));
          const removeCondGroup = (gIdx) => setEditingTrigger(prev => ({
            ...prev, conditionGroups: (prev.conditionGroups||[]).filter((_, i) => i !== gIdx)
          }));
          const moveCondGroup = (gIdx, dir) => setEditingTrigger(prev => {
            const groups = [...(prev.conditionGroups||[])];
            const newIdx = gIdx + dir;
            if (newIdx < 0 || newIdx >= groups.length) return prev;
            [groups[gIdx], groups[newIdx]] = [groups[newIdx], groups[gIdx]];
            return {...prev, conditionGroups: groups};
          });
          const actionGroups = editingTrigger.actionGroups || [{ id: 1, probability: 100, actions: [] }];
          const updActionGroup = (gIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {...g, [field]: val})
          }));
          const updAction = (gIdx, aIdx, field, val) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, actions: g.actions.map((a, ai) => ai !== aIdx ? a : {...a, [field]: val})
            })
          }));
          const removeAction = (gIdx, aIdx) => setEditingTrigger(prev => ({
            ...prev,
            actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
              ...g, actions: g.actions.filter((_, ai) => ai !== aIdx)
            })
          }));
          const addActionToGroup = (gIdx, type) => {
            const newId = Date.now();
            const base = { id: newId, type, duration: '', emoji: '' };
            const sendTextExtra = type === 'send_text' || type === 'dm' ? {
              variants: [{ id: Date.now(), text: '', media_type: 'none' }],
              currentVariant: 0, msgTab: 'editor', reply_target: 'none',
              settings: { delete_after: false, delete_after_sec: 60, send_delayed: false, pin: false, disable_preview: false, disable_notify: false, delete_previous: false, content_protection: false },
              keyboard: [],
              reply_text: '', media_type: 'none', bot_msg_delete: 'no', bot_msg_delete_after: 60,
            } : { reply_text: '', media_type: 'none', reply_target: 'none', bot_msg_delete: 'no', bot_msg_delete_after: 60 };
            setEditingTrigger(prev => ({
              ...prev,
              actionGroups: (prev.actionGroups||[]).map((g, gi) => gi !== gIdx ? g : {
                ...g, actions: [...g.actions, { ...base, ...sendTextExtra }]
              })
            }));
            setShowActPickerModal(false);
            setNewActionIds(prev => { const n = new Set(prev); n.add(newId); return n; });
            setTimeout(() => {
              setNewActionIds(prev => { const n = new Set(prev); n.delete(newId); return n; });
            }, 800);
          };
          const addActionGroup = () => setEditingTrigger(prev => ({
            ...prev, actionGroups: [...(prev.actionGroups||[]), { id: Date.now(), probability: 100, actions: [] }]
          }));
          const removeActionGroup = (gIdx) => setEditingTrigger(prev => ({
            ...prev, actionGroups: (prev.actionGroups||[]).filter((_, i) => i !== gIdx)
          }));
          const moveActionGroup = (gIdx, dir) => setEditingTrigger(prev => {
            const groups = [...(prev.actionGroups||[])];
            const newIdx = gIdx + dir;
            if (newIdx < 0 || newIdx >= groups.length) return prev;
            [groups[gIdx], groups[newIdx]] = [groups[newIdx], groups[gIdx]];
            return {...prev, actionGroups: groups};
          });
          const moveActionInGroup = (gIdx, aIdx, dir) => setEditingTrigger(prev => {
            const groups = (prev.actionGroups||[]).map((g, gi) => {
              if (gi !== gIdx) return g;
              const acts = [...g.actions];
              const newIdx = aIdx + dir;
              if (newIdx < 0 || newIdx >= acts.length) return g;
              [acts[aIdx], acts[newIdx]] = [acts[newIdx], acts[aIdx]];
              return {...g, actions: acts};
            });
            return {...prev, actionGroups: groups};
          });
          const COND_TOOLTIP_TEXT = {
            'msg_keyword': 'Проверяет текст входящего сообщения — содержит ли оно указанное слово или фразу.',
            'msg_any':     'Срабатывает на любое текстовое сообщение, без проверки содержимого.',
            'qmsg_keyword': 'Проверяет текст сообщения, на которое ответили (цитируемое).',
            'qmsg_any':    'Срабатывает, когда пользователь отвечает на любое сообщение цитированием.',
            'msg_reply_type': 'Проверяет тип сообщения: обычное, реплай, первое сообщение пользователя, комментарий под постом и т.д.',
            'msg_msg_type':   'Проверяет формат входящего сообщения: фото, видео, стикер, документ, голосовое и т.д. Всего 15 типов.',
          };
          const MSG_TYPE_OPTIONS = [
            { key: 'text',       label: 'Текст' },
            { key: 'photo',      label: 'Фото' },
            { key: 'photo_file', label: 'Фотофайл' },
            { key: 'video',      label: 'Видео' },
            { key: 'video_file', label: 'Видеофайл' },
            { key: 'video_note', label: 'Видео заметка' },
            { key: 'document',   label: 'Документ' },
            { key: 'sticker',    label: 'Стикер' },
            { key: 'animation',  label: 'Анимация' },
            { key: 'audio',      label: 'Аудио' },
            { key: 'voice',      label: 'Войс' },
            { key: 'contact',    label: 'Контакт' },
            { key: 'location',   label: 'Локация' },
            { key: 'poll',       label: 'Опрос' },
            { key: 'game',       label: 'Игра' },
          ];
          const MSG_TYPE_INFO = `Вызов триггера через параметр тип (или формат) посылаемого сообщения: фото, аудио, стикер и т.д. Всего доступно 15 типов сообщений.

• Текст — триггер сработает, если пользователь отправил обычное текстовое сообщение без вложений.
• Фото — триггер сработает, если отправлена фотография из галереи телефона.
• Фотофайл — триггер сработает, если изображение отправлено как файл (без сжатия).
• Видео — триггер сработает, если видеозапись загружена напрямую из галереи телефона.
• Видеофайл — триггер сработает, если видеозапись отправлена как файл, а не из галереи.
• Видео заметка — триггер сработает, если отправлено круглое видео (видеокружок).
• Документ — триггер сработает, если отправлен файл: doc, word, pdf, excel и т.д.
• Стикер — триггер сработает, если отправлен статичный или анимированный стикер Telegram.
• Анимация — триггер сработает, если отправлен GIF или анимированное изображение.
• Аудио — триггер сработает, если отправлен музыкальный файл или аудиозапись. Не относится к голосовым сообщениям.
• Войс — триггер сработает, если отправлено голосовое сообщение в Telegram.
• Контакт — триггер сработает, если отправлен контакт (номер телефона).
• Локация — триггер сработает, если отправлена геолокация.
• Опрос — триггер сработает, если создан опрос в чате.
• Игра — триггер сработает, если отправлена Telegram-игра.`;

          const REPLY_TYPE_OPTIONS = [
            { key: 'any',                label: 'Любое сообщение' },
            { key: 'any_reply',          label: 'Все ответы' },
            { key: 'reply_bot',          label: 'Ответ боту' },
            { key: 'reply_user',         label: 'Ответ участнику' },
            { key: 'reply_admin',        label: 'Ответ админу' },
            { key: 'reply_non_admin',    label: 'Ответ не админу' },
            { key: 'reply_self_bot',     label: 'Ответ @Pulse_On_bot' },
            { key: 'non_reply',          label: 'Не ответ' },
            { key: 'first_message',      label: 'Первое сообщение пользователя' },
            { key: 'reply_linked_post',  label: 'Ответ на пост в привязанном канале' },
            { key: 'reply_channel',      label: 'Ответ на сообщение от имени канала' },
            { key: 'comment_under_post', label: 'Любой комментарий под постом' },
            { key: 'reply_self',         label: 'Ответ самому себе' },
          ];
          const REPLY_TYPE_INFO = `Бот будет реагировать на определённые типы сообщения участников чата. Например, на «ответы админу». Настройка полезна, если хотите контролировать ответы в группе, например — разрешить или запретить их.

• Любое сообщение — триггер будет срабатывать на любые типы сообщений участников.
• Все ответы — сработает, если участник написал сообщение в ответ (реплай) на любое сообщение.
• Ответ боту — сработает, если участник написал сообщение в ответ на сообщение бота.
• Ответ участнику — сработает, если участник написал сообщение в ответ на сообщение другого участника.
• Ответ админу — сработает, если участник написал сообщение в ответ на сообщение администратора.
• Ответ не админу — сработает, если участник написал сообщение в ответ тому, кто не является админом.
• Ответ @Pulse_On_bot — сработает, если участник написал сообщение в ответ нашему боту.
• Не ответ — сработает, если участник написал обычное сообщение, не в ответ кому-либо.
• Первое сообщение пользователя — сработает, если участник написал в чате впервые.
• Ответ на пост в привязанном канале — сработает, если участник пишет в ответ на пост в канале, который привязан к группе.
• Ответ на сообщение от имени канала — сработает, если участник пишет в ответ на сообщение, которое написано от имени любого канала.
• Любой комментарий под постом — сработает, если участник оставит любой комментарий или ответ на комментарий под постом.
• Ответ самому себе — сработает, если участник отвечает на своё собственное сообщение.`;

          const COND_LABELS = { contains:'Содержит', exact:'Точное', starts_with:'Начало', ends_with:'Конец', whole_word:'Целое слово' };
          const ACTION_TYPES = [
            { type:'send_text', label:'Отправить сообщение в чат', Icon: MessageCircle },
            { type:'dm',        label:'Личное сообщение',   Icon: Send          },
            { type:'mute',      label:'Мут',               Icon: Clock         },
            { type:'ban',       label:'Бан',               Icon: ShieldBan     },
            { type:'warn',      label:'Предупреждение',    Icon: AlertOctagon  },
            { type:'delete',    label:'Удалить сообщение', Icon: Trash2        },
            { type:'emoji',     label:'Реакция',           Icon: Smile         },
            { type:'pin',       label:'Закрепить сообщение',Icon: CheckCircle2   },
          ];

          return (
            <div className="pb-24 animate-in fade-in duration-300">

              {/* ── Шапка редактора ── */}
              <div className="bg-white rounded-[2rem] border border-gray-100 shadow-sm p-5 mb-5 space-y-4">

                {/* Кнопки действий */}
                <div className="flex items-center gap-2">
                  <button onClick={() => { setLeaveTarget(null); setShowLeaveConfirm(true); }}
                    className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all mr-auto">
                    <X size={20}/>
                  </button>
                  <button onClick={saveTrigger}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-green-500 text-white rounded-xl font-black text-sm shadow-md shadow-green-100 active:scale-95 transition-all">
                    <CheckCircle2 size={15}/> Сохранить
                  </button>
                  <div className="relative">
                    <button onClick={() => setShowTriggerEditMenu(v=>!v)}
                      className="px-3 py-2.5 bg-gray-100 text-gray-500 rounded-xl font-black text-sm active:scale-95 transition-all hover:bg-gray-200">
                      ···
                    </button>
                    {showTriggerEditMenu && (
                      <div className="absolute right-0 top-full mt-1.5 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-10 overflow-hidden"
                        onClick={() => setShowTriggerEditMenu(false)}>
                        <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed border-b border-gray-50">
                          <FileText size={14} className="text-gray-200"/>
                          <span>Сохранить и продолжить</span>
                          <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                        </button>
                        <button className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-gray-300 cursor-not-allowed">
                          <Download size={14} className="text-gray-200"/>
                          <span>Экспортировать триггер</span>
                          <span className="ml-auto text-[9px] bg-gray-100 text-gray-300 px-1.5 py-0.5 rounded font-black">***</span>
                        </button>
                      </div>
                    )}
                  </div>
                  {editingTrigger.id && userCan('triggers.delete') && (
                    <button onClick={() => { deleteTrigger(editingTrigger.id); setEditingTrigger(null); }}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-red-500 text-white rounded-xl font-black text-sm shadow-md shadow-red-100 active:scale-95 transition-all">
                      <Trash2 size={15}/> Удалить
                    </button>
                  )}
                </div>

                {/* Имя триггера */}
                <div>
                  <p className="text-xs font-black text-gray-800 mb-0.5">
                    Имя триггера <span className="text-red-500">*</span>
                  </p>
                  <p className="text-[10px] text-gray-400 font-medium mb-2">
                    Позволяет быстро найти нужный триггер и включить его
                  </p>
                  <input type="text" placeholder="Например: Мут за спам"
                    value={editingTrigger.name} onChange={e => upd('name', e.target.value)}
                    className="w-full px-4 py-3.5 bg-gray-50 border-2 border-gray-100 rounded-2xl font-black text-base outline-none focus:border-blue-200 transition-all"/>
                </div>
              </div>

              {/* ── Вероятность + Лимит срабатываний ── */}
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="bg-amber-50 p-4 rounded-2xl border border-amber-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black text-amber-700 uppercase tracking-widest flex items-center gap-1">
                      <Percent size={11}/> Шанс срабатывания
                    </span>
                    <span className="text-xl font-black text-amber-800">{editingTrigger.probability}%</span>
                  </div>
                  <input type="range" min="1" max="100" value={editingTrigger.probability}
                    onChange={e => upd('probability', parseInt(e.target.value))}
                    className="w-full h-2 bg-amber-200 rounded-full appearance-none cursor-pointer accent-amber-600"/>
                </div>
                <div className="bg-blue-50 p-4 rounded-2xl border border-blue-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-black text-blue-700 uppercase tracking-widest">Лимит срабатываний</span>
                    <span className="text-[10px] font-bold text-blue-400">{(editingTrigger.fire_limit || 0) === 0 ? '∞' : editingTrigger.fire_limit}</span>
                  </div>
                  <input type="number" min="0" max="9999"
                    value={editingTrigger.fire_limit || 0}
                    onChange={e => upd('fire_limit', parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 bg-white border border-blue-200 rounded-xl font-black text-sm outline-none focus:border-blue-400 transition-all text-center"/>
                  <p className="text-[9px] text-blue-400 mt-1 text-center">0 = без лимита</p>
                </div>
              </div>

              {/* ── УСЛОВИЯ + ДЕЙСТВИЯ (2 колонки) ── */}
              <div className="grid grid-cols-2 gap-3 mb-5">

              {/* ─── Левая колонка: УСЛОВИЯ ─── */}
              <div className="space-y-3">
                {/* Заголовок блока */}
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Условия</span>
                  <div className="relative">
                    <button
                      onClick={() => setCondTooltip(condTooltip === 'block' ? null : 'block')}
                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 active:scale-90 transition-all flex-shrink-0">
                      ?
                    </button>
                    {condTooltip === 'block' && (
                      <div className="absolute left-0 top-6 w-64 bg-gray-900 text-white text-[11px] font-medium p-3 rounded-2xl shadow-xl z-50 leading-relaxed">
                        Условия определяют, на что реагирует триггер. Несколько условий в одной группе работают как «И» (все должны совпасть). Несколько групп работают как «ИЛИ» (достаточно одной).
                        <div className="absolute -top-1.5 left-2 w-3 h-3 bg-gray-900 rotate-45"/>
                      </div>
                    )}
                  </div>
                  {conditionGroups.length > 1 && (
                    <span className="ml-auto text-[9px] font-black text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full uppercase">
                      {conditionGroups.length} группы
                    </span>
                  )}
                </div>

                {/* Группы условий */}
                {conditionGroups.map((group, gIdx) => {
                  return (
                    <div key={group.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm">
                      {/* Шапка группы */}
                      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                        <span className="text-[10px] font-black text-gray-600 uppercase tracking-widest flex-1">
                          {conditionGroups.length > 1 ? `Группа ${gIdx + 1}` : 'Условия'}
                          {conditionGroups.length > 1 && gIdx < conditionGroups.length - 1 && (
                            <span className="ml-2 text-[9px] font-black text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full">ИЛИ ↓</span>
                          )}
                        </span>
                        <div className="flex items-center gap-0.5">
                          <button onClick={() => moveCondGroup(gIdx, -1)} disabled={gIdx === 0}
                            className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↑</button>
                          <button onClick={() => moveCondGroup(gIdx, 1)} disabled={gIdx === conditionGroups.length - 1}
                            className="p-1 text-gray-300 hover:text-gray-500 disabled:opacity-20 active:scale-90 transition-all text-xs font-black">↓</button>
                          {conditionGroups.length > 1 && (
                            <button onClick={() => removeCondGroup(gIdx)}
                              className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all ml-0.5">
                              <Trash2 size={12}/>
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Условия внутри группы */}
                      <div className="p-3">
                        {group.conditions.length === 0 && (
                          <div className="text-center py-4 text-gray-300 text-[11px] font-black uppercase tracking-widest">
                            Список пуст
                          </div>
                        )}
                        {group.conditions.map((cond, cIdx) => {
                          const COND_TYPE_LABELS = { exact:'Полное совпадение', ends_with:'Сообщение заканчивается на', starts_with:'Сообщение начинается с', contains:'Сообщение содержит', whole_word:'Целое слово' };
                          const typeKey = `type_${gIdx}_${cIdx}`;
                          const modKey  = `mod_${gIdx}_${cIdx}`;
                          return (
                          <div key={cond.id}>
                            {cIdx > 0 && (
                              <div className="flex justify-center my-3">
                                <div className="flex flex-col items-center">
                                  <div className="w-2 h-2 rounded-full bg-blue-200"/>
                                  <div className="w-px h-6 bg-blue-100"/>
                                  <div className="w-2 h-2 rounded-full bg-blue-200"/>
                                </div>
                              </div>
                            )}
                          <div className="bg-white rounded-2xl border border-gray-200"
                            style={condOpenDropdown && condOpenDropdown.endsWith(`_${gIdx}_${cIdx}`) ? {position:'relative', zIndex:9999} : {}}>
                            {/* Шапка: ⚙️ + Условие N + ↑↓🗑 */}
                            <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                              <button onClick={() => setCondSettingsModal({gIdx, cIdx})}
                                className="p-1 text-gray-400 hover:text-gray-600 active:scale-90 transition-all flex-shrink-0">
                                <Settings size={12}/>
                              </button>
                              <span className="text-[11px] font-black text-gray-700 flex-1">Условие {cIdx + 1}</span>
                              {cond.placeholder_key && (
                                <span className="text-[9px] font-bold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded-full">%{cond.placeholder_key}%</span>
                              )}
                              <div className="flex items-center gap-0.5">
                                <button onClick={() => moveCondInGroup(gIdx, cIdx, -1)} disabled={cIdx === 0}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                                  <ChevronUp size={14}/>
                                </button>
                                <button onClick={() => moveCondInGroup(gIdx, cIdx, 1)} disabled={cIdx === group.conditions.length - 1}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                                  <ChevronDown size={14}/>
                                </button>
                                <button onClick={() => removeCond(gIdx, cIdx)}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-red-300 hover:text-red-500 hover:bg-red-50 active:scale-90 transition-all ml-0.5">
                                  <Trash2 size={11}/>
                                </button>
                              </div>
                            </div>

                            {/* Тело карточки */}
                            <div className="px-3 py-3 space-y-3" onClick={() => setCondOpenDropdown(null)}>

                              {cond.type === 'reply_type' ? (
                                <>
                                  {/* Заголовок "Тип ответа" + ? */}
                                  <div className="flex items-center gap-1.5 relative">
                                    <span className="text-[13px] font-black text-gray-800">Тип ответа</span>
                                    <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `rt_info_${gIdx}_${cIdx}` ? null : `rt_info_${gIdx}_${cIdx}`); }}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">?</button>
                                    {condTooltip === `rt_info_${gIdx}_${cIdx}` && (
                                      <div className="absolute left-0 top-6 z-[600] w-[280px] bg-gray-900 text-white text-[10px] font-medium p-3 rounded-xl shadow-2xl leading-relaxed whitespace-pre-line max-h-80 overflow-y-auto">
                                        {REPLY_TYPE_INFO}
                                      </div>
                                    )}
                                  </div>
                                  <p className="text-[10px] text-orange-500 font-semibold -mt-1">
                                    Сигнал для вызова триггера: 📋 Сообщение
                                  </p>
                                  {/* Значения условия (multi-select) */}
                                  <div onClick={e => e.stopPropagation()}>
                                    <div className="flex items-center gap-1.5 mb-2">
                                      <p className="text-[9px] font-black text-gray-500 uppercase">
                                        Значения условия <span className="text-red-400">*</span>
                                      </p>
                                      <button
                                        onClick={e => { e.stopPropagation(); setCondGearModal({gIdx, cIdx}); }}
                                        className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">⚙</button>
                                    </div>
                                    <div className="relative">
                                      <button
                                        onClick={() => setCondOpenDropdown(condOpenDropdown === `rt_dd_${gIdx}_${cIdx}` ? null : `rt_dd_${gIdx}_${cIdx}`)}
                                        className="w-full flex items-start justify-between gap-2 min-h-[42px] px-3 py-2 bg-white border-2 border-gray-200 rounded-xl hover:border-gray-300 transition-all">
                                        <div className="flex flex-wrap gap-1 flex-1">
                                          {(cond.chips||[]).length === 0 && <span className="text-gray-300 text-sm font-medium">—</span>}
                                          {(cond.chips||[]).map((key, ci) => {
                                            const lbl = REPLY_TYPE_OPTIONS.find(o => o.key === key)?.label || key;
                                            return (
                                              <span key={ci} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-700 rounded-lg text-[10px] font-bold">
                                                {lbl}
                                                <button onClick={e => { e.stopPropagation(); const chips = (cond.chips||[]).filter(c => c !== key); updCond(gIdx, cIdx, 'chips', chips); }} className="text-gray-400 hover:text-gray-700 leading-none ml-0.5">×</button>
                                              </span>
                                            );
                                          })}
                                        </div>
                                        <ChevronDown size={14} className={`text-gray-400 flex-shrink-0 mt-1 transition-transform ${condOpenDropdown === `rt_dd_${gIdx}_${cIdx}` ? 'rotate-180' : ''}`}/>
                                      </button>
                                      {condOpenDropdown === `rt_dd_${gIdx}_${cIdx}` && (
                                        <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden max-h-64 overflow-y-auto">
                                          {REPLY_TYPE_OPTIONS.filter(o => !(cond.chips||[]).includes(o.key)).map(o => (
                                            <button key={o.key}
                                              onClick={() => { const chips = [...(cond.chips||[]), o.key]; updCond(gIdx, cIdx, 'chips', chips); }}
                                              className="w-full px-4 py-2.5 text-sm font-bold text-left transition-all text-gray-700 hover:bg-gray-50">
                                              {o.label}
                                            </button>
                                          ))}
                                          {REPLY_TYPE_OPTIONS.filter(o => !(cond.chips||[]).includes(o.key)).length === 0 && (
                                            <div className="px-4 py-3 text-xs text-gray-400 text-center font-medium">Все опции выбраны</div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                    {(cond.chips||[]).length === 0 && <p className="text-[9px] text-red-400 mt-1">Обязательное поле</p>}
                                  </div>
                                  {/* Инвертировать */}
                                  <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <span className="text-[11px] font-black text-gray-700">Инвертировать условие</span>
                                        <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `rt_inv_${gIdx}_${cIdx}` ? null : `rt_inv_${gIdx}_${cIdx}`); }}
                                          className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                      </div>
                                      <button onClick={() => updCond(gIdx, cIdx, 'inverted', !(cond.inverted||false))}
                                        className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${cond.inverted ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${cond.inverted ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                      </button>
                                    </div>
                                    <p className="text-[9px] text-gray-400 leading-relaxed">* Триггер будет работать наоборот. Бот будет реагировать, если условие не выполнено.</p>
                                  </div>
                                </>
                              ) : cond.type === 'msg_type' ? (
                                <>
                                  {/* Заголовок "Тип сообщения" + ? */}
                                  <div className="flex items-center gap-1.5 relative">
                                    <span className="text-[13px] font-black text-gray-800">Тип сообщения</span>
                                    <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `mt_info_${gIdx}_${cIdx}` ? null : `mt_info_${gIdx}_${cIdx}`); }}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">?</button>
                                    {condTooltip === `mt_info_${gIdx}_${cIdx}` && (
                                      <div className="absolute left-0 top-6 z-[600] w-[300px] bg-gray-900 text-white text-[10px] font-medium p-3 rounded-xl shadow-2xl leading-relaxed whitespace-pre-line max-h-80 overflow-y-auto">
                                        {MSG_TYPE_INFO}
                                      </div>
                                    )}
                                  </div>
                                  <p className="text-[10px] text-orange-500 font-semibold -mt-1">
                                    Сигнал для вызова триггера: 📨 Сообщение
                                  </p>
                                  {/* Мультивыбор типов */}
                                  <div onClick={e => e.stopPropagation()}>
                                    <div className="flex items-center gap-1.5 mb-2">
                                      <p className="text-[9px] font-black text-gray-500 uppercase">
                                        Тип сообщения <span className="text-red-400">*</span>
                                      </p>
                                      <button
                                        onClick={e => { e.stopPropagation(); setCondGearModal({gIdx, cIdx}); }}
                                        className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">⚙</button>
                                    </div>
                                    <div className="relative">
                                      <button
                                        onClick={() => setCondOpenDropdown(condOpenDropdown === `mt_dd_${gIdx}_${cIdx}` ? null : `mt_dd_${gIdx}_${cIdx}`)}
                                        className="w-full flex items-start justify-between gap-2 min-h-[42px] px-3 py-2 bg-white border-2 border-gray-200 rounded-xl hover:border-gray-300 transition-all">
                                        <div className="flex flex-wrap gap-1 flex-1">
                                          {(cond.chips||[]).length === 0 && <span className="text-gray-300 text-sm font-medium">—</span>}
                                          {(cond.chips||[]).map((key, ci) => {
                                            const lbl = MSG_TYPE_OPTIONS.find(o => o.key === key)?.label || key;
                                            return (
                                              <span key={ci} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-700 rounded-lg text-[10px] font-bold">
                                                {lbl}
                                                <button onClick={e => { e.stopPropagation(); const chips = (cond.chips||[]).filter(c => c !== key); updCond(gIdx, cIdx, 'chips', chips); }} className="text-gray-400 hover:text-gray-700 leading-none ml-0.5">×</button>
                                              </span>
                                            );
                                          })}
                                        </div>
                                        <ChevronDown size={14} className={`text-gray-400 flex-shrink-0 mt-1 transition-transform ${condOpenDropdown === `mt_dd_${gIdx}_${cIdx}` ? 'rotate-180' : ''}`}/>
                                      </button>
                                      {condOpenDropdown === `mt_dd_${gIdx}_${cIdx}` && (
                                        <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden max-h-64 overflow-y-auto">
                                          {MSG_TYPE_OPTIONS.filter(o => !(cond.chips||[]).includes(o.key)).map(o => (
                                            <button key={o.key}
                                              onClick={() => { const chips = [...(cond.chips||[]), o.key]; updCond(gIdx, cIdx, 'chips', chips); }}
                                              className="w-full px-4 py-2.5 text-sm font-bold text-left transition-all text-gray-700 hover:bg-gray-50">
                                              {o.label}
                                            </button>
                                          ))}
                                          {MSG_TYPE_OPTIONS.filter(o => !(cond.chips||[]).includes(o.key)).length === 0 && (
                                            <div className="px-4 py-3 text-xs text-gray-400 text-center font-medium">Список пуст</div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                    {(cond.chips||[]).length === 0 && <p className="text-[9px] text-red-400 mt-1">Обязательное поле</p>}
                                  </div>
                                  {/* Инвертировать */}
                                  <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <span className="text-[11px] font-black text-gray-700">Инвертировать условие</span>
                                        <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `mt_inv_${gIdx}_${cIdx}` ? null : `mt_inv_${gIdx}_${cIdx}`); }}
                                          className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                      </div>
                                      <button onClick={() => updCond(gIdx, cIdx, 'inverted', !(cond.inverted||false))}
                                        className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${cond.inverted ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${cond.inverted ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                      </button>
                                    </div>
                                    <p className="text-[9px] text-gray-400 leading-relaxed">* Триггер будет работать наоборот. Бот будет реагировать, если условие не выполнено.</p>
                                  </div>
                                </>
                              ) : (<>
                              {/* Сигнал */}
                              <div className="flex items-center gap-1.5">
                                <span className="text-[12px] font-black text-gray-800">
                                  {cond.signal === 'message' ? 'Сообщение' : 'Цитируемое'}
                                </span>
                                <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `sig_${gIdx}_${cIdx}` ? null : `sig_${gIdx}_${cIdx}`); }}
                                  className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">?</button>
                                {condTooltip === `sig_${gIdx}_${cIdx}` && (
                                  <div className="absolute z-50 mt-1 w-52 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl leading-relaxed">
                                    {cond.signal === 'message' ? 'Условие проверяет текст входящего сообщения.' : 'Условие проверяет текст цитируемого (reply) сообщения.'}
                                  </div>
                                )}
                              </div>

                              {/* Тип условия */}
                              <div onClick={e => e.stopPropagation()}>
                                <p className="text-[9px] font-black text-gray-500 uppercase mb-1.5">
                                  Выберите тип условия <span className="text-red-400">*</span>
                                </p>
                                <div className="relative">
                                  <button
                                    onClick={() => setCondOpenDropdown(condOpenDropdown === typeKey ? null : typeKey)}
                                    className="w-full flex items-center justify-between px-3 py-2.5 bg-white border-2 border-gray-200 rounded-xl text-sm font-bold text-gray-700 hover:border-gray-300 transition-all">
                                    <span>{COND_TYPE_LABELS[cond.condition] || cond.condition}</span>
                                    <ChevronDown size={14} className={`text-gray-400 transition-transform duration-200 ${condOpenDropdown === typeKey ? 'rotate-180' : ''}`}/>
                                  </button>
                                  {condOpenDropdown === typeKey && (
                                    <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                      {Object.entries(COND_TYPE_LABELS).map(([key, lbl]) => (
                                        <button key={key}
                                          onClick={() => { updCond(gIdx, cIdx, 'condition', key); setCondOpenDropdown(null); }}
                                          className={`w-full px-4 py-2.5 text-sm font-bold text-left transition-all ${cond.condition === key ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                          {lbl}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Сигнал для вызова */}
                              <p className="text-[10px] text-orange-500 font-semibold -mt-1">
                                Сигнал для вызова триггера: {cond.signal === 'message' ? '📋 Сообщение' : '↩️ Цитируемое'}
                              </p>

                              {/* Значения условия (Chips / Text) */}
                              <div onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1.5 mb-2">
                                  <p className="text-[9px] font-black text-gray-500 uppercase">
                                    Значения условия <span className="text-red-400">*</span>
                                  </p>
                                  <div className="relative">
                                    <button
                                      onClick={() => setCondOpenDropdown(condOpenDropdown === `kw_${gIdx}_${cIdx}` ? null : `kw_${gIdx}_${cIdx}`)}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600 flex-shrink-0">
                                      ⚙
                                    </button>
                                    {condOpenDropdown === `kw_${gIdx}_${cIdx}` && (
                                      <div className="absolute left-0 top-6 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl overflow-hidden min-w-[160px]">
                                        <button onClick={() => { updCond(gIdx, cIdx, 'chips', []); updCond(gIdx, cIdx, 'keyword', ''); setCondOpenDropdown(null); setCondChipInput(''); }}
                                          className="w-full flex items-center gap-2 px-3 py-2.5 text-[11px] font-bold text-red-500 hover:bg-red-50 transition-all text-left">
                                          <RotateCcw size={11}/> Отменить изменения
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                </div>
                                {/* Табы */}
                                <div className="flex border-b border-gray-200 mb-2">
                                  <button onClick={() => updCond(gIdx, cIdx, 'keywordMode', 'chips')}
                                    className={`flex items-center gap-1 px-3 py-1.5 text-[10px] font-black border-b-2 -mb-px transition-all ${(cond.keywordMode||'chips') === 'chips' ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                                    🏷 Chips ({(cond.chips||[]).length})
                                  </button>
                                  <button onClick={() => updCond(gIdx, cIdx, 'keywordMode', 'text')}
                                    className={`flex items-center gap-1 px-3 py-1.5 text-[10px] font-black border-b-2 -mb-px transition-all ${(cond.keywordMode||'chips') === 'text' ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                                    📄 Text
                                  </button>
                                </div>
                                {(cond.keywordMode||'chips') === 'chips' ? (
                                  <div>
                                    {(cond.chips||[]).length > 0 && (
                                      <div className="flex flex-wrap gap-1 mb-2">
                                        {(cond.chips||[]).map((chip, ci) => (
                                          <span key={ci} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-lg text-[10px] font-bold">
                                            {chip}
                                            <button onClick={() => removeChip(gIdx, cIdx, ci)} className="text-blue-400 hover:text-blue-700 leading-none ml-0.5">×</button>
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                    <div className="flex gap-1">
                                      <input type="text"
                                        value={getChipInput(gIdx, cIdx)}
                                        onChange={e => setChipInput(gIdx, cIdx, e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addChip(gIdx, cIdx, getChipInput(gIdx, cIdx)); }}}
                                        placeholder=""
                                        className="flex-1 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                                      <button onClick={() => addChip(gIdx, cIdx, getChipInput(gIdx, cIdx))}
                                        className={`px-3 py-2 rounded-xl active:scale-95 transition-all ${getChipInput(gIdx, cIdx).trim() ? 'bg-green-500 hover:bg-green-600 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-500'}`}>
                                        <Check size={13}/>
                                      </button>
                                    </div>
                                    <p className="text-[9px] text-gray-400 mt-1">* Введите значения по одному с помощью «Enter»</p>
                                    {(cond.chips||[]).length === 0 && <p className="text-[9px] text-red-400 mt-0.5">Обязательное поле</p>}
                                  </div>
                                ) : (
                                  <div>
                                    <textarea
                                      value={(cond.chips||[]).join(', ')}
                                      onChange={e => { const chips = e.target.value.split(',').map(s=>s.trim()).filter(Boolean); updCond(gIdx, cIdx, 'chips', chips); updCond(gIdx, cIdx, 'keyword', e.target.value); }}
                                      rows={2}
                                      className="w-full p-2.5 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 resize-none transition-all"/>
                                    <p className="text-[9px] text-gray-400 mt-1">* Перечислите значения через запятую</p>
                                  </div>
                                )}
                              </div>

                              {/* Модификаторы */}
                              <div onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1 mb-1.5">
                                  <p className="text-[9px] font-black text-gray-500 uppercase">Модификаторы</p>
                                  <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `modtip_${gIdx}_${cIdx}` ? null : `modtip_${gIdx}_${cIdx}`); }}
                                    className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                  {condTooltip === `modtip_${gIdx}_${cIdx}` && (
                                    <div className="absolute z-50 mt-1 w-52 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl leading-relaxed">
                                      Модификаторы изменяют поведение проверки. «Не учитывать регистр» позволяет реагировать на «Привет» и «привет» одинаково.
                                    </div>
                                  )}
                                </div>
                                <div className="relative">
                                  <button onClick={() => setCondOpenDropdown(condOpenDropdown === modKey ? null : modKey)}
                                    className="w-full flex items-center justify-between px-3 py-2 bg-white border-2 border-gray-200 rounded-xl text-sm hover:border-gray-300 transition-all">
                                    <div className="flex items-center gap-1.5 flex-1 flex-wrap">
                                      {cond.modifier === 'nocase' ? (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-lg text-[10px] font-bold text-gray-600">
                                          Не учитывать регистр
                                          <button onClick={e => { e.stopPropagation(); updCond(gIdx, cIdx, 'modifier', ''); }} className="ml-0.5 text-gray-400 hover:text-gray-700 leading-none">×</button>
                                        </span>
                                      ) : <span className="text-gray-400 text-sm font-medium">—</span>}
                                    </div>
                                    <ChevronDown size={13} className={`text-gray-400 flex-shrink-0 transition-transform ${condOpenDropdown === modKey ? 'rotate-180' : ''}`}/>
                                  </button>
                                  {condOpenDropdown === modKey && (
                                    <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                      <button onClick={() => { updCond(gIdx, cIdx, 'modifier', 'nocase'); setCondOpenDropdown(null); }}
                                        className={`w-full px-4 py-2.5 text-sm font-bold text-left transition-all ${cond.modifier === 'nocase' ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                        Не учитывать регистр
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Инвертировать */}
                              <div className="space-y-1">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[11px] font-black text-gray-700">Инвертировать условие</span>
                                    <button onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `inv_${gIdx}_${cIdx}` ? null : `inv_${gIdx}_${cIdx}`); }}
                                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center hover:bg-blue-600">?</button>
                                  </div>
                                  <button onClick={() => updCond(gIdx, cIdx, 'inverted', !(cond.inverted||false))}
                                    className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${cond.inverted ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${cond.inverted ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                  </button>
                                </div>
                                <p className="text-[9px] text-gray-400 leading-relaxed">* Триггер будет работать наоборот. Бот будет реагировать, если условие не выполнено.</p>
                              </div>
                              </>)}

                            </div>
                          </div>
                          </div>
                          );
                        })}

                        {/* Добавить условие в эту группу */}
                        <button
                          onClick={() => { setCondPickerGroupIdx(gIdx); setCondPickerTab('message'); setCondPickerSearch(''); setShowCondPickerModal(true); }}
                          className="w-full py-2.5 border-2 border-dashed border-blue-200 rounded-xl text-blue-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-400 hover:text-blue-500 transition-all bg-blue-50/30 active:scale-[0.98]">
                          <PlusCircle size={12}/> Добавить условие
                        </button>
                      </div>
                    </div>
                  );
                })}

                {/* Добавить группу условий */}
                <button
                  onClick={addCondGroup}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-200 hover:text-blue-400 transition-all bg-white active:scale-[0.98]">
                  <PlusCircle size={11}/> Добавить группу условий
                </button>
              </div>{/* конец левой колонки */}

              {/* ─── Правая колонка: ДЕЙСТВИЯ ─── */}
              <div className="space-y-3">
                {/* Заголовок */}
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Действия</span>
                  <div className="relative">
                    <button
                      onClick={() => setCondTooltip(condTooltip === 'actions_block' ? null : 'actions_block')}
                      className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 active:scale-90 transition-all flex-shrink-0">
                      ?
                    </button>
                    {condTooltip === 'actions_block' && (
                      <div className="absolute left-0 top-6 w-64 bg-gray-900 text-white text-[11px] font-medium p-3 rounded-2xl shadow-xl z-50 leading-relaxed">
                        Действия — это что бот делает при срабатывании триггера. Можно добавить несколько групп: каждая группа имеет свой шанс выполнения.
                        <div className="absolute -top-1.5 left-2 w-3 h-3 bg-gray-900 rotate-45"/>
                      </div>
                    )}
                  </div>
                </div>

                {/* Группы действий */}
                {actionGroups.map((group, gIdx) => (
                  <div key={group.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm">
                    {/* Шапка группы */}
                    <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                      {/* Шестерёнка */}
                      <div className="relative">
                        <button
                          onClick={e => { e.stopPropagation(); setActGroupSettingsIdx(gIdx); }}
                          className="p-1 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <Settings size={12}/>
                        </button>
                      </div>
                      <span className="text-[10px] font-black text-gray-600 uppercase tracking-widest flex-1">
                        {actionGroups.length > 1 ? `Группа ${gIdx + 1}` : 'Действия'}
                        {group.probability < 100 && (
                          <span className="ml-1.5 text-[9px] font-black text-orange-500 bg-orange-50 px-1.5 py-0.5 rounded-full">{group.probability}%</span>
                        )}
                      </span>
                      <div className="flex items-center gap-0.5">
                        <button onClick={() => moveActionGroup(gIdx, -1)} disabled={gIdx === 0}
                          className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                          <ChevronUp size={14}/>
                        </button>
                        <button onClick={() => moveActionGroup(gIdx, 1)} disabled={gIdx === actionGroups.length - 1}
                          className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                          <ChevronDown size={14}/>
                        </button>
                        {actionGroups.length > 1 && (
                          <button onClick={() => removeActionGroup(gIdx)}
                            className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all ml-0.5">
                            <Trash2 size={12}/>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Действия внутри группы */}
                    <div className="p-2.5">
                      {group.actions.length === 0 && (
                        <div className="text-center py-4 text-gray-300 text-[11px] font-black uppercase tracking-widest">
                          Список пуст
                        </div>
                      )}
                      {group.actions.map((action, aIdx) => {
                        const actCfg = ACTION_TYPES.find(a => a.type === action.type) || ACTION_TYPES[0];
                        const variants = action.variants || [{ id: 1, text: '', media_type: 'none' }];
                        const curVarIdx = action.currentVariant || 0;
                        const curVar = variants[curVarIdx] || variants[0] || { text: '', media_type: 'none' };
                        const msgTab = action.msgTab || 'editor';
                        const settings = action.settings || {};
                        const keyboard = action.keyboard || [];
                        const replyDropKey = `reply_${gIdx}_${aIdx}`;

                        const updVar = (field, val) => updAction(gIdx, aIdx, 'variants',
                          variants.map((v, vi) => vi === curVarIdx ? {...v, [field]: val} : v));
                        const addVariant = () => {
                          updAction(gIdx, aIdx, 'variants', [...variants, { id: Date.now(), text: '', media_type: 'none' }]);
                          updAction(gIdx, aIdx, 'currentVariant', variants.length);
                        };
                        const deleteVariant = () => {
                          if (variants.length <= 1) return;
                          const newVars = variants.filter((_, vi) => vi !== curVarIdx);
                          updAction(gIdx, aIdx, 'variants', newVars);
                          updAction(gIdx, aIdx, 'currentVariant', Math.max(0, curVarIdx - 1));
                        };
                        const updSetting = (key, val) => updAction(gIdx, aIdx, 'settings', {...settings, [key]: val});

                        return (
                          <div key={action.id}>
                            {aIdx > 0 && (
                              <div className="flex justify-center my-3">
                                <div className={`flex flex-col items-center ${newActionIds.has(action.id) ? 'connector-insert' : ''}`}>
                                  <div className="w-2 h-2 rounded-full bg-blue-200 connector-dot-top"/>
                                  <div className="w-px h-6 bg-blue-100 connector-line"/>
                                  <div className="w-2 h-2 rounded-full bg-blue-200 connector-dot-bot"/>
                                </div>
                              </div>
                            )}
                            <div className="bg-white rounded-2xl border border-gray-200">
                            {/* Шапка: ⚙️ + "Действие N" + ↑↓🗑 */}
                            <div className="flex items-center gap-1.5 px-3 py-2 bg-gray-50 border-b border-gray-100 rounded-t-2xl overflow-hidden">
                              <button
                                onClick={() => { setActionSettingsPct(action.action_probability ?? 100); setActionSettingsModal({gIdx, aIdx}); }}
                                className="p-1 text-gray-400 hover:text-blue-500 active:scale-90 transition-all flex-shrink-0">
                                <Settings size={12}/>
                              </button>
                              <span className="text-[11px] font-black text-gray-700 flex-1">Действие {aIdx + 1}</span>
                              <div className="flex items-center gap-0">
                                <button onClick={() => moveActionInGroup(gIdx, aIdx, -1)} disabled={aIdx === 0}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                                  <ChevronUp size={14}/>
                                </button>
                                <button onClick={() => moveActionInGroup(gIdx, aIdx, 1)} disabled={aIdx === group.actions.length - 1}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 disabled:opacity-20 active:scale-90 transition-all">
                                  <ChevronDown size={14}/>
                                </button>
                                <button onClick={() => removeAction(gIdx, aIdx)}
                                  className="p-1 text-red-300 hover:text-red-500 active:scale-90 transition-all">
                                  <Trash2 size={11}/>
                                </button>
                              </div>
                            </div>

                            {/* Тело карточки */}
                            <div className="px-3 py-3 space-y-3">

                              {/* Тип действия — заголовок */}
                              <div className="flex items-center gap-1.5">
                                <span className="text-[12px] font-black text-gray-800">{actCfg.label}</span>
                                <div className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center">?</div>
                              </div>

                              {/* ── send_text / dm ── */}
                              {(action.type === 'send_text' || action.type === 'dm') && (
                                <div className="space-y-3">

                                  {/* ── Сообщение * ── */}
                                  <div>
                                    <p className="text-sm font-black text-gray-800 mb-2">
                                      {action.type === 'dm' ? 'Текст сообщения' : 'Сообщение'} <span className="text-red-400">*</span>
                                    </p>

                                    {/* Навигация вариантов */}
                                    <div className="flex items-center gap-2 mb-2">
                                      <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
                                        <button onClick={() => updAction(gIdx, aIdx, 'currentVariant', Math.max(0, curVarIdx - 1))}
                                          disabled={curVarIdx === 0}
                                          className="px-2.5 py-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-sm font-bold transition-colors">‹</button>
                                        <span className="text-xs font-black text-gray-700 px-2 border-x border-gray-200">{curVarIdx + 1} из {variants.length}</span>
                                        <button onClick={() => updAction(gIdx, aIdx, 'currentVariant', Math.min(variants.length - 1, curVarIdx + 1))}
                                          disabled={curVarIdx === variants.length - 1}
                                          className="px-2.5 py-1.5 text-gray-500 hover:text-gray-700 disabled:opacity-30 text-sm font-bold transition-colors">›</button>
                                      </div>
                                      <button onClick={addVariant}
                                        className="flex items-center gap-1.5 px-3 py-1.5 border border-blue-200 text-blue-600 rounded-lg text-xs font-black hover:bg-blue-50 transition-all active:scale-95 ml-auto">
                                        <PlusCircle size={11}/> Добавить вариант сообщения
                                      </button>
                                      {variants.length > 1 && (
                                        <button onClick={deleteVariant}
                                          className="p-1.5 text-red-300 hover:text-red-500 active:scale-90 transition-all">
                                          <Trash2 size={14}/>
                                        </button>
                                      )}
                                    </div>

                                    {/* Медиа область */}
                                    {(() => {
                                      const isUploading = mediaUploading && mediaUploading.gIdx===gIdx && mediaUploading.aIdx===aIdx && mediaUploading.varIdx===curVarIdx;
                                      const hasMedia = curVar.media_type && curVar.media_type !== 'none';
                                      const mediaPos = curVar.media_pos || 'above';
                                      const mediaPosKey = `mediaPos_${gIdx}_${aIdx}`;

                                      const pickFile = (accept) => {
                                        const inp = document.createElement('input');
                                        inp.type = 'file';
                                        inp.accept = accept;
                                        inp.onchange = async (e) => {
                                          const file = e.target.files?.[0];
                                          if (!file) return;
                                          setMediaUploading({gIdx, aIdx, varIdx: curVarIdx});
                                          try {
                                            const fd = new FormData();
                                            fd.append('file', file);
                                            const res = await fetch('/api/media/upload', { method: 'POST', body: fd });
                                            if (!res.ok) throw new Error(await res.text());
                                            const data = await res.json();
                                            updAction(gIdx, aIdx, 'variants',
                                              variants.map((v, vi) => vi === curVarIdx
                                                ? {...v, media_type: data.media_type, media_url: data.url, media_server_path: data.server_path}
                                                : v));
                                          } catch(err) {
                                            alert('Ошибка загрузки: ' + err.message);
                                          } finally {
                                            setMediaUploading(false);
                                          }
                                        };
                                        inp.click();
                                      };

                                      const MEDIA_TYPES = [
                                        { type:'photo',     label:'Изображение', icon:'🖼',  accept:'image/jpeg,image/png,image/webp', active:true  },
                                        { type:'video',     label:'Видео',        icon:'🎬',  accept:'video/mp4,video/quicktime',       active:true  },
                                        { type:'animation', label:'Анимация',     icon:'🎭',  accept:'image/gif',                       active:true  },
                                        { type:'voice',     label:'Голосовое',    icon:'🎤',  accept:'',                                active:false },
                                        { type:'audio',     label:'Аудио',        icon:'🎵',  accept:'',                                active:false },
                                        { type:'document',  label:'Документ',     icon:'📄',  accept:'',                                active:false },
                                      ];

                                      const typeLabel = { photo:'Изображение', video:'Видео', animation:'Анимация' };

                                      return (
                                        <div className="mb-2 space-y-2">
                                          {!hasMedia ? (
                                            <>
                                              <div style={{display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'6px'}}>
                                                {MEDIA_TYPES.map(m => (
                                                  <button key={m.type}
                                                    onClick={() => m.active && !isUploading && pickFile(m.accept)}
                                                    className={`relative flex flex-col items-center justify-center gap-1 py-3 border-2 rounded-xl text-xs font-bold transition-all active:scale-95
                                                      ${m.active ? 'border-gray-200 text-gray-600 hover:border-blue-300 hover:bg-blue-50' : 'border-dashed border-gray-200 text-gray-300 cursor-not-allowed'}`}>
                                                    <span className="text-xl">{m.icon}</span>
                                                    <span>{m.label}</span>
                                                    {!m.active && <span className="absolute top-1 right-1 text-[7px] font-black bg-amber-100 text-amber-500 px-1 py-0.5 rounded-full uppercase">Скоро</span>}
                                                  </button>
                                                ))}
                                                {/* Расположение */}
                                                <button
                                                  onClick={() => setActOpenDropdown(actOpenDropdown === mediaPosKey ? null : mediaPosKey)}
                                                  className={`relative flex flex-col items-center justify-center gap-1 py-3 border-2 rounded-xl text-xs font-bold transition-all active:scale-95
                                                    ${actOpenDropdown === mediaPosKey ? 'border-blue-400 bg-blue-50 text-blue-600' : 'border-gray-200 text-gray-600 hover:border-blue-300 hover:bg-blue-50'}
                                                    ${mediaPos !== 'above' ? 'border-blue-300' : ''}`}>
                                                  <span className="text-xl">📐</span>
                                                  <span>Расположение</span>
                                                  {mediaPos !== 'above' && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-400 rounded-full"/>}
                                                </button>
                                              </div>
                                              {actOpenDropdown === mediaPosKey && (
                                                <div className="border border-gray-200 rounded-xl overflow-hidden">
                                                  {[
                                                    { v:'above', icon:'🖼', l:'Медиа над текстом',      desc:'Сначала медиа, текст идёт подписью снизу (одно сообщение)' },
                                                    { v:'below', icon:'📝', l:'Медиа под текстом',      desc:'Сначала текст, потом медиа отдельным сообщением' },
                                                    { v:'reply', icon:'💬', l:'Текст реплаем на медиа', desc:'Медиа отдельно → текст как ответ на него (стиль ChatKeeper, голубая полоса слева)' },
                                                  ].map(o => (
                                                    <button key={o.v}
                                                      onClick={() => { updAction(gIdx,aIdx,'variants',variants.map((v,vi)=>vi===curVarIdx?{...v,media_pos:o.v}:v)); setActOpenDropdown(null); }}
                                                      className={`w-full px-4 py-3 text-left border-b border-gray-50 last:border-0 transition-all flex items-start gap-3 ${mediaPos===o.v?'bg-blue-50':'hover:bg-gray-50'}`}>
                                                      <span className="text-lg mt-0.5">{o.icon}</span>
                                                      <div>
                                                        <p className={`text-sm font-bold ${mediaPos===o.v?'text-blue-600':'text-gray-700'}`}>{o.l}</p>
                                                        <p className="text-[10px] text-gray-400 font-medium mt-0.5">{o.desc}</p>
                                                      </div>
                                                      {mediaPos===o.v && <span className="ml-auto text-blue-500 text-sm">✓</span>}
                                                    </button>
                                                  ))}
                                                </div>
                                              )}
                                              {isUploading && (
                                                <div className="flex items-center justify-center gap-2 py-3 border-2 border-dashed border-blue-200 rounded-xl">
                                                  <span className="animate-spin text-xl">⏳</span>
                                                  <span className="text-sm text-blue-500 font-semibold">Загрузка...</span>
                                                </div>
                                              )}
                                            </>
                                          ) : (
                                            <>
                                              <div className="w-full rounded-xl overflow-hidden border border-gray-200 bg-gray-50 relative group">
                                                {curVar.media_type === 'photo' ? (
                                                  <img src={curVar.media_url} alt="preview" className="w-full max-h-48 object-contain"/>
                                                ) : curVar.media_type === 'video' ? (
                                                  <video src={curVar.media_url} className="w-full max-h-48 object-contain" controls={false} muted/>
                                                ) : (
                                                  <img src={curVar.media_url} alt="gif" className="w-full max-h-48 object-contain"/>
                                                )}
                                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center gap-3">
                                                  <button onClick={e=>{e.stopPropagation();pickFile('image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime');}}
                                                    className="px-3 py-1.5 bg-white text-gray-800 rounded-lg text-xs font-bold shadow">Заменить</button>
                                                  <button onClick={e=>{e.stopPropagation();updAction(gIdx,aIdx,'variants',variants.map((v,vi)=>vi===curVarIdx?{...v,media_type:'none',media_url:'',media_server_path:''}:v));}}
                                                    className="px-3 py-1.5 bg-red-500 text-white rounded-lg text-xs font-bold shadow">Удалить</button>
                                                </div>
                                                <span className="absolute top-1.5 left-1.5 text-[9px] font-black text-white bg-black/50 px-1.5 py-0.5 rounded uppercase">
                                                  {typeLabel[curVar.media_type] || curVar.media_type}
                                                </span>
                                              </div>
                                              {/* Расположение после загрузки */}
                                              <div className="flex gap-1.5">
                                                {[
                                                  { v:'above', l:'🖼 Над' },
                                                  { v:'below', l:'📝 Под' },
                                                  { v:'reply', l:'💬 Реплаем' },
                                                ].map(o => (
                                                  <button key={o.v}
                                                    onClick={() => updAction(gIdx,aIdx,'variants',variants.map((v,vi)=>vi===curVarIdx?{...v,media_pos:o.v}:v))}
                                                    className={`flex-1 py-2 rounded-xl text-[11px] font-bold transition-all border-2 ${mediaPos===o.v?'border-blue-400 bg-blue-50 text-blue-600':'border-gray-200 text-gray-500 hover:border-blue-200'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            </>
                                          )}
                                        </div>
                                      );
                                    })()}

                                    {/* Топики + вкладки + редактор */}
                                    <div className="border border-gray-200 rounded-xl">
                                      {/* Строка вкладок */}
                                      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200 rounded-t-xl">
                                        <div className="flex items-center gap-1.5">
                                          {/* Топик-пикер */}
                                          {(() => {
                                            const topicDropKey = `topic_${gIdx}_${aIdx}`;
                                            const isOpen = actOpenDropdown === topicDropKey;
                                            const selectedTopic = action.target_thread_id
                                              ? topics.find(t => t.thread_id === action.target_thread_id)
                                              : null;
                                            const openTopicDrop = () => {
                                              if (!topicsLoaded) {
                                                fetch('/api/topics').then(r=>r.json()).then(data=>{
                                                  setTopics(Array.isArray(data)?data:[]);
                                                  setTopicsLoaded(true);
                                                }).catch(()=>setTopicsLoaded(true));
                                              }
                                              setActOpenDropdown(isOpen ? null : topicDropKey);
                                            };
                                            return (
                                              <div className="relative">
                                                <button onClick={openTopicDrop}
                                                  className={`flex items-center gap-1 text-xs font-black rounded-lg px-2 py-1 transition-all ${action.target_thread_id ? 'bg-blue-100 text-blue-600' : 'text-gray-500 hover:bg-gray-100'}`}>
                                                  <span>📋</span>
                                                  <span className="max-w-[80px] truncate">{selectedTopic ? selectedTopic.name : 'Топик'}</span>
                                                  {action.target_thread_id && (
                                                    <span onClick={e=>{e.stopPropagation();updAction(gIdx,aIdx,'target_thread_id',null);}}
                                                      className="ml-0.5 text-blue-400 hover:text-red-500">×</span>
                                                  )}
                                                </button>
                                                {isOpen && (
                                                  <div className="absolute top-full left-0 z-[600] bg-white border border-gray-200 rounded-xl shadow-xl mt-1 min-w-[200px] max-h-60 overflow-y-auto">
                                                    <div className="px-3 py-2 border-b border-gray-100">
                                                      <span className="text-[10px] font-black text-gray-400 uppercase">Ветки группы</span>
                                                    </div>
                                                    {!topicsLoaded ? (
                                                      <div className="px-4 py-3 text-xs text-gray-400">Загрузка...</div>
                                                    ) : topics.length === 0 ? (
                                                      <div className="px-4 py-3 text-xs text-gray-400">Ветки не найдены</div>
                                                    ) : (
                                                      <>
                                                        <button onClick={()=>{updAction(gIdx,aIdx,'target_thread_id',null);setActOpenDropdown(null);}}
                                                          className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 transition-all ${!action.target_thread_id?'text-blue-600 bg-blue-50':'text-gray-600 hover:bg-gray-50'}`}>
                                                          Автоматически
                                                        </button>
                                                        {topics.map(t => (
                                                          <button key={t.thread_id}
                                                            onClick={()=>{updAction(gIdx,aIdx,'target_thread_id',t.thread_id);setActOpenDropdown(null);}}
                                                            className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${action.target_thread_id===t.thread_id?'text-blue-600 bg-blue-50':'text-gray-600 hover:bg-gray-50'}`}>
                                                            {t.is_main ? '🏠 ' : '📌 '}{t.name}
                                                          </button>
                                                        ))}
                                                      </>
                                                    )}
                                                  </div>
                                                )}
                                              </div>
                                            );
                                          })()}
                                        </div>
                                        <div className="flex gap-0.5">
                                          {[
                                            { v:'editor',   l:'✏ Редактор' },
                                            { v:'code',     l:'<> Код'     },
                                            { v:'settings', l:'⚙ Настройки'},
                                          ].map(t => (
                                            <button key={t.v} onClick={() => updAction(gIdx, aIdx, 'msgTab', t.v)}
                                              className={`px-2.5 py-1 text-[11px] font-black rounded transition-all ${msgTab===t.v ? 'bg-blue-500 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
                                              {t.l}
                                            </button>
                                          ))}
                                        </div>
                                      </div>

                                      {/* Редактор — WYSIWYG */}
                                      {msgTab === 'editor' && (() => {
                                        const ceId = `ce_${gIdx}_${aIdx}_${curVarIdx}`;

                                        // execCommand-форматирование (bold/italic/underline/strikeThrough)
                                        const execFmt = (cmd) => {
                                          const el = document.getElementById(ceId);
                                          if (!el) return;
                                          el.focus();
                                          document.execCommand(cmd, false, null);
                                          updVar('text', el.innerHTML);
                                        };

                                        // Вставка произвольного HTML-тега вокруг выделения
                                        const insertCustomTag = (open, close) => {
                                          const el = document.getElementById(ceId);
                                          if (!el) return;
                                          el.focus();
                                          const sel = window.getSelection();
                                          if (!sel || !sel.rangeCount) return;
                                          const range = sel.getRangeAt(0);
                                          const text = range.toString() || '\u200B';
                                          const tmp = document.createElement('div');
                                          tmp.innerHTML = open + text + close;
                                          const frag = document.createDocumentFragment();
                                          let last;
                                          while (tmp.firstChild) last = frag.appendChild(tmp.firstChild);
                                          range.deleteContents();
                                          range.insertNode(frag);
                                          if (last) {
                                            const r2 = document.createRange();
                                            r2.setStartAfter(last);
                                            r2.collapse(true);
                                            sel.removeAllRanges();
                                            sel.addRange(r2);
                                          }
                                          setTimeout(() => updVar('text', el.innerHTML), 0);
                                        };

                                        // Ссылка
                                        const insertLink = () => {
                                          const el = document.getElementById(ceId);
                                          if (!el) return;
                                          const url = window.prompt('Введите URL:');
                                          if (!url) return;
                                          el.focus();
                                          document.execCommand('createLink', false, url);
                                          // Убираем target="_blank" который браузер может добавить
                                          el.querySelectorAll('a').forEach(a => a.removeAttribute('target'));
                                          updVar('text', el.innerHTML);
                                        };

                                        // Очистить теги в выделении
                                        const clearFmt = () => {
                                          const el = document.getElementById(ceId);
                                          if (!el) return;
                                          el.focus();
                                          const sel = window.getSelection();
                                          if (!sel || !sel.rangeCount) return;
                                          const range = sel.getRangeAt(0);
                                          const text = range.toString();
                                          range.deleteContents();
                                          range.insertNode(document.createTextNode(text));
                                          setTimeout(() => updVar('text', el.innerHTML), 0);
                                        };

                                        const TOOLBAR = [
                                          { l:'B',  cmd:'bold',          cls:'font-black',      tip:'Жирный' },
                                          { l:'I',  cmd:'italic',        cls:'italic',          tip:'Курсив' },
                                          { l:'S',  cmd:'strikeThrough', cls:'line-through',    tip:'Зачёркнутый' },
                                          { l:'U',  cmd:'underline',     cls:'underline',       tip:'Подчёркнутый' },
                                          { l:'<>', custom:()=>insertCustomTag('<code>','</code>'),            cls:'font-mono text-[9px]', tip:'Моноширинный / код' },
                                          { l:'»',  custom:()=>insertCustomTag('<blockquote>','</blockquote>'),cls:'',                    tip:'Цитата' },
                                          { l:'🔗', custom:insertLink,                                         cls:'',                    tip:'Ссылка' },
                                          { l:'✒',  custom:()=>insertCustomTag('<tg-spoiler>','</tg-spoiler>'), cls:'',                    tip:'Спойлер' },
                                          { l:'Tx', custom:clearFmt,                                           cls:'text-[9px]',           tip:'Очистить форматирование' },
                                        ];

                                        const textLen = (curVar.text||'').replace(/<[^>]+>/g,'').length;

                                        return (
                                          <div>
                                            <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-gray-100 flex-wrap">
                                              {TOOLBAR.map(f => {
                                                const isActive = f.cmd ? fmtState[f.cmd] : false;
                                                return (
                                                  <button key={f.l}
                                                    title={f.tip}
                                                    onMouseDown={e => { e.preventDefault(); f.cmd ? execFmt(f.cmd) : f.custom(); }}
                                                    className={`w-7 h-7 text-[11px] rounded flex items-center justify-center transition-all active:scale-90 ${f.cls} ${isActive ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}>
                                                    {f.l}
                                                  </button>
                                                );
                                              })}
                                              {/* ── Emoji picker ── */}
                                              {(() => {
                                                const emojiKey = `emoji_${gIdx}_${aIdx}_${curVarIdx}`;
                                                const emojiOpen = actOpenDropdown === emojiKey;
                                                const EMOJIS = ['😀','😂','😍','🥰','😎','🤔','👍','👎','🙏','🔥','❤️','💯','🎉','😊','😭','🤣','😱','😴','💪','✅','❌','⚠️','💡','📌','🚀','👋','🌟','💬','🎯','⭐','🏆','🔑','💎','🍀','🎵'];
                                                const insertEmoji = (emoji) => {
                                                  const el = document.getElementById(ceId);
                                                  if (!el) return;
                                                  el.focus();
                                                  document.execCommand('insertText', false, emoji);
                                                  updVar('text', el.innerHTML);
                                                  setActOpenDropdown(null);
                                                };
                                                return (
                                                  <div className="relative">
                                                    <button
                                                      title="Эмодзи"
                                                      onMouseDown={e => { e.preventDefault(); setActOpenDropdown(emojiOpen ? null : emojiKey); }}
                                                      className={`w-7 h-7 text-[13px] rounded flex items-center justify-center transition-all active:scale-90 ${emojiOpen ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}>
                                                      😊
                                                    </button>
                                                    {emojiOpen && (
                                                      <div className="absolute left-0 top-8 z-[700] bg-white border border-gray-200 rounded-xl shadow-xl p-1.5 gap-0.5" style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',width:'220px'}}>
                                                        {EMOJIS.map(em => (
                                                          <button key={em}
                                                            onMouseDown={ev => { ev.preventDefault(); insertEmoji(em); }}
                                                            className="w-7 h-7 text-base flex items-center justify-center rounded hover:bg-gray-100 transition-all active:scale-90">
                                                            {em}
                                                          </button>
                                                        ))}
                                                      </div>
                                                    )}
                                                  </div>
                                                );
                                              })()}
                                              {/* ── Кнопка %плейсхолдеры% с выпадающим списком ── */}
                                              {(() => {
                                                const phKey = `${gIdx}_${aIdx}_${curVarIdx}`;
                                                const phOpen = phDropdown === phKey;

                                                const PH_GROUPS = [
                                                  { label:'Инициатор', color:'blue', items:[
                                                    { key:'user_name',     label:'Имя' },
                                                    { key:'user_username', label:'@username' },
                                                    { key:'user_id',       label:'ID' },
                                                    { key:'act_tgun',      label:'Имя TG' },
                                                    { key:'act_nn',        label:'@nick (новый)' },
                                                  ]},
                                                  { label:'Цель', color:'purple', items:[
                                                    { key:'target_name',     label:'Имя цели' },
                                                    { key:'target_username', label:'@username цели' },
                                                    { key:'target_id',       label:'ID цели' },
                                                  ]},
                                                  { label:'Чат', color:'green', items:[
                                                    { key:'chat_name', label:'Название чата' },
                                                    { key:'date',      label:'Дата' },
                                                    { key:'time',      label:'Время' },
                                                  ]},
                                                  { label:'Статистика', color:'amber', items:[
                                                    { key:'act_msg',   label:'Сообщений всего' },
                                                    { key:'act_msg_t', label:'Сегодня' },
                                                    { key:'act_msg_w', label:'За неделю' },
                                                    { key:'act_msg_m', label:'За месяц' },
                                                    { key:'act_blns',  label:'Пульсы' },
                                                    { key:'act_d',     label:'Дней в чате' },
                                                    { key:'act_plc',   label:'Место в топе' },
                                                    { key:'act_rnk',   label:'Ранг' },
                                                  ]},
                                                  { label:'Санкции', color:'red', items:[
                                                    { key:'warn_count', label:'Предупреждений' },
                                                    { key:'act_w',      label:'Предупр. (новый)' },
                                                  ]},
                                                  { label:'Анкета', color:'pink', items:[
                                                    { key:'act_form', label:'Полная анкета' },
                                                    { key:'act_un',   label:'Имя из анкеты' },
                                                    { key:'act_city', label:'Город' },
                                                    { key:'act_yo',   label:'Возраст' },
                                                    { key:'act_sr',   label:'Роль' },
                                                  ]},
                                                ];

                                                const COLOR_MAP = {
                                                  blue:   'bg-blue-50 text-blue-600 hover:bg-blue-100 border-blue-100',
                                                  purple: 'bg-purple-50 text-purple-600 hover:bg-purple-100 border-purple-100',
                                                  green:  'bg-green-50 text-green-700 hover:bg-green-100 border-green-100',
                                                  amber:  'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-100',
                                                  red:    'bg-red-50 text-red-600 hover:bg-red-100 border-red-100',
                                                  pink:   'bg-pink-50 text-pink-600 hover:bg-pink-100 border-pink-100',
                                                };

                                                const openPh = () => {
                                                  // Сохраняем позицию курсора в редакторе
                                                  const sel = window.getSelection();
                                                  if (sel && sel.rangeCount) {
                                                    window._savedPhRange = sel.getRangeAt(0).cloneRange();
                                                  } else {
                                                    window._savedPhRange = null;
                                                  }
                                                  if (!phOpen) {
                                                    // Загружаем кастомные плейсхолдеры при открытии
                                                    fetch('/api/placeholders')
                                                      .then(r => r.json())
                                                      .then(data => setCustomPlaceholders(Array.isArray(data) ? data : []))
                                                      .catch(() => setCustomPlaceholders([]));
                                                  }
                                                  setPhDropdown(phOpen ? null : phKey);
                                                };

                                                const insertPh = (key) => {
                                                  const el = document.getElementById(ceId);
                                                  if (!el) return;
                                                  el.focus();
                                                  // Восстанавливаем сохранённую позицию
                                                  if (window._savedPhRange) {
                                                    const sel = window.getSelection();
                                                    sel.removeAllRanges();
                                                    sel.addRange(window._savedPhRange);
                                                    window._savedPhRange = null;
                                                  }
                                                  document.execCommand('insertText', false, `%${key}%`);
                                                  updVar('text', el.innerHTML);
                                                  setPhDropdown(null);
                                                };

                                                return (
                                                  <div className="ml-auto">
                                                    <button
                                                      onMouseDown={e => { e.preventDefault(); e.stopPropagation(); openPh(); }}
                                                      className={`px-2 py-1 text-[10px] font-bold border rounded-lg transition-all whitespace-nowrap ${phOpen ? 'bg-blue-500 text-white border-blue-500' : 'text-blue-500 border-blue-200 hover:bg-blue-50'}`}>
                                                      %плейсхолдеры%
                                                    </button>
                                                  </div>
                                                );
                                              })()}
                                              <div className="flex items-center gap-0.5 ml-1">
                                                <button
                                                  onMouseDown={e => { e.preventDefault(); setShowEditorHelp(true); }}
                                                  className="w-6 h-6 text-[10px] text-gray-400 hover:text-blue-500 font-black rounded hover:bg-blue-50 flex items-center justify-center transition-all">?</button>
                                                <button
                                                  onMouseDown={e => {
                                                    e.preventDefault();
                                                    setShowPreview({
                                                      text: curVar.text || '',
                                                      mediaUrl: curVar.media_url || '',
                                                      mediaType: curVar.media_type || 'none',
                                                      keyboard: keyboard,
                                                    });
                                                  }}
                                                  title="Предпросмотр"
                                                  className="w-6 h-6 text-[10px] text-gray-400 hover:text-blue-500 rounded hover:bg-blue-50 flex items-center justify-center transition-all">↗</button>
                                              </div>
                                            </div>
                                            <div className="relative">
                                              {!curVar.text && (
                                                <span className="absolute top-3 left-4 text-sm text-gray-300 italic pointer-events-none select-none">
                                                  Insert text here ...
                                                </span>
                                              )}
                                              <div
                                                key={`ce_${gIdx}_${aIdx}_${curVarIdx}`}
                                                id={ceId}
                                                contentEditable
                                                suppressContentEditableWarning
                                                ref={el => {
                                                  if (el) {
                                                    const html = curVar.text || '';
                                                    if (el.innerHTML !== html) el.innerHTML = html;
                                                  }
                                                }}
                                                onInput={e => updVar('text', e.currentTarget.innerHTML)}
                                                className="w-full min-h-[120px] px-4 py-3 text-sm font-medium text-gray-700 outline-none bg-white"
                                                style={{wordBreak:'break-word'}}
                                              />
                                              <span className="absolute bottom-2 right-3 text-[10px] text-blue-500 font-black bg-white px-1">{textLen}/4096</span>
                                            </div>
                                          </div>
                                        );
                                      })()}

                                      {/* Код */}
                                      {msgTab === 'code' && (
                                        <textarea
                                          value={curVar.text || ''}
                                          onChange={e => updVar('text', e.target.value)}
                                          placeholder="HTML код сообщения..."
                                          rows={6}
                                          className="w-full px-4 py-3 font-mono text-sm text-gray-700 outline-none resize-none bg-white"/>
                                      )}

                                      {/* Настройки */}
                                      {msgTab === 'settings' && (() => {
                                        const SETTING_HINTS = {
                                          delete_after:      'Сообщение бота будет удалено через указанное время. Оставьте "0", чтобы не удалять.',
                                          send_delayed:      'Сообщение будет отправлено через указанное время. Оставьте "0", чтобы отправлять без задержки.',
                                          pin:               'Если включить, отправленное сообщение автоматически закрепится в шапке чата.',
                                          disable_preview:   'В Telegram при добавлении ссылки прикрепляется превью. Включи — превью показано не будет.',
                                          disable_notify:    'Сообщение придёт без звука. Удобно в ночное время суток.',
                                          delete_previous:   'Предыдущее сообщение бота, связанное с этим триггером, будет удалено.',
                                          content_protection:'Защищает содержимое сообщения от пересылки и сохранения.',
                                        };
                                        const TIME_UNITS_SHORT = ['секунда','минута','час','день'];
                                        const TIME_UNITS_LONG  = ['секунда','минута','час','день','неделя','месяц'];

                                        const SETTINGS_CFG = [
                                          { key:'delete_after',      label:'Удалить сообщение через',        hasTime:true,  units:TIME_UNITS_SHORT, valKey:'delete_after_val',   unitKey:'delete_after_unit'  },
                                          { key:'send_delayed',      label:'Отправить с задержкой',          hasTime:true,  units:TIME_UNITS_LONG,  valKey:'send_delayed_val',   unitKey:'send_delayed_unit'  },
                                          { key:'pin',               label:'Закрепить сообщение',            hasTime:false },
                                          { key:'disable_preview',   label:'Откл. предпросмотр ссылок',      hasTime:false },
                                          { key:'disable_notify',    label:'Отключить уведомления',          hasTime:false },
                                          { key:'delete_previous',   label:'Удалять предыдущее сообщение',   hasTime:false },
                                          { key:'content_protection',label:'Защита контента',                hasTime:false },
                                        ];

                                        return (
                                          <div className="p-4 space-y-3">
                                            {SETTINGS_CFG.map(s => (
                                              <div key={s.key}>
                                                <div className="flex items-center justify-between gap-2">
                                                  <div className="flex items-center gap-1 min-w-0">
                                                    <span className="text-xs font-medium text-gray-700 leading-tight">{s.label}</span>
                                                    <button
                                                      onMouseDown={e => {
                                                        e.preventDefault();
                                                        const r = e.currentTarget.getBoundingClientRect();
                                                        setSettingHintPos({x: r.right + 10, y: r.top - 8});
                                                        setSettingHint(settingHint === s.key ? null : s.key);
                                                      }}
                                                      className={`w-4 h-4 rounded-full text-[9px] font-black flex items-center justify-center flex-shrink-0 transition-all ${settingHint===s.key?'bg-blue-500 text-white':'bg-blue-100 text-blue-500 hover:bg-blue-200'}`}>?</button>
                                                  </div>
                                                  <button onClick={() => updSetting(s.key, !settings[s.key])}
                                                    className={`relative w-10 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${settings[s.key] ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                                    <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${settings[s.key] ? 'left-[calc(100%-1.125rem)]' : 'left-0.5'}`}/>
                                                  </button>
                                                </div>

                                                {/* Инпут времени (для delete_after и send_delayed) */}
                                                {s.hasTime && settings[s.key] && (
                                                  <div className="flex gap-2 mt-2">
                                                    <input
                                                      type="number" min="0" max="9999"
                                                      value={settings[s.valKey] ?? 1}
                                                      onChange={e => updSetting(s.valKey, Math.max(0, parseInt(e.target.value)||0))}
                                                      className="w-20 px-2 py-1.5 text-sm font-bold text-gray-700 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-blue-300 transition-all text-center"
                                                    />
                                                    <div className="relative flex-1">
                                                      <select
                                                        value={settings[s.unitKey] ?? s.units[0]}
                                                        onChange={e => updSetting(s.unitKey, e.target.value)}
                                                        className="w-full px-3 py-1.5 text-sm font-bold text-gray-700 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-blue-300 appearance-none transition-all cursor-pointer">
                                                        {s.units.map(u => <option key={u} value={u}>{u}</option>)}
                                                      </select>
                                                      <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"/>
                                                    </div>
                                                  </div>
                                                )}
                                              </div>
                                            ))}
                                          </div>
                                        );
                                      })()}

                                      {/* Создать / Редактировать клавиатуру */}
                                      <div className="border-t border-gray-100 rounded-b-xl overflow-hidden">
                                        {keyboard.length === 0 ? (
                                          <button
                                            onClick={() => { setKbModalTarget({gIdx, aIdx}); setKbButtonType(null); setKbNewButton({}); setShowKeyboardModal(true); }}
                                            className="w-full py-3 text-sm font-bold text-gray-500 hover:bg-gray-50 flex items-center justify-center gap-2 transition-all active:scale-[0.99]">
                                            ✏️ Создать клавиатуру
                                          </button>
                                        ) : (
                                          <div>
                                            <div className="p-2 space-y-1.5">
                                              {keyboard.map((btn, bi) => (
                                                <div key={btn.id} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg border border-gray-100">
                                                  <GripVertical size={13} className="text-gray-300 cursor-grab flex-shrink-0"/>
                                                  <span className="text-base w-5 text-center">{btn.emoji || '○'}</span>
                                                  <span className="text-xs font-bold text-gray-700 flex-1 truncate">{btn.text || 'Текст кнопки'}</span>
                                                  <button onClick={() => updAction(gIdx, aIdx, 'keyboard', keyboard.filter((_,i)=>i!==bi))}
                                                    className="text-red-300 hover:text-red-500 text-lg leading-none">×</button>
                                                </div>
                                              ))}
                                            </div>
                                            <button
                                              onClick={() => { setKbModalTarget({gIdx, aIdx}); setKbButtonType(null); setKbNewButton({}); setShowKeyboardModal(true); }}
                                              className="w-full py-2.5 text-xs font-bold text-blue-500 hover:bg-blue-50 flex items-center justify-center gap-1.5 transition-all border-t border-gray-100">
                                              ✏️ Редактировать клавиатуру
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Отправить ответом — только для send_text */}
                                    {action.type === 'send_text' && (
                                      <div className="mt-3">
                                        <p className="text-sm font-black text-gray-800 mb-1.5">
                                          Отправить ответом <span className="text-red-400">*</span>
                                        </p>
                                        <div className="relative">
                                          <button onClick={() => setActOpenDropdown(actOpenDropdown === replyDropKey ? null : replyDropKey)}
                                            className="w-full flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm font-bold text-gray-700 hover:border-gray-300 transition-all">
                                            <span>{action.reply_target === 'initiator' ? 'Ответить реплаем автору' : action.reply_target === 'quoted' ? 'Ответить на цитируемое' : 'Без реплая (обычное сообщение)'}</span>
                                            <ChevronDown size={14} className={`text-gray-400 transition-transform ${actOpenDropdown === replyDropKey ? 'rotate-180' : ''}`}/>
                                          </button>
                                          {actOpenDropdown === replyDropKey && (
                                            <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                              {[{v:'none',l:'Без реплая (обычное сообщение)'},{v:'initiator',l:'Ответить реплаем автору'},{v:'quoted',l:'Ответить на цитируемое'}].map(o => (
                                                <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'reply_target', o.v); setActOpenDropdown(null); }}
                                                  className={`w-full px-4 py-3 text-sm font-bold text-left transition-all border-b border-gray-50 last:border-0 ${action.reply_target === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                  {o.l}
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* ── mute ── */}
                              {action.type === 'mute' && (() => {
                                const MUTE_TARGETS = [
                                  { v:'initiator', l:'Инициатор триггера' },
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'replied',   l:'Кому ответили' },
                                  { v:'command',   l:'Режим команды' },
                                ];
                                const MUTE_UNITS = [
                                  { v:'seconds', l:'секунда' },
                                  { v:'minutes', l:'минута'  },
                                  { v:'hours',   l:'час'     },
                                  { v:'days',    l:'день'    },
                                  { v:'weeks',   l:'неделя'  },
                                  { v:'months',  l:'месяц'   },
                                ];
                                const MUTE_TYPES = [
                                  { v:'all',     l:'Все сообщения'          },
                                  { v:'media',   l:'Медиа файлы'            },
                                  { v:'inline',  l:'Inline сообщения'       },
                                  { v:'invite',  l:'Возможность приглашать' },
                                  { v:'polls',   l:'Опросы'                 },
                                ];
                                const muteTarget    = action.mute_target     || 'initiator';
                                const muteTimeOn    = action.mute_time_enabled || false;
                                const muteTimeVal   = action.mute_time_value  ?? 1;
                                const muteTimeUnit  = action.mute_time_unit   || 'days';
                                const muteType      = action.mute_type        || 'all';

                                const muteTgtKey    = `muteTgt_${gIdx}_${aIdx}`;
                                const muteUnitKey   = `muteUnit_${gIdx}_${aIdx}`;
                                const muteTypeKey   = `muteType_${gIdx}_${aIdx}`;
                                const muteTgtGear   = `muteTgtGear_${gIdx}_${aIdx}`;
                                const muteTimeGear  = `muteTimeGear_${gIdx}_${aIdx}`;

                                const curTgt  = MUTE_TARGETS.find(o => o.v === muteTarget) || MUTE_TARGETS[0];
                                const curUnit = MUTE_UNITS.find(o => o.v === muteTimeUnit) || MUTE_UNITS[3];
                                const curType = MUTE_TYPES.find(o => o.v === muteType)     || MUTE_TYPES[0];

                                return (
                                  <div className="space-y-4">

                                    {/* На кого распространяется */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {muteTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTgtGear ? null : muteTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === muteTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'mute_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                                <button onClick={() => { updAction(gIdx, aIdx, 'mute_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTgtKey ? null : muteTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === muteTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === muteTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {MUTE_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Кол-во времени */}
                                    <div>
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                          <p className="text-sm font-black text-gray-800">
                                            Кол-во времени <span className="text-red-400">*</span>
                                          </p>
                                          {muteTimeOn && (
                                            <div className="relative">
                                              <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTimeGear ? null : muteTimeGear)}
                                                className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                                <Settings size={14}/>
                                              </button>
                                              {actOpenDropdown === muteTimeGear && (
                                                <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'mute_time_value', 1); updAction(gIdx, aIdx, 'mute_time_unit', 'days'); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                  </button>
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'mute_time_enabled', false); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                  </button>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                        {muteTimeOn ? (
                                          <button onClick={() => updAction(gIdx, aIdx, 'mute_time_enabled', false)}
                                            className="p-1.5 border border-gray-200 rounded-lg text-gray-400 hover:text-red-500 hover:border-red-200 active:scale-90 transition-all">
                                            <Ban size={14}/>
                                          </button>
                                        ) : (
                                          <button onClick={() => updAction(gIdx, aIdx, 'mute_time_enabled', true)}
                                            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-black text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-all active:scale-95">
                                            Включить
                                          </button>
                                        )}
                                      </div>
                                      {muteTimeOn && (
                                        <div className="flex gap-2 mt-2">
                                          <input type="number" min="1"
                                            value={muteTimeVal}
                                            onChange={e => updAction(gIdx, aIdx, 'mute_time_value', Math.max(1, parseInt(e.target.value)||1))}
                                            className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === muteUnitKey ? null : muteUnitKey)}
                                              className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 min-w-[110px] hover:border-blue-300 transition-all ${actOpenDropdown === muteUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                              <span className="flex-1">{curUnit.l}</span>
                                              <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteUnitKey ? 'rotate-180' : ''}`}/>
                                            </button>
                                            {actOpenDropdown === muteUnitKey && (
                                              <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[110px]">
                                                {MUTE_UNITS.map(o => (
                                                  <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_time_unit', o.v); setActOpenDropdown(null); }}
                                                    className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteTimeUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                    </div>

                                    {/* Тип ограничения */}
                                    <div>
                                      <p className="text-sm font-black text-gray-800 mb-1.5">Тип ограничения</p>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === muteTypeKey ? null : muteTypeKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === muteTypeKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curType.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === muteTypeKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === muteTypeKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {MUTE_TYPES.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'mute_type', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${muteType === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── ban ── */}
                              {action.type === 'ban' && (() => {
                                const BAN_TARGETS = [
                                  { v:'initiator', l:'Инициатор триггера' },
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'replied',   l:'Кому ответили' },
                                ];
                                const BAN_UNITS = [
                                  { v:'seconds', l:'секунда' },
                                  { v:'minutes', l:'минута'  },
                                  { v:'hours',   l:'час'     },
                                  { v:'days',    l:'день'    },
                                ];
                                const banTarget      = action.ban_target        || 'initiator';
                                const banTimeOn      = action.ban_time_enabled  || false;
                                const banTimeVal     = action.ban_time_value    ?? 1;
                                const banTimeUnit    = action.ban_time_unit     || 'hours';
                                const banRevokeMsgs  = action.ban_revoke_messages || false;

                                const banTgtKey     = `banTgt_${gIdx}_${aIdx}`;
                                const banUnitKey    = `banUnit_${gIdx}_${aIdx}`;
                                const banTgtGear    = `banTgtGear_${gIdx}_${aIdx}`;
                                const banTimeGear   = `banTimeGear_${gIdx}_${aIdx}`;
                                const banRevokeGear = `banRevokeGear_${gIdx}_${aIdx}`;

                                const curTgt  = BAN_TARGETS.find(o => o.v === banTarget) || BAN_TARGETS[0];
                                const curUnit = BAN_UNITS.find(o => o.v === banTimeUnit) || BAN_UNITS[2];

                                return (
                                  <div className="space-y-4">

                                    {/* На кого распространяется */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {banTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === banTgtGear ? null : banTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === banTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'ban_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === banTgtKey ? null : banTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === banTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === banTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === banTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {BAN_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'ban_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${banTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Временный бан */}
                                    <div>
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                          <p className="text-sm font-black text-gray-800">Временный бан</p>
                                          {banTimeOn && (
                                            <div className="relative">
                                              <button onClick={() => setActOpenDropdown(actOpenDropdown === banTimeGear ? null : banTimeGear)}
                                                className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                                <Settings size={14}/>
                                              </button>
                                              {actOpenDropdown === banTimeGear && (
                                                <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'ban_time_enabled', false); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                  </button>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                        {banTimeOn ? (
                                          <button onClick={() => updAction(gIdx, aIdx, 'ban_time_enabled', false)}
                                            className="p-1.5 border border-gray-200 rounded-lg text-gray-400 hover:text-red-500 hover:border-red-200 active:scale-90 transition-all">
                                            <Ban size={14}/>
                                          </button>
                                        ) : (
                                          <button onClick={() => updAction(gIdx, aIdx, 'ban_time_enabled', true)}
                                            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-black text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-all active:scale-95">
                                            Включить
                                          </button>
                                        )}
                                      </div>
                                      {banTimeOn && (
                                        <div className="flex gap-2 mt-2">
                                          <input type="number" min="1"
                                            value={banTimeVal}
                                            onChange={e => updAction(gIdx, aIdx, 'ban_time_value', Math.max(1, parseInt(e.target.value)||1))}
                                            className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === banUnitKey ? null : banUnitKey)}
                                              className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 min-w-[110px] hover:border-blue-300 transition-all ${actOpenDropdown === banUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                              <span className="flex-1">{curUnit.l}</span>
                                              <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === banUnitKey ? 'rotate-180' : ''}`}/>
                                            </button>
                                            {actOpenDropdown === banUnitKey && (
                                              <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[110px]">
                                                {BAN_UNITS.map(o => (
                                                  <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'ban_time_unit', o.v); setActOpenDropdown(null); }}
                                                    className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${banTimeUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                      {!banTimeOn && (
                                        <p className="text-[11px] text-gray-400 mt-1">Без ограничения по времени (перманентный бан)</p>
                                      )}
                                    </div>

                                    {/* Удалить сообщения за 24ч */}
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-medium text-gray-700">Удалить сообщения пользователя за 24ч</p>
                                        {banRevokeMsgs && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === banRevokeGear ? null : banRevokeGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === banRevokeGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'ban_revoke_messages', false); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <button onClick={() => updAction(gIdx, aIdx, 'ban_revoke_messages', !banRevokeMsgs)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${banRevokeMsgs ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${banRevokeMsgs ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── emoji ── */}
                              {action.type === 'emoji' && (() => {
                                const EMOJI_TARGETS = [
                                  { v:'initiator', l:'инициатора триггера'   },
                                  { v:'replied',   l:'на которое ответили'   },
                                ];
                                const TG_EMOJIS = [
                                  '👍','👎','❤️','🔥','🥰','👏','😁','🤔','🤯','😱',
                                  '🤬','😢','🎉','🤩','🤮','💩','🙏','👌','🕊','🤡',
                                  '🥱','🥴','😍','🐳','❤️‍🔥','🌚','🌭','💯','🤣','⚡',
                                  '🍌','🏆','💔','🤨','😐','🍓','🍾','💋','🖕','😈',
                                  '😴','😭','🤓','👻','👨‍💻','👀','🎃','🙈','😇','😂',
                                  '🤝','✍️','🤗','🫡','🎅','🎄','☃️','💅','🤪','🗿',
                                  '🆒','💘','🙉','🦄','😘','💊','🙊','😎','👾','🤷',
                                  '🫠',
                                ];
                                const emojiTarget  = action.emoji_target  || 'initiator';
                                // основной ключ — action.emoji; emoji_reaction оставлен как legacy-фолбэк для старых триггеров
                                const emojiReaction = action.emoji || action.emoji_reaction || '👍';
                                const emojiTgtKey  = `emojiTgt_${gIdx}_${aIdx}`;
                                const emojiPickKey = `emojiPick_${gIdx}_${aIdx}`;
                                const emojiTgtGear = `emojiTgtGear_${gIdx}_${aIdx}`;
                                const curTgt = EMOJI_TARGETS.find(o => o.v === emojiTarget) || EMOJI_TARGETS[0];

                                return (
                                  <div className="space-y-4">

                                    {/* Отметить эмодзи сообщение */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">Отметить эмодзи сообщение</p>
                                        {emojiTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === emojiTgtGear ? null : emojiTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === emojiTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'emoji_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === emojiTgtKey ? null : emojiTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === emojiTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === emojiTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === emojiTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {EMOJI_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'emoji_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${emojiTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Эмодзи */}
                                    <div>
                                      <p className="text-sm font-black text-gray-800 mb-1.5">Эмодзи</p>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === emojiPickKey ? null : emojiPickKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-lg hover:border-blue-300 transition-all ${actOpenDropdown === emojiPickKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{emojiReaction}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === emojiPickKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === emojiPickKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden max-h-52 overflow-y-auto">
                                            {TG_EMOJIS.map(em => (
                                              <button key={em} onClick={() => { updAction(gIdx, aIdx, 'emoji', em); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2 text-xl text-left border-b border-gray-50 last:border-0 transition-all hover:bg-gray-50 ${emojiReaction === em ? 'bg-blue-50' : ''}`}>
                                                {em}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── warn ── */}
                              {action.type === 'warn' && (() => {
                                const WARN_TARGETS = [
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'initiator', l:'Инициатор триггера'                 },
                                  { v:'replied',   l:'Кому ответили'                      },
                                  { v:'command',   l:'Режим команды'                      },
                                ];
                                const warnNotify  = action.warn_notify  ?? true;
                                const warnTarget  = action.warn_target  || 'initiator';
                                const warnCount   = action.warn_count   ?? 1;

                                const warnTgtKey    = `warnTgt_${gIdx}_${aIdx}`;
                                const warnNotifyGear = `warnNotifyGear_${gIdx}_${aIdx}`;
                                const warnTgtGear    = `warnTgtGear_${gIdx}_${aIdx}`;

                                const curTgt = WARN_TARGETS.find(o => o.v === warnTarget) || WARN_TARGETS[1];

                                return (
                                  <div className="space-y-4">

                                    {/* Отправлять уведомление */}
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-medium text-gray-700">Отправлять уведомление о предупреждении</p>
                                        {!warnNotify && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === warnNotifyGear ? null : warnNotifyGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === warnNotifyGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_notify', true); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <button onClick={() => updAction(gIdx, aIdx, 'warn_notify', !warnNotify)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${warnNotify ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${warnNotify ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                    {/* На кого */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {warnTarget !== 'initiator' && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === warnTgtGear ? null : warnTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === warnTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                                <button onClick={() => { updAction(gIdx, aIdx, 'warn_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <Ban size={11} className="text-gray-400"/> Отключить настройку
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === warnTgtKey ? null : warnTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === warnTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTgt.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === warnTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === warnTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {WARN_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'warn_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-4 py-2.5 text-sm font-bold text-left border-b border-gray-50 last:border-0 transition-all ${warnTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Кол-во */}
                                    <div className="flex items-center justify-between gap-3">
                                      <p className="text-sm font-black text-gray-800">
                                        Кол-во <span className="text-red-400">*</span>
                                      </p>
                                      <input type="number" min="1" max="999"
                                        value={warnCount}
                                        onChange={e => updAction(gIdx, aIdx, 'warn_count', Math.max(1, parseInt(e.target.value)||1))}
                                        className="w-20 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm text-center outline-none focus:border-blue-300 transition-all"/>
                                    </div>

                                    {/* Период варнов */}
                                    <div className="flex items-center justify-between gap-3">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-black text-gray-800">Период варнов</p>
                                        <span className="text-xs text-gray-400 font-normal">(дней, 0 = без сброса)</span>
                                      </div>
                                      <input type="number" min="0" max="365"
                                        value={action.warn_period ?? 0}
                                        onChange={e => updAction(gIdx, aIdx, 'warn_period', Math.max(0, parseInt(e.target.value)||0))}
                                        className="w-20 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm text-center outline-none focus:border-blue-300 transition-all"/>
                                    </div>

                                    {/* Длительность мута при достижении кол-ва */}
                                    <div className="flex items-center justify-between gap-3">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-black text-gray-800">Длительность мута</p>
                                        <span className="text-xs text-gray-400 font-normal">(минут, при эскалации)</span>
                                      </div>
                                      <input type="number" min="1" max="43200"
                                        value={Math.max(1, Math.floor((action.warn_mute_duration_seconds ?? 3600) / 60))}
                                        onChange={e => updAction(gIdx, aIdx, 'warn_mute_duration_seconds', Math.max(60, (parseInt(e.target.value)||1) * 60))}
                                        className="w-20 px-3 py-2 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm text-center outline-none focus:border-blue-300 transition-all"/>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── delete ── */}
                              {action.type === 'delete' && (() => {
                                const delTarget    = action.delete_target    || 'initiator';
                                const delDelay     = action.delete_delay     ?? 0;
                                const delDelayUnit = action.delete_delay_unit|| 'seconds';
                                const delTgtKey    = `delTgt_${gIdx}_${aIdx}`;
                                const delUnitKey   = `delUnit_${gIdx}_${aIdx}`;
                                const delGearKey   = `delGear_${gIdx}_${aIdx}`;
                                const isModified   = delTarget !== 'initiator';

                                const TARGET_OPTIONS = [
                                  { v:'both',      l:'Кому ответили и инициатор триггера' },
                                  { v:'initiator', l:'Инициатор триггера'                 },
                                  { v:'replied',   l:'Кому ответили'                      },
                                ];
                                const UNIT_OPTIONS = [
                                  { v:'seconds', l:'секунд' },
                                  { v:'minutes', l:'минут'  },
                                  { v:'hours',   l:'часов'  },
                                  { v:'days',    l:'дней'   },
                                ];
                                const curTarget = TARGET_OPTIONS.find(o => o.v === delTarget) || TARGET_OPTIONS[1];
                                const curUnit   = UNIT_OPTIONS.find(o => o.v === delDelayUnit) || UNIT_OPTIONS[0];

                                return (
                                  <div className="space-y-4">

                                    {/* На кого распространяется */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-black text-gray-800">
                                          На кого распространяется действие <span className="text-red-400">*</span>
                                        </p>
                                        {isModified && (
                                          <div className="relative">
                                            <button
                                              onClick={() => setActOpenDropdown(actOpenDropdown === delGearKey ? null : delGearKey)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === delGearKey && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-lg shadow-xl z-[500] overflow-hidden whitespace-nowrap">
                                                <button
                                                  onClick={() => { updAction(gIdx, aIdx, 'delete_target', 'initiator'); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button
                                          onClick={() => setActOpenDropdown(actOpenDropdown === delTgtKey ? null : delTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all ${actOpenDropdown === delTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span>{curTarget.l}</span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === delTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === delTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {TARGET_OPTIONS.map(o => (
                                              <button key={o.v}
                                                onClick={() => { updAction(gIdx, aIdx, 'delete_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-3 py-2 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${delTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Задержка */}
                                    <div>
                                      <p className="text-sm font-black text-gray-800 mb-1.5">
                                        Задержка <span className="text-red-400">*</span>
                                      </p>
                                      <div className="flex gap-2">
                                        <input
                                          type="number" min="0"
                                          value={delDelay}
                                          onChange={e => updAction(gIdx, aIdx, 'delete_delay', Math.max(0, parseInt(e.target.value)||0))}
                                          className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                        <div className="relative">
                                          <button
                                            onClick={() => setActOpenDropdown(actOpenDropdown === delUnitKey ? null : delUnitKey)}
                                            className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 hover:border-blue-300 transition-all min-w-[110px] ${actOpenDropdown === delUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                            <span className="flex-1">{curUnit.l}</span>
                                            <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === delUnitKey ? 'rotate-180' : ''}`}/>
                                          </button>
                                          {actOpenDropdown === delUnitKey && (
                                            <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[100px]">
                                              {UNIT_OPTIONS.map(o => (
                                                <button key={o.v}
                                                  onClick={() => { updAction(gIdx, aIdx, 'delete_delay_unit', o.v); setActOpenDropdown(null); }}
                                                  className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${delDelayUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                  {o.l}
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                              {/* ── pin ── */}
                              {action.type === 'pin' && (() => {
                                const pinTimeEnabled = action.pin_time_enabled || false;
                                const pinTimeValue   = action.pin_time_value   ?? 10;
                                const pinTimeUnit    = action.pin_time_unit    || 'seconds';
                                const pinNotify      = action.pin_notify       || false;
                                const pinTarget      = action.pin_target       || '';
                                const pinUnitKey     = `pinUnit_${gIdx}_${aIdx}`;
                                const pinTgtKey      = `pinTgt_${gIdx}_${aIdx}`;
                                const pinNotifyGear  = `pinNotifyGear_${gIdx}_${aIdx}`;
                                const pinTgtGear     = `pinTgtGear_${gIdx}_${aIdx}`;
                                const pinTimeGear    = `pinTimeGear_${gIdx}_${aIdx}`;

                                const PIN_UNITS = [
                                  { v:'seconds', l:'секунд'  },
                                  { v:'minutes', l:'минут'   },
                                  { v:'hours',   l:'часов'   },
                                  { v:'days',    l:'дней'    },
                                  { v:'weeks',   l:'недель'  },
                                  { v:'months',  l:'месяцев' },
                                ];
                                const PIN_TARGETS = [
                                  { v:'initiator', l:'инициатора триггера' },
                                  { v:'replied',   l:'на которое ответили' },
                                ];
                                const curUnit   = PIN_UNITS.find(o => o.v === pinTimeUnit)   || PIN_UNITS[0];
                                const curTarget = PIN_TARGETS.find(o => o.v === pinTarget);

                                return (
                                  <div className="space-y-4">

                                    {/* Автозакреп ответа бота (trigger-level) */}
                                    <div className="flex items-center justify-between bg-emerald-50 -mx-1 px-3 py-2.5 rounded-xl border border-emerald-100">
                                      <div className="flex flex-col">
                                        <p className="text-sm font-black text-emerald-700">Автозакреп ответа бота</p>
                                        <p className="text-[10px] text-emerald-500 font-semibold">Закрепить сообщение-ответ бота после отправки</p>
                                      </div>
                                      <button onClick={() => upd('auto_pin', editingTrigger.auto_pin ? 0 : 1)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${editingTrigger.auto_pin ? 'bg-emerald-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${editingTrigger.auto_pin ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                    {/* Через какое время открепить */}
                                    <div>
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                          <p className="text-sm font-medium text-gray-700">Через какое время открепить</p>
                                          {pinTimeEnabled && (
                                            <div className="relative">
                                              <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTimeGear ? null : pinTimeGear)}
                                                className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                                <Settings size={14}/>
                                              </button>
                                              {actOpenDropdown === pinTimeGear && (
                                                <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                  <button onClick={() => { updAction(gIdx, aIdx, 'pin_time_enabled', false); updAction(gIdx, aIdx, 'pin_time_value', 10); updAction(gIdx, aIdx, 'pin_time_unit', 'seconds'); setActOpenDropdown(null); }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                    <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                  </button>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                        {pinTimeEnabled ? (
                                          <button onClick={() => updAction(gIdx, aIdx, 'pin_time_enabled', false)}
                                            className="p-1.5 border border-gray-200 rounded-lg text-gray-400 hover:text-red-500 hover:border-red-200 active:scale-90 transition-all">
                                            <Ban size={14}/>
                                          </button>
                                        ) : (
                                          <button onClick={() => updAction(gIdx, aIdx, 'pin_time_enabled', true)}
                                            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-black text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-all active:scale-95">
                                            Включить
                                          </button>
                                        )}
                                      </div>
                                      {pinTimeEnabled && (
                                        <div className="flex gap-2 mt-2">
                                          <input type="number" min="1"
                                            value={pinTimeValue}
                                            onChange={e => updAction(gIdx, aIdx, 'pin_time_value', Math.max(1, parseInt(e.target.value)||1))}
                                            className="flex-1 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinUnitKey ? null : pinUnitKey)}
                                              className={`flex items-center gap-2 px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-700 min-w-[110px] hover:border-blue-300 transition-all ${actOpenDropdown === pinUnitKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                              <span className="flex-1">{curUnit.l}</span>
                                              <ChevronDown size={13} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === pinUnitKey ? 'rotate-180' : ''}`}/>
                                            </button>
                                            {actOpenDropdown === pinUnitKey && (
                                              <div className="absolute top-full right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden min-w-[100px]">
                                                {PIN_UNITS.map(o => (
                                                  <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'pin_time_unit', o.v); setActOpenDropdown(null); }}
                                                    className={`w-full px-3 py-1.5 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${pinTimeUnit === o.v ? 'text-blue-600 bg-blue-50 font-black' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                    {o.l}
                                                  </button>
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                    </div>

                                    {/* Уведомить участников чата */}
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5">
                                        <p className="text-sm font-medium text-gray-700">Уведомить участников чата</p>
                                        {pinNotify && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinNotifyGear ? null : pinNotifyGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === pinNotifyGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'pin_notify', false); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <button onClick={() => updAction(gIdx, aIdx, 'pin_notify', !pinNotify)}
                                        className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${pinNotify ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200 ${pinNotify ? 'left-[calc(100%-1.25rem)]' : 'left-1'}`}/>
                                      </button>
                                    </div>

                                    {/* Закрепить сообщение */}
                                    <div>
                                      <div className="flex items-center gap-1.5 mb-1.5">
                                        <p className="text-sm font-medium text-gray-700">Закрепить сообщение</p>
                                        {pinTarget && (
                                          <div className="relative">
                                            <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTgtGear ? null : pinTgtGear)}
                                              className="text-blue-400 hover:text-blue-600 active:scale-90 transition-all">
                                              <Settings size={14}/>
                                            </button>
                                            {actOpenDropdown === pinTgtGear && (
                                              <div className="absolute left-0 top-6 bg-white border border-gray-100 rounded-xl shadow-xl z-[500] whitespace-nowrap overflow-hidden">
                                                <button onClick={() => { updAction(gIdx, aIdx, 'pin_target', ''); setActOpenDropdown(null); }}
                                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 w-full">
                                                  <RotateCcw size={11} className="text-red-400"/> Отменить изменения
                                                </button>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      <div className="relative">
                                        <button onClick={() => setActOpenDropdown(actOpenDropdown === pinTgtKey ? null : pinTgtKey)}
                                          className={`w-full flex items-center justify-between px-4 py-3 bg-white border-2 rounded-xl text-sm font-bold text-gray-600 hover:border-blue-300 transition-all ${actOpenDropdown === pinTgtKey ? 'border-blue-300' : 'border-gray-200'}`}>
                                          <span className={curTarget ? 'text-gray-800' : 'text-gray-400'}>
                                            {curTarget ? curTarget.l : '-'}
                                          </span>
                                          <ChevronDown size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${actOpenDropdown === pinTgtKey ? 'rotate-180' : ''}`}/>
                                        </button>
                                        {actOpenDropdown === pinTgtKey && (
                                          <div className="absolute top-full left-0 right-0 z-[500] bg-white border border-gray-100 rounded-xl shadow-xl mt-1 overflow-hidden">
                                            {PIN_TARGETS.map(o => (
                                              <button key={o.v} onClick={() => { updAction(gIdx, aIdx, 'pin_target', o.v); setActOpenDropdown(null); }}
                                                className={`w-full px-3 py-2 text-xs font-bold text-left border-b border-gray-50 last:border-0 transition-all ${pinTarget === o.v ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`}>
                                                {o.l}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                  </div>
                                );
                              })()}

                            </div>

                            </div>
                          </div>
                        );
                      })}

                      {/* Добавить действие в группу — всегда видна (в т.ч. когда список пуст) */}
                      <button
                        onClick={() => { setActPickerGroupIdx(gIdx); setActPickerSearch(''); setShowActPickerModal(true); }}
                        className="w-full py-2.5 border-2 border-dashed border-blue-200 rounded-xl text-blue-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-400 hover:text-blue-500 transition-all bg-blue-50/30 active:scale-[0.98]">
                        <PlusCircle size={12}/> Добавить действие
                      </button>
                    </div>
                  </div>
                ))}

                {/* Добавить группу действий */}
                <button
                  onClick={addActionGroup}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-2xl text-gray-400 font-black text-[10px] uppercase flex items-center justify-center gap-1.5 hover:border-blue-200 hover:text-blue-400 transition-all bg-white active:scale-[0.98]">
                  <PlusCircle size={11}/> Добавить группу действий
                </button>
              </div>{/* конец правой колонки */}

              </div>{/* конец grid */}

              {/* ── МОДАЛ ВЫБОРА УСЛОВИЯ (full-screen overlay) ── */}
              {showCondPickerModal && (
                <div className="fixed inset-0 z-[200] flex flex-col" onClick={e => { if (e.target === e.currentTarget) setShowCondPickerModal(false); }}>
                  {/* Backdrop */}
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowCondPickerModal(false)}/>
                  {/* Panel */}
                  <div className="relative mt-auto bg-white rounded-t-[2rem] max-h-[85vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                    {/* Drag handle */}
                    <div className="flex justify-center pt-3 pb-1">
                      <div className="w-10 h-1 bg-gray-200 rounded-full"/>
                    </div>
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
                      <h3 className="font-black text-base text-gray-900">Выберите условие</h3>
                      <button onClick={() => setShowCondPickerModal(false)} className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={18}/>
                      </button>
                    </div>
                    {/* Signal tabs */}
                    <div className="flex border-b border-gray-100">
                      {[{v:'message',l:'Сообщение'},{v:'quoted',l:'Цитируемое'}].map(tab => (
                        <button key={tab.v} onClick={() => setCondPickerTab(tab.v)}
                          className={`flex-1 py-3 text-[11px] font-black uppercase tracking-wide transition-all border-b-2 ${condPickerTab===tab.v ? 'text-blue-600 border-blue-500' : 'text-gray-400 border-transparent'}`}>
                          {tab.l}
                        </button>
                      ))}
                    </div>
                    {/* Info box */}
                    <div className="mx-4 mt-3 px-4 py-3 bg-blue-50 border border-blue-100 rounded-2xl text-[11px] text-blue-700 font-medium leading-relaxed">
                      {condPickerTab === 'message'
                        ? '📨 Триггер проверит входящее сообщение участника чата по выбранному условию.'
                        : '↩️ Триггер проверит сообщение, на которое ответил пользователь (цитируемое).'}
                    </div>
                    {/* Search */}
                    <div className="px-4 mt-3">
                      <div className="relative">
                        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"/>
                        <input
                          type="text"
                          placeholder="Поиск условий..."
                          value={condPickerSearch}
                          onChange={e => setCondPickerSearch(e.target.value)}
                          className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                      </div>
                    </div>
                    {/* Conditions list */}
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                      {/* Секция: Условия по тексту */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">
                          Условия по {condPickerTab === 'message' ? 'сообщению' : 'цитируемому сообщению'}
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {/* Сообщение (any) */}
                          {(condPickerSearch === '' || 'сообщение любое'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, condPickerTab === 'message' ? 'message' : 'quoted')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">📩</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">
                                {condPickerTab === 'message' ? 'Сообщение' : 'Цитируемое'}
                              </span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Любое входящее сообщение</span>
                              {/* ⓘ tooltip */}
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `picker_any_${condPickerTab}` ? null : `picker_any_${condPickerTab}`); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === `picker_any_${condPickerTab}` && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {condPickerTab === 'message' ? COND_TOOLTIP_TEXT['msg_any'] : COND_TOOLTIP_TEXT['qmsg_any']}
                                </div>
                              )}
                            </button>
                          )}
                          {/* Слово в сообщении */}
                          {(condPickerSearch === '' || 'слово ключевое keyword'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, condPickerTab === 'message' ? 'message' : 'quoted')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">🔤</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">Слово в сообщении</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Реагирует на ключевые слова</span>
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === `picker_kw_${condPickerTab}` ? null : `picker_kw_${condPickerTab}`); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === `picker_kw_${condPickerTab}` && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {condPickerTab === 'message' ? COND_TOOLTIP_TEXT['msg_keyword'] : COND_TOOLTIP_TEXT['qmsg_keyword']}
                                </div>
                              )}
                            </button>
                          )}
                          {/* Тип ответа — только для message-таба */}
                          {condPickerTab === 'message' && (condPickerSearch === '' || 'тип ответа reply'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, 'message', 'reply_type')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">↩️</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">Тип ответа</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Реплай, первое сообщ., коммент...</span>
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === 'picker_rt' ? null : 'picker_rt'); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === 'picker_rt' && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {COND_TOOLTIP_TEXT['msg_reply_type']}
                                </div>
                              )}
                            </button>
                          )}
                          {/* Тип сообщения — только для message-таба */}
                          {condPickerTab === 'message' && (condPickerSearch === '' || 'тип сообщения формат медиа фото стикер'.includes(condPickerSearch.toLowerCase())) && (
                            <button
                              onClick={() => addConditionToGroup(condPickerGroupIdx, 'message', 'msg_type')}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                              <span className="text-xl">🗂</span>
                              <span className="text-[11px] font-black text-gray-800 leading-tight">Тип сообщения</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">Фото, видео, стикер, документ...</span>
                              <span className="absolute top-1.5 left-1.5 text-[8px] font-black bg-green-500 text-white px-1.5 py-0.5 rounded-full uppercase animate-pulse z-10">NEW</span>
                              <button
                                onClick={e => { e.stopPropagation(); setCondTooltip(condTooltip === 'picker_mt' ? null : 'picker_mt'); }}
                                className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none hover:bg-blue-600 z-10">
                                ?
                              </button>
                              {condTooltip === 'picker_mt' && (
                                <div className="absolute top-8 right-2 w-48 bg-gray-900 text-white text-[10px] font-medium p-2.5 rounded-xl shadow-xl z-20 leading-relaxed">
                                  {COND_TOOLTIP_TEXT['msg_msg_type']}
                                </div>
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Секция: Условия по параметрам */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">
                          Условия по параметрам сообщения
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { icon: '📎', label: 'Тип медиа', sub: 'Фото, видео, файл...' },
                            { icon: '👤', label: 'Автор', sub: 'ID или username' },
                            { icon: '💬', label: 'Длина текста', sub: 'Больше/меньше N символов' },
                            { icon: '🕐', label: 'Время отправки', sub: 'В заданный промежуток' },
                          ].map(item => (
                            <div key={item.label}
                              className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                              <span className="text-xl">{item.icon}</span>
                              <span className="text-[11px] font-black text-gray-500 leading-tight">{item.label}</span>
                              <span className="text-[9px] text-gray-400 font-medium leading-tight">{item.sub}</span>
                              <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                              <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── МОДАЛ НАСТРОЕК ГРУППЫ ДЕЙСТВИЙ (Шанс выполнения) ── */}
              {actGroupSettingsIdx !== null && (() => {
                const gIdx = actGroupSettingsIdx;
                const group = actionGroups[gIdx];
                if (!group) return null;
                return (
                  <div className="fixed inset-0 z-[400] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setActGroupSettingsIdx(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-xs p-5 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="font-black text-sm text-gray-900">Настройки группы {actionGroups.length > 1 ? gIdx + 1 : ''}</h3>
                        <button onClick={() => setActGroupSettingsIdx(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <div className="flex items-center gap-3 mb-4">
                        <label className="text-sm font-bold text-gray-600 flex-1">Шанс выполнения</label>
                        <div className="flex items-center gap-1.5 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                          <input
                            type="number" min="1" max="100"
                            value={group.probability}
                            onChange={e => updActionGroup(gIdx, 'probability', Math.min(100, Math.max(1, parseInt(e.target.value)||1)))}
                            className="w-12 text-center font-black text-sm bg-transparent outline-none"/>
                          <span className="text-xs font-black text-gray-400">%</span>
                        </div>
                      </div>
                      <button onClick={() => setActGroupSettingsIdx(null)}
                        className="w-full px-4 py-2.5 bg-blue-500 text-white rounded-xl font-black text-sm hover:bg-blue-600 active:scale-95 transition-all">
                        Готово
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* ── МОДАЛ ШЕСТЕРЁНКИ УСЛОВИЯ (Отменить изменения) ── */}
              {condGearModal && (() => {
                const { gIdx, cIdx } = condGearModal;
                const cond = conditionGroups[gIdx]?.conditions[cIdx];
                if (!cond) return null;
                return (
                  <div className="fixed inset-0 z-[400] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCondGearModal(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-xs p-5 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="font-black text-sm text-gray-900">Значения условия</h3>
                        <button onClick={() => setCondGearModal(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <button
                        onClick={() => { updCond(gIdx, cIdx, 'chips', []); setCondGearModal(null); }}
                        className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-red-500 hover:bg-red-50 rounded-2xl transition-all text-left">
                        <RotateCcw size={14}/> Отменить изменения
                      </button>
                      <button onClick={() => setCondGearModal(null)}
                        className="w-full mt-2 px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-black text-sm hover:bg-gray-200 active:scale-95 transition-all">
                        Закрыть
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* ── МОДАЛ НАСТРОЕК УСЛОВИЯ (ключ плейсхолдера) ── */}
              {condSettingsModal && (() => {
                const { gIdx, cIdx } = condSettingsModal;
                const cond = conditionGroups[gIdx]?.conditions[cIdx];
                if (!cond) return null;
                return (
                  <div className="fixed inset-0 z-[300] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCondSettingsModal(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between">
                        <h3 className="font-black text-base text-gray-900">Дополнительные настройки условия</h3>
                        <button onClick={() => setCondSettingsModal(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center gap-1.5">
                          <p className="text-sm font-black text-gray-700">Ключ плейсхолдера</p>
                          <div className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center">?</div>
                        </div>
                        <p className="text-red-400 text-[10px] font-bold">*</p>
                        <p className="text-[11px] text-gray-500 font-medium leading-relaxed">
                          Укажите ключ, который станет плейсхолдером и будет выводить в тексте условие сработки триггера.<br/>
                          <span className="text-gray-400">Пример: <span className="font-mono font-bold">words_list</span></span>
                        </p>
                        <p className="text-[11px] text-gray-500 font-medium leading-relaxed">
                          Поместите этот ключ между <span className="font-mono font-bold text-purple-600">%%</span> и добавьте его в текст действия «Отправить сообщение в чат».<br/>
                          <span className="text-gray-400">Пример: <span className="font-mono text-purple-600">%words_list%</span></span>
                        </p>
                        <input type="text"
                          value={cond.placeholder_key || ''}
                          onChange={e => updCond(gIdx, cIdx, 'placeholder_key', e.target.value)}
                          placeholder="words_list"
                          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-200 rounded-2xl font-mono font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                      </div>
                      <div className="flex gap-2 justify-end pt-1">
                        <button onClick={() => setCondSettingsModal(null)}
                          className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-black text-sm hover:bg-gray-200 active:scale-95 transition-all">
                          Отмена
                        </button>
                        <button onClick={() => setCondSettingsModal(null)}
                          className="px-5 py-2.5 bg-blue-500 text-white rounded-xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-95 transition-all">
                          Сохранить
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ── МОДАЛ ВЫБОРА ДЕЙСТВИЯ (full-screen overlay) ── */}
              {showActPickerModal && (
                <div className="fixed inset-0 z-[200] flex flex-col">
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowActPickerModal(false)}/>
                  <div className="relative mt-auto bg-white rounded-t-[2rem] max-h-[85vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                    <div className="flex justify-center pt-3 pb-1">
                      <div className="w-10 h-1 bg-gray-200 rounded-full"/>
                    </div>
                    <div className="flex items-start justify-between px-6 py-3 border-b border-gray-100">
                      <div>
                        <h3 className="font-black text-base text-gray-900">Выберите действия</h3>
                        <p className="text-[10px] text-gray-400 font-medium mt-0.5">Укажите реакцию бота на выполненное условие</p>
                      </div>
                      <button onClick={() => setShowActPickerModal(false)} className="p-2 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={18}/>
                      </button>
                    </div>
                    <div className="px-4 mt-3">
                      <div className="relative">
                        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"/>
                        <input type="text" placeholder="Поиск действий..." value={actPickerSearch}
                          onChange={e => setActPickerSearch(e.target.value)}
                          className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold outline-none focus:border-blue-300 transition-all"/>
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
                      {/* Секция 1: Действия с сообщениями */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Действия с сообщениями</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'send_text', icon:'📤', label:'Отправить сообщение в чат', sub:'Ответить сообщением', active:true  },
                            { type:'delete',    icon:'🗑',  label:'Удалить сообщение', sub:'Удалить триггер-сообщение', active:true  },
                            { type:'dm',        icon:'✉️',  label:'Личное сообщение',  sub:'Написать пользователю в ЛС',active:true  },
                            { type:'pin',       icon:'📌',  label:'Закрепить',          sub:'Закрепить сообщение',      active:true  },
                            { type:'unpin',     icon:'📍',  label:'Открепить',          sub:'Открепить сообщение',      active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                      {/* Секция 2: Действия по пользователям */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Действия по пользователям</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'mute',   icon:'🔇', label:'Запретить писать', sub:'Мут на время',        active:true  },
                            { type:'ban',    icon:'🚫', label:'Заблокировать',     sub:'Бан из чата',         active:true  },
                            { type:'kick',   icon:'👢', label:'Удалить из чата',   sub:'Кик с возможностью вернуться', active:false },
                            { type:'unmute', icon:'🔊', label:'Разрешить писать',  sub:'Снять мут',           active:false },
                            { type:'unban',  icon:'✅', label:'Разблокировать',    sub:'Снять бан',           active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                      {/* Секция 3: Прочее */}
                      <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Прочее</p>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { type:'warn',  icon:'⚠️', label:'Предупреждение',   sub:'Варн с эскалацией',    active:true  },
                            { type:'emoji', icon:'😀', label:'Реакция эмодзи',    sub:'Поставить реакцию',    active:true  },
                            { type:'warn_add', icon:'✋', label:'Уровень наказания', sub:'Добавить варн',     active:false },
                            { type:'trigger_toggle', icon:'🔄', label:'Изменить триггер', sub:'Вкл/выкл другой', active:false },
                          ].filter(a => actPickerSearch === '' || a.label.toLowerCase().includes(actPickerSearch.toLowerCase())).map(a => (
                            a.active ? (
                              <button key={a.type} onClick={() => addActionToGroup(actPickerGroupIdx, a.type)}
                                className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-gray-100 rounded-2xl text-left hover:border-blue-200 hover:bg-blue-50/30 active:scale-[0.97] transition-all">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-800 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </button>
                            ) : (
                              <div key={a.type} className="relative flex flex-col items-start gap-1.5 p-3.5 bg-gray-50 border border-dashed border-gray-200 rounded-2xl opacity-50 cursor-not-allowed">
                                <span className="text-xl">{a.icon}</span>
                                <span className="text-[11px] font-black text-gray-500 leading-tight">{a.label}</span>
                                <span className="text-[9px] text-gray-400 font-medium leading-tight">{a.sub}</span>
                                <span className="absolute top-2 right-2 text-[8px] font-black bg-gray-200 text-gray-400 px-1.5 py-0.5 rounded-full uppercase">***</span>
                                <div className="absolute top-2 right-8 w-4 h-4 rounded-full bg-gray-300 text-white text-[9px] font-black flex items-center justify-center leading-none">?</div>
                              </div>
                            )
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── МОДАЛ КЛАВИАТУРЫ ── */}
              {showKeyboardModal && kbModalTarget && (() => {
                const { gIdx, aIdx } = kbModalTarget;
                const tgt = (editingTrigger.actionGroups||[])[gIdx]?.actions[aIdx];
                if (!tgt) return null;
                const keyboard = tgt.keyboard || [];
                const addKbButton = (btn) => {
                  updAction(gIdx, aIdx, 'keyboard', [...keyboard, { id: Date.now(), ...btn }]);
                  setKbButtonType(null);
                  setKbNewButton({});
                };
                const REACTION_PRESETS = [
                  { emoji: '🌍' }, { emoji: '👋' }, { emoji: '🔥' }, { emoji: '💡' },
                ];
                return (
                  <div className="fixed inset-0 z-[300] flex flex-col bg-white">

                    {/* ── Шапка ── */}
                    <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0">
                      <span className="text-[10px] font-black bg-blue-100 text-blue-600 px-2 py-0.5 rounded uppercase tracking-wide">Beta</span>
                      <button onClick={() => { setShowKeyboardModal(false); setKbButtonType(null); setKbNewButton({}); }}
                        className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                        <X size={20}/>
                      </button>
                    </div>

                    {/* ── Список добавленных кнопок ── */}
                    <div className="px-5 py-3 border-b border-gray-100 flex-shrink-0">
                      {keyboard.length === 0 ? (
                        <p className="text-sm font-bold text-gray-400 text-center py-1">Кнопки не выбраны</p>
                      ) : (
                        <div className="space-y-1.5">
                          {keyboard.map((btn, bi) => (
                            <div key={btn.id} className="flex items-center gap-2.5 px-3 py-2 bg-gray-50 rounded-xl border border-gray-100">
                              <span className="text-gray-300 font-black text-lg select-none leading-none">+</span>
                              <span className="text-base w-5 text-center leading-none">{btn.emoji || '○'}</span>
                              <span className="text-sm font-bold text-gray-500 flex-1 truncate">{btn.text || 'Текст кнопки'}</span>
                              <button onClick={() => updAction(gIdx, aIdx, 'keyboard', keyboard.filter((_,i)=>i!==bi))}
                                className="text-red-300 hover:text-red-500 text-xl leading-none flex-shrink-0">×</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* ── Контент ── */}
                    <div className="flex-1 overflow-y-auto">
                      {kbButtonType === null ? (

                        /* Выбор типа кнопки */
                        <div className="px-5 py-5">
                          <p className="text-sm font-black text-gray-800 mb-4">Выберите тип кнопки</p>
                          <div className="grid grid-cols-3 gap-2">
                            <button
                              onClick={() => { setKbButtonType('link'); setKbNewButton({}); }}
                              className="px-4 py-4 border border-gray-200 rounded-xl text-sm font-bold text-gray-700 text-left hover:border-blue-300 hover:bg-blue-50 transition-all active:scale-[0.97]">
                              🔗 Ссылка
                            </button>
                            <div className="relative px-4 py-4 border border-dashed border-gray-200 rounded-xl text-sm font-bold text-gray-400 text-left cursor-not-allowed select-none">
                              Вызов триггера
                              <span className="absolute top-1.5 right-1.5 text-[8px] font-black bg-amber-100 text-amber-500 px-1.5 py-0.5 rounded-full uppercase">Скоро</span>
                            </div>
                            {REACTION_PRESETS.map((r, ri) => (
                              <div key={ri} className="relative flex items-center gap-2 px-4 py-4 border border-dashed border-gray-200 rounded-xl text-sm font-bold text-gray-400 text-left cursor-not-allowed select-none">
                                <span className="text-lg">{r.emoji}</span>
                                <span>Реакция</span>
                                <span className="absolute top-1.5 right-1.5 text-[8px] font-black bg-amber-100 text-amber-500 px-1.5 py-0.5 rounded-full uppercase">Скоро</span>
                              </div>
                            ))}
                          </div>
                        </div>

                      ) : (

                        /* Подформа */
                        <div className="px-5 py-5 space-y-4">
                          {/* Назад + заголовок */}
                          <div className="flex items-center gap-2">
                            <button onClick={() => { setKbButtonType(null); setKbNewButton({}); }}
                              className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all text-lg font-bold leading-none">←</button>
                            {kbButtonType === 'reaction' && <span className="text-xl">{kbReactionEmoji}</span>}
                            <h3 className="text-base font-black text-gray-900">
                              {kbButtonType === 'reaction' ? 'Реакция' : 'Ссылка'}
                            </h3>
                          </div>

                          {/* Info box */}
                          <div className="px-4 py-3 bg-blue-50 border border-blue-100 rounded-2xl text-[12px] text-blue-700 font-medium leading-relaxed">
                            {kbButtonType === 'reaction' && <>
                              Если вы отключили реакции на посты в канале, но мнение пользователей об определённой публикации или теме важно — помогут кнопки с реакциями. Можно вставить любые эмодзи вместо предложенных в поле "Текст кнопки".<br/><br/>
                              После того, как читатели нажмут на кнопку, рядом с эмодзи появится количество нажатий. Вот как это будет выглядеть с использованием текущего эмодзи: {kbReactionEmoji} - 3.
                            </>}
                            {kbButtonType === 'link' && <>
                              Кнопка-ссылка — при нажатии открывает указанный URL в браузере пользователя.
                            </>}
                          </div>

                          {/* Текст кнопки */}
                          <div>
                            <p className="text-sm font-black text-gray-700 mb-1.5">Текст кнопки <span className="text-red-400">*</span></p>
                            <input type="text" placeholder="Текст кнопки"
                              value={kbNewButton.text || ''}
                              onChange={e => setKbNewButton(p => ({...p, text: e.target.value}))}
                              className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                          </div>

                          {/* URL */}
                          {kbButtonType === 'link' && (
                            <div>
                              <p className="text-sm font-black text-gray-700 mb-1.5">URL <span className="text-red-400">*</span></p>
                              <input type="url" placeholder="https://..."
                                value={kbNewButton.url || ''}
                                onChange={e => setKbNewButton(p => ({...p, url: e.target.value}))}
                                className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all"/>
                            </div>
                          )}

                          {/* Реакция: сообщение + чекбоксы */}
                          {kbButtonType === 'reaction' && (<>
                            <div>
                              <p className="text-sm font-black text-gray-700 mb-1.5">Сообщение пользователю</p>
                              <div className="relative">
                                <textarea
                                  value={kbNewButton.user_msg || ''}
                                  onChange={e => setKbNewButton(p => ({...p, user_msg: e.target.value.slice(0,200)}))}
                                  rows={4}
                                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 transition-all resize-none"/>
                                <span className="absolute bottom-2 right-3 text-[10px] text-gray-400 font-bold">
                                  {(kbNewButton.user_msg||'').length} / 200
                                </span>
                              </div>
                            </div>
                            <div className="space-y-4">
                              <div className="flex items-start gap-3 cursor-pointer" onClick={() => setKbNewButton(p => ({...p, noMultiple: !p.noMultiple}))}>
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all ${kbNewButton.noMultiple ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                                  {kbNewButton.noMultiple && <Check size={12} className="text-white"/>}
                                </div>
                                <div>
                                  <p className="text-sm font-bold text-gray-700">Запрет на выбор нескольких вариантов</p>
                                  <p className="text-[11px] text-gray-400 font-medium mt-0.5">* Активируйте данный параметр, чтобы запретить пользователю выбирать несколько вариантов реакции</p>
                                </div>
                              </div>
                              <div className="flex items-start gap-3 cursor-pointer" onClick={() => setKbNewButton(p => ({...p, uniqueOnly: !p.uniqueOnly}))}>
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-all ${kbNewButton.uniqueOnly ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                                  {kbNewButton.uniqueOnly && <Check size={12} className="text-white"/>}
                                </div>
                                <div>
                                  <p className="text-sm font-bold text-gray-700">Учитывать только уникальные нажатия</p>
                                  <p className="text-[11px] text-gray-400 font-medium mt-0.5">* При активации данного параметра будет зачтено только первое нажатие на кнопку от уникального пользователя. Если параметр выключен, то учитываться в счётчике будут все нажатия от одного и того же человека</p>
                                </div>
                              </div>
                            </div>
                          </>)}
                        </div>
                      )}
                    </div>

                    {/* ── Добавить кнопку ── */}
                    {kbButtonType !== null && (
                      <div className="px-5 py-4 border-t border-gray-100 flex-shrink-0">
                        <button
                          onClick={() => {
                            if (!kbNewButton.text) return;
                            addKbButton({
                              type: kbButtonType,
                              text: kbNewButton.text,
                              emoji: kbButtonType === 'reaction' ? kbReactionEmoji : undefined,
                              trigger_id: kbNewButton.trigger_id,
                              url: kbNewButton.url,
                              user_msg: kbNewButton.user_msg,
                              noMultiple: kbNewButton.noMultiple,
                              uniqueOnly: kbNewButton.uniqueOnly,
                            });
                          }}
                          className="w-full py-4 bg-blue-500 text-white font-black text-sm rounded-2xl shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-[0.98] transition-all">
                          Добавить кнопку
                        </button>
                      </div>
                    )}

                  </div>
                );
              })()}

              {/* ── МОДАЛ ДОПОЛНИТЕЛЬНЫХ НАСТРОЕК ДЕЙСТВИЯ (через портал — вне стэкинг-контекста карточек) ── */}
              {actionSettingsModal && createPortal((() => {
                const { gIdx, aIdx } = actionSettingsModal;
                return (
                  <div className="fixed inset-0 z-[99999] flex items-center justify-center px-4">
                    <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setActionSettingsModal(null)}/>
                    <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-5 animate-in fade-in zoom-in-95 duration-200">
                      <div className="flex items-center justify-between">
                        <h3 className="font-black text-base text-gray-900">Дополнительные настройки действия</h3>
                        <button onClick={() => setActionSettingsModal(null)} className="p-1.5 text-gray-400 hover:text-gray-600 active:scale-90 transition-all">
                          <X size={16}/>
                        </button>
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <p className="text-sm font-black text-gray-800">Шанс выполнения действия <span className="text-red-400">*</span></p>
                        </div>
                        <input
                          type="number" min="1" max="100"
                          value={actionSettingsPct}
                          onChange={e => setActionSettingsPct(Math.min(100, Math.max(1, parseInt(e.target.value)||1)))}
                          className="w-full px-4 py-3 bg-gray-50 border-2 border-gray-200 rounded-2xl font-black text-sm text-right outline-none focus:border-blue-300 transition-all"
                          style={{appearance:'textfield'}}/>
                      </div>
                      <div className="flex gap-2 justify-end pt-1">
                        <button onClick={() => setActionSettingsModal(null)}
                          className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl font-black text-sm hover:bg-gray-200 active:scale-95 transition-all">
                          Отмена
                        </button>
                        <button onClick={() => { updAction(gIdx, aIdx, 'action_probability', actionSettingsPct); setActionSettingsModal(null); }}
                          className="px-5 py-2.5 bg-blue-500 text-white rounded-xl font-black text-sm shadow-md shadow-blue-100 hover:bg-blue-600 active:scale-95 transition-all">
                          Сохранить
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })(), document.body)}

              {/* ── ДЕЙСТВИЯ (старый блок — удалён, теперь в правой колонке) ── */}
              {false && <div className="mb-5 space-y-2">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest block px-1">Действия</span>
                {[].map((action, idx) => {
                  const actCfg = ACTION_TYPES.find(a=>a.type===action.type)||ACTION_TYPES[0];
                  const ActIcon = actCfg.Icon;
                  return (
                    <div key={action.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                        <div className="flex items-center gap-2"><ActIcon size={14} className="text-gray-600"/><span className="text-sm font-black text-gray-800">{actCfg.label}</span></div>
                        <button onClick={() => removeAction(idx)} className="p-1.5 text-red-400 hover:text-red-600 active:scale-90 transition-all"><X size={13}/></button>
                      </div>
                      <div className="px-4 py-3 space-y-3">
                        {(action.type==='send_text'||action.type==='dm') && (<>
                          {action.type==='send_text' && (
                            <div className="flex gap-1.5 flex-wrap">
                              {[{v:'none',l:'Обычный'},{v:'initiator',l:'→ Автор'},{v:'quoted',l:'→ Цитата'}].map(o => (
                                <button key={o.v} onClick={() => updAction(idx,'reply_target',o.v)}
                                  className={`px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${action.reply_target===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                                </button>
                              ))}
                            </div>
                          )}
                          <textarea placeholder="Текст сообщения..."
                            value={action.reply_text} onChange={e => updAction(idx,'reply_text',e.target.value)} rows={3}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-bold text-sm outline-none focus:border-blue-300 resize-none transition-all"/>
                          {action.type==='send_text' && (<>
                            <div>
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-[10px] font-black text-gray-400 uppercase">Медиафайл</span>
                                <button onClick={() => { if (showMediaPicker) updAction(idx,'media_type','none'); setShowMediaPicker(v=>!v); }}
                                  className={`flex items-center gap-1 px-3 py-1 rounded-xl text-[10px] font-black uppercase transition-all ${action.media_type!=='none' ? 'bg-blue-600 text-white' : showMediaPicker ? 'bg-gray-200 text-gray-600' : 'bg-gray-100 text-gray-500'}`}>
                                  {action.media_type==='none' ? <><ImageIcon size={11}/><span>{showMediaPicker?'Убрать':'+ Добавить'}</span></> :
                                   action.media_type==='photo' ? <><ImageIcon size={11}/><span>Фото</span><X size={9} className="ml-1 opacity-60"/></> :
                                   action.media_type==='video' ? <><Video size={11}/><span>Видео</span><X size={9} className="ml-1 opacity-60"/></> :
                                   <><Smile size={11}/><span>GIF</span><X size={9} className="ml-1 opacity-60"/></>}
                                </button>
                              </div>
                              <div className={`overflow-hidden transition-all duration-300 ${showMediaPicker ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'}`}>
                                <div className="grid grid-cols-3 gap-2 pb-1">
                                  {[{v:'photo',l:'Фото',I:ImageIcon},{v:'video',l:'Видео',I:Video},{v:'animation',l:'GIF',I:Smile}].map(m => (
                                    <button key={m.v} onClick={() => { updAction(idx,'media_type',m.v); setShowMediaPicker(false); }}
                                      className={`flex flex-col items-center gap-1 py-2.5 rounded-xl border-2 text-[10px] font-black uppercase transition-all ${action.media_type===m.v ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-200 text-gray-500'}`}>
                                      <m.I size={16}/>{m.l}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <div>
                              <span className="text-[10px] font-black text-gray-400 uppercase block mb-1.5">Удаление ответа бота</span>
                              <div className="flex gap-2">
                                {[{v:'no',l:'Нет'},{v:'previous',l:'Пред.'},{v:'period',l:'Таймер'}].map(o => (
                                  <button key={o.v} onClick={() => updAction(idx,'bot_msg_delete',o.v)}
                                    className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${action.bot_msg_delete===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                                  </button>
                                ))}
                              </div>
                              {action.bot_msg_delete==='period' && (
                                <input type="number" placeholder="Секунд" value={action.bot_msg_delete_after}
                                  onChange={e => updAction(idx,'bot_msg_delete_after',parseInt(e.target.value))}
                                  className="w-full mt-2 p-3 bg-white border border-gray-200 rounded-xl font-black text-center outline-none focus:border-blue-300"/>
                              )}
                            </div>
                          </>)}
                        </>)}
                        {(action.type==='mute'||action.type==='ban') && (
                          <input type="text" placeholder="Длительность: 30m / 2h / forever"
                            value={action.duration} onChange={e => updAction(idx,'duration',e.target.value)}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-black text-sm outline-none focus:border-blue-300"/>
                        )}
                        {action.type==='warn' && (
                          <div>
                            <div className="flex items-center gap-1.5 mb-2">
                              <span className="text-[10px] font-black text-gray-400 uppercase">За какой период считать предупреждения</span>
                              <div className="relative group">
                                <span className="w-4 h-4 rounded-full bg-gray-200 text-gray-500 text-[9px] font-black flex items-center justify-center cursor-help">?</span>
                                <div className="absolute bottom-5 left-1/2 -translate-x-1/2 w-56 bg-gray-900 text-white text-[10px] font-bold rounded-xl px-3 py-2 opacity-0 group-hover:opacity-100 transition-all pointer-events-none z-50 leading-relaxed">
                                  Бот считает сколько раз этот пользователь уже получал предупреждение за последние N секунд. Когда набирается 3 — мут на час, 5 — мут на сутки. 0 = считать за всё время без сброса.
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <input type="number" min="0" placeholder="0"
                                value={editingTrigger.warn_period || 0}
                                onChange={e => upd('warn_period', parseInt(e.target.value)||0)}
                                className="w-28 p-3 bg-gray-50 border border-gray-200 rounded-xl font-black text-sm text-center outline-none focus:border-blue-300"/>
                              <span className="text-[11px] font-bold text-gray-400">секунд (0 = за всё время)</span>
                            </div>
                          </div>
                        )}
                        {action.type==='emoji' && (
                          <input type="text" placeholder="👀 🔥 ❤️"
                            value={action.emoji} onChange={e => updAction(idx,'emoji',e.target.value)}
                            className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl font-black text-2xl text-center outline-none focus:border-blue-300"/>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>}

              {/* ── Дополнительно ── */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 space-y-4">
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Дополнительно</span>

                {/* Где срабатывает */}
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">Где срабатывает</p>
                  <div className="flex gap-2">
                    {[{v:'all',l:'Везде'},{v:'chat',l:'Чат'},{v:'pv',l:'Личка'}].map(o => (
                      <button key={o.v} onClick={() => upd('where_fires',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.where_fires===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* На кого реагирует (initiator) */}
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">На кого реагирует</p>
                  <div className="flex gap-2">
                    {[{v:'all',l:'Все'},{v:'users',l:'Юзеры'},{v:'admins',l:'Админы'}].map(o => (
                      <button key={o.v} onClick={() => upd('initiator',o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 ${editingTrigger.initiator===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Действие применить к (target) */}
                <div>
                  <p className="text-[10px] font-bold text-gray-500 mb-2 uppercase">Действие применить к</p>
                  <div className="flex gap-2 flex-wrap">
                    {[{v:'initiator',l:'Инициатор'},{v:'replied',l:'Цитируемый'},{v:'both',l:'Оба'},{v:'specific',l:'Указанный'},{v:'nobody',l:'Никто'}].map(o => (
                      <button key={o.v} onClick={() => upd('target', o.v)}
                        className={`flex-1 py-2 rounded-xl text-[10px] font-black uppercase transition-all active:scale-95 min-w-[60px] ${editingTrigger.target===o.v ? 'bg-gray-900 text-white' : 'bg-gray-50 border border-gray-200 text-gray-500'}`}>{o.l}
                      </button>
                    ))}
                  </div>
                  {editingTrigger.target === 'specific' && (
                    <div className="mt-2">
                      <input
                        type="text"
                        value={editingTrigger.target_user || ''}
                        onChange={e => upd('target_user', e.target.value.trim())}
                        placeholder="user_id или @username"
                        className="w-full px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm font-bold text-gray-700 outline-none focus:border-blue-400 transition-all"
                      />
                      <p className="text-[9px] text-gray-400 mt-1">Целевой пользователь для действий на «Указанного»</p>
                    </div>
                  )}
                </div>

              </div>

            </div>
          );
        }

        // ── Список триггеров ──
        const tSearch = triggerSearch.toLowerCase();
        const activeTriggers   = triggers.filter(t =>  t.is_enabled && (!tSearch || t.name.toLowerCase().includes(tSearch) || (t.keyword||'').toLowerCase().includes(tSearch)));
        const inactiveTriggers = triggers.filter(t => !t.is_enabled && (!tSearch || t.name.toLowerCase().includes(tSearch) || (t.keyword||'').toLowerCase().includes(tSearch)));

        const TriggerRow = ({ t, index, active }) => (
          <div
            key={t.id}
            draggable={active}
            onDragStart={() => active && handleDragStart(t.id)}
            onDragOver={e => { e.preventDefault(); }}
            onDrop={() => active && handleDrop(t.id)}
            className={`flex items-center py-3 px-4 border-b border-gray-50 last:border-b-0 transition-opacity ${dragId === t.id ? 'opacity-40' : 'opacity-100'}`}
          >
            {/* drag handle (только активные) */}
            {active ? (
              <GripVertical size={16} className="text-gray-300 mr-2 flex-shrink-0 cursor-grab active:cursor-grabbing"/>
            ) : (
              <div className="w-[20px] mr-2 flex-shrink-0"/>
            )}

            {/* номер (только активные) */}
            {active && (
              <span className="w-7 h-7 rounded-full bg-blue-500 text-white text-[10px] font-black flex items-center justify-center mr-3 flex-shrink-0">
                {index + 1}
              </span>
            )}

            {/* название */}
            <button
              onClick={() => openTriggerModal(t)}
              className="flex-1 text-left text-sm font-bold text-blue-600 hover:text-blue-800 truncate"
            >
              {t.name}
            </button>

            {/* кнопки */}
            <div className="flex items-center gap-1 ml-2 flex-shrink-0">
              {/* удалить — только неактивные */}
              {!active && userCan('triggers.delete') && (
                <button
                  onClick={() => deleteTrigger(t.id)}
                  className="p-2 text-red-400 hover:text-red-600 active:scale-90 transition-all"
                >
                  <Trash2 size={16}/>
                </button>
              )}
              {/* копировать (создание дубликата) */}
              {userCan('triggers.create') && (
                <button
                  onClick={() => copyTrigger(t.id)}
                  disabled={copyingTrigger === t.id}
                  className="p-2 text-blue-400 hover:text-blue-600 active:scale-90 transition-all disabled:opacity-40"
                >
                  {copyingTrigger === t.id ? <Loader2 size={16} className="animate-spin"/> : <Copy size={16}/>}
                </button>
              )}
              {/* пауза (активные) / старт (неактивные) */}
              {userCan('triggers.toggle') && (
                <button
                  onClick={() => toggleTrigger(t.id)}
                  disabled={togglingTrigger === t.id}
                  className={`p-0.5 rounded-full active:scale-90 transition-all disabled:opacity-40 ${
                    active ? 'text-red-500 hover:text-red-700' : 'text-green-500 hover:text-green-700'
                  }`}
                >
                  {togglingTrigger === t.id
                    ? <Loader2 size={22} className="animate-spin"/>
                    : active
                      ? <span className="w-6 h-6 rounded-full border-2 border-red-500 flex items-center justify-center"><Square size={8} fill="currentColor"/></span>
                      : <span className="w-6 h-6 rounded-full border-2 border-green-500 flex items-center justify-center"><Play size={9} fill="currentColor"/></span>
                  }
                </button>
              )}
            </div>
          </div>
        );

        return (
          <div className="space-y-4 pb-24">
            {/* ── Поиск ── */}
            <div className="relative">
              <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-300"/>
              <input
                value={triggerSearch}
                onChange={e => setTriggerSearch(e.target.value)}
                placeholder="Поиск по названию или ключевым словам..."
                className="w-full bg-white border border-gray-100 rounded-2xl pl-10 pr-4 py-3.5 text-sm font-bold focus:outline-none focus:border-blue-300 shadow-sm"
              />
            </div>

            {/* ── Панель действий ── */}
            <div className="flex items-center space-x-2">
              <button className="flex items-center space-x-2 px-5 py-3 bg-white border border-gray-100 rounded-2xl font-black text-xs text-gray-500 shadow-sm active:scale-95 transition-all">
                <Activity size={14}/><span>Статистика</span>
              </button>
              {userCan('triggers.create') && (
                <button
                  onClick={() => openTriggerModal()}
                  className="flex-1 flex items-center justify-center space-x-2 py-3 bg-blue-600 text-white rounded-2xl font-black text-xs shadow-md shadow-blue-100 active:scale-95 transition-all"
                >
                  <PlusCircle size={14}/><span>Создать триггер</span>
                </button>
              )}
              {/* меню ··· (показываем только если хоть один пункт доступен) */}
              {(userCan('triggers.create') || userCan('triggers.toggle')) && (
                <div className="relative">
                  <button
                    onClick={() => setShowTriggerMenu(v => !v)}
                    className="p-3 bg-white border border-gray-100 rounded-2xl text-gray-400 shadow-sm active:scale-95 transition-all font-black text-lg leading-none"
                  >···</button>
                  {showTriggerMenu && (
                    <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-gray-100 rounded-2xl shadow-xl z-50 overflow-hidden" onClick={() => setShowTriggerMenu(false)}>
                      {userCan('triggers.create') && (
                        <button className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3">
                          <Download size={14} className="text-gray-400"/> Импортировать триггеры
                        </button>
                      )}
                      {userCan('triggers.create') && (
                        <button className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3">
                          <Clock size={14} className="text-gray-400"/> Восстановить удалённый
                        </button>
                      )}
                      {userCan('triggers.toggle') && (
                        <button
                          onClick={() => { triggers.forEach(t => t.is_enabled && toggleTrigger(t.id)); }}
                          className="w-full text-left px-5 py-3.5 text-sm font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-3"
                        >
                          <Power size={14} className="text-gray-400"/> Отключить все триггеры
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {triggersLoading && (
              <div className="text-center py-8 text-gray-400 font-black text-sm">
                <Loader2 size={24} className="animate-spin mx-auto mb-2"/> Загрузка...
              </div>
            )}

            {/* ── Активные ── */}
            {!triggersLoading && activeTriggers.length > 0 && (
              <div>
                <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Активные триггеры</p>
                <div className="bg-white rounded-[2rem] border-l-4 border-l-green-500 border border-gray-100 shadow-sm overflow-hidden">
                  {activeTriggers.map((t, i) => <TriggerRow key={t.id} t={t} index={i} active={true}/>)}
                </div>
              </div>
            )}

            {/* ── Неактивные ── */}
            {!triggersLoading && inactiveTriggers.length > 0 && (
              <div>
                <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2 px-1">Не активные триггеры</p>
                <div className="bg-white rounded-[2rem] border-l-4 border-l-red-400 border border-gray-100 shadow-sm overflow-hidden">
                  {inactiveTriggers.map((t, i) => <TriggerRow key={t.id} t={t} index={i} active={false}/>)}
                </div>
              </div>
            )}

            {!triggersLoading && triggers.length === 0 && (
              <div className="text-center py-12 text-gray-300 font-black text-sm uppercase tracking-widest">
                Триггеров пока нет
              </div>
            )}
          </div>
        );
      }

      case 'updates':
        return (
          <div className="space-y-4 pb-24 animate-in fade-in duration-300">
            <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm flex items-center space-x-4">
              <div className="w-14 h-14 bg-blue-600 rounded-[1.5rem] flex items-center justify-center shadow-lg">
                <Megaphone size={26} className="text-white" />
              </div>
              <div>
                <h2 className="font-black text-2xl text-gray-900 leading-none">Обновления</h2>
                <p className="text-xs text-gray-400 font-bold mt-1">История улучшений панели и бота</p>
              </div>
            </div>

            {UPDATES.map((upd) => (
              <div key={upd.version} className="bg-white rounded-[2.5rem] p-6 border border-gray-100 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <span className="bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full">{upd.version}</span>
                  <span className="text-xs text-gray-300 font-mono">{upd.date}</span>
                </div>
                <h3 className="font-black text-lg text-gray-900">{upd.title}</h3>
                <div className="space-y-2">
                  {upd.items.map((item, i) => {
                    const typeCfg = {
                      new:     { icon: PartyPopper, bg: 'bg-green-50',  text: 'text-green-600',  border: 'border-green-100',  label: 'НОВОЕ'      },
                      improve: { icon: Sparkles,    bg: 'bg-blue-50',   text: 'text-blue-600',   border: 'border-blue-100',   label: 'УЛУЧШЕНО'   },
                      fix:     { icon: Wrench,      bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', label: 'ИСПРАВЛЕНО' },
                    }[item.type] || { icon: Info, bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-100', label: '' };
                    const tagCfg = {
                      site:       { emoji: '🌐', label: 'Сайт',       color: 'bg-indigo-50 text-indigo-500' },
                      statistics: { emoji: '📊', label: 'Статистика', color: 'bg-violet-50 text-violet-500' },
                      journal:    { emoji: '📋', label: 'Журнал',     color: 'bg-sky-50 text-sky-500'       },
                      triggers:   { emoji: '⚡', label: 'Триггеры',   color: 'bg-yellow-50 text-yellow-600' },
                      bot:        { emoji: '🤖', label: 'Бот',        color: 'bg-gray-100 text-gray-500'    },
                    }[item.tag] || null;
                    const Icon = typeCfg.icon;
                    return (
                      <div key={i} className={`flex items-start space-x-3 p-3 rounded-2xl border ${typeCfg.bg} ${typeCfg.border}`}>
                        <div className={`flex-shrink-0 flex items-center space-x-1 ${typeCfg.text}`}>
                          <Icon size={14} />
                          <span className="text-[9px] font-black uppercase tracking-widest">{typeCfg.label}</span>
                        </div>
                        <p className="text-xs text-gray-700 font-medium leading-relaxed flex-1">{item.text}</p>
                        {tagCfg && (() => {
                          const key = `${upd.version}-${i}`;
                          return (
                            <span
                              onClick={() => triggerJiggle(key)}
                              onAnimationEnd={() => setJigglingTag(null)}
                              className={`flex-shrink-0 text-[9px] font-black px-2 py-1 rounded-full cursor-pointer select-none hover:scale-110 transition-transform ${tagCfg.color} ${jigglingTag === key ? 'tag-jiggle' : ''}`}
                            >
                              {tagCfg.emoji} {tagCfg.label}
                            </span>
                          );
                        })()}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );

      case 'profile': {
        const initials = (authUser.first_name || '?').slice(0, 1).toUpperCase();
        const fmtDate = (iso) => {
          if (!iso) return null;
          const d = new Date(iso);
          if (isNaN(d.getTime())) return null;
          const months = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
          return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
        };
        const role = profileData?.role || 'user';
        const roleStyles = {
          owner:     { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: Crown },
          developer: { bg: 'bg-orange-100', text: 'text-orange-700', icon: ShieldCheck },
          deputy:    { bg: 'bg-purple-100', text: 'text-purple-700', icon: ShieldCheck },
          admin:     { bg: 'bg-green-100',  text: 'text-green-700',  icon: ShieldCheck },
          user:      { bg: 'bg-gray-100',   text: 'text-gray-500',   icon: User },
        };
        const rs = roleStyles[role] || roleStyles.user;
        const RoleIcon = rs.icon;
        const placeholderVal = profileLoading
          ? <Loader2 size={14} className="animate-spin text-gray-300"/>
          : <span className="text-xs text-gray-300 font-black uppercase">—</span>;
        const ICON_MAP = {
          ShieldAlert, HeartHandshake, Send, ScrollText, PieChart,
          Settings, ShieldCheck, Ban, ShieldBan,
        };
        const ACTION_COLORS = {
          view:   'bg-gray-100 text-gray-600',
          create: 'bg-blue-100 text-blue-700',
          edit:   'bg-amber-100 text-amber-700',
          delete: 'bg-red-100 text-red-700',
          toggle: 'bg-green-100 text-green-700',
          export: 'bg-purple-100 text-purple-700',
        };
        const accesses = profileData?.accesses || [];
        const totalActions = accesses.reduce((sum, r) => sum + r.actions.length, 0);

        return (
          <div className="pb-24 animate-in fade-in duration-500 space-y-4">

            {/* ─── HERO (компактный, горизонтальный) ─── */}
            <div className="bg-white rounded-[2rem] p-5 border border-gray-100 shadow-sm
                            flex items-center gap-5">
              {authUser.photo_url
                ? <img src={authUser.photo_url} alt="avatar"
                       className="w-20 h-20 rounded-2xl border-2 border-white shadow-lg object-cover flex-shrink-0"/>
                : <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-700
                                  flex items-center justify-center text-white font-black text-4xl
                                  border-2 border-white shadow-lg flex-shrink-0">
                    {initials}
                  </div>
              }
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-black text-gray-900 truncate">{authUser.first_name || 'Пользователь'}</h2>
                {authUser.username && (
                  <p className="text-xs font-bold text-gray-400 truncate">@{authUser.username}</p>
                )}
                <div className={`mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                                ${rs.bg} ${rs.text} text-[10px] font-black uppercase tracking-wide`}>
                  <RoleIcon size={11}/> {profileData?.role_label || 'Загрузка...'}
                </div>
              </div>
            </div>

            {/* ─── ДВУХКОЛОНОЧНАЯ СЕТКА (на mobile — стек) ─── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              {/* TELEGRAM */}
              <div className="bg-white rounded-[2rem] p-5 border border-gray-100 space-y-2">
                <h3 className="font-black text-gray-900 text-xs uppercase flex items-center mb-2">
                  <User className="mr-2 text-blue-500" size={14}/> Telegram
                </h3>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                  <div className="flex items-center gap-2">
                    <Hash size={14} className="text-gray-400"/>
                    <span className="text-[11px] font-bold text-gray-400 uppercase">ID</span>
                  </div>
                  <span className="font-mono font-black text-sm text-gray-900">{authUser.id}</span>
                </div>
                {authUser.username && (
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <AtSign size={14} className="text-gray-400"/>
                      <span className="text-[11px] font-bold text-gray-400 uppercase">Username</span>
                    </div>
                    <span className="font-black text-sm text-gray-900">@{authUser.username}</span>
                  </div>
                )}
              </div>

              {/* ЧАТ / БЕЗ ЧАТА */}
              {profileData && profileData.has_chat === false ? (
                <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-[2rem] p-5
                                border border-blue-700 shadow-md text-white flex flex-col justify-between">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-white/15 backdrop-blur
                                    flex items-center justify-center border border-white/30 flex-shrink-0">
                      <Plug size={18} className="text-white"/>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-black uppercase tracking-wide">Без чата</h3>
                      <p className="text-xs font-medium text-blue-100 mt-1 leading-snug">
                        Pulse Bot ещё не работает в вашем чате
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowConnectChat(true)}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                               bg-white text-blue-700 font-black text-xs uppercase tracking-wide
                               hover:bg-blue-50 active:scale-[0.98] transition-all shadow">
                    <Plug size={14}/> Подключить чат
                  </button>
                </div>
              ) : (
                <div className="bg-white rounded-[2rem] p-5 border border-gray-100 space-y-2">
                  <h3 className="font-black text-gray-900 text-xs uppercase flex items-center mb-2">
                    <MessageCircle className="mr-2 text-green-500" size={14}/> Чат
                  </h3>
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <Calendar size={14} className="text-gray-400"/>
                      <span className="text-[11px] font-bold text-gray-400 uppercase">В чате с</span>
                    </div>
                    {fmtDate(profileData?.joined_at)
                      ? <span className="font-black text-sm text-gray-900">{fmtDate(profileData.joined_at)}</span>
                      : placeholderVal}
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <Clock size={14} className="text-gray-400"/>
                      <span className="text-[11px] font-bold text-gray-400 uppercase">Последнее</span>
                    </div>
                    {fmtDate(profileData?.last_message)
                      ? <span className="font-black text-sm text-gray-900">{fmtDate(profileData.last_message)}</span>
                      : placeholderVal}
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-2">
                      <MessageCircle size={14} className="text-gray-400"/>
                      <span className="text-[11px] font-bold text-gray-400 uppercase">Сообщений</span>
                    </div>
                    {profileData
                      ? <span className="font-black text-sm text-gray-900">{(profileData.total_messages || 0).toLocaleString('ru-RU')}</span>
                      : placeholderVal}
                  </div>
                </div>
              )}

              {/* ВАШИ ДОСТУПЫ — collapsible, на полную ширину сетки */}
              {accesses.length > 0 && (
                <div className="lg:col-span-2 bg-white rounded-[2rem] border border-gray-100 overflow-hidden">
                  <button
                    onClick={() => setAccessesOpen(v => !v)}
                    className="w-full flex items-center justify-between p-5 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-indigo-100 flex items-center justify-center">
                        <ShieldCheck size={16} className="text-indigo-600"/>
                      </div>
                      <div className="text-left">
                        <h3 className="font-black text-gray-900 text-sm uppercase">Ваши доступы</h3>
                        <p className="text-[11px] font-bold text-gray-400 mt-0.5">
                          {accesses.length} разделов · {totalActions} действий
                        </p>
                      </div>
                    </div>
                    {accessesOpen
                      ? <ChevronUp   size={18} className="text-gray-400"/>
                      : <ChevronDown size={18} className="text-gray-400"/>}
                  </button>
                  {accessesOpen && (
                    <div className="px-5 pb-5 grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {accesses.map((res) => {
                        const Icon = ICON_MAP[res.icon] || ShieldCheck;
                        return (
                          <div key={res.key} className="p-3 bg-gray-50 rounded-xl">
                            <div className="flex items-center gap-2 mb-2">
                              <Icon size={14} className="text-indigo-500 flex-shrink-0"/>
                              <span className="font-black text-xs text-gray-900 uppercase tracking-wide truncate">{res.label}</span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {res.actions.map((a) => (
                                <span key={a.key}
                                      className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase
                                                  tracking-wide ${ACTION_COLORS[a.key] || 'bg-gray-100 text-gray-600'}`}>
                                  {a.label}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ─── МОДАЛКА: ИНСТРУКЦИЯ ПОДКЛЮЧЕНИЯ ─── */}
            {showConnectChat && createPortal(
              <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4
                              bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
                   onClick={() => setShowConnectChat(false)}>
                <div className="bg-white w-full max-w-md rounded-t-[2.5rem] sm:rounded-[2.5rem] p-6
                                shadow-2xl animate-in slide-in-from-bottom duration-300"
                     onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-start justify-between mb-5">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-2xl bg-blue-100 flex items-center justify-center">
                        <Plug size={22} className="text-blue-600"/>
                      </div>
                      <div>
                        <h3 className="font-black text-gray-900 text-base">Подключение чата</h3>
                        <p className="text-xs text-gray-500 font-medium">5 простых шагов</p>
                      </div>
                    </div>
                    <button onClick={() => setShowConnectChat(false)}
                            className="p-2 rounded-xl hover:bg-gray-100 active:scale-90 transition-all">
                      <X size={18} className="text-gray-400"/>
                    </button>
                  </div>

                  <ol className="space-y-3 mb-5">
                    {[
                      <>Откройте Telegram и найдите бота{' '}
                        <span className="font-black text-blue-600">@{profileData?.bot_username || 'Pulse_On_bot'}</span></>,
                      <>Нажмите кнопку <span className="font-black">«Добавить в группу»</span></>,
                      <>Выберите свой чат из списка</>,
                      <>Назначьте бота <span className="font-black">администратором</span> с правами:
                        удаление сообщений, бан пользователей, закрепление сообщений</>,
                      <>Вернитесь сюда — чат появится в профиле автоматически</>,
                    ].map((text, i) => (
                      <li key={i} className="flex gap-3 items-start">
                        <span className="flex-shrink-0 w-7 h-7 rounded-xl bg-blue-100 text-blue-700
                                         font-black text-xs flex items-center justify-center">
                          {i + 1}
                        </span>
                        <span className="text-sm text-gray-700 font-medium leading-relaxed pt-0.5">{text}</span>
                      </li>
                    ))}
                  </ol>

                  <a href={`https://t.me/${profileData?.bot_username || 'Pulse_On_bot'}?startgroup=true`}
                     target="_blank" rel="noopener noreferrer"
                     className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl
                                bg-blue-600 text-white font-black text-sm uppercase tracking-wide
                                hover:bg-blue-700 active:scale-[0.98] transition-all shadow-lg">
                    <Send size={16}/> Открыть Telegram
                  </a>
                </div>
              </div>,
              document.body
            )}

            {/* ─── ДЕЙСТВИЯ ─── */}
            <div className="bg-white rounded-[2.5rem] p-6 border border-gray-100">
              <button
                onClick={() => { localStorage.removeItem('auth_token'); setAuthUser(null); }}
                className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl
                           bg-red-50 text-red-600 font-black text-sm uppercase tracking-wide
                           hover:bg-red-100 active:scale-[0.98] transition-all">
                <LogOut size={16}/> Выйти из аккаунта
              </button>
            </div>

          </div>
        );
      }

      case 'permissions': {
        if (!authUser?.is_owner && profileData?.role_raw !== 'developer') {
          return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4 pb-24 animate-in fade-in duration-500">
              <div className="w-20 h-20 rounded-3xl bg-red-50 flex items-center justify-center border border-red-100">
                <ShieldCheck size={36} className="text-red-400"/>
              </div>
              <p className="font-black text-gray-900 text-lg">Доступно только владельцу</p>
              <p className="text-sm text-gray-400 text-center max-w-xs">Этот раздел позволяет изменять права ролей. Только владелец чата имеет доступ.</p>
            </div>
          );
        }

        const PERM_ICON_MAP = {
          ShieldAlert, HeartHandshake, Send, ScrollText, PieChart,
          Settings, ShieldCheck, Ban, ShieldBan, Coins,
        };
        const ACTION_BADGE_COLORS = {
          view:   'bg-gray-100 text-gray-600',
          create: 'bg-blue-100 text-blue-700',
          edit:   'bg-amber-100 text-amber-700',
          delete: 'bg-red-100 text-red-700',
          toggle: 'bg-green-100 text-green-700',
          export: 'bg-purple-100 text-purple-700',
        };
        const ACTION_DESCRIPTIONS = {
          view:   'просматривать раздел',
          create: 'создавать записи',
          edit:   'редактировать записи',
          delete: 'удалять записи',
          toggle: 'включать / выключать',
          export: 'выгружать данные',
        };

        const editableRoles = (permCatalog?.roles || []).filter(r => r.editable);
        const totalPerms = (permCatalog?.resources?.length || 0) * (permCatalog?.actions?.length || 0);
        const currentSet = permLocal[permActiveRole] || new Set();
        const selectedResData = permCatalog?.resources?.find(r => r.key === permSelectedRes);

        const togglePerm = (perm) => {
          setPermLocal(prev => {
            const next = new Set(prev[permActiveRole]);
            next.has(perm) ? next.delete(perm) : next.add(perm);
            return { ...prev, [permActiveRole]: next };
          });
          setPermDirty(true);
        };

        const toggleAllForResource = (resKey, enable) => {
          setPermLocal(prev => {
            const next = new Set(prev[permActiveRole]);
            (permCatalog?.actions || []).forEach(a => {
              const p = `${resKey}.${a.key}`;
              enable ? next.add(p) : next.delete(p);
            });
            return { ...prev, [permActiveRole]: next };
          });
          setPermDirty(true);
        };

        const savePermissions = () => {
          const token = localStorage.getItem('auth_token');
          if (!token) return;
          setPermSaving(true);
          fetch(`/api/admin/permissions/roles/${permActiveRole}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ permissions: [...currentSet] }),
          })
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(() => {
              setPermDirty(false);
              setPermToast('Сохранено');
              setTimeout(() => setPermToast(null), 2500);
            })
            .catch(() => {
              setPermToast('Ошибка сохранения');
              setTimeout(() => setPermToast(null), 3000);
            })
            .finally(() => setPermSaving(false));
        };

        return (
          <div className="space-y-4 pb-24 animate-in fade-in duration-500">

            {/* Toast */}
            {permToast && (
              <div className={`fixed top-20 right-4 z-50 px-5 py-3 rounded-2xl shadow-2xl font-black text-sm text-white transition-all duration-300 ${permToast.startsWith('Ошибка') ? 'bg-red-500' : 'bg-green-500'}`}>
                {permToast}
              </div>
            )}

            {/* Шапка */}
            <div className="bg-white rounded-[2rem] border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-indigo-50 flex items-center justify-center border border-indigo-100 flex-shrink-0">
                  <ShieldCheck size={18} className="text-indigo-500"/>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-black text-gray-900 text-base leading-none">Права доступа</p>
                  <p className="text-xs text-gray-400 font-medium mt-0.5">Роли: зам владельца и администратор</p>
                </div>
                <button
                  onClick={savePermissions}
                  disabled={!permDirty || permSaving}
                  className={`flex items-center gap-1.5 px-5 py-2.5 rounded-xl font-black text-sm transition-all active:scale-95 ${
                    permDirty && !permSaving
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-100 hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-300 cursor-not-allowed'
                  }`}
                >
                  {permSaving ? <Loader2 size={14} className="animate-spin"/> : <CheckCircle2 size={14}/>}
                  Сохранить
                </button>
              </div>
            </div>

            {/* Переключатель ролей */}
            {permLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={28} className="text-blue-400 animate-spin"/>
              </div>
            ) : (
              <>
                <div className="flex gap-2">
                  {editableRoles.map(role => {
                    const roleSet = permLocal[role.key] || new Set();
                    return (
                      <button
                        key={role.key}
                        onClick={() => setPermActiveRole(role.key)}
                        className={`flex-1 py-3 px-4 rounded-2xl transition-all duration-200 text-left ${
                          permActiveRole === role.key
                            ? 'bg-blue-600 text-white shadow-md shadow-blue-100'
                            : 'bg-white text-gray-500 border border-gray-100 hover:border-blue-200'
                        }`}
                      >
                        <p className={`font-black text-sm ${permActiveRole === role.key ? 'text-white' : 'text-gray-900'}`}>{role.label}</p>
                        <p className={`text-[10px] font-bold mt-0.5 uppercase tracking-wide ${permActiveRole === role.key ? 'text-blue-200' : 'text-gray-400'}`}>
                          {roleSet.size} из {totalPerms} разрешений
                        </p>
                      </button>
                    );
                  })}
                </div>

                {/* Аккордеон: каждый ресурс — раскрывающаяся карточка */}
                <div className="space-y-2">
                  {(permCatalog?.resources || []).map(res => {
                    const ResIcon = PERM_ICON_MAP[res.icon] || ShieldCheck;
                    const resPerms = (permCatalog?.actions || []).map(a => `${res.key}.${a.key}`);
                    const enabledCount = resPerms.filter(p => currentSet.has(p)).length;
                    const allEnabled = enabledCount === resPerms.length;
                    const isExpanded = permSelectedRes === res.key;
                    return (
                      <div key={res.key} className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
                        {/* Заголовок — клик раскрывает/закрывает */}
                        <div
                          onClick={() => setPermSelectedRes(isExpanded ? null : res.key)}
                          className={`flex items-center gap-3 p-4 cursor-pointer transition-all hover:bg-gray-50 ${isExpanded ? 'border-b border-gray-100' : ''}`}
                        >
                          <div className={`w-9 h-9 rounded-xl flex items-center justify-center border flex-shrink-0 transition-colors ${isExpanded ? 'bg-blue-50 border-blue-100' : 'bg-gray-50 border-gray-100'}`}>
                            <ResIcon size={15} className={isExpanded ? 'text-blue-500' : 'text-gray-400'}/>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-black text-sm text-gray-900 leading-none">{res.label}</p>
                            <p className="text-[10px] text-gray-400 font-medium mt-0.5">
                              {enabledCount === 0 ? 'Нет доступа' : `${enabledCount} из ${resPerms.length} действий`}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <button
                              onClick={e => { e.stopPropagation(); toggleAllForResource(res.key, !allEnabled); }}
                              className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wide transition-all active:scale-90 ${allEnabled ? 'bg-red-50 text-red-500 hover:bg-red-100' : 'bg-green-50 text-green-600 hover:bg-green-100'}`}
                            >
                              {allEnabled ? 'Выкл' : 'Вкл'}
                            </button>
                            <ChevronDown size={14} className={`text-gray-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}/>
                          </div>
                        </div>
                        {/* Раскрытая панель: 2 колонки действий */}
                        {isExpanded && (
                          <div className="grid grid-cols-2 gap-2 p-4">
                            {(permCatalog?.actions || []).map(action => {
                              const perm = `${res.key}.${action.key}`;
                              const enabled = currentSet.has(perm);
                              const badgeCls = ACTION_BADGE_COLORS[action.key] || 'bg-gray-100 text-gray-600';
                              return (
                                <label
                                  key={action.key}
                                  className={`flex items-center gap-2.5 p-3 rounded-xl border cursor-pointer transition-all active:scale-95 ${enabled ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-100 hover:border-gray-200'}`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={enabled}
                                    onChange={() => togglePerm(perm)}
                                    className="w-4 h-4 accent-blue-600 flex-shrink-0 cursor-pointer"
                                  />
                                  <div className="min-w-0">
                                    <span className={`block text-[10px] font-black uppercase tracking-wide leading-none ${badgeCls.split(' ').slice(1).join(' ')}`}>
                                      {action.label}
                                    </span>
                                    <span className="text-[9px] text-gray-400 font-medium mt-0.5 block leading-tight">
                                      {ACTION_DESCRIPTIONS[action.key] || action.label}
                                    </span>
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        );
      }

      case 'economy':
        return (
          <EconomyErrorBoundary>
            <EconomyPage token={localStorage.getItem('auth_token')} />
          </EconomyErrorBoundary>
        );

      default: return null;
    }
  };

  if (authLoading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <Loader2 size={32} className="text-blue-400 animate-spin"/>
    </div>
  );
  if (!authUser) return <LoginPage onLogin={setAuthUser}/>;

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans text-gray-900 selection:bg-blue-100 overflow-hidden">
      <aside className={`fixed inset-y-0 left-0 z-50 w-[260px] bg-white border-r border-gray-100 flex flex-col transform transition-transform duration-500 lg:translate-x-0 lg:static ${isSidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}`}>
        <div className="h-16 flex items-center justify-between px-5 border-b border-gray-100">
          <div className="flex items-center space-x-3">
            <img src="/logo.jpg" alt="Puls Chat" className="w-9 h-9 rounded-xl object-cover shadow-md"/>
            <div>
              <span className="block font-black text-base text-gray-900 leading-none">Puls Chat</span>
              <span className="text-[9px] font-bold text-blue-500 uppercase tracking-wider mt-0.5 block">Owner Console</span>
            </div>
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden p-3 bg-white rounded-2xl text-gray-400 border border-gray-50 active:scale-90 transition-all"><X size={24} /></button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-4 space-y-6">
          {['top', 'main', 'modules', 'features'].map(group => (
            <div key={group} className="space-y-2">
              {group !== 'top' && (
                <p className="px-5 text-[11px] font-black text-gray-300 uppercase tracking-[0.3em] mb-6">
                  {group === 'main' ? 'Мониторинг' : group === 'modules' ? 'Модули' : 'Сервис'}
                </p>
              )}
              {navigation.filter(n => n.group === group && (!n.ownerOnly || authUser?.is_owner || profileData?.role_raw === 'developer')).map((item) => (
                <button
                  key={item.id}
                  onClick={() => { navigateTo(item.id); setIsSidebarOpen(false); setJigglingNav(item.id); }}
                  className={`w-full flex items-center px-4 py-2.5 rounded-xl transition-all duration-200 ${
                    activeTab === item.id
                    ? 'bg-gray-900 text-white shadow-md font-black'
                    : 'text-gray-500 hover:bg-gray-50 active:bg-gray-100'
                  }`}
                >
                  <item.icon
                    size={18}
                    onAnimationEnd={() => setJigglingNav(null)}
                    className={`mr-3 ${activeTab === item.id ? 'text-blue-400' : 'text-gray-400'} ${jigglingNav === item.id ? 'tag-jiggle' : ''}`}
                  />
                  <span className="text-sm flex-1">{item.name}</span>
                  {item.id === 'updates' && hasNewUpdate && (
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse shadow-md shadow-red-300" />
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#F8FAFC]">
        <header className="h-16 lg:h-16 bg-white border-b border-gray-100 flex items-center justify-between px-4 sm:px-6 z-10 shrink-0">
          <div className="flex items-center">
            <button className="lg:hidden p-4 bg-gray-50 rounded-[1.5rem] mr-5 border border-gray-100 shadow-sm" onClick={() => setIsSidebarOpen(true)}>
              <Menu size={26} />
            </button>
            <h1 className="text-2xl sm:text-3xl font-black text-gray-900 tracking-tighter">
              {navigation.find(n => n.id === activeTab)?.name}
            </h1>
          </div>
          <div className="flex items-center space-x-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigateTo('profile')}
                className="flex items-center gap-2 p-1 pr-2 rounded-2xl hover:bg-gray-50 transition-all active:scale-95 cursor-pointer"
                title="Открыть профиль">
                <div className="text-right hidden sm:block pl-2">
                  <p className="text-sm font-black text-gray-900 leading-none">{authUser.first_name}</p>
                  {authUser.username && <p className="text-[10px] font-bold text-gray-400 mt-0.5">@{authUser.username}</p>}
                </div>
                {authUser.photo_url
                  ? <img src={authUser.photo_url} alt="avatar" className="w-10 h-10 rounded-2xl border-2 border-white shadow-lg object-cover"/>
                  : <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-700 flex items-center justify-center text-white font-black text-lg border-2 border-white shadow-lg">
                      {(authUser.first_name||'?')[0]}
                    </div>
                }
              </button>
              <button onClick={() => { localStorage.removeItem('auth_token'); setAuthUser(null); }}
                className="p-2 rounded-xl text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all active:scale-90"
                title="Выйти">
                <Power size={16}/>
              </button>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-gray-50/10 custom-scrollbar">
          <div className={activeTab === 'triggers' && editingTrigger ? 'w-full' : 'max-w-3xl mx-auto'}>
            {renderContent()}
          </div>
        </div>
      </main>

      {/* ── Модал: панель плейсхолдеров ── */}
      {phDropdown && (() => {
        const PH_GROUPS_FULL = [
          { label:'Инициатор', color:'blue', desc:'Пользователь, чьё сообщение сработало триггер', items:[
            { key:'user_name',     label:'Имя',            desc:'Отображаемое имя в Telegram' },
            { key:'user_username', label:'@username',       desc:'Никнейм (может отсутствовать)' },
            { key:'user_id',       label:'ID',              desc:'Числовой ID пользователя' },
            { key:'act_tgun',      label:'Имя TG (новый)', desc:'Имя в Telegram (новый формат)' },
            { key:'act_nn',        label:'@nick (новый)',   desc:'Никнейм (новый формат)' },
            { key:'act_blns',      label:'Баланс пульсов',  desc:'Текущий баланс пульсов' },
            { key:'act_d',         label:'Дней в чате',     desc:'Сколько дней участник в чате' },
            { key:'act_rnk',       label:'Ранг',            desc:'Текущий ранг пользователя' },
            { key:'act_plc',       label:'Место в топе',    desc:'Позиция в рейтинге чата' },
            { key:'act_jt',        label:'Дата вступления', desc:'Когда вступил в чат' },
          ]},
          { label:'Цель', color:'purple', desc:'Пользователь, на которого направлено действие', items:[
            { key:'target_name',     label:'Имя цели',       desc:'Отображаемое имя цели' },
            { key:'target_username', label:'@username цели',  desc:'Никнейм цели' },
            { key:'target_id',       label:'ID цели',         desc:'Числовой ID цели' },
          ]},
          { label:'Чат', color:'green', desc:'Данные о текущем чате и времени', items:[
            { key:'chat_name', label:'Название чата', desc:'Официальное название группы' },
            { key:'date',      label:'Дата',           desc:'Текущая дата дд.мм.гггг' },
            { key:'time',      label:'Время',          desc:'Текущее время чч:мм (МСК)' },
          ]},
          { label:'Статистика сообщений', color:'amber', desc:'Количество сообщений инициатора', items:[
            { key:'act_msg',   label:'Сообщений всего', desc:'За всё время' },
            { key:'act_msg_t', label:'За сегодня',      desc:'Сообщений за текущий день' },
            { key:'act_msg_w', label:'За неделю',        desc:'Сообщений за последние 7 дней' },
            { key:'act_msg_m', label:'За месяц',         desc:'Сообщений за последние 30 дней' },
            { key:'act_msg_y', label:'За год',           desc:'Сообщений за последние 365 дней' },
          ]},
          { label:'Санкции', color:'red', desc:'Нарушения и предупреждения', items:[
            { key:'warn_count', label:'Предупреждений',        desc:'Общее кол-во предупреждений' },
            { key:'act_w',      label:'Предупреждений (новый)',desc:'Предупреждения (новый формат)' },
          ]},
          { label:'Анкета', color:'pink', desc:'Данные из анкеты пользователя', items:[
            { key:'act_form', label:'Полная анкета', desc:'Все поля анкеты одним блоком' },
            { key:'act_un',   label:'Имя из анкеты', desc:'Имя, указанное в анкете' },
            { key:'act_city', label:'Город',          desc:'Город из анкеты' },
            { key:'act_yo',   label:'Возраст',        desc:'Возраст из анкеты' },
            { key:'act_sr',   label:'Роль',           desc:'Роль/статус из анкеты' },
          ]},
          { label:'Рефералы', color:'green', desc:'Реферальная программа', items:[
            { key:'act_rfrl_c', label:'Кол-во рефералов', desc:'Сколько человек пригласил' },
          ]},
        ];

        const COLOR_BADGE = {
          blue:   'bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100',
          purple: 'bg-purple-50 text-purple-700 border border-purple-100 hover:bg-purple-100',
          green:  'bg-green-50 text-green-700 border border-green-100 hover:bg-green-100',
          amber:  'bg-amber-50 text-amber-700 border border-amber-100 hover:bg-amber-100',
          red:    'bg-red-50 text-red-700 border border-red-100 hover:bg-red-100',
          pink:   'bg-pink-50 text-pink-700 border border-pink-100 hover:bg-pink-100',
        };

        const insertPh = (key) => {
          const el = document.getElementById(`ce_${phDropdown}`);
          if (!el) return;
          el.focus();
          if (window._savedPhRange) {
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(window._savedPhRange);
            window._savedPhRange = null;
          }
          document.execCommand('insertText', false, `%${key}%`);
          // Синхронизируем state через событие input
          el.dispatchEvent(new Event('input', { bubbles: true }));
          setPhDropdown(null);
        };

        return (
          <div className="fixed inset-0 z-[300] flex items-center justify-end bg-black/20 backdrop-blur-sm animate-in fade-in duration-150"
            onClick={() => setPhDropdown(null)}>
            <div className="relative bg-white h-full w-[380px] max-w-[95vw] shadow-2xl flex flex-col animate-in slide-in-from-right duration-200"
              onClick={e => e.stopPropagation()}>

              {/* Шапка */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 shrink-0">
                <div>
                  <p className="font-black text-gray-900 text-base">Плейсхолдеры</p>
                  <p className="text-[11px] text-gray-400 mt-0.5">Нажми — вставится в позицию курсора</p>
                </div>
                <button onClick={() => setPhDropdown(null)}
                  className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all active:scale-90">
                  <X size={16}/>
                </button>
              </div>

              {/* Список */}
              <div className="flex-1 overflow-y-auto p-4 space-y-5">
                {PH_GROUPS_FULL.map(g => (
                  <div key={g.label}>
                    <div className="mb-2">
                      <p className="text-[11px] font-black text-gray-500 uppercase tracking-wider">{g.label}</p>
                      <p className="text-[10px] text-gray-400">{g.desc}</p>
                    </div>
                    <div className="space-y-1">
                      {g.items.map(it => (
                        <button key={it.key}
                          onClick={() => insertPh(it.key)}
                          className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all active:scale-[0.98] text-left ${COLOR_BADGE[g.color]}`}>
                          <div className="min-w-0">
                            <p className="text-xs font-black leading-tight">{it.label}</p>
                            <p className="text-[10px] opacity-70 mt-0.5 leading-tight">{it.desc}</p>
                          </div>
                          <span className="ml-3 font-mono text-[10px] opacity-60 shrink-0">%{it.key}%</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Кастомные плейсхолдеры из БД */}
                {customPlaceholders.length > 0 && (
                  <div>
                    <div className="mb-2">
                      <p className="text-[11px] font-black text-gray-500 uppercase tracking-wider">Кастомные</p>
                      <p className="text-[10px] text-gray-400">Созданы вручную через бота</p>
                    </div>
                    <div className="space-y-1">
                      {customPlaceholders.map(ph => (
                        <button key={ph.name}
                          onClick={() => insertPh(ph.name)}
                          className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all active:scale-[0.98] text-left bg-gray-50 text-gray-700 border border-gray-100 hover:bg-gray-100">
                          <div className="min-w-0">
                            <p className="text-xs font-black leading-tight">{ph.name}</p>
                            {ph.description && <p className="text-[10px] opacity-60 mt-0.5 leading-tight">{ph.description}</p>}
                            {ph.value && <p className="text-[10px] text-blue-500 mt-0.5 leading-tight truncate max-w-[180px]">{ph.value}</p>}
                          </div>
                          <span className="ml-3 font-mono text-[10px] opacity-50 shrink-0">%{ph.name}%</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="bg-gray-50 border border-gray-100 rounded-2xl p-3">
                  <p className="text-[10px] font-black text-gray-500 mb-1">💡 Для цитируемого</p>
                  <p className="text-[10px] text-gray-400 leading-relaxed">Замени <code className="bg-gray-200 px-1 rounded">act_</code> на <code className="bg-gray-200 px-1 rounded">rpl_</code> — получишь данные пользователя, на сообщение которого ответили.</p>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Попап: подсказка по тумблеру настроек ── */}
      {settingHint && (() => {
        const HINTS = {
          delete_after:      'Сообщение бота будет удалено через указанное время. Оставьте "0", чтобы не удалять.',
          send_delayed:      'Сообщение будет отправлено через указанное время после срабатывания триггера.',
          pin:               'Отправленное сообщение автоматически закрепится в шапке чата.',
          disable_preview:   'В Telegram ссылки показывают превью. Включи — превью скрыто не будет.',
          disable_notify:    'Сообщение придёт без звука. Удобно для ночных рассылок.',
          delete_previous:   'Предыдущее сообщение бота по этому триггеру будет удалено при следующем срабатывании.',
          content_protection:'Защищает содержимое сообщения от пересылки и сохранения.',
        };
        const left = Math.min(settingHintPos.x, window.innerWidth - 300);
        const top  = Math.min(settingHintPos.y, window.innerHeight - 120);
        return (
          <div className="fixed z-[400] w-72 bg-white rounded-2xl shadow-2xl border border-gray-100 p-4 animate-in fade-in zoom-in-95 duration-150"
            style={{left, top}}>
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Info size={14} className="text-blue-500"/>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed flex-1">{HINTS[settingHint]}</p>
              <button onClick={() => setSettingHint(null)}
                className="w-5 h-5 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-400 flex-shrink-0 transition-all">
                <X size={10}/>
              </button>
            </div>
          </div>
        );
      })()}

      {/* ── Модал: справка по кнопкам форматирования ── */}
      {showEditorHelp && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150"
          onClick={() => setShowEditorHelp(false)}>
          <div className="bg-white rounded-3xl shadow-2xl w-[420px] max-w-[95vw] max-h-[85vh] overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}>

            {/* Шапка */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <p className="font-black text-gray-900 text-base">Подсказка по форматированию</p>
              <button onClick={() => setShowEditorHelp(false)}
                className="w-7 h-7 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-all active:scale-90">
                <X size={14}/>
              </button>
            </div>

            {/* Контент */}
            <div className="overflow-y-auto p-5 space-y-5 max-h-[70vh]">
              {[
                { btn:'B',  label:'Жирный',        tag:'<b>',           preview:<><b>Привет, как дела?</b></> },
                { btn:'I',  label:'Курсив',         tag:'<i>',           preview:<><i>Привет, как дела?</i></> },
                { btn:'S',  label:'Зачеркнутый',    tag:'<s>',           preview:<><s>Привет, как дела?</s></> },
                { btn:'U',  label:'Подчеркнутый',   tag:'<u>',           preview:<><u>Привет, как дела?</u></> },
                { btn:'<>',  label:'Моноширинный (code)', tag:'<code>',  preview:<><code className="bg-gray-100 px-1 rounded text-sm">Привет, как дела?</code></> },
                { btn:'»',  label:'Цитата (blockquote)', tag:'<blockquote>', preview:<div className="border-l-4 border-gray-300 pl-3 text-gray-500 italic text-sm">Привет, как дела?</div> },
                { btn:'🔗', label:'Ссылка',         tag:'<a href="...">',preview:<><a className="text-blue-500 underline" href="#">Привет, как дела?</a></> },
                { btn:'✒',  label:'Скрытый текст (spoiler)', tag:'<tg-spoiler>', preview:<span className="bg-gray-800 text-gray-800 rounded px-1 select-none text-sm">Привет, как дела?</span> },
                { btn:'Tx', label:'Очистить форматирование', tag:'—',    preview:<>Привет, как дела?</> },
              ].map(row => (
                <div key={row.btn}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-6 h-6 bg-blue-100 text-blue-600 text-[11px] font-black rounded flex items-center justify-center flex-shrink-0">{row.btn}</span>
                    <span className="text-sm font-black text-gray-800">{row.label}</span>
                    <span className="ml-auto text-[10px] font-mono text-gray-400 bg-gray-50 px-2 py-0.5 rounded">{row.tag}</span>
                  </div>
                  <div className="flex items-center gap-3 bg-gray-50 rounded-2xl px-4 py-3 border border-gray-100 min-h-[42px]">
                    <span className="text-sm text-gray-700">{row.preview}</span>
                  </div>
                </div>
              ))}

              <div className="bg-amber-50 border border-amber-100 rounded-2xl px-4 py-3">
                <p className="text-[11px] font-black text-amber-700 mb-1">💡 Совет</p>
                <p className="text-[11px] text-amber-600 leading-relaxed">
                  Выдели текст, затем нажми кнопку — форматирование применится к выделенному фрагменту.
                  Для цитируемого пользователя в плейсхолдерах замени <b>act_</b> на <b>rpl_</b>.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Модал: предпросмотр сообщения ── */}
      {showPreview && (
        <div className="fixed inset-0 z-[350] flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={() => setShowPreview(null)}>
          <div className="w-[380px] max-w-[95vw] flex flex-col" onClick={e => e.stopPropagation()}>
            {/* Шапка */}
            <div className="flex items-center justify-between mb-3 px-1">
              <span className="text-xs font-black text-white/70 uppercase tracking-widest">Предпросмотр</span>
              <button onClick={() => setShowPreview(null)}
                className="w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-all">
                <X size={14}/>
              </button>
            </div>

            {/* TG-style bubble */}
            <div className="bg-[#212121] rounded-2xl p-4 shadow-2xl">
              {/* Sender */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-sm font-black flex-shrink-0">🤖</div>
                <div>
                  <p className="text-sm font-black text-[#6ab3f3]">Bot</p>
                </div>
              </div>

              {/* Медиа */}
              {showPreview.mediaUrl && showPreview.mediaType !== 'none' && (
                <div className="mb-2 rounded-xl overflow-hidden">
                  {showPreview.mediaType === 'photo' || showPreview.mediaType === 'animation' ? (
                    <img src={showPreview.mediaUrl} alt="media" className="w-full max-h-64 object-contain bg-black/20"/>
                  ) : (
                    <video src={showPreview.mediaUrl} className="w-full max-h-64 object-contain bg-black/20" controls muted/>
                  )}
                </div>
              )}

              {/* Текст (HTML) */}
              {showPreview.text && (
                <div
                  className="text-[14px] leading-relaxed text-white mb-2 break-words"
                  style={{fontFamily:'system-ui,sans-serif'}}
                  dangerouslySetInnerHTML={{__html: showPreview.text}}
                />
              )}
              {!showPreview.text && !showPreview.mediaUrl && (
                <p className="text-sm text-white/40 italic mb-2">Текст не задан</p>
              )}

              {/* Время */}
              <div className="flex justify-end">
                <span className="text-[11px] text-white/40">{new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}</span>
              </div>

              {/* Клавиатура */}
              {showPreview.keyboard && showPreview.keyboard.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {showPreview.keyboard.map((btn, bi) => (
                    <div key={bi} className="w-full py-2 rounded-xl bg-[#2b5278] text-center text-sm font-bold text-[#6ab3f3] select-none">
                      {btn.emoji ? `${btn.emoji} ` : ''}{btn.text || 'Кнопка'}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Модал: подтверждение выхода из редактора триггера ── */}
      {showLeaveConfirm && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl shadow-2xl p-6 w-80 max-w-[90vw] space-y-4 animate-in zoom-in-95 duration-200">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Info size={20} className="text-amber-600"/>
              </div>
              <div>
                <p className="font-black text-gray-900 text-base leading-tight">Внимание</p>
                <p className="text-sm text-gray-500 mt-1.5 leading-relaxed">
                  Вы уверены, что хотите покинуть раздел?<br/>
                  Несохранённые изменения триггера будут потеряны.
                </p>
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => {
                  setShowLeaveConfirm(false);
                  setEditingTrigger(null);
                  if (leaveTarget) { _doNavigate(leaveTarget); }
                  setLeaveTarget(null);
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-gray-600 bg-gray-100 hover:bg-gray-200 active:scale-95 transition-all">
                Выйти
              </button>
              <button
                onClick={() => { setShowLeaveConfirm(false); setLeaveTarget(null); }}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-blue-500 hover:bg-blue-600 active:scale-95 transition-all shadow-md shadow-blue-200">
                Продолжить настройку
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
