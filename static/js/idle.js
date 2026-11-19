/*
 * Faolsizlik bo'yicha avtomatik chiqish.
 *  - Foydalanuvchi IDLE_TIMEOUT soniya hech narsa qilmasa (sichqoncha, klaviatura, skroll, teginish yo'q)
 *    tizimdan chiqariladi va login sahifasiga o'tkaziladi.
 *  - Faol foydalanuvchi uchun (masalan, uzoq forma to'ldirayotgan) har ~5 daqiqada serverga "keepalive"
 *    yuboriladi, shunda server sessiyasi foydalanuvchi ishlab turganda tugab qolmaydi.
 *  - Kompyuter uyquga ketib qaytsa yoki yorliq qayta ochilsa, vaqt darhol tekshiriladi.
 */
(function () {
  'use strict';
  var cfg = document.getElementById('idle-config');
  if (!cfg) return;
  var timeoutMs = parseInt(cfg.dataset.timeout, 10) * 1000;
  var loginUrl = cfg.dataset.loginUrl;
  var logoutUrl = cfg.dataset.logoutUrl;
  var pingUrl = cfg.dataset.pingUrl;
  if (!timeoutMs || timeoutMs <= 0) return;

  var PING_EVERY_MS = Math.min(5 * 60 * 1000, Math.floor(timeoutMs / 3));
  var lastActivity = Date.now();
  var lastPing = Date.now();
  var leaving = false;

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) return decodeURIComponent(m[1]);
    var el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function toLogin() {
    if (leaving) return;
    leaving = true;
    var go = function () { window.location.href = loginUrl + '?expired=1'; };
    try {
      fetch(logoutUrl, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, credentials: 'same-origin' })
        .then(go, go);
    } catch (e) { go(); }
  }

  function activity() { lastActivity = Date.now(); }
  ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel', 'click', 'input'].forEach(function (ev) {
    window.addEventListener(ev, activity, { passive: true, capture: true });
  });

  function ping() {
    lastPing = Date.now();
    fetch(pingUrl, { credentials: 'same-origin', cache: 'no-store' }).then(function (r) {
      if (r.status === 401 || r.status === 403) toLogin();
    }).catch(function () { /* tarmoq xatosi: keyingi urinishda */ });
  }

  function tick() {
    var now = Date.now();
    if (now - lastActivity >= timeoutMs) { toLogin(); return; }
    if (lastActivity > lastPing && now - lastPing >= PING_EVERY_MS) ping();
  }

  setInterval(tick, 15000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) tick(); });
  window.addEventListener('focus', tick);
  window.addEventListener('pageshow', tick);
})();
