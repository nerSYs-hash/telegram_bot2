/* ===================================================
   PULSE CHAT — App Initializer
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // Init theme
  Theme.init();

  // Init notifications
  if (typeof Notify !== 'undefined') Notify.init();

  // Init input listener
  const msgInput = document.getElementById('msgInput');
  if (msgInput) {
    msgInput.addEventListener('input', () => Chat._updateSendBtn());
  }

  // Close context menu on outside click
  document.addEventListener('click', (e) => {
    const menu = document.querySelector('.context-menu');
    if (menu && !menu.contains(e.target)) menu.remove();
    const picker = document.querySelector('.reaction-picker');
    if (picker && !picker.contains(e.target)) picker.remove();
  });

  // ═══ CHECK INVITE URL FIRST ═══
  if (typeof Invite !== 'undefined' && Invite.checkUrl()) {
    console.log('🔗 Invite link detected');
    if (!State.currentUser) {
      Auth.tryAutoLogin();
    }
  }
  // ═══ АВТОЛОГИН ═══
  else if (!Auth.tryAutoLogin()) {
    console.log('👋 Не авторизован — показываем лендинг');
  }

  console.log('✨ Pulse Chat initialized');

  // Reset title when tab becomes visible again
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && typeof Notify !== 'undefined') {
      Notify.clearUnread();
    }
  });
});
