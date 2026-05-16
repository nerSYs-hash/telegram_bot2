// Workspaces API wrapper (V1.17.0b12)
// V1.17.0d (Подпроект #3): активный workspace в localStorage + общий хедер.
const WS_KEY = 'active_ws_id';

export function getActiveWs() {
  const v = localStorage.getItem(WS_KEY);
  return v ? parseInt(v, 10) : null;
}

export function setActiveWs(wsId) {
  if (wsId == null) localStorage.removeItem(WS_KEY);
  else localStorage.setItem(WS_KEY, String(wsId));
}

function wsHeaders(token, extra = {}) {
  const h = { Authorization: `Bearer ${token}`, ...extra };
  const ws = getActiveWs();
  if (ws != null) h['X-Workspace-Id'] = String(ws);
  return h;
}

export async function fetchWorkspaces(token) {
  const r = await fetch('/api/workspaces', {
    headers: wsHeaders(token),
  });
  if (!r.ok) throw new Error(`fetchWorkspaces ${r.status}`);
  return r.json();
}

export async function fetchWorkspaceDetails(token, wsId) {
  const r = await fetch(`/api/workspaces/${wsId}`, {
    headers: wsHeaders(token),
  });
  if (!r.ok) throw new Error(`fetchWorkspaceDetails ${r.status}`);
  return r.json();
}

export async function inviteMember(token, wsId, userId, role) {
  const r = await fetch(`/api/workspaces/${wsId}/members`, {
    method: 'POST',
    headers: wsHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, role }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `inviteMember ${r.status}`);
  }
  return r.json();
}

export async function removeMember(token, wsId, userId) {
  const r = await fetch(`/api/workspaces/${wsId}/members/${userId}`, {
    method: 'DELETE',
    headers: wsHeaders(token),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `removeMember ${r.status}`);
  }
  return r.json();
}

export async function renameWorkspace(token, wsId, newName) {
  const r = await fetch(`/api/workspaces/${wsId}`, {
    method: 'PATCH',
    headers: wsHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ name: newName }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `renameWorkspace ${r.status}`);
  }
  return r.json();
}

// V1.17.0c (F): обновить роль чата (main|admin|journal|null)
export async function updateChatRole(token, wsId, chatId, role) {
  const r = await fetch(`/api/workspaces/${wsId}/chats/${chatId}`, {
    method: 'PATCH',
    headers: wsHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ role }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `updateChatRole ${r.status}`);
  }
  return r.json();
}

// V1.17.0c (G): отключить чат от сообщества (бот покидает чат)
export async function disconnectChat(token, wsId, chatId) {
  const r = await fetch(`/api/workspaces/${wsId}/chats/${chatId}`, {
    method: 'DELETE',
    headers: wsHeaders(token),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `disconnectChat ${r.status}`);
  }
  return r.json();
}

// V1.17.0c (G): удалить сообщество целиком (бот покидает все его чаты)
export async function deleteWorkspace(token, wsId) {
  const r = await fetch(`/api/workspaces/${wsId}`, {
    method: 'DELETE',
    headers: wsHeaders(token),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `deleteWorkspace ${r.status}`);
  }
  return r.json();
}
