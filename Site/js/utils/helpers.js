/* ===================================================
   PULSE CHAT — Utility Helpers
   =================================================== */

const AVATAR_COLORS = [
  '#e17076', '#eda86c', '#a695e7', '#7bc862',
  '#6ec9cb', '#65aadd', '#ee7aae', '#faa774'
];

function getAvatarColor(id) {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function getInitials(name) {
  const parts = name.split(' ');
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.substring(0, 2).toUpperCase();
}

function formatTime(ts) {
  const d = new Date(ts);
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
}

function formatDateSep(ts) {
  const d = new Date(ts);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return 'Сегодня';
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Вчера';
  const months = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
  return d.getDate() + ' ' + months[d.getMonth()];
}

function formatChatTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  const days = Math.floor((now - d) / 86400000);
  if (days === 0) return formatTime(ts);
  if (days === 1) return 'Вчера';
  if (days < 7) return ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'][d.getDay()];
  return d.getDate() + '.' + (d.getMonth() + 1).toString().padStart(2, '0');
}

function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString('ru-RU');
}

function formatLastSeen(ts) {
  const mins = Math.floor((Date.now() - ts) / 60000);
  if (mins < 1) return 'только что';
  if (mins < 60) return `${mins} мин. назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч. назад`;
  return formatDateSep(ts) + ' в ' + formatTime(ts);
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function linkify(text) {
  // Linkify URLs
  text = text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:var(--accent)">$1</a>');
  // Highlight @mentions
  text = text.replace(/@(\w+)/g, '<span class="msg-mention" onclick="event.stopPropagation()">@$1</span>');
  return text;
}

// ═══ TG Ripple Effect ═══
function initRipple(el) {
  if (!el || el._rippleInit) return;
  el._rippleInit = true;
  el.classList.add('rp');
  el.addEventListener('pointerdown', function(e) {
    const rippleContainer = document.createElement('div');
    rippleContainer.className = 'c-ripple';
    const circle = document.createElement('div');
    circle.className = 'c-ripple__circle';
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    circle.style.width = circle.style.height = size + 'px';
    circle.style.left = (e.clientX - rect.left - size/2) + 'px';
    circle.style.top = (e.clientY - rect.top - size/2) + 'px';
    rippleContainer.appendChild(circle);
    el.appendChild(rippleContainer);
    setTimeout(() => rippleContainer.remove(), 400);
  });
}

// ═══ TG Avatar Gradient Colors ═══
const TG_AVATAR_COLORS = ['red','orange','violet','green','cyan','blue','pink'];
function getAvatarColor(id) {
  return TG_AVATAR_COLORS[(id || 0) % TG_AVATAR_COLORS.length];
}
function makeAvatarHTML(name, id, size) {
  const s = size || 54;
  const color = getAvatarColor(id);
  const initials = name ? (name.length >= 2 ? name.substring(0,2) : name[0] || '?').toUpperCase() : '?';
  const fontSize = Math.round(s * 0.38);
  return `<div class="avatar-gradient" data-color="${color}" style="width:${s}px;height:${s}px;font-size:${fontSize}px">${initials}</div>`;
}
