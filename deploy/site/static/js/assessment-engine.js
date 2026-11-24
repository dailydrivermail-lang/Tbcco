/* Guided SWMS assessment: evaluation engine.
   Mirrors swms/assessment.py (evaluate). tests/test_assessment.py runs both on the same cases. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.AssessmentEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var CONTEXT = ["job_type", "state", "building_age"];

  function vals(answers, key) {
    var v = answers[key];
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return [];
    return Array.isArray(v) ? v.map(String) : [String(v)];
  }
  function cond(c, answers) {
    if (!c) return true;
    if (c.all) return c.all.every(function (x) { return cond(x, answers); });
    if (c.any) return c.any.some(function (x) { return cond(x, answers); });
    if (c.not) return !cond(c.not, answers);
    var allowed = c["in"].map(String);
    return vals(answers, c.q).some(function (v) { return allowed.indexOf(v) >= 0; });
  }
  function questionsFor(spec, jobType) {
    var jt = spec.job_types.filter(function (j) { return j.id === jobType; })[0];
    if (!jt) return [];
    var out = [];
    jt.sections.forEach(function (sec) {
      spec.questions.forEach(function (q) { if (q.section === sec) out.push(q); });
    });
    spec.questions.forEach(function (q) { if (q.priority === "quick") out.push(q); });
    return out;
  }
  function pushUnique(arr, v) {
    var key = JSON.stringify(v);
    if (!arr.some(function (x) { return JSON.stringify(x) === key; })) arr.push(v);
  }
  function evaluate(answers, spec) {
    var jt = spec.job_types.filter(function (j) { return j.id === answers.job_type; })[0];
    var res = { job_type: jt ? jt.id : null, template: jt ? jt.template : null, visible: [], missing: [], hazards: [], hrcw: [],
      controls: [], needs: [], licences: [], plant: [], blockers: [], checks: [], stops: [], details: [], quick_no: [], clean: {} };
    if (!jt) return res;
    var live = {};
    CONTEXT.forEach(function (k) { live[k] = answers[k] === undefined ? null : answers[k]; });
    questionsFor(spec, jt.id).forEach(function (q) {
      if (!cond(q.when, live)) return;
      res.visible.push(q.id);
      var allowed = q.options.map(function (o) { return o.v; });
      var v = vals(answers, q.id).filter(function (x) { return allowed.indexOf(x) >= 0; });
      if (q.type !== "multi") v = v.slice(0, 1);
      if (!v.length) { res.missing.push(q.id); return; }
      live[q.id] = q.type === "multi" ? v : v[0];
      res.clean[q.id] = live[q.id];
      var labels = q.options.filter(function (o) { return v.indexOf(o.v) >= 0; }).map(function (o) { return o.label; });
      if (q.priority === "quick") {
        if (v[0] !== "yes") res.quick_no.push({ id: q.id, label: q.short, answer: labels[0] });
      } else {
        res.details.push({ id: q.id, label: q.short, answer: labels.join("; "), priority: q.priority,
          unsure: v.some(function (x) { return ["unsure", "unknown", "undecided"].indexOf(x) >= 0; }) });
      }
      (q.effects || []).forEach(function (e) {
        var hit = e["if"].map(String);
        if (!v.some(function (x) { return hit.indexOf(x) >= 0; }) || !cond(e.when, live)) return;
        if (e.hazard) pushUnique(res.hazards, e.hazard);
        (e.hrcw || []).forEach(function (i) { pushUnique(res.hrcw, i); });
        if (e.control) res.controls.push(e.control);
        if (e.need) pushUnique(res.needs, e.need);
        if (e.licence) pushUnique(res.licences, e.licence);
        if (e.plant) pushUnique(res.plant, e.plant);
        if (e.blocker) pushUnique(res.blockers, e.blocker);
        if (e.check) pushUnique(res.checks, e.check);
        if (e.stop) pushUnique(res.stops, e.stop);
      });
    });
    return res;
  }
  return { evaluate: evaluate, cond: cond, questionsFor: questionsFor };
});
