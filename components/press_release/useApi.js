// Тонкий API-клиент для пресс-релизов

export function makeApi(token) {
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  const j = (r) => r.ok ? r.json() : r.json().then((e) => Promise.reject(e));

  return {
    // bot_chats
    listChats:        ()                 => fetch('/api/bot-chats', { headers }).then(j),
    addChatLookup:    (chat_id_or_username) => fetch('/api/bot-chats/lookup', { method:'POST', headers, body: JSON.stringify({ chat_id_or_username }) }).then(j),
    addTopic:         (body)             => fetch('/api/bot-chats/topics',  { method:'POST', headers, body: JSON.stringify(body) }).then(j),
    deleteTopic:      (cid, tid)         => fetch(`/api/bot-chats/topics/${cid}/${tid}`, { method:'DELETE', headers }).then(j),

    // press releases
    list:             (status)           => fetch(`/api/press-releases${status ? `?status=${status}` : ''}`, { headers }).then(j),
    get:              (id)               => fetch(`/api/press-releases/${id}`, { headers }).then(j),
    create:           (body)             => fetch('/api/press-releases', { method:'POST', headers, body: JSON.stringify(body) }).then(j),
    update:           (id, body)         => fetch(`/api/press-releases/${id}`, { method:'PUT', headers, body: JSON.stringify(body) }).then(j),
    remove:           (id)               => fetch(`/api/press-releases/${id}`, { method:'DELETE', headers }).then(j),
    cancel:           (id)               => fetch(`/api/press-releases/${id}/cancel`, { method:'POST', headers }).then(j),
    restore:          (id)               => fetch(`/api/press-releases/${id}/restore`, { method:'POST', headers }).then(j),
    clone:            (id)               => fetch(`/api/press-releases/${id}/clone`,   { method:'POST', headers }).then(j),
    publishNow:       (id)               => fetch(`/api/press-releases/${id}/publish-now`, { method:'POST', headers }).then(j),
    deleteFromTg:     (id)               => fetch(`/api/press-releases/${id}/from-telegram`, { method:'DELETE', headers }).then(j),
    versions:         (id)               => fetch(`/api/press-releases/${id}/versions`, { headers }).then(j),

    // templates
    listTemplates:    ()                 => fetch('/api/press-release-templates', { headers }).then(j),
    createTemplate:   (body)             => fetch('/api/press-release-templates', { method:'POST', headers, body: JSON.stringify(body) }).then(j),
    updateTemplate:   (id, body)         => fetch(`/api/press-release-templates/${id}`, { method:'PUT', headers, body: JSON.stringify(body) }).then(j),
    deleteTemplate:   (id)               => fetch(`/api/press-release-templates/${id}`, { method:'DELETE', headers }).then(j),

    // branding
    getBranding:      ()                 => fetch('/api/branding', { headers }).then(j),
    setBranding:      (key, value)       => fetch('/api/branding', { method:'PUT', headers, body: JSON.stringify({ key, value }) }).then(j),
  };
}
