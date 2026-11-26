// Wolf site behaviour: nav, video player (tabs + minimal controls), scroll reveals, the typing subject line.
// Everything here is an enhancement. With JavaScript off, the pages read the same and the videos keep native controls.
(function () {
  var d = document, w = window;
  var reduce = w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var noop = function () {};

  // nav: mobile menu, and a hairline + shadow once the page has scrolled
  var nav = d.querySelector(".nav"), btn = d.querySelector(".menu-btn");
  if (btn) {
    btn.addEventListener("click", function () { var o = nav.classList.toggle("open"); btn.setAttribute("aria-expanded", String(o)); });
    d.addEventListener("keydown", function (e) { if (e.key === "Escape" && nav.classList.contains("open")) { nav.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
  }
  if (nav) {
    var onScroll = function () { nav.classList.toggle("scrolled", nav.getBoundingClientRect().top <= 0 && w.scrollY > 4); };
    w.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  }

  // video frames: swap native controls for a quiet play button, progress bar and full-screen button
  var ICON = {
    pause: '<svg class="ic-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h4v16H7zM13 4h4v16h-4z"/></svg>',
    play: '<svg class="ic-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4l13 8-13 8z"/></svg>',
    full: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>'
  };
  d.querySelectorAll(".frame").forEach(function (f) {
    var v = f.querySelector("video"); if (!v) return;
    v.removeAttribute("controls");
    var c = d.createElement("div"); c.className = "vc";
    c.innerHTML = '<button type="button" class="vc-play">' + ICON.pause + ICON.play + '</button><div class="vc-bar"><span><i></i></span></div><button type="button" class="vc-full" aria-label="Full screen">' + ICON.full + "</button>";
    f.appendChild(c);
    var play = c.querySelector(".vc-play"), bar = c.querySelector(".vc-bar"), fill = bar.querySelector("i"), raf = 0;
    var sync = function () { f.classList.toggle("paused", v.paused); play.setAttribute("aria-label", v.paused ? "Play video" : "Pause video"); };
    var tick = function () { if (v.duration) fill.style.transform = "scaleX(" + (v.currentTime / v.duration) + ")"; raf = v.paused ? 0 : w.requestAnimationFrame(tick); };
    var toggle = function () { if (v.paused) { v.dataset.held = ""; v.play().catch(noop); } else { v.dataset.held = "1"; v.pause(); } };
    play.addEventListener("click", toggle); v.addEventListener("click", toggle);
    v.addEventListener("play", function () { sync(); if (!raf) tick(); });
    v.addEventListener("pause", sync); v.addEventListener("seeked", tick); v.addEventListener("loadedmetadata", tick);
    bar.addEventListener("click", function (e) { var r = bar.getBoundingClientRect(); if (v.duration) v.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * v.duration; });
    c.querySelector(".vc-full").addEventListener("click", function () { var fn = v.requestFullscreen || v.webkitRequestFullscreen || v.webkitEnterFullscreen; if (fn) fn.call(v); });
    sync();
  });

  // hero player: segmented tabs with a sliding indicator
  var seg = d.querySelector(".seg"), video = d.querySelector("[data-player]"), tabs = d.querySelectorAll("[data-video]");
  var caption = d.querySelector("[data-caption]"), more = d.querySelector("[data-more]"), moreText = d.querySelector("[data-more-text]");
  var place = function () {
    if (!seg) return; var on = seg.querySelector('[aria-selected="true"]'); if (!on) return;
    seg.style.setProperty("--sx", on.offsetLeft + "px"); seg.style.setProperty("--sw", on.offsetWidth + "px"); seg.classList.add("ready");
  };
  tabs.forEach(function (t) {
    t.addEventListener("click", function () {
      if (t.getAttribute("aria-selected") === "true") return;
      tabs.forEach(function (x) { x.setAttribute("aria-selected", String(x === t)); x.tabIndex = x === t ? 0 : -1; });
      place();
      var frame = video.closest(".frame"), swap = function () {
        video.poster = t.getAttribute("data-poster"); video.src = t.getAttribute("data-video"); video.dataset.held = "";
        if (caption) caption.textContent = t.getAttribute("data-text");
        if (more) more.href = t.getAttribute("data-href");
        if (moreText) moreText.textContent = t.getAttribute("data-link");
        video.play().catch(noop); frame.classList.remove("swap");
      };
      if (reduce) swap(); else { frame.classList.add("swap"); w.setTimeout(swap, 200); }
    });
    t.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      var list = Array.prototype.slice.call(tabs), n = list[(list.indexOf(t) + (e.key === "ArrowRight" ? 1 : list.length - 1)) % list.length];
      n.focus(); n.click();
    });
  });
  place(); w.addEventListener("resize", place); if (d.fonts && d.fonts.ready) d.fonts.ready.then(place);

  // play a video only while it is on screen, and never restart one the visitor paused
  if (!reduce && "IntersectionObserver" in w) {
    d.querySelectorAll("video[data-auto]").forEach(function (v) {
      new IntersectionObserver(function (es) { es.forEach(function (e) {
        if (e.isIntersecting) { if (v.dataset.held !== "1") v.play().catch(noop); } else v.pause();
      }); }, { threshold: 0.4 }).observe(v);
    });
  }

  // scroll reveals. Only elements below the fold at load are hidden, so nothing visible ever flashes.
  if (!reduce && "IntersectionObserver" in w) {
    var sel = "main .kicker, main h2, main .sub, main .card, main .addr, main .one, main .step, main .flow-link, main .trust, main .frame-wrap, main .stage-foot, main .faq-group, main .cta, main .terms, main .wrap > .fine";
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) {
      if (!e.isIntersecting) return; var el = e.target; io.unobserve(el); el.classList.add("in");
      w.setTimeout(function () { el.classList.remove("rv", "in"); el.style.removeProperty("--d"); }, 1400);
    }); }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    var vh = w.innerHeight;
    d.querySelectorAll(sel).forEach(function (el) {
      var cta = el.closest(".cta");
      if (el.closest(".hero") || (cta && cta !== el) || el.getBoundingClientRect().top < vh * 0.92) return;
      var p = el.parentElement, i = Array.prototype.indexOf.call(p.children, el);
      if (p.matches(".grid-2, .grid-3, .ones, .steps, .flow, .faq")) el.style.setProperty("--d", Math.min(i, 4) * 90 + "ms");
      el.classList.add("rv"); io.observe(el);
    });
  }

  // long chip lists fold away on phones, behind a "Show all" button
  if (w.matchMedia && w.matchMedia("(max-width: 860px)").matches) {
    d.querySelectorAll(".names").forEach(function (n) {
      if (n.children.length < 12) return;
      var b = d.createElement("button"); b.type = "button"; b.className = "more-btn"; b.textContent = "Show all " + n.children.length;
      b.addEventListener("click", function () { n.classList.remove("clamp"); b.remove(); });
      n.classList.add("clamp"); n.after(b);
    });
  }

  // the subject line in the mail composer types through a few real examples
  d.querySelectorAll("[data-type]").forEach(function (el) {
    var list; try { list = JSON.parse(el.getAttribute("data-type")); } catch (e) { return; }
    if (reduce || !list || list.length < 2 || !("IntersectionObserver" in w)) return;
    var i = 0, n = list[0].length, phase = "hold", on = false, timer = 0;
    var step = function () {
      timer = 0; if (!on) return;
      var s = list[i];
      if (phase === "hold") { phase = "del"; timer = w.setTimeout(step, 2200); return; }
      if (phase === "del") {
        if (n > 0) { n--; el.textContent = s.slice(0, n); timer = w.setTimeout(step, 18); }
        else { i = (i + 1) % list.length; phase = "type"; timer = w.setTimeout(step, 350); }
        return;
      }
      if (n < s.length) { n++; el.textContent = s.slice(0, n); timer = w.setTimeout(step, 42); }
      else { phase = "hold"; timer = w.setTimeout(step, 30); }
    };
    new IntersectionObserver(function (es) { on = es[0].isIntersecting; if (on && !timer) timer = w.setTimeout(step, 400); }, { threshold: 0.5 }).observe(el);
  });
})();
