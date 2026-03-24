(function() {
  'use strict';

  // Konfiguracija
  const CONFIG = {
    apiUrl: 'https://pod-goro-ai-production.up.railway.app/chat',
    brandColor: '#3a6b35',
    brandColorHover: '#5d472d',
    title: 'Domačija Pod Goro',
    subtitle: 'Kako vam lahko pomagam?',
    placeholder: 'Vprašajte karkoli...',
    welcomeMessage: 'Pozdravljeni! 👋 Sem vaš virtualni pomočnik za Domačijo Pod Goro. Kako vam lahko pomagam z rezervacijo ali informacijami?',
    mobileBreakpoint: 768,
    autoOpenDesktop: true,  // Auto-popup na desktopu
    autoOpenDelay: 2000,  // ms
    maxStoredMessages: 50  // Maksimalno število shranjenih sporočil
  };

  // CSS stili
  const styles = `
    #kv-widget-container * {
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    #kv-widget-bubble {
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: ${CONFIG.brandColor};
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 999999;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    #kv-widget-bubble:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 24px rgba(0,0,0,0.25);
    }

    #kv-widget-bubble svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    #kv-widget-bubble.kv-has-notification::after {
      content: '';
      position: absolute;
      top: 2px;
      right: 2px;
      width: 14px;
      height: 14px;
      background: #ef4444;
      border-radius: 50%;
      border: 2px solid white;
    }

    #kv-widget-panel {
      position: fixed;
      bottom: 90px;
      right: 20px;
      width: 380px;
      height: 520px;
      max-height: calc(100vh - 120px);
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      z-index: 999998;
      opacity: 0;
      visibility: hidden;
      transform: translateY(20px);
      transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s;
    }

    #kv-widget-panel.kv-open {
      opacity: 1;
      visibility: visible;
      transform: translateY(0);
    }

    /* Mobilni full-screen */
    @media (max-width: ${CONFIG.mobileBreakpoint}px) {
      #kv-widget-panel {
        position: fixed !important;
        inset: 0 !important;
        width: 100% !important;
        height: 100dvh !important;
        height: 100vh !important;
        max-height: none !important;
        border-radius: 0 !important;
        margin: 0 !important;
      }

      #kv-widget-panel.kv-open {
        opacity: 1 !important;
        visibility: visible !important;
        transform: translateY(0) !important;
      }

      #kv-widget-bubble {
        bottom: 20px;
        right: 20px;
        width: 56px;
        height: 56px;
      }

      #kv-widget-header {
        padding-top: max(16px, env(safe-area-inset-top)) !important;
        padding-left: max(16px, env(safe-area-inset-left)) !important;
        padding-right: max(16px, env(safe-area-inset-right)) !important;
      }

      #kv-widget-messages {
        -webkit-overflow-scrolling: touch;
        padding-left: max(16px, env(safe-area-inset-left));
        padding-right: max(16px, env(safe-area-inset-right));
      }

      #kv-widget-input-area {
        padding-bottom: max(12px, env(safe-area-inset-bottom)) !important;
        padding-left: max(16px, env(safe-area-inset-left)) !important;
        padding-right: max(16px, env(safe-area-inset-right)) !important;
      }

      #kv-widget-input {
        font-size: 16px !important; /* Prepreči zoom na iOS */
      }

      #kv-scroll-down {
        bottom: 90px;
      }
    }

    #kv-widget-header {
      background: #ffffff;
      color: #1a1a1a;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
      border-bottom: 1px solid #e8e0d8;
    }

    #kv-widget-header-icon {
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    #kv-widget-header-icon img {
      width: 48px;
      height: 48px;
      object-fit: contain;
    }

    #kv-widget-header-text {
      flex: 1;
    }

    #kv-widget-header-text h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: ${CONFIG.brandColor};
    }

    #kv-widget-header-text p {
      margin: 2px 0 0;
      font-size: 12px;
      color: #6a6a6a;
    }

    .kv-header-btn {
      background: none;
      border: none;
      color: ${CONFIG.brandColor};
      cursor: pointer;
      padding: 8px;
      border-radius: 8px;
      transition: background 0.15s;
    }

    .kv-header-btn:hover {
      background: rgba(123,94,59,0.1);
    }

    .kv-header-btn svg {
      width: 18px;
      height: 18px;
      fill: ${CONFIG.brandColor};
    }

    #kv-widget-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      background: #f9f7f5;
    }

    .kv-message {
      margin-bottom: 12px;
      display: flex;
      flex-direction: column;
    }

    .kv-message.kv-bot {
      align-items: flex-start;
    }

    .kv-message.kv-user {
      align-items: flex-end;
    }

    .kv-message-bubble {
      max-width: 85%;
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    }

    .kv-bot .kv-message-bubble {
      background: white;
      color: #1a1a1a;
      border-bottom-left-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    .kv-user .kv-message-bubble {
      background: ${CONFIG.brandColor};
      color: white;
      border-bottom-right-radius: 4px;
    }

    .kv-typing {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
    }

    .kv-typing span {
      width: 8px;
      height: 8px;
      background: #999;
      border-radius: 50%;
      animation: kv-bounce 1.2s infinite;
    }

    .kv-typing span:nth-child(2) { animation-delay: 0.2s; }
    .kv-typing span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes kv-bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-6px); }
    }

    #kv-widget-input-area {
      padding: 12px 16px;
      background: white;
      border-top: 1px solid #eee;
      display: flex;
      gap: 10px;
      flex-shrink: 0;
    }

    #kv-widget-input {
      flex: 1;
      border: 1px solid #ddd;
      border-radius: 24px;
      padding: 12px 18px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s;
    }

    #kv-widget-input:focus {
      border-color: ${CONFIG.brandColor};
    }

    #kv-widget-send {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: ${CONFIG.brandColor};
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
      flex-shrink: 0;
    }

    #kv-widget-send:hover {
      background: ${CONFIG.brandColorHover};
    }

    #kv-widget-send:disabled {
      background: #ccc;
      cursor: not-allowed;
    }

    #kv-widget-send svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    /* Scroll down arrow indicator */
    #kv-scroll-down {
      position: absolute;
      bottom: 80px;
      left: 50%;
      transform: translateX(-50%);
      width: 36px;
      height: 36px;
      background: ${CONFIG.brandColor};
      border-radius: 50%;
      display: none;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      z-index: 10;
      animation: kv-bounce-arrow 1s infinite;
    }

    #kv-scroll-down.kv-visible {
      display: flex;
    }

    #kv-scroll-down svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    @keyframes kv-bounce-arrow {
      0%, 100% { transform: translateX(-50%) translateY(0); }
      50% { transform: translateX(-50%) translateY(4px); }
    }
  `;

  // Ikone (SVG)
  const icons = {
    chat: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7z"/></svg>',
    close: '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    send: '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>',
    home: '<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>',
    arrowDown: '<svg viewBox="0 0 24 24"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>'
  };

  // Session ID in shranjeni pogovori
  let sessionId = localStorage.getItem('kv_widget_session') || generateSessionId();
  localStorage.setItem('kv_widget_session', sessionId);

  // Naloži shranjene pogovore
  let storedMessages = [];
  try {
    const stored = localStorage.getItem('kv_widget_messages');
    if (stored) {
      storedMessages = JSON.parse(stored);
    }
  } catch (e) {
    storedMessages = [];
  }

  function generateSessionId() {
    return 'widget_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  function saveMessages() {
    // Ohrani samo zadnjih N sporočil
    const toSave = storedMessages.slice(-CONFIG.maxStoredMessages);
    localStorage.setItem('kv_widget_messages', JSON.stringify(toSave));
  }

  function clearConversation() {
    storedMessages = [];
    localStorage.removeItem('kv_widget_messages');
    // Nov session ID za nov pogovor
    sessionId = generateSessionId();
    localStorage.setItem('kv_widget_session', sessionId);
    // Počisti UI
    const messages = document.getElementById('kv-widget-messages');
    messages.innerHTML = '';
    // Dodaj welcome message
    addMessage(CONFIG.welcomeMessage, 'bot', false);
  }

  // Ustvari widget HTML
  function createWidget() {
    // Dodaj stile
    const styleEl = document.createElement('style');
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);

    // Container
    const container = document.createElement('div');
    container.id = 'kv-widget-container';

    // Bubble (ikonica)
    const bubble = document.createElement('div');
    bubble.id = 'kv-widget-bubble';
    bubble.innerHTML = icons.chat;
    bubble.onclick = togglePanel;

    // Panel
    const panel = document.createElement('div');
    panel.id = 'kv-widget-panel';
    panel.innerHTML = `
      <div id="kv-widget-header">
        <div id="kv-widget-header-icon"><img src="https://kovacnik.com/wp-content/uploads/2023/03/LOGO-KOVACNIK-2023.png" alt="Pod Goro"></div>
        <div id="kv-widget-header-text">
          <h3>${CONFIG.title}</h3>
          <p>${CONFIG.subtitle}</p>
        </div>
        <button class="kv-header-btn" id="kv-widget-refresh" title="Nov pogovor">${icons.refresh}</button>
        <button class="kv-header-btn" id="kv-widget-close" title="Zapri">${icons.close}</button>
      </div>
      <div id="kv-widget-messages"></div>
      <div id="kv-scroll-down" title="Scroll dol">${icons.arrowDown}</div>
      <div id="kv-widget-input-area">
        <input type="text" id="kv-widget-input" placeholder="${CONFIG.placeholder}">
        <button id="kv-widget-send">${icons.send}</button>
      </div>
    `;

    container.appendChild(bubble);
    container.appendChild(panel);
    document.body.appendChild(container);

    // Event listeners
    document.getElementById('kv-widget-close').onclick = closePanel;
    document.getElementById('kv-widget-refresh').onclick = clearConversation;
    document.getElementById('kv-widget-send').onclick = sendMessage;
    document.getElementById('kv-widget-input').onkeypress = function(e) {
      if (e.key === 'Enter') sendMessage();
    };

    // Scroll arrow functionality
    const messagesEl = document.getElementById('kv-widget-messages');
    const scrollArrow = document.getElementById('kv-scroll-down');

    scrollArrow.onclick = function() {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    messagesEl.onscroll = function() {
      const isNearBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 50;
      if (isNearBottom) {
        scrollArrow.classList.remove('kv-visible');
      }
    };

    // Naloži shranjene pogovore ali welcome message (brez auto-scroll)
    if (storedMessages.length > 0) {
      storedMessages.forEach(function(msg) {
        addMessageToUI(msg.text, msg.sender, false);  // false = ne scrollaj
      });
    } else {
      addMessageToUI(CONFIG.welcomeMessage, 'bot', false);  // false = ne scrollaj
    }

    // Auto-open na desktopu - vedno odpri na desktopu
    if (CONFIG.autoOpenDesktop && window.innerWidth > CONFIG.mobileBreakpoint) {
      setTimeout(function() {
        if (!document.getElementById('kv-widget-panel').classList.contains('kv-open')) {
          openPanel();
        }
      }, CONFIG.autoOpenDelay);
    }
  }

  function togglePanel() {
    const panel = document.getElementById('kv-widget-panel');
    if (panel.classList.contains('kv-open')) {
      closePanel();
    } else {
      openPanel();
    }
  }

  function openPanel() {
    document.getElementById('kv-widget-panel').classList.add('kv-open');
    document.getElementById('kv-widget-bubble').classList.remove('kv-has-notification');
    // Na mobilnem: skrij bubble in blokiraj scroll strani
    if (window.innerWidth <= CONFIG.mobileBreakpoint) {
      document.getElementById('kv-widget-bubble').style.display = 'none';
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.width = '100%';
    }
    document.getElementById('kv-widget-input').focus();
    localStorage.setItem('kv_widget_open', 'true');
    // NE scrollaj na dno - ostani na vrhu
    // Če je več vsebine, pokaži puščico
    const messages = document.getElementById('kv-widget-messages');
    const scrollArrow = document.getElementById('kv-scroll-down');
    if (messages.scrollHeight > messages.clientHeight) {
      scrollArrow.classList.add('kv-visible');
    }
  }

  function closePanel() {
    document.getElementById('kv-widget-panel').classList.remove('kv-open');
    // Pokaži bubble spet in omogoči scroll strani
    document.getElementById('kv-widget-bubble').style.display = 'flex';
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.width = '';
    localStorage.setItem('kv_widget_open', 'false');
  }

  function addMessageToUI(text, sender, autoScroll = true) {
    const messages = document.getElementById('kv-widget-messages');
    const scrollArrow = document.getElementById('kv-scroll-down');

    const msg = document.createElement('div');
    msg.className = 'kv-message kv-' + sender;
    msg.innerHTML = '<div class="kv-message-bubble">' + escapeHtml(text) + '</div>';
    messages.appendChild(msg);

    // Če je autoScroll false (pri nalaganju), ne scrollaj
    if (!autoScroll) return;

    // Ko pošlješ novo sporočilo, VEDNO scrollaj na dno da vidiš pogovor
    messages.scrollTop = messages.scrollHeight;
    // Skrij puščico ker smo na dnu
    if (scrollArrow) {
      scrollArrow.classList.remove('kv-visible');
    }
  }

  function addMessage(text, sender, save = true) {
    addMessageToUI(text, sender);
    if (save) {
      storedMessages.push({ text: text, sender: sender, time: Date.now() });
      saveMessages();
    }
  }

  function showTyping() {
    const messages = document.getElementById('kv-widget-messages');
    const scrollArrow = document.getElementById('kv-scroll-down');

    const typing = document.createElement('div');
    typing.id = 'kv-typing-indicator';
    typing.className = 'kv-message kv-bot';
    typing.innerHTML = '<div class="kv-message-bubble kv-typing"><span></span><span></span><span></span></div>';
    messages.appendChild(typing);

    // Vedno scrollaj na dno ko se pokaže typing
    messages.scrollTop = messages.scrollHeight;
    if (scrollArrow) {
      scrollArrow.classList.remove('kv-visible');
    }
  }

  function hideTyping() {
    const typing = document.getElementById('kv-typing-indicator');
    if (typing) typing.remove();
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  async function sendMessage() {
    const input = document.getElementById('kv-widget-input');
    const sendBtn = document.getElementById('kv-widget-send');
    const text = input.value.trim();

    if (!text) return;

    // Dodaj user message
    addMessage(text, 'user');
    input.value = '';
    sendBtn.disabled = true;

    // Pokaži typing indicator
    showTyping();

    try {
      const response = await fetch(CONFIG.apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionId
        })
      });

      hideTyping();

      if (!response.ok) throw new Error('API error');

      const data = await response.json();
      const reply = data.reply || data.response || data.message || 'Oprostite, prišlo je do napake.';
      addMessage(reply, 'bot');

    } catch (err) {
      hideTyping();
      addMessage('Oprostite, trenutno ni mogoče vzpostaviti povezave. Poskusite ponovno.', 'bot');
      console.error('[KV Widget] Error:', err);
    }

    sendBtn.disabled = false;
    input.focus();
  }

  // Zaženi widget ko je DOM pripravljen
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidget);
  } else {
    createWidget();
  }
})();
