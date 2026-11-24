/* Small page behaviours: list filters and the upload drop zone. Progressive enhancement only. */
(function () {
  "use strict";
  document.querySelectorAll("[data-filter]").forEach(function (bar) {
    var list = document.querySelector('[data-filter-list="' + bar.getAttribute("data-filter") + '"]');
    if (!list) return;
    var search = bar.querySelector("[data-filter-search]"), status = "all";
    var empty = list.querySelector("[data-filter-empty]");
    function apply() {
      var term = (search ? search.value : "").trim().toLowerCase(), shown = 0;
      list.querySelectorAll("[data-search]").forEach(function (n) {
        var ok = (!term || n.getAttribute("data-search").indexOf(term) >= 0) && (status === "all" || n.getAttribute("data-status") === status);
        n.hidden = !ok; if (ok) shown++;
      });
      if (empty) empty.hidden = shown > 0;
    }
    if (search) search.addEventListener("input", apply);
    bar.querySelectorAll("[data-filter-status]").forEach(function (b) {
      b.addEventListener("click", function () {
        status = b.getAttribute("data-filter-status");
        bar.querySelectorAll("[data-filter-status]").forEach(function (x) { x.classList.toggle("is-on", x === b); });
        apply();
      });
    });
  });

  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    var input = zone.querySelector("input[type=file]"), out = zone.parentNode.querySelector("[data-filelist]");
    function show() {
      if (!out) return;
      out.textContent = ""; out.hidden = !input.files.length;
      Array.prototype.forEach.call(input.files, function (f) {
        var li = document.createElement("li"), name = document.createElement("span"), size = document.createElement("span");
        name.textContent = f.name; size.className = "size";
        size.textContent = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(f.size / 1024)) + " KB";
        li.appendChild(name); li.appendChild(size); out.appendChild(li);
      });
    }
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach(function (e) { zone.addEventListener(e, function (ev) { ev.preventDefault(); zone.classList.add("is-over"); }); });
    ["dragleave", "drop"].forEach(function (e) { zone.addEventListener(e, function (ev) { ev.preventDefault(); zone.classList.remove("is-over"); }); });
    zone.addEventListener("drop", function (ev) { if (ev.dataTransfer && ev.dataTransfer.files.length) { input.files = ev.dataTransfer.files; show(); } });
  });
})();
