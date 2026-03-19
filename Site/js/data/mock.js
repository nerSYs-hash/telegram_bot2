/* ===================================================
   PULSE CHAT — Mock Data (dev mode)
   Replace with API calls in production
   =================================================== */

const NOW = Date.now();
const MIN = 60000;
const HOUR = 3600000;

const contacts = {
  1: { id:1, name:'Алексей Петров', online:true, lastSeen:NOW },
  2: { id:2, name:'Мария Иванова', online:false, lastSeen:NOW-35*MIN },
  3: { id:3, name:'Дмитрий Козлов', online:true, lastSeen:NOW },
  4: { id:4, name:'Елена Смирнова', online:false, lastSeen:NOW-3*HOUR },
  5: { id:5, name:'Группа: Работа', isGroup:true, members:[1,2,3,4] },
  6: { id:6, name:'Анна Волкова', online:false, lastSeen:NOW-24*HOUR },
  8: { id:8, name:'Канал: Новости', isChannel:true },
};

const chats = [
  { id:101, contactId:1, pinned:true, muted:false, unread:2, messages:[
    { id:'m1', from:1, text:'Привет! Как дела?', ts:NOW-2*HOUR, status:'read' },
    { id:'m2', from:0, text:'Привет! Работаю над Pulse', ts:NOW-2*HOUR+3*MIN, status:'read' },
    { id:'m3', from:1, text:'Какой проект?', ts:NOW-HOUR, status:'read' },
    { id:'m4', from:0, text:'Делаю мессенджер — Pulse Chat', ts:NOW-58*MIN, status:'read' },
    { id:'m5', from:1, text:'Круто! Покажешь когда готов?', ts:NOW-50*MIN, status:'read' },
    { id:'m6', from:1, text:'Кстати, завтра встречаемся?', ts:NOW-5*MIN, status:'delivered' },
  ]},
  { id:102, contactId:2, pinned:false, muted:false, unread:0, messages:[
    { id:'m10', from:2, text:'Документы отправила на почту', ts:NOW-5*HOUR, status:'read' },
    { id:'m11', from:0, text:'Спасибо! Посмотрю', ts:NOW-4.5*HOUR, status:'read' },
    { id:'m12', from:0, text:'Получил, выглядит отлично 👍', ts:NOW-4*HOUR, status:'read' },
  ]},
  { id:103, contactId:5, pinned:true, muted:true, unread:14, messages:[
    { id:'m20', from:3, text:'Коллеги, завтра митинг в 10:00', ts:NOW-3*HOUR, status:'read' },
    { id:'m21', from:1, text:'Буду!', ts:NOW-2.5*HOUR, status:'read' },
    { id:'m22', from:4, text:'Подготовлю презентацию', ts:NOW-2*HOUR, status:'read' },
    { id:'m23', from:2, text:'Кто ведёт встречу?', ts:NOW-30*MIN, status:'delivered' },
  ]},
  { id:104, contactId:3, pinned:false, muted:false, unread:1, messages:[
    { id:'m30', from:0, text:'Дима, отправь файлы', ts:NOW-8*HOUR, status:'read' },
    { id:'m31', from:3, text:'Да, секунду', ts:NOW-7.5*HOUR, status:'read' },
    { id:'m32', from:3, text:'Готово, проверяй!', ts:NOW-20*MIN, status:'delivered' },
  ]},
  { id:105, contactId:4, pinned:false, muted:false, unread:0, messages:[
    { id:'m40', from:4, text:'Добрый день!', ts:NOW-26*HOUR, status:'read' },
    { id:'m41', from:0, text:'Отправлю завтра', ts:NOW-24*HOUR, status:'read' },
  ]},
  { id:106, contactId:6, pinned:false, muted:false, unread:0, messages:[
    { id:'m50', from:6, text:'Видел новую вакансию?', ts:NOW-48*HOUR, status:'read' },
    { id:'m51', from:0, text:'Нет, пришли ссылку', ts:NOW-47*HOUR, status:'read' },
  ]},
  { id:107, contactId:8, pinned:false, muted:true, unread:5, messages:[
    { id:'m60', from:8, text:'📢 Обновление: новые функции доступны!', ts:NOW-2*HOUR, status:'delivered' },
  ]},
];

// Mock economy data
const mockEconomy = {
  balance: 12450,
  frozen: 500,
  course: 0.042,
  courseChange: +2.5,
};

// Mock top data
const mockTopRich = [
  { id:1, name:'Алексей Петров', balance:45200 },
  { id:3, name:'Дмитрий Козлов', balance:38100 },
  { id:2, name:'Мария Иванова', balance:27300 },
  { id:4, name:'Елена Смирнова', balance:19800 },
  { id:6, name:'Анна Волкова', balance:15600 },
];

const mockTopActive = [
  { id:3, name:'Дмитрий Козлов', index:94.2 },
  { id:1, name:'Алексей Петров', index:87.5 },
  { id:2, name:'Мария Иванова', index:76.1 },
  { id:6, name:'Анна Волкова', index:65.3 },
  { id:4, name:'Елена Смирнова', index:52.8 },
];

// Helpers
function getSortedChats() {
  return [...chats].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return (b.messages[b.messages.length-1]?.ts || 0) - (a.messages[a.messages.length-1]?.ts || 0);
  });
}

let msgCounter = 100;
function newMsgId() { return 'msg_' + (++msgCounter); }
