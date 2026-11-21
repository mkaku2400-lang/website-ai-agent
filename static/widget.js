/*
 * Website AI agent - chat widget.
 *
 * Add to any page, just before </body>:
 *   <script src="https://YOUR-SERVER/widget.js" data-title="Northgate Family Dental"
 *           data-color="#0f766e" defer></script>
 *
 * Optional attributes: data-subtitle, data-greeting, data-placeholder, data-position ("left" or "right").
 * The widget talks to the server it was loaded from, so no other setup is needed.
 */
(function () {
  "use strict";
  if (window.__websiteAgentLoaded) return;
  window.__websiteAgentLoaded = true;

  var script = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var cfg = {
    api: new URL(script.src, location.href).origin + "/api/chat",
    title: script.dataset.title || "Questions? Ask us",
    subtitle: script.dataset.subtitle || "Answers from our team's own information",
    greeting: script.dataset.greeting || "Hi, I can answer questions about prices, opening hours and treatments, or pass a request to our front desk.",
    placeholder: script.dataset.placeholder || "Type your question",
    color: script.dataset.color || "#0f766e",
    position: script.dataset.position === "left" ? "left" : "right",
  };
  var STORE_KEY = "website-agent:" + cfg.api;

  var css = [
    ":host{all:initial}",
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}",
    ".launcher{position:fixed;bottom:20px;" + cfg.position + ":20px;z-index:2147483000;display:flex;align-items:center;gap:8px;",
    " padding:12px 18px 12px 14px;border:0;border-radius:999px;background:var(--c);color:#fff;font-size:15px;font-weight:600;",
    " cursor:pointer;box-shadow:0 6px 20px rgba(15,23,42,.22)}",
    ".launcher:focus-visible,.send:focus-visible,.close:focus-visible{outline:3px solid #fbbf24;outline-offset:2px}",
    ".launcher svg{width:20px;height:20px}",
    ".panel{position:fixed;bottom:84px;" + cfg.position + ":20px;z-index:2147483000;width:370px;max-width:calc(100vw - 24px);",
    " height:540px;max-height:calc(100vh - 110px);display:none;flex-direction:column;background:#fff;border-radius:14px;",
    " overflow:hidden;box-shadow:0 18px 50px rgba(15,23,42,.28);border:1px solid #e2e8f0}",
    ".panel.open{display:flex}",
    ".head{background:var(--c);color:#fff;padding:14px 16px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}",
    ".head h2{margin:0;font-size:16px;font-weight:650;line-height:1.3}",
    ".head p{margin:2px 0 0;font-size:12.5px;opacity:.85}",
    ".close{background:transparent;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:0 2px}",
    ".log{flex:1;overflow-y:auto;padding:14px;background:#f8fafc;display:flex;flex-direction:column;gap:8px}",
    ".msg{max-width:85%;padding:9px 12px;border-radius:12px;font-size:14.5px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}",
    ".bot{align-self:flex-start;background:#fff;color:#0f172a;border:1px solid #e2e8f0;border-bottom-left-radius:4px}",
    ".me{align-self:flex-end;background:var(--c);color:#fff;border-bottom-right-radius:4px}",
    ".note{align-self:center;font-size:12px;color:#0f5132;background:#d1fae5;border-radius:999px;padding:4px 10px}",
    ".typing{align-self:flex-start;color:#64748b;font-size:13px;padding:4px 2px}",
    ".form{display:flex;gap:8px;padding:10px;border-top:1px solid #e2e8f0;background:#fff}",
    ".form label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}",
    ".input{flex:1;border:1px solid #cbd5e1;border-radius:10px;padding:10px 12px;font-size:14.5px;color:#0f172a}",
    ".input:focus{outline:2px solid var(--c);outline-offset:-1px;border-color:transparent}",
    ".send{border:0;border-radius:10px;background:var(--c);color:#fff;font-weight:600;font-size:14px;padding:0 14px;cursor:pointer}",
    ".send:disabled{opacity:.5;cursor:default}",
    ".foot{font-size:11px;color:#94a3b8;text-align:center;padding:0 10px 8px;background:#fff}",
    "@media (max-width:480px){.panel{bottom:0;" + cfg.position + ":0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}}",
  ].join("");

  var host = document.createElement("div");
  host.id = "website-agent";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    "<style>" + css + "</style>" +
    '<button class="launcher" type="button" aria-expanded="false" aria-controls="wa-panel">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z"/></svg>' +
    "<span>Ask a question</span></button>" +
    '<section class="panel" id="wa-panel" role="dialog" aria-label="Chat">' +
    '<div class="head"><div><h2></h2><p></p></div><button class="close" type="button" aria-label="Close chat">&times;</button></div>' +
    '<div class="log" aria-live="polite"></div>' +
    '<form class="form"><label for="wa-input">Your message</label>' +
    '<input class="input" id="wa-input" autocomplete="off" maxlength="1000">' +
    '<button class="send" type="submit">Send</button></form>' +
    '<div class="foot">AI assistant. A person from our team handles bookings.</div></section>';
  host.style.setProperty("--c", cfg.color);

  var launcher = root.querySelector(".launcher");
  var panel = root.querySelector(".panel");
  var log = root.querySelector(".log");
  var form = root.querySelector(".form");
  var input = root.querySelector(".input");
  var send = root.querySelector(".send");
  root.querySelector(".head h2").textContent = cfg.title;
  root.querySelector(".head p").textContent = cfg.subtitle;
  input.placeholder = cfg.placeholder;

  var state = load();
  var busy = false;

  function load() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(STORE_KEY));
      if (saved && Array.isArray(saved.messages)) return saved;
    } catch (e) { /* ignore broken storage */ }
    return { sessionId: null, leadSent: false, messages: [{ who: "bot", text: cfg.greeting }] };
  }
  function save() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* private mode */ }
  }
  function bubble(who, text) {
    var el = document.createElement("div");
    el.className = who === "me" ? "msg me" : who === "note" ? "note" : "msg bot";
    el.textContent = text;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }
  function render() {
    log.textContent = "";
    state.messages.forEach(function (m) { bubble(m.who, m.text); });
  }
  function add(who, text) {
    state.messages.push({ who: who, text: text });
    save();
    bubble(who, text);
  }
  function toggle(open) {
    panel.classList.toggle("open", open);
    launcher.setAttribute("aria-expanded", String(open));
    if (open) { render(); input.focus(); }
  }

  launcher.addEventListener("click", function () { toggle(!panel.classList.contains("open")); });
  root.querySelector(".close").addEventListener("click", function () { toggle(false); launcher.focus(); });
  root.addEventListener("keydown", function (e) { if (e.key === "Escape") { toggle(false); launcher.focus(); } });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    add("me", text);
    busy = true;
    send.disabled = true;
    var typing = document.createElement("div");
    typing.className = "typing";
    typing.textContent = "Typing...";
    log.appendChild(typing);
    log.scrollTop = log.scrollHeight;

    fetch(cfg.api, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, message: text }),
    })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (data) {
        typing.remove();
        state.sessionId = data.session_id;
        add("bot", data.reply);
        if (data.lead_sent && !state.leadSent) {
          state.leadSent = true;
          add("note", "Your details were sent to the front desk");
        }
      })
      .catch(function () {
        typing.remove();
        add("bot", "Sorry, the connection failed. Please try again in a moment.");
      })
      .then(function () { busy = false; send.disabled = false; input.focus(); });
  });
})();
