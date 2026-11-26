// Hero player tabs, mobile menu, and "play only while visible" for the videos.
(function () {
  var nav = document.querySelector(".nav"), btn = document.querySelector(".menu-btn");
  if (btn) btn.addEventListener("click", function () { var o = nav.classList.toggle("open"); btn.setAttribute("aria-expanded", String(o)); });
  var video = document.querySelector("[data-player]"), tabs = document.querySelectorAll("[data-video]");
  var caption = document.querySelector("[data-caption]"), more = document.querySelector("[data-more]");
  tabs.forEach(function (t) {
    t.addEventListener("click", function () {
      tabs.forEach(function (x) { x.setAttribute("aria-selected", String(x === t)); });
      video.poster = t.getAttribute("data-poster"); video.src = t.getAttribute("data-video");
      if (caption) caption.textContent = t.getAttribute("data-text");
      if (more) { more.href = t.getAttribute("data-href"); more.textContent = t.getAttribute("data-link") + " →"; }
      video.play().catch(function () {});
    });
  });
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("video[data-auto]").forEach(function (v) {
    if (reduce || !("IntersectionObserver" in window)) return;
    new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) v.play().catch(function () {}); else v.pause(); }); }, { threshold: 0.4 }).observe(v);
  });
})();
