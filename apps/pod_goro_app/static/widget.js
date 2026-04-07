(function() {
  'use strict';

  const CONFIG = {
    apiUrl: 'https://kmetija-pod-goro-production.up.railway.app/chat',
    brandColor: '#2d3e2f',
    brandColorHover: '#1e2d20',
    accentColor: '#c19a6b',
    title: 'Kmetija Pod Goro',
    subtitle: 'Kako vam lahko pomagam?',
    placeholder: 'Vprašajte karkoli...',
    welcomeMessage: 'Pozdravljeni! 👋 Sem vaš virtualni pomočnik Kmetije Pod Goro. Kako vam lahko pomagam? — Feel free to write in any language!',
    mobileBreakpoint: 768,
    autoOpenDesktop: true,
    autoOpenDelay: 1000,
    maxStoredMessages: 50
  };

  const styles = `
    #pg-widget-container * {
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    #pg-widget-bubble {
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
    #pg-widget-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(0,0,0,0.25); }
    #pg-widget-bubble svg { width: 28px; height: 28px; fill: white; }

    #pg-widget-panel {
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
    #pg-widget-panel.pg-open {
      opacity: 1; visibility: visible; transform: translateY(0);
    }

    @media (max-width: ${CONFIG.mobileBreakpoint}px) {
      #pg-widget-panel {
        position: fixed !important; inset: 0 !important;
        width: 100% !important; height: 100dvh !important;
        height: 100vh !important; max-height: none !important;
        border-radius: 0 !important; margin: 0 !important;
      }
      #pg-widget-bubble { bottom: 20px; right: 20px; width: 56px; height: 56px; }
      #pg-widget-header {
        padding-top: max(16px, env(safe-area-inset-top)) !important;
      }
      #pg-widget-input-area {
        padding-bottom: max(12px, env(safe-area-inset-bottom)) !important;
      }
      #pg-widget-input { font-size: 16px !important; }
    }

    #pg-widget-header {
      background: ${CONFIG.brandColor};
      color: #fff;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    #pg-widget-header-icon {
      width: 40px; height: 40px;
      background: rgba(255,255,255,0.15);
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 20px;
    }
    #pg-widget-header-text { flex: 1; }
    #pg-widget-header-text h3 { margin: 0; font-size: 15px; font-weight: 700; color: #fff; }
    #pg-widget-header-text p { margin: 2px 0 0; font-size: 12px; color: rgba(255,255,255,0.75); }

    .pg-header-btn {
      background: rgba(255,255,255,0.15); border: none; color: #fff;
      cursor: pointer; padding: 7px; border-radius: 8px; transition: background 0.15s;
    }
    .pg-header-btn:hover { background: rgba(255,255,255,0.25); }
    .pg-header-btn svg { width: 16px; height: 16px; fill: #fff; display: block; }

    #pg-widget-messages {
      flex: 1; overflow-y: auto; padding: 16px; background: #f5f4f1;
    }

    .pg-message { margin-bottom: 12px; display: flex; flex-direction: column; }
    .pg-message.pg-bot { align-items: flex-start; }
    .pg-message.pg-user { align-items: flex-end; }
    .pg-message-bubble {
      max-width: 85%; padding: 11px 14px; border-radius: 14px;
      font-size: 14px; line-height: 1.5; word-wrap: break-word;
    }
    .pg-bot .pg-message-bubble {
      background: #fff; color: #2f302b;
      border-bottom-left-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .pg-user .pg-message-bubble {
      background: ${CONFIG.brandColor}; color: white;
      border-bottom-right-radius: 4px;
    }

    .pg-typing { display: flex; gap: 4px; padding: 11px 14px; }
    .pg-typing span {
      width: 8px; height: 8px; background: #aaa;
      border-radius: 50%; animation: pg-bounce 1.2s infinite;
    }
    .pg-typing span:nth-child(2) { animation-delay: 0.2s; }
    .pg-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes pg-bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-6px); }
    }

    #pg-widget-input-area {
      padding: 8px 12px 4px;
      background: white;
      border-top: 1px solid #e8e4de;
      display: flex; gap: 8px; flex-shrink: 0;
    }
    #pg-bf-open-bar {
      padding: 0 12px 10px; background: white;
    }
    #pg-bf-open-btn {
      width: 100%; padding: 9px;
      border-radius: 8px; border: 2px solid ${CONFIG.brandColor};
      background: #f2f7f3; cursor: pointer;
      font-size: 13px; font-weight: 600;
      color: ${CONFIG.brandColor};
      display: flex; align-items: center; justify-content: center; gap: 6px;
      transition: background 0.15s;
    }
    #pg-bf-open-btn:hover { background: #e4f0e6; }

    #pg-widget-powered {
      text-align: center; font-size: 12px; color: #bbb;
      padding: 3px 0 6px; background: white;
    }
    #pg-widget-powered a { color: ${CONFIG.accentColor}; text-decoration: none; }

    #pg-widget-input {
      flex: 1; border: 1px solid #ddd; border-radius: 22px;
      padding: 10px 16px; font-size: 14px; outline: none;
      transition: border-color 0.15s;
    }
    #pg-widget-input:focus { border-color: ${CONFIG.brandColor}; }

    #pg-widget-send {
      width: 40px; height: 40px; border-radius: 50%;
      background: ${CONFIG.brandColor}; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: background 0.15s; flex-shrink: 0;
    }
    #pg-widget-send:hover { background: ${CONFIG.brandColorHover}; }
    #pg-widget-send:disabled { background: #ccc; cursor: not-allowed; }
    #pg-widget-send svg { width: 18px; height: 18px; fill: white; }

    /* Booking form overlay */
    #pg-booking-form {
      position: absolute; inset: 0; background: #fff;
      z-index: 10; display: none; flex-direction: column; overflow: hidden;
    }
    #pg-booking-form.pg-open { display: flex; }

    #pg-bf-header {
      background: ${CONFIG.brandColor}; color: #fff;
      padding: 13px 16px; display: flex; align-items: center; gap: 10px; flex-shrink: 0;
    }
    #pg-bf-header h3 { margin: 0; font-size: 15px; flex: 1; }
    #pg-bf-back {
      background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.5);
      color: #fff; cursor: pointer; padding: 5px 10px; border-radius: 6px;
      font-size: 13px; font-weight: 600; white-space: nowrap; transition: background 0.15s;
    }
    #pg-bf-back:hover { background: rgba(255,255,255,0.35); }

    #pg-bf-body {
      flex: 1; overflow-y: auto; padding: 14px;
      display: flex; flex-direction: column; gap: 11px;
    }

    .pg-bf-tabs { display: flex; gap: 8px; }
    .pg-bf-tab {
      flex: 1; padding: 9px; border: 2px solid #ddd;
      border-radius: 8px; background: #fff; cursor: pointer;
      font-size: 13px; font-weight: 600; color: #666;
      transition: all 0.15s; text-align: center;
    }
    .pg-bf-tab.active {
      border-color: ${CONFIG.brandColor};
      background: #f2f7f3; color: ${CONFIG.brandColor};
    }

    #pg-bf-prices {
      font-size: 11px; color: #888; line-height: 1.6;
      background: #f5f4f1; border-radius: 6px; padding: 7px 10px;
    }
    #pg-bf-prices a { color: ${CONFIG.accentColor}; font-weight: 600; }

    .pg-bf-row { display: flex; gap: 10px; }
    .pg-bf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
    .pg-bf-field label { font-size: 12px; color: #555; font-weight: 600; }
    .pg-bf-field input, .pg-bf-field textarea {
      border: 1px solid #ddd; border-radius: 8px;
      padding: 8px 11px; font-size: 14px; outline: none;
      transition: border-color 0.15s; font-family: inherit;
    }
    .pg-bf-field input:focus, .pg-bf-field textarea:focus { border-color: ${CONFIG.brandColor}; }
    .pg-bf-field textarea { resize: none; height: 58px; }

    .pg-stepper {
      display: flex; align-items: center;
      border: 1px solid #ddd; border-radius: 8px; overflow: hidden; height: 36px;
    }
    .pg-stepper button {
      width: 34px; background: #f0f4f1; border: none;
      font-size: 17px; cursor: pointer; color: ${CONFIG.brandColor};
      font-weight: 700; flex-shrink: 0; height: 100%; transition: background 0.15s;
    }
    .pg-stepper button:hover { background: #dceade; }
    .pg-stepper span {
      flex: 1; text-align: center; font-size: 14px; font-weight: 600; color: #333;
    }

    .pg-bf-section-title {
      font-size: 11px; font-weight: 700; color: #aaa;
      text-transform: uppercase; letter-spacing: 1px; margin-top: 2px;
    }

    .pg-bf-gdpr {
      display: flex; gap: 8px; align-items: flex-start;
      font-size: 12px; color: #888; line-height: 1.4;
    }
    .pg-bf-gdpr input { margin-top: 2px; flex-shrink: 0; }

    #pg-bf-footer {
      padding: 11px 14px;
      padding-bottom: max(11px, env(safe-area-inset-bottom));
      border-top: 1px solid #eee; background: #fff; flex-shrink: 0;
    }
    #pg-bf-submit {
      width: 100%; padding: 12px;
      background: ${CONFIG.brandColor}; color: #fff;
      border: none; border-radius: 9px; font-size: 14px;
      font-weight: 700; cursor: pointer; transition: background 0.15s;
    }
    #pg-bf-submit:hover { background: ${CONFIG.brandColorHover}; }
    #pg-bf-submit:disabled { background: #aaa; cursor: not-allowed; }
  `;

  const icons = {
    chat: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>',
    close: '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    send: '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>'
  };

  let sessionId = localStorage.getItem('pg_widget_session') || generateSessionId();
  localStorage.setItem('pg_widget_session', sessionId);

  let storedMessages = [];
  try {
    const stored = localStorage.getItem('pg_widget_messages');
    if (stored) storedMessages = JSON.parse(stored);
  } catch(e) { storedMessages = []; }

  function generateSessionId() {
    return 'pg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  function saveMessages() {
    localStorage.setItem('pg_widget_messages', JSON.stringify(storedMessages.slice(-CONFIG.maxStoredMessages)));
  }

  function clearConversation() {
    storedMessages = [];
    localStorage.removeItem('pg_widget_messages');
    sessionId = generateSessionId();
    localStorage.setItem('pg_widget_session', sessionId);
    document.getElementById('pg-widget-messages').innerHTML = '';
    addMessage(CONFIG.welcomeMessage, 'bot', false);
  }

  function createWidget() {
    const styleEl = document.createElement('style');
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);

    const container = document.createElement('div');
    container.id = 'pg-widget-container';

    const bubble = document.createElement('div');
    bubble.id = 'pg-widget-bubble';
    bubble.innerHTML = icons.chat;
    bubble.onclick = togglePanel;

    const panel = document.createElement('div');
    panel.id = 'pg-widget-panel';
    panel.innerHTML = `
      <div id="pg-widget-header">
        <div id="pg-widget-header-icon">🏡</div>
        <div id="pg-widget-header-text">
          <h3>${CONFIG.title}</h3>
          <p>${CONFIG.subtitle}</p>
        </div>
        <button class="pg-header-btn" id="pg-widget-refresh" title="Nov pogovor">${icons.refresh}</button>
        <button class="pg-header-btn" id="pg-widget-close" title="Zapri">${icons.close}</button>
      </div>
      <div id="pg-widget-messages"></div>
      <div id="pg-widget-input-area">
        <input type="text" id="pg-widget-input" placeholder="${CONFIG.placeholder}">
        <button id="pg-widget-send">${icons.send}</button>
      </div>
      <div id="pg-bf-open-bar">
        <button id="pg-bf-open-btn">📅 Rezerviraj sobo ali mizo</button>
      </div>
      <div id="pg-widget-powered">built by: <a href="https://spoznaj-ai.si" target="_blank">spoznaj-ai.si</a></div>
    `;

    // Booking form overlay
    const bookingForm = document.createElement('div');
    bookingForm.id = 'pg-booking-form';
    bookingForm.innerHTML = `
      <div id="pg-bf-header">
        <button id="pg-bf-back">&#8592; Nazaj v pogovor</button>
        <h3>Rezervacija</h3>
      </div>
      <div id="pg-bf-body">
        <div class="pg-bf-tabs">
          <button class="pg-bf-tab active" data-type="room">🛏️ Soba</button>
          <button class="pg-bf-tab" data-type="table">🍽️ Miza</button>
        </div>

        <div id="pg-bf-prices"></div>

        <div class="pg-bf-row">
          <div class="pg-bf-field">
            <label>Datum prihoda *</label>
            <input type="date" id="pg-bf-date" required>
          </div>
          <div class="pg-bf-field" id="pg-bf-nights-wrap">
            <label>Število noči</label>
            <div class="pg-stepper">
              <button type="button" data-step="nights" data-dir="-1">−</button>
              <span id="pg-bf-nights-val">2</span>
              <button type="button" data-step="nights" data-dir="1">+</button>
            </div>
          </div>
          <div class="pg-bf-field" id="pg-bf-time-wrap" style="display:none">
            <label>Ura prihoda</label>
            <input type="time" id="pg-bf-time" value="13:00">
          </div>
        </div>

        <div class="pg-bf-section-title">Gostje</div>
        <div class="pg-bf-row">
          <div class="pg-bf-field">
            <label>Odrasli</label>
            <div class="pg-stepper">
              <button type="button" data-step="adults" data-dir="-1">−</button>
              <span id="pg-bf-adults-val">2</span>
              <button type="button" data-step="adults" data-dir="1">+</button>
            </div>
          </div>
          <div class="pg-bf-field">
            <label>Otroci (do 12 let)</label>
            <div class="pg-stepper">
              <button type="button" data-step="children" data-dir="-1">−</button>
              <span id="pg-bf-children-val">0</span>
              <button type="button" data-step="children" data-dir="1">+</button>
            </div>
          </div>
        </div>

        <div id="pg-bf-children-ages-wrap" style="display:none">
          <div class="pg-bf-field">
            <label>Starosti otrok (npr. 5, 8)</label>
            <input type="text" id="pg-bf-children-ages" placeholder="npr. 5, 8">
          </div>
        </div>

        <div class="pg-bf-section-title">Vaši podatki</div>
        <div class="pg-bf-row">
          <div class="pg-bf-field">
            <label>Ime in priimek *</label>
            <input type="text" id="pg-bf-name" placeholder="Janez Novak" required>
          </div>
        </div>
        <div class="pg-bf-row">
          <div class="pg-bf-field">
            <label>Telefon *</label>
            <input type="tel" id="pg-bf-phone" placeholder="031 123 456" required>
          </div>
          <div class="pg-bf-field">
            <label>Email</label>
            <input type="email" id="pg-bf-email" placeholder="janez@email.com">
          </div>
        </div>

        <div id="pg-bf-dinner-wrap" class="pg-bf-field">
          <label>
            <input type="checkbox" id="pg-bf-dinner" style="margin-right:6px">
            Večerja — 30 €/odrasla oseba, 15 €/otrok do 12 let (pon/tor ni)
          </label>
        </div>

        <div class="pg-bf-field">
          <label>Posebnosti / opombe</label>
          <textarea id="pg-bf-note" placeholder="Alergije, posebne želje..."></textarea>
        </div>

        <div class="pg-bf-gdpr">
          <input type="checkbox" id="pg-bf-gdpr" required>
          <span>Strinjam se z obdelavo osebnih podatkov za namen rezervacije. Podatki se hranijo izključno za potrebe rezervacije pri Kmetiji Pod Goro.</span>
        </div>
      </div>
      <div id="pg-bf-footer">
        <button id="pg-bf-submit">Pošlji rezervacijo ✓</button>
      </div>
    `;
    panel.appendChild(bookingForm);

    container.appendChild(bubble);
    container.appendChild(panel);
    document.body.appendChild(container);

    // Event listeners
    document.getElementById('pg-widget-close').onclick = closePanel;
    document.getElementById('pg-widget-refresh').onclick = clearConversation;
    document.getElementById('pg-widget-send').onclick = sendMessage;
    document.getElementById('pg-widget-input').onkeypress = function(e) {
      if (e.key === 'Enter') sendMessage();
    };

    // Booking form state
    let bookingType = 'room';
    let stepValues = { nights: 2, adults: 2, children: 0 };
    const stepMin = { nights: 1, adults: 1, children: 0 };
    const stepMax = { nights: 14, adults: 10, children: 6 };

    var pricesRoom = '50 €/os/noč z zajtrkom (min. 2 osebi, 2 noči) &nbsp;·&nbsp; otroci do 3 let brezplačno &nbsp;·&nbsp; do 12 let 50% popust &nbsp;·&nbsp; večerja 30 €/odrasla, 15 €/otrok';
    var pricesTable = 'Vikend kosila (sob–ned): <a href="https://kmetijapodgoro.si/meni" target="_blank">kmetijapodgoro.si/meni</a> &nbsp;·&nbsp; Rezervacija za kosilo ob sobotah in nedeljah';

    function updatePrices() {
      document.getElementById('pg-bf-prices').innerHTML = bookingType === 'room' ? pricesRoom : pricesTable;
    }
    updatePrices();

    // Tabs
    document.querySelectorAll('.pg-bf-tab').forEach(function(tab) {
      tab.onclick = function() {
        document.querySelectorAll('.pg-bf-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        bookingType = tab.dataset.type;
        document.getElementById('pg-bf-nights-wrap').style.display = bookingType === 'room' ? '' : 'none';
        document.getElementById('pg-bf-time-wrap').style.display = bookingType === 'table' ? '' : 'none';
        document.getElementById('pg-bf-dinner-wrap').style.display = bookingType === 'room' ? '' : 'none';
        updatePrices();
      };
    });

    // Steppers
    document.querySelectorAll('[data-step]').forEach(function(btn) {
      btn.onclick = function() {
        var key = btn.dataset.step;
        var dir = parseInt(btn.dataset.dir);
        stepValues[key] = Math.min(stepMax[key], Math.max(stepMin[key], stepValues[key] + dir));
        document.getElementById('pg-bf-' + key + '-val').textContent = stepValues[key];
        if (key === 'children') {
          document.getElementById('pg-bf-children-ages-wrap').style.display = stepValues.children > 0 ? '' : 'none';
        }
      };
    });

    // Min date = today
    document.getElementById('pg-bf-date').min = new Date().toISOString().split('T')[0];

    // Open form button
    document.getElementById('pg-bf-open-btn').onmousedown = function(e) { e.preventDefault(); };
    document.getElementById('pg-bf-open-btn').onclick = function(e) {
      e.preventDefault();
      document.getElementById('pg-booking-form').classList.add('pg-open');
    };

    // Back button
    document.getElementById('pg-bf-back').onclick = function() {
      document.getElementById('pg-booking-form').classList.remove('pg-open');
    };

    // Submit
    async function submitBookingForm() {
      var date = document.getElementById('pg-bf-date').value;
      var name = document.getElementById('pg-bf-name').value.trim();
      var phone = document.getElementById('pg-bf-phone').value.trim();
      var gdpr = document.getElementById('pg-bf-gdpr').checked;

      if (!date) { alert('Izberite datum prihoda.'); return; }
      if (!name) { alert('Vnesite ime in priimek.'); return; }
      if (!phone) { alert('Vnesite telefonsko številko.'); return; }
      if (!gdpr) { alert('Potrdite soglasje za obdelavo osebnih podatkov.'); return; }

      var submitBtn = document.getElementById('pg-bf-submit');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Pošiljam...';

      var childrenAgesRaw = document.getElementById('pg-bf-children-ages').value;
      var childrenAges = [];
      if (childrenAgesRaw.trim()) {
        childrenAges = childrenAgesRaw.split(/[,\s]+/).map(function(x) {
          return parseInt(x);
        }).filter(function(x) { return !isNaN(x); });
      }

      var payload = {
        session_id: sessionId,
        booking_type: bookingType,
        date: date,
        nights: bookingType === 'room' ? stepValues.nights : null,
        time: bookingType === 'table' ? document.getElementById('pg-bf-time').value : null,
        adults: stepValues.adults,
        children: stepValues.children,
        children_ages: childrenAges,
        name: name,
        phone: phone,
        email: document.getElementById('pg-bf-email').value.trim(),
        dinner: bookingType === 'room' ? document.getElementById('pg-bf-dinner').checked : false,
        note: document.getElementById('pg-bf-note').value.trim(),
        gdpr: gdpr
      };

      try {
        var response = await fetch(CONFIG.apiUrl + '/quick-booking', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        var data = await response.json();
        document.getElementById('pg-booking-form').classList.remove('pg-open');
        if (data.ok) {
          addMessage('✅ Rezervacija sprejeta! (ID: #' + data.reservation_id + ')\n\nKmalu boste prejeli potrditev. Se vidimo na Kmetiji Pod Goro! 🏡', 'bot');
        } else {
          addMessage('⚠️ ' + (data.error || 'Napaka pri pošiljanju. Pokličite nas na 02 601 54 00.'), 'bot');
        }
      } catch (err) {
        document.getElementById('pg-booking-form').classList.remove('pg-open');
        addMessage('⚠️ Napaka pri pošiljanju. Pokličite nas na 02 601 54 00.', 'bot');
        console.error('[PG Widget] Booking error:', err);
      }

      submitBtn.disabled = false;
      submitBtn.textContent = 'Pošlji rezervacijo ✓';
    }

    document.getElementById('pg-bf-submit').onclick = submitBookingForm;

    // Load messages
    if (storedMessages.length > 0) {
      storedMessages.forEach(function(msg) { addMessageToUI(msg.text, msg.sender, false); });
    } else {
      addMessageToUI(CONFIG.welcomeMessage, 'bot', false);
    }

    // Auto-open on desktop
    if (CONFIG.autoOpenDesktop && window.innerWidth > CONFIG.mobileBreakpoint) {
      setTimeout(function() {
        if (!document.getElementById('pg-widget-panel').classList.contains('pg-open')) {
          openPanel();
        }
      }, CONFIG.autoOpenDelay);
    }
  }

  function togglePanel() {
    const panel = document.getElementById('pg-widget-panel');
    if (panel.classList.contains('pg-open')) closePanel(); else openPanel();
  }

  function openPanel() {
    document.getElementById('pg-widget-panel').classList.add('pg-open');
    if (window.innerWidth <= CONFIG.mobileBreakpoint) {
      document.getElementById('pg-widget-bubble').style.display = 'none';
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.width = '100%';
    }
    document.getElementById('pg-widget-input').focus();
  }

  function closePanel() {
    document.getElementById('pg-widget-panel').classList.remove('pg-open');
    document.getElementById('pg-widget-bubble').style.display = 'flex';
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.width = '';
  }

  function addMessageToUI(text, sender, autoScroll) {
    if (autoScroll === undefined) autoScroll = true;
    const messages = document.getElementById('pg-widget-messages');
    const msg = document.createElement('div');
    msg.className = 'pg-message pg-' + sender;
    msg.innerHTML = '<div class="pg-message-bubble">' + escapeHtml(text) + '</div>';
    messages.appendChild(msg);
    if (autoScroll) messages.scrollTop = messages.scrollHeight;
  }

  function addMessage(text, sender, save) {
    if (save === undefined) save = true;
    addMessageToUI(text, sender);
    if (save) {
      storedMessages.push({ text: text, sender: sender, time: Date.now() });
      saveMessages();
    }
  }

  function showTyping() {
    const messages = document.getElementById('pg-widget-messages');
    const typing = document.createElement('div');
    typing.id = 'pg-typing-indicator';
    typing.className = 'pg-message pg-bot';
    typing.innerHTML = '<div class="pg-message-bubble pg-typing"><span></span><span></span><span></span></div>';
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping() {
    const t = document.getElementById('pg-typing-indicator');
    if (t) t.remove();
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  async function sendMessage() {
    const input = document.getElementById('pg-widget-input');
    const sendBtn = document.getElementById('pg-widget-send');
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    input.value = '';
    sendBtn.disabled = true;
    showTyping();

    try {
      const response = await fetch(CONFIG.apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });
      hideTyping();
      if (!response.ok) throw new Error('API error');
      const data = await response.json();
      const reply = data.reply || data.response || data.message || 'Oprostite, prišlo je do napake.';
      addMessage(reply, 'bot');

      // Auto-odpri formo ob booking intentu
      if (data.action === 'open_booking_form') {
        var hint = data.booking_type_hint || 'room';
        document.querySelectorAll('.pg-bf-tab').forEach(function(t) { t.classList.remove('active'); });
        var activeTab = document.querySelector('.pg-bf-tab[data-type="' + hint + '"]');
        if (activeTab) { activeTab.classList.add('active'); activeTab.onclick && activeTab.onclick(); }
        setTimeout(function() {
          document.getElementById('pg-booking-form').classList.add('pg-open');
        }, 400);
      }
    } catch (err) {
      hideTyping();
      addMessage('Oprostite, trenutno ni mogoče vzpostaviti povezave. Poskusite ponovno.', 'bot');
      console.error('[PG Widget] Error:', err);
    }

    sendBtn.disabled = false;
    input.focus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidget);
  } else {
    createWidget();
  }
})();
