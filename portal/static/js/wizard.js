/* Guided SWMS job assessment (client side). Data comes from #assess-data; logic from assessment-engine.js.
   The server re-evaluates everything on submit. */
(function () {
  "use strict";
  var dataEl = document.getElementById("assess-data");
  if (!dataEl) return;
  var boot = JSON.parse(dataEl.textContent);
  var spec = boot.spec, E = window.AssessmentEngine, req = boot.req;
  var STAGES = [
    { id: "type", label: "Job type" },
    { id: "site", label: "Site and timing" },
    { id: "risks", label: "Key risks" },
    { id: "quick", label: "Quick checks" },
    { id: "crew", label: "Crew and plant" },
    { id: "review", label: "Review and send" }
  ];
  var UNSURE = ["unsure", "unknown", "undecided"];
  var EXCLUSIVE = ["none", "unknown"];
  var STORE = "swms-assessment-" + boot.client_id;
  var main = document.getElementById("wz-main"), side = document.getElementById("wz-side"), steps = document.getElementById("wz-steps");
  var form = document.getElementById("wz-form");
  var state = initialState();
  var seen = {};

  function initialState() {
    var s = null;
    if (boot.prefill) {
      s = { stage: "review", job_type: boot.prefill.job_type, site: boot.prefill.site || {}, answers: boot.prefill.answers || {},
            crew: boot.prefill.crew || [], crew_later: !(boot.prefill.crew || []).length, plant_other: boot.prefill.plant_other || "",
            notes: boot.prefill.notes || "", confirm: false, editing: null, reached: STAGES.length - 1 };
    } else {
      try { s = JSON.parse(sessionStorage.getItem(STORE)); } catch (e) { s = null; }
    }
    if (!s || !s.site) {
      s = { stage: "type", job_type: null, site: { state: boot.states.length === 1 ? boot.states[0] : "" }, answers: {}, crew: [],
            crew_later: false, plant_other: "", notes: "", confirm: false, editing: null, reached: 0 };
    }
    return s;
  }
  function save() { try { sessionStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* storage unavailable */ } }

  // ---------- helpers
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, "");
      else n.setAttribute(k, v);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function icon(name, cls) {
    var ns = "http://www.w3.org/2000/svg", s = document.createElementNS(ns, "svg"), u = document.createElementNS(ns, "use");
    s.setAttribute("class", "icon" + (cls ? " " + cls : "")); s.setAttribute("aria-hidden", "true");
    u.setAttribute("href", "#i-" + name); s.appendChild(u); return s;
  }
  function allAnswers() {
    var a = { job_type: state.job_type, state: state.site.state, building_age: state.site.building_age };
    Object.keys(state.answers).forEach(function (k) { a[k] = state.answers[k]; });
    return a;
  }
  function result() { return E.evaluate(allAnswers(), spec); }
  function q(id) { return spec.questions.filter(function (x) { return x.id === id; })[0]; }
  function jobType() { return spec.job_types.filter(function (j) { return j.id === state.job_type; })[0]; }
  function prune(r) { Object.keys(state.answers).forEach(function (k) { if (r.visible.indexOf(k) < 0) delete state.answers[k]; }); }
  function stageIndex(id) { return STAGES.map(function (s) { return s.id; }).indexOf(id); }
  function go(id) {
    state.stage = id; state.editing = null;
    state.reached = Math.max(state.reached || 0, stageIndex(id));
    save(); render();
    var top = document.getElementById("wz-top");
    if (top && top.scrollIntoView) top.scrollIntoView({ block: "start" });
    var h = main.querySelector("h2"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
  }
  function riskQuestions(r) { return r.visible.map(q).filter(function (x) { return x.priority !== "quick"; }); }
  function quickQuestions(r) { return r.visible.map(q).filter(function (x) { return x.priority === "quick"; }); }
  function answered(x) { var v = state.answers[x.id]; return Array.isArray(v) ? v.length > 0 : !!v; }
  function fmtDate(iso) { if (!iso) return ""; var p = iso.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }

  // ---------- stepper
  function renderSteps() {
    steps.textContent = "";
    var cur = stageIndex(state.stage);
    STAGES.forEach(function (s, i) {
      var reachable = i <= (state.reached || 0) && state.job_type;
      var cls = "wz-step" + (i === cur ? " is-current" : i < cur || reachable ? " is-done" : "");
      var inner = [el("span", { class: "wz-step-dot" }, [i < cur ? icon("check") : document.createTextNode(String(i + 1))]),
                   el("span", { class: "wz-step-label", text: s.label })];
      steps.appendChild(reachable && i !== cur
        ? el("li", { class: cls }, [el("button", { type: "button", class: "wz-step-btn", onclick: function () { go(s.id); } }, inner)])
        : el("li", { class: cls, "aria-current": i === cur ? "step" : null }, [el("span", { class: "wz-step-btn" }, inner)]));
    });
  }

  // ---------- stage: job type
  function renderType() {
    main.appendChild(head("What kind of job is it?", "Pick the closest match. We'll only ask what matters for that kind of work."));
    var grid = el("div", { class: "wz-types" });
    spec.job_types.forEach(function (j) {
      grid.appendChild(el("button", { type: "button", class: "wz-type" + (state.job_type === j.id ? " is-selected" : ""), onclick: function () {
        if (state.job_type !== j.id) { state.job_type = j.id; state.answers = {}; state.confirm = false; state.reached = 0; }
        go("site");
      } }, [
        el("span", { class: "wz-type-icon" }, [icon(j.icon)]),
        el("span", { class: "wz-type-body" }, [el("strong", { text: j.title }), el("span", { text: j.blurb })]),
        el("span", { class: "wz-type-time", text: "About " + j.minutes + " min" })
      ]));
    });
    main.appendChild(grid);
  }

  // ---------- stage: site
  function renderSite() {
    main.appendChild(head("Where and when?", "The basics for the front page of the SWMS."));
    var s = state.site, errs = el("div", { class: "alert alert-danger", hidden: true, role: "alert" });
    function field(label, input, hint) { return el("label", { class: "field" }, [el("span", { class: "field-label", text: label }), input, hint ? el("span", { class: "field-hint", text: hint }) : null]); }
    function text(key, attrs) {
      var a = { class: "input", value: s[key] || "", oninput: function (e) { s[key] = e.target.value; save(); } };
      Object.keys(attrs || {}).forEach(function (k) { a[k] = attrs[k]; });
      return el("input", a);
    }
    function segmented(key, options, onpick) {
      var g = el("div", { class: "segmented", role: "radiogroup" });
      options.forEach(function (o) {
        g.appendChild(el("button", { type: "button", role: "radio", "aria-checked": String(s[key] === o.v), class: "segmented-item" + (s[key] === o.v ? " is-on" : ""),
          onclick: function () { s[key] = o.v; save(); if (onpick) onpick(); render(); } }, [o.label]));
      });
      return g;
    }
    var scope = el("textarea", { class: "input", rows: "2", placeholder: "For example: replace 40 m of sewer under the driveway and fit a new boundary trap",
      oninput: function (e) { s.scope = e.target.value; save(); } });
    scope.value = s.scope || "";
    main.appendChild(el("div", { class: "card card-pad stack" }, [
      errs,
      field("Site address", text("site_address", { autocomplete: "street-address", placeholder: "Street address and suburb" })),
      el("div", { class: "field-row" }, [
        el("div", { class: "field" }, [el("span", { class: "field-label", text: "State or territory" }), segmented("state", [{ v: "ACT", label: "ACT" }, { v: "NSW", label: "NSW" }])]),
        field("Start date", text("start_date", { type: "date", min: boot.today }))
      ]),
      field("The job in a sentence", scope),
      el("div", { class: "field" }, [
        el("span", { class: "field-label", text: "When was the building built?" }),
        segmented("building_age", spec.building_ages, function () { prune(result()); }),
        el("span", { class: "field-hint", text: "Buildings from before 2004 may contain asbestos, so we ask a few extra questions for those." })
      ]),
      el("div", { class: "field-row" }, [
        field("Builder or head contractor", text("head_contractor", { placeholder: "Optional" })),
        field("Your job reference", text("client_ref", { placeholder: "Optional" }))
      ])
    ]));
    main.appendChild(nav("type", function () {
      var missing = [];
      if (!(s.site_address || "").trim()) missing.push("site address");
      if (!s.state) missing.push("state or territory");
      if (!s.start_date) missing.push("start date");
      if (!(s.scope || "").trim()) missing.push("a short description of the job");
      if (!s.building_age) missing.push("when the building was built");
      if (missing.length) { errs.hidden = false; errs.textContent = "Still needed: " + missing.join(", ") + "."; errs.scrollIntoView({ block: "center" }); return; }
      go("risks");
    }));
  }

  // ---------- stage: risks (cascading)
  function renderRisks() {
    var r = result(), list = riskQuestions(r);
    var done = list.filter(answered).length;
    var active = state.editing ? q(state.editing) : list.filter(function (x) { return !answered(x); })[0];
    main.appendChild(head("Key risks for this job", "One question at a time. Each answer decides what we ask next, so you only see what applies."));
    main.appendChild(el("div", { class: "wz-progress" }, [
      el("progress", { max: String(Math.max(list.length, 1)), value: String(done) }),
      el("span", { text: done + " answered" + (list.length > done ? " · " + (list.length - done) + " to go, depending on your answers" : "") })
    ]));
    var wrap = el("div", { class: "wz-flow" }), lastSection = null;
    list.forEach(function (x) {
      var isActive = active && active.id === x.id;
      if (!answered(x) && !isActive) return;
      if (x.section !== lastSection) { wrap.appendChild(el("div", { class: "wz-section", text: spec.section_titles[x.section] })); lastSection = x.section; }
      wrap.appendChild(isActive ? questionCard(x) : answeredRow(x, "risks"));
    });
    main.appendChild(wrap);
    if (!active) {
      main.appendChild(el("div", { class: "wz-complete" }, [icon("check-circle"), el("div", {}, [
        el("strong", { text: "That's every risk question for this job." }),
        el("span", { text: " Next, a few quick box ticks." })])]));
    }
    main.appendChild(nav("site", active ? null : function () { go("quick"); }));
  }
  function answerLabel(x) {
    var v = state.answers[x.id]; v = Array.isArray(v) ? v : [v];
    return x.options.filter(function (o) { return v.indexOf(o.v) >= 0; }).map(function (o) { return o.label; }).join("; ");
  }
  function isUnsure(x) { var v = state.answers[x.id]; v = Array.isArray(v) ? v : [v]; return v.some(function (y) { return UNSURE.indexOf(y) >= 0; }); }
  function flagged(x) {
    var v = state.answers[x.id]; v = Array.isArray(v) ? v : [v];
    return (x.effects || []).some(function (e) {
      return (e.blocker || e.stop) && e["if"].some(function (y) { return v.indexOf(String(y)) >= 0; }) && E.cond(e.when, allAnswers());
    });
  }
  function answeredRow(x, stage) {
    var warn = isUnsure(x) || flagged(x);
    return el("div", { class: "wz-answered" + (x.priority === "key" ? " is-key" : "") + (warn ? " is-flagged" : "") }, [
      el("span", { class: "wz-answered-mark" }, [icon(warn ? "alert-triangle" : "check")]),
      el("span", { class: "wz-answered-q", text: x.short }),
      el("span", { class: "wz-answered-a", text: answerLabel(x) }),
      el("button", { type: "button", class: "btn btn-ghost btn-sm", "aria-label": "Change answer: " + x.short,
        onclick: function () { state.stage = stage; state.editing = x.id; save(); render(); } }, ["Change"])
    ]);
  }
  function setAnswer(x, v) {
    state.answers[x.id] = v; state.editing = null; state.confirm = false;
    prune(result()); save(); render();
    var next = main.querySelector(".wz-question"); if (next && next.scrollIntoView) next.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  function questionCard(x) {
    var key = x.priority === "key";
    var card = el("div", { class: "wz-question" + (key ? " is-key" : "") }, [
      el("div", { class: "wz-question-meta" }, [
        key ? el("span", { class: "pill pill-key" }, [icon("target"), "Key question · take a moment"]) : el("span", { class: "pill pill-neutral", text: "Standard question" })
      ]),
      el("h3", { class: "wz-question-text", text: x.ask }),
      x.why ? el("p", { class: "wz-why" }, [icon("info"), el("span", { text: x.why })]) : null
    ]);
    var cur = state.answers[x.id], opts = el("div", { class: "wz-options" + (x.options.length <= 3 ? " is-row" : "") });
    if (x.type === "multi") {
      var sel = Array.isArray(cur) ? cur.slice() : [];
      var cont = el("button", { type: "button", class: "btn btn-primary", disabled: !sel.length, onclick: function () { setAnswer(x, sel); } }, ["Continue"]);
      x.options.forEach(function (o) {
        var b = el("button", { type: "button", role: "checkbox", "aria-checked": String(sel.indexOf(o.v) >= 0), class: "wz-option is-multi" + (sel.indexOf(o.v) >= 0 ? " is-on" : ""),
          onclick: function () {
            var i = sel.indexOf(o.v);
            if (i >= 0) sel.splice(i, 1);
            else if (EXCLUSIVE.indexOf(o.v) >= 0) sel = [o.v];
            else { sel = sel.filter(function (y) { return EXCLUSIVE.indexOf(y) < 0; }); sel.push(o.v); }
            Array.prototype.forEach.call(opts.children, function (c) {
              var on = sel.indexOf(c.getAttribute("data-v")) >= 0; c.classList.toggle("is-on", on); c.setAttribute("aria-checked", String(on));
            });
            cont.disabled = !sel.length;
          } }, [el("span", { class: "wz-option-box" }, [icon("check")]), el("span", { class: "wz-option-label", text: o.label })]);
        b.setAttribute("data-v", o.v); opts.appendChild(b);
      });
      card.appendChild(el("p", { class: "field-hint", text: "Choose all that apply." }));
      card.appendChild(opts); card.appendChild(el("div", { class: "wz-question-actions" }, [cont]));
    } else {
      x.options.forEach(function (o) {
        opts.appendChild(el("button", { type: "button", class: "wz-option" + (cur === o.v ? " is-on" : "") + (UNSURE.indexOf(o.v) >= 0 ? " is-unsure" : ""),
          onclick: function () { setAnswer(x, o.v); } }, [
          el("span", { class: "wz-option-label" }, [el("span", { text: o.label }), o.hint ? el("small", { text: o.hint }) : null]),
          o.tag ? el("span", { class: "pill pill-warn", text: o.tag }) : null
        ]));
      });
      card.appendChild(opts);
      if (key && x.options.some(function (o) { return UNSURE.indexOf(o.v) >= 0; })) {
        card.appendChild(el("p", { class: "field-hint", text: "Not sure is a fine answer. We'll plan for the higher risk and call you to confirm." }));
      }
    }
    return card;
  }

  // ---------- stage: quick checks
  function renderQuick() {
    var r = result(), list = quickQuestions(r);
    main.appendChild(head("Quick checks", "Standard items for any job. Tick through them; say no if something isn't in place and we'll note it."));
    var allBtn = el("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: function () {
      list.forEach(function (x) { if (!answered(x)) state.answers[x.id] = "yes"; }); save(); render();
    } }, [icon("check"), "Yes to all remaining"]);
    var card = el("div", { class: "card" }, [el("div", { class: "card-head" }, [el("span", { class: "muted", text: list.filter(answered).length + " of " + list.length + " answered" }), allBtn])]);
    list.forEach(function (x) {
      var seg = el("div", { class: "segmented segmented-sm", role: "radiogroup", "aria-label": x.short });
      x.options.forEach(function (o) {
        seg.appendChild(el("button", { type: "button", role: "radio", "aria-checked": String(state.answers[x.id] === o.v),
          class: "segmented-item" + (state.answers[x.id] === o.v ? " is-on is-" + o.v : ""), onclick: function () { state.answers[x.id] = o.v; save(); render(); } }, [o.label]));
      });
      card.appendChild(el("div", { class: "wz-quick" }, [el("span", { text: x.ask }), seg]));
    });
    main.appendChild(card);
    var errs = el("div", { class: "alert alert-danger", hidden: true, role: "alert", text: "Answer each item to continue." });
    main.appendChild(errs);
    main.appendChild(nav("risks", function () { if (list.some(function (x) { return !answered(x); })) { errs.hidden = false; return; } go("crew"); }));
  }

  // ---------- stage: crew and plant
  function credStatus(person, code) {
    var c = person.creds.filter(function (x) { return x.code === code; });
    if (!c.length) return "missing";
    var start = state.site.start_date || boot.today;
    if (c.some(function (x) { return x.no_expiry || (x.expiry && x.expiry >= start); })) return "ok";
    return c.some(function (x) { return x.expiry; }) ? "expired" : "missing";
  }
  function requirements(r) {
    var st = state.site.state, everyone = [], anyone = [];
    function add(list, code, label) { if (!list.some(function (x) { return x.code === code; })) list.push({ code: code, label: label || req.cred_names[code] || code }); }
    ["base"].concat(r.hazards).forEach(function (m) {
      ((req.modules[m] || {}).competencies || []).forEach(function (c) {
        if (c.scope !== "ALL" && c.scope !== st) return;
        if (req.optional.indexOf(c.code) >= 0) return;
        add(req.any_one.indexOf(c.code) >= 0 ? anyone : everyone, c.code);
      });
    });
    r.needs.forEach(function (n) { add(n.who === "all" ? everyone : anyone, n.code); });
    var trades = (req.template_licence[r.template] || []).slice();
    r.licences.forEach(function (t) { if (trades.indexOf(t) < 0) trades.push(t); });
    var licences = trades.map(function (t) { return { trade: t, codes: (req.licences[t] || {})[st] || [], label: st + " " + t + " licence" }; });
    return { everyone: everyone, anyone: anyone, licences: licences };
  }
  function renderCrew() {
    var r = result(), R = requirements(r);
    main.appendChild(head("Who's on the job?", "Pick the crew and we'll check their licences and tickets against this job, as at the start date."));
    var chosen = boot.people.filter(function (p) { return state.crew.indexOf(p.id) >= 0; });
    var team = el("div", { class: "wz-team" });
    R.licences.forEach(function (L) {
      var holders = chosen.filter(function (p) { return L.codes.some(function (c) { return credStatus(p, c) === "ok"; }); });
      team.appendChild(teamRow(L.label, holders, chosen.length));
    });
    R.anyone.forEach(function (a) {
      team.appendChild(teamRow(a.label, chosen.filter(function (p) { return credStatus(p, a.code) === "ok"; }), chosen.length));
    });
    if (team.children.length) {
      main.appendChild(el("div", { class: "card card-pad" }, [el("h3", { class: "card-title", text: "At least one person on the crew needs" }), team]));
    }
    var grid = el("div", { class: "wz-people" });
    boot.people.forEach(function (p) {
      var on = state.crew.indexOf(p.id) >= 0;
      var chips = el("div", { class: "wz-chips" });
      R.everyone.forEach(function (c) {
        var s = credStatus(p, c.code);
        chips.appendChild(el("span", { class: "chip chip-" + (s === "ok" ? "ok" : "bad") }, [icon(s === "ok" ? "check" : "x"), c.label + (s === "expired" ? " (expired)" : s === "missing" ? " (not on file)" : "")]));
      });
      grid.appendChild(el("button", { type: "button", role: "checkbox", "aria-checked": String(on), class: "wz-person" + (on ? " is-on" : ""), onclick: function () {
        var i = state.crew.indexOf(p.id); if (i >= 0) state.crew.splice(i, 1); else state.crew.push(p.id);
        state.crew_later = false; save(); render();
      } }, [
        el("span", { class: "wz-option-box" }, [icon("check")]),
        el("span", { class: "avatar", text: p.initials }),
        el("span", { class: "wz-person-body" }, [el("strong", { text: p.name }), el("span", { class: "muted", text: p.roles }), chips])
      ]));
    });
    main.appendChild(el("div", { class: "card card-pad" }, [
      el("h3", { class: "card-title", text: "Crew" }),
      boot.people.length ? grid : el("p", { class: "muted", text: "No people on your register yet. Send us your staff list and we'll add them." }),
      el("label", { class: "checkline" }, [el("input", { type: "checkbox", checked: state.crew_later, onchange: function (e) { state.crew_later = e.target.checked; if (state.crew_later) state.crew = []; save(); render(); } }),
        el("span", { text: "Crew not decided yet. We'll confirm with you before the SWMS is issued." })])
    ]));
    var other = el("input", { class: "input", value: state.plant_other, placeholder: "For example: jetter, pipe threader, core drill", oninput: function (e) { state.plant_other = e.target.value; save(); } });
    var auto = el("div", { class: "wz-chips" });
    r.plant.forEach(function (p) { auto.appendChild(el("span", { class: "chip chip-neutral", text: p })); });
    main.appendChild(el("div", { class: "card card-pad stack" }, [
      el("h3", { class: "card-title", text: "Plant and equipment" }),
      r.plant.length ? el("div", {}, [el("span", { class: "field-hint", text: "From your answers:" }), auto]) : null,
      el("label", { class: "field" }, [el("span", { class: "field-label", text: "Anything else?" }), other])
    ]));
    var errs = el("div", { class: "alert alert-danger", hidden: true, role: "alert", text: "Pick at least one person, or tick 'Crew not decided yet'." });
    main.appendChild(errs);
    main.appendChild(nav("quick", function () { if (!state.crew.length && !state.crew_later) { errs.hidden = false; return; } go("review"); }));
  }
  function teamRow(label, holders, crewSize) {
    var ok = holders.length > 0;
    return el("div", { class: "wz-team-row " + (ok ? "is-ok" : crewSize ? "is-bad" : "is-wait") }, [
      icon(ok ? "check-circle" : crewSize ? "alert-triangle" : "clock"),
      el("span", { class: "wz-team-label", text: label }),
      el("span", { class: "wz-team-who", text: ok ? holders.map(function (p) { return p.name; }).join(", ") : crewSize ? "Nobody selected holds this" : "Pick the crew to check" })
    ]);
  }

  // ---------- stage: review
  function renderReview() {
    var r = result(), s = state.site, jt = jobType();
    main.appendChild(head("Check and send", "Have a last look at the answers that matter most, then send it to our team."));
    r.stops.forEach(function (t) { main.appendChild(el("div", { class: "alert alert-danger alert-lg", role: "alert" }, [icon("octagon"), el("div", {}, [el("strong", { text: "This job needs a specialist first" }), el("p", { text: t })])])); });
    if (r.missing.length) {
      main.appendChild(el("div", { class: "alert alert-warn" }, [icon("alert-triangle"), el("div", {}, [el("strong", { text: "A few questions are unanswered. " }),
        el("button", { type: "button", class: "linklike", onclick: function () { go(q(r.missing[0]).priority === "quick" ? "quick" : "risks"); } }, ["Go back and finish them"])])]));
    }
    if (r.blockers.length) {
      var ul = el("ul", { class: "plainlist" });
      r.blockers.forEach(function (b) { ul.appendChild(el("li", { text: b })); });
      main.appendChild(el("div", { class: "alert alert-warn alert-lg" }, [icon("alert-triangle"), el("div", {}, [
        el("strong", { text: "To sort out before we can issue the SWMS" }), ul,
        el("p", { class: "small", text: "You can still send this now. We'll call you about these, or change your answers if you know more." })])]));
    }
    var keys = r.details.filter(function (d) { return d.priority === "key"; }), rest = r.details.filter(function (d) { return d.priority !== "key"; });
    var keyCard = el("div", { class: "card wz-keycard" }, [el("div", { class: "card-head" }, [
      el("div", {}, [el("h3", { class: "card-title" }, [icon("target"), "Key answers"]), el("p", { class: "muted small", text: "These decide what the SWMS says. Please read each one." })])])]);
    keys.forEach(function (d) { keyCard.appendChild(answeredRow(q(d.id), "risks")); });
    if (!keys.length) keyCard.appendChild(el("p", { class: "card-pad muted", text: "No key risk questions applied to this job." }));
    main.appendChild(keyCard);

    var summary = el("dl", { class: "deflist" });
    function row(k, v) { summary.appendChild(el("dt", { text: k })); summary.appendChild(el("dd", { text: v || "—" })); }
    row("Job type", jt ? jt.title : ""); row("Site", s.site_address); row("State", s.state); row("Start date", fmtDate(s.start_date));
    row("Job", s.scope); row("Building", (spec.building_ages.filter(function (b) { return b.v === s.building_age; })[0] || {}).label);
    if (s.head_contractor) row("Head contractor", s.head_contractor);
    row("Crew", state.crew.length ? boot.people.filter(function (p) { return state.crew.indexOf(p.id) >= 0; }).map(function (p) { return p.name; }).join(", ") : "To be confirmed");
    row("Plant", r.plant.concat(state.plant_other ? [state.plant_other] : []).join(", "));
    var qk = quickQuestions(r);
    row("Quick checks", (qk.length - r.quick_no.length) + " of " + qk.length + " in place" + (r.quick_no.length ? ". Not confirmed: " + r.quick_no.map(function (x) { return x.label; }).join(", ") : ""));
    main.appendChild(el("div", { class: "card" }, [el("div", { class: "card-head" }, [el("h3", { class: "card-title", text: "Job summary" }),
      el("button", { type: "button", class: "btn btn-ghost btn-sm", onclick: function () { go("site"); } }, ["Edit"])]), el("div", { class: "card-pad" }, [summary])]));
    if (rest.length) {
      var det = el("details", { class: "card wz-more" }, [el("summary", {}, [el("span", { text: "Other answers (" + rest.length + ")" }), icon("chevron-down")])]);
      rest.forEach(function (d) { det.appendChild(answeredRow(q(d.id), "risks")); });
      main.appendChild(det);
    }
    var notes = el("textarea", { class: "input", rows: "2", placeholder: "Access, occupants, anything unusual about the site", oninput: function (e) { state.notes = e.target.value; save(); } });
    notes.value = state.notes || "";
    var submit = el("button", { type: "button", class: "btn btn-primary btn-lg", disabled: !state.confirm || r.missing.length > 0, onclick: send }, [boot.prefill ? "Save changes" : "Send to our team", icon("arrow-right")]);
    main.appendChild(el("div", { class: "card card-pad stack" }, [
      el("label", { class: "field" }, [el("span", { class: "field-label", text: "Anything else we should know?" }), notes]),
      el("label", { class: "checkline checkline-strong" }, [el("input", { type: "checkbox", checked: state.confirm, onchange: function (e) { state.confirm = e.target.checked; save(); submit.disabled = !state.confirm || r.missing.length > 0; } }),
        el("span", { text: "I've checked the key answers above and they're right for this job." })]),
      el("div", { class: "wz-nav" }, [el("button", { type: "button", class: "btn btn-secondary", onclick: function () { go("crew"); } }, [icon("arrow-left"), "Back"]), submit]),
      el("p", { class: "field-hint", text: "A person on our team reviews every SWMS before it's issued. We aim to have it back to you within 24 hours." })
    ]));
  }
  function send() {
    var r = result();
    var payload = { job_type: state.job_type, site: state.site, answers: r.clean, crew: state.crew, plant_other: state.plant_other, notes: state.notes };
    document.getElementById("wz-payload").value = (form.getAttribute("method") || "").toLowerCase() === "get" ? "" : JSON.stringify(payload);
    try { sessionStorage.removeItem(STORE); } catch (e) { /* ignore */ }
    form.submit();
  }

  // ---------- shared pieces
  function head(title, sub) { return el("div", { class: "wz-head" }, [el("h2", { text: title }), el("p", { class: "muted", text: sub })]); }
  function nav(back, next) {
    return el("div", { class: "wz-nav" }, [
      el("button", { type: "button", class: "btn btn-secondary", onclick: function () { go(back); } }, [icon("arrow-left"), "Back"]),
      next ? el("button", { type: "button", class: "btn btn-primary", onclick: next }, ["Continue", icon("arrow-right")]) : null
    ]);
  }

  // ---------- live risk profile
  function renderSide() {
    side.textContent = "";
    var jt = jobType();
    if (!jt) {
      side.appendChild(el("div", { class: "profile-empty" }, [icon("shield"), el("strong", { text: "Job risk profile" }),
        el("p", { class: "muted", text: "As you answer, this panel shows what the SWMS will cover and what the job needs." })]));
      return;
    }
    var r = result(), R = requirements(r), now = {};
    side.appendChild(el("div", { class: "profile-head" }, [el("span", { class: "wz-type-icon" }, [icon(jt.icon)]), el("div", {}, [el("span", { class: "eyebrow", text: "Job risk profile" }), el("strong", { text: jt.title })])]));
    function block(title, items, cls, empty) {
      var b = el("div", { class: "profile-block" }, [el("h4", { text: title })]);
      if (!items.length) { b.appendChild(el("p", { class: "muted small", text: empty })); side.appendChild(b); return; }
      var ul = el("ul", { class: "profile-list " + cls });
      items.forEach(function (t) { now[title + t] = 1; ul.appendChild(el("li", { class: seen[title + t] ? "" : "is-new" }, [icon(cls === "is-risk" ? "alert-triangle" : cls === "is-stop" ? "octagon" : cls === "is-todo" ? "clock" : cls === "is-need" ? "shield" : "check"), el("span", { text: t })])); });
      b.appendChild(ul); side.appendChild(b);
    }
    var hr = [];
    r.hazards.forEach(function (h) { var t = (req.modules[h] || {}).hrcw; if (t && hr.indexOf(t) < 0) hr.push(t); });
    r.hrcw.forEach(function (i) { var t = req.hrcw_all[i]; if (hr.indexOf(t) < 0 && !hr.some(function (x) { return t.indexOf(x) === 0 || x.indexOf(t) === 0; })) hr.push(t); });
    if (r.stops.length) block("Specialist needed first", r.stops, "is-stop", "");
    block("High-risk construction work", hr, "is-risk", "None triggered so far.");
    var also = r.hazards.filter(function (h) { return !(req.modules[h] || {}).hrcw; }).map(function (h) { return req.modules[h].title; });
    if (also.length) block("The SWMS will also cover", also, "is-cover", "");
    var lic = R.licences.map(function (l) { return l.label.charAt(0).toUpperCase() + l.label.slice(1); }).concat(R.anyone.map(function (a) { return a.label; }));
    block("Licences and tickets the crew needs", lic.concat(R.everyone.map(function (e) { return e.label + " (everyone)"; })), "is-need", "");
    if (r.blockers.length) block("To sort out before issue", r.blockers, "is-todo", "");
    if (boot.is_staff && r.checks.length) block("Reviewer checks (staff only)", r.checks, "is-todo", "");
    else if (r.checks.length) side.appendChild(el("p", { class: "profile-foot" }, [icon("users"), el("span", { text: "Our reviewer will confirm " + r.checks.length + " more item" + (r.checks.length === 1 ? "" : "s") + " with you if needed." })]));
    seen = now;
  }

  function render() {
    main.textContent = "";
    renderSteps();
    ({ type: renderType, site: renderSite, risks: renderRisks, quick: renderQuick, crew: renderCrew, review: renderReview })[state.stage]();
    renderSide();
  }
  if (!state.job_type) state.stage = "type";
  render();
})();
