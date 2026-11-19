/*
 * Real-time filtrlar.
 *
 * <form method="get" data-live-filter> ichidagi har qanday maydon o'zgarishi bilan
 * sahifa qayta yuklanmasdan natijalar (#live-results) yangilanadi.
 *  - matn/son/sana maydonlari: yozish tugagach (debounce, 300ms)
 *  - select/checkbox/radio: darhol
 *  - paginatsiya havolalari (#live-results ichida) filtrlarni saqlagan holda ishlaydi
 *  - URL history.replaceState orqali yangilanadi (sahifani yangilash/ulashish ishlaydi)
 * JS o'chirilgan bo'lsa forma oddiy GET sifatida ishlayveradi.
 */
(function () {
  'use strict';

  var DEBOUNCE_MS = 300;

  function buildQuery(form, extra) {
    var params = new URLSearchParams();
    new FormData(form).forEach(function (value, key) {
      if (typeof value === 'string' && value.trim() !== '') params.append(key, value.trim());
    });
    if (extra) Object.keys(extra).forEach(function (k) { params.set(k, extra[k]); });
    return params;
  }

  function init(form) {
    if (form.getAttribute('data-live-ready')) return; // ikki marta ulanmasin
    form.setAttribute('data-live-ready', '1');
    var targetId = form.getAttribute('data-live-target') || 'live-results';
    var timer = null;
    var controller = null;
    var seq = 0;

    form.classList.add('live-ready');

    function container() { return document.getElementById(targetId); }

    function load(params) {
      var el = container();
      if (!el) { form.submit(); return; }
      var qs = params.toString();
      var url = window.location.pathname + (qs ? '?' + qs : '');
      if (controller) controller.abort();
      controller = new AbortController();
      var mySeq = ++seq;
      el.classList.add('live-loading');
      fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-Live-Filter': '1' },
        credentials: 'same-origin',
        signal: controller.signal,
      }).then(function (resp) {
        if (resp.redirected && resp.url.indexOf(window.location.pathname) === -1) {
          window.location.href = resp.url; // sessiya tugagan (login'ga yo'naltirildi)
          return null;
        }
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.text();
      }).then(function (html) {
        if (html === null || mySeq !== seq) return;
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var fresh = doc.getElementById(targetId);
        if (!fresh) throw new Error('target not found');
        el.innerHTML = fresh.innerHTML;
        el.classList.remove('live-loading');
        history.replaceState(null, '', url);
        el.dispatchEvent(new CustomEvent('live:updated', { bubbles: true }));
      }).catch(function (err) {
        if (err && err.name === 'AbortError') return;
        el.classList.remove('live-loading');
        form.submit(); // xato bo'lsa oddiy yuklashga qaytamiz
      });
    }

    function schedule(delay) {
      clearTimeout(timer);
      timer = setTimeout(function () { load(buildQuery(form)); }, delay);
    }

    form.addEventListener('input', function (e) {
      var t = e.target;
      if (!t.name) return;
      if (t.tagName === 'SELECT' || t.type === 'checkbox' || t.type === 'radio') return; // 'change' hal qiladi
      schedule(DEBOUNCE_MS);
    });
    form.addEventListener('change', function (e) {
      if (!e.target.name) return;
      schedule(0);
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      schedule(0);
    });
    form.addEventListener('reset', function () {
      setTimeout(function () { schedule(0); }, 0);
    });

    // "Tozalash" tugmasi
    form.addEventListener('click', function (e) {
      var clear = e.target.closest('[data-live-clear]');
      if (!clear) return;
      e.preventDefault();
      Array.prototype.forEach.call(form.elements, function (f) {
        if (!f.name) return;
        if (f._flatpickr) f._flatpickr.clear();
        else if (f.type === 'checkbox' || f.type === 'radio') f.checked = false;
        else if (f.tagName === 'SELECT') f.selectedIndex = 0;
        else f.value = '';
      });
      schedule(0);
    });

    // Paginatsiya: filtrlarni saqlab, faqat page ni almashtiramiz
    document.addEventListener('click', function (e) {
      var a = e.target.closest('a.page-link');
      var el = container();
      if (!a || !el || !el.contains(a)) return;
      var href = a.getAttribute('href') || '';
      var m = href.match(/[?&]page=(\d+)/);
      if (!m) return;
      e.preventDefault();
      load(buildQuery(form, { page: m[1] }));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-live-filter]').forEach(init);
  });
})();
