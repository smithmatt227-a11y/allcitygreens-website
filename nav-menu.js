/* All City Greens: phone menu for the site header (added 2026-11-07).
   On screens 768px and narrower, style.css hides the header links and shows
   the "Menu" button instead. This script opens and closes that menu.
   Every page loads it right after </header>; dispensary_pages.py writes the
   same tag for the store pages, so the 6 AM rebuild keeps it. */
(function () {
  var header = document.getElementById('nav');
  if (!header) return;
  var btn = header.querySelector('.nav-menu-toggle');
  var links = header.querySelector('.nav-links');
  if (!btn || !links) return;

  function isOpen() { return btn.getAttribute('aria-expanded') === 'true'; }
  function setOpen(open, returnFocus) {
    header.classList.toggle('menu-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (!open && returnFocus) btn.focus();
  }

  btn.addEventListener('click', function () { setOpen(!isOpen()); });

  // Tapping any link in the menu closes it (also covers same-page #anchors).
  links.addEventListener('click', function (e) {
    var t = e.target;
    while (t && t !== links) {
      if (t.tagName === 'A') { setOpen(false); return; }
      t = t.parentNode;
    }
  });

  // Escape closes and puts focus back on the button.
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Escape' || e.key === 'Esc') && isOpen()) setOpen(false, true);
  });

  // A tap anywhere outside the header closes it.
  document.addEventListener('click', function (e) {
    if (isOpen() && !header.contains(e.target)) setOpen(false);
  });

  // Rotating to a wide screen resets it, so desktop never inherits an open state.
  if (window.matchMedia) {
    var mq = window.matchMedia('(max-width: 768px)');
    var onChange = function (e) { if (!e.matches) setOpen(false); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }
})();
