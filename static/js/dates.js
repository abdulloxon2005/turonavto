/*
 * Sana maydonlari: brauzer/OS tiliga bog'liq bo'lmagan holda doim kun.oy.yil ko'rinadi.
 * <input type="date"> ning asl qiymati (serverga ketadigan) YYYY-MM-DD bo'lib qoladi,
 * foydalanuvchi esa kun.oy.yil ko'rinishidagi alohida maydonni ko'radi va unga qo'lda yozishi ham mumkin.
 */
(function () {
  'use strict';

  function initDates(root) {
    if (typeof flatpickr === 'undefined') return; // CDN yuklanmasa, oddiy sana maydoni ishlayveradi
    var locale = (flatpickr.l10ns && flatpickr.l10ns.uz_latn) || 'default';
    if (locale !== 'default') locale = Object.assign({}, locale, { firstDayOfWeek: 1 });
    (root || document).querySelectorAll('input[type="date"]').forEach(function (el) {
      if (el._flatpickr) return;
      flatpickr(el, {
        altInput: true,
        altFormat: 'd.m.Y',
        dateFormat: 'Y-m-d',
        allowInput: true,
        locale: locale,
        disableMobile: true, // telefonda ham native (brauzerga bog'liq) maydon chiqmasin
        altInputClass: el.className,
      });
      if (el.getAttribute('placeholder') === null && el._flatpickr.altInput) {
        el._flatpickr.altInput.setAttribute('placeholder', 'kun.oy.yil');
      }
    });
  }

  window.initDates = initDates;
  document.addEventListener('DOMContentLoaded', function () { initDates(document); });
})();
