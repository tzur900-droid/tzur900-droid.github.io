// The page of the font maker: the settings, the live preview and the download.
(function () {
  "use strict";

  const D = FontMaker.DEFAULTS;

  const SLIDERS = [
    { key: "weight", label: "עובי", min: 0.05, max: 0.26, step: 0.005, fmt: (v) => Math.round(v * 100) },
    { key: "contrast", label: "ניגודיות", help: "כמה הקווים העומדים דקים מהשוכבים", min: 1, max: 4, step: 0.05, fmt: (v) => v.toFixed(1) },
    { key: "width", label: "רוחב", min: 0.75, max: 1.3, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "height", label: "גובה האותיות", min: 440, max: 640, step: 5, fmt: (v) => v },
    { key: "round", label: "עיגול הפינות", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "serif", label: "תגים", help: "הראש שבקצה הגג של האותיות. 0 = גופן נקי", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "angle", label: "זווית הקולמוס", help: "כמו סופר שמטה את הקולמוס", min: -20, max: 20, step: 1, fmt: (v) => v + "°" },
    { key: "slant", label: "נטייה", min: -14, max: 14, step: 0.5, fmt: (v) => v + "°" },
    { key: "spacing", label: "ריווח בין האותיות", min: 0.6, max: 1.8, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "descender", label: "אורך הסופיות (ך ן ף ץ ק)", min: 0.25, max: 0.6, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "ascender", label: "גובה הלמ״ד", min: 0.25, max: 0.6, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
  ];

  const PRESETS = [
    { name: "ספר", prm: {} },
    { name: "כותרת כבדה", prm: { weight: 0.22, contrast: 1.9, width: 1.08, round: 0.25, serif: 0.45, spacing: 0.95 } },
    { name: "נקי", prm: { weight: 0.11, contrast: 1.1, width: 0.98, round: 0.5, serif: 0, spacing: 1.05 } },
    { name: "עדין", prm: { weight: 0.075, contrast: 2.2, round: 0.4, serif: 0.6, spacing: 1.08 } },
    { name: "קולמוס", prm: { weight: 0.14, contrast: 3.2, angle: 14, serif: 0.9, round: 0.6 } },
    { name: "מרובע", prm: { weight: 0.15, contrast: 2.0, round: 0, serif: 0.35, width: 1.05 } },
    { name: "צר", prm: { weight: 0.13, width: 0.8, spacing: 0.9 } },
    { name: "נטוי", prm: { weight: 0.12, slant: 9, width: 0.94 } },
  ];

  const STORE = "font-maker-settings";
  let prm = Object.assign({}, D, { edits: {}, hand: [] });

  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------- settings

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE) || "null");
      if (saved && saved.prm) {
        prm = sanitize(saved.prm);
        if (saved.family) $("family").value = saved.family;
        if (saved.style) document.querySelector(`input[name=style][value=${saved.style}]`).checked = true;
      }
    } catch (e) { /* no storage: start from the defaults */ }
  }

  function store() {
    try {
      localStorage.setItem(STORE, JSON.stringify({ prm, family: $("family").value, style: style() }));
    } catch (e) { /* ignore */ }
  }

  function sanitize(p) {
    const out = Object.assign({}, D);
    for (const s of SLIDERS) {
      const v = Number(p && p[s.key]);
      if (isFinite(v)) out[s.key] = Math.min(s.max, Math.max(s.min, v));
    }
    out.edits = {};
    const ed = p && p.edits;
    if (ed && typeof ed === "object") {
      for (const g in ed) {
        for (const k in ed[g]) {
          const v = ed[g][k];
          if (/^\d+\.\d+$/.test(k) && Array.isArray(v) && isFinite(v[0]) && isFinite(v[1])) {
            (out.edits[g] = out.edits[g] || {})[k] = [Number(v[0]), Number(v[1])];
          }
        }
      }
    }
    out.hand = Array.isArray(p && p.hand) ? p.hand.filter((n) => typeof n === "string" && out.edits[n]) : [];
    return out;
  }

  function style() {
    return document.querySelector("input[name=style]:checked").value;
  }

  // ---------------------------------------------------------------- controls

  function buildControls() {
    const box = $("sliders");
    for (const s of SLIDERS) {
      const wrap = document.createElement("div");
      wrap.className = "slider";
      wrap.innerHTML = `<label class="lbl" for="s-${s.key}"><span>${s.label}</span><span class="val" id="v-${s.key}"></span></label>
        <input type="range" id="s-${s.key}" min="${s.min}" max="${s.max}" step="${s.step}">` +
        (s.help ? `<small>${s.help}</small>` : "");
      box.appendChild(wrap);
      const input = wrap.querySelector("input");
      input.addEventListener("input", () => {
        prm[s.key] = Number(input.value);
        markPreset(null);
        changed();
      });
    }
    const chips = $("presets");
    PRESETS.forEach((p, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = p.name;
      b.dataset.i = i;
      b.addEventListener("click", () => {
        prm = Object.assign({}, D, p.prm, { edits: prm.edits, hand: prm.hand });
        markPreset(i);
        syncControls();
        changed();
      });
      chips.appendChild(b);
    });
    $("surprise").addEventListener("click", () => {
      prm = Object.assign(surprise(), { edits: prm.edits, hand: prm.hand });
      markPreset(null);
      syncControls();
      changed();
    });
    $("reset").addEventListener("click", () => {
      prm = Object.assign({}, D, { edits: prm.edits, hand: prm.hand });
      markPreset(0);
      syncControls();
      changed();
    });
    $("family").addEventListener("input", store);
    document.querySelectorAll("input[name=style]").forEach((r) => r.addEventListener("change", store));
    $("size").addEventListener("input", () => document.documentElement.style.setProperty("--pv-size", $("size").value + "px"));
    $("download").addEventListener("click", download);
    $("save-settings").addEventListener("click", saveSettings);
    $("load-settings").addEventListener("change", loadSettings);
  }

  function markPreset(i) {
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", String(i) === c.dataset.i));
  }

  function syncControls() {
    for (const s of SLIDERS) {
      $("s-" + s.key).value = prm[s.key];
      $("v-" + s.key).textContent = s.fmt(prm[s.key]);
    }
  }

  // A random font that still looks like a font: every setting stays in its sensible middle.
  function surprise() {
    const r = (a, b) => a + Math.random() * (b - a);
    const p = Object.assign({}, D, {
      weight: r(0.08, 0.2),
      contrast: r(1.2, 3.2),
      width: r(0.88, 1.12),
      round: r(0.1, 0.65),
      serif: Math.random() < 0.25 ? 0 : r(0.3, 0.95),
      angle: Math.random() < 0.5 ? 0 : Math.round(r(-6, 14)),
      slant: Math.random() < 0.85 ? 0 : Math.round(r(4, 10)),
      spacing: r(0.92, 1.15),
      height: Math.round(r(510, 570) / 5) * 5,
    });
    if (p.contrast < 1.5) p.serif = Math.min(p.serif, 0.4);
    return sanitize(p);
  }

  // ---------------------------------------------------------------- preview

  let face = null, timer = 0, busy = false, again = false;

  function changed() {
    syncControls();
    drawEditor();
    store();
    clearTimeout(timer);
    timer = setTimeout(render, 60);
  }

  async function render() {
    if (busy) { again = true; return; }
    busy = true;
    try {
      const buf = FontMaker.makeFont(prm, { family: "Preview" });
      const f = new FontFace("Preview", buf);
      await f.load();
      document.fonts.add(f);
      if (face) document.fonts.delete(face);
      face = f;
    } catch (e) {
      $("status").textContent = "שגיאה בתצוגה: " + e.message;
    }
    busy = false;
    if (again) { again = false; render(); }
  }

  // ---------------------------------------------------------------- letter editor
  //
  // The skeleton of the letter (the middle of its strokes) is drawn over the letter, with a point
  // at every place it can be bent. Dragging a point stores how far it moved; the settings still
  // shape the letter, and the move is added on top.

  const SVGNS = "http://www.w3.org/2000/svg";
  let current = "alef", drag = null;
  const undo = [];

  function buildEditor() {
    const box = $("letters");
    for (const g of FontMaker.editableGlyphs()) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = g.char;
      b.dataset.name = g.name;
      b.title = g.name;
      b.addEventListener("click", () => { current = g.name; drawEditor(); });
      box.appendChild(b);
    }
    const svg = $("ed-svg");
    svg.addEventListener("pointerdown", startDrag);
    svg.addEventListener("pointermove", moveDrag);
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointercancel", endDrag);
    $("ed-undo").addEventListener("click", () => {
      if (!undo.length) return;
      const u = JSON.parse(undo.pop());
      prm.edits = u.edits;
      prm.hand = u.hand;
      changed();
    });
    $("ed-reset").addEventListener("click", () => {
      if (!prm.edits[current]) return;
      pushUndo();
      delete prm.edits[current];
      prm.hand = prm.hand.filter((n) => n !== current);
      changed();
    });
    $("ed-reset-all").addEventListener("click", () => {
      if (!Object.keys(prm.edits).length) return;
      if (!confirm("להחזיר את כל האותיות שערכת לצורה המקורית?")) return;
      pushUndo();
      prm.edits = {};
      prm.hand = [];
      changed();
    });
    $("ed-apply").addEventListener("click", () => {
      const hebrew = FontMaker.editableGlyphs().slice(0, 27).map((g) => g.name);
      const sources = prm.hand.filter((n) => hebrew.includes(n));
      if (!sources.length) {
        $("ed-msg").textContent = "קודם משנים אות אחת לפחות (גוררים נקודות), ואז לוחצים כאן.";
        return;
      }
      pushUndo();
      prm.edits = FontMaker.styleFrom(prm, sources);
      const names = sources.map((n) => FontMaker.editableGlyphs().find((g) => g.name === n).char).join(" ");
      $("ed-msg").textContent = "כל האותיות קיבלו את השינויים של: " + names + ". לא אהבת? ↶ ביטול.";
      changed();
    });
    drawEditor();
  }

  function pushUndo() {
    undo.push(JSON.stringify({ edits: prm.edits, hand: prm.hand }));
    if (undo.length > 60) undo.shift();
  }

  function el(name, attrs, parent) {
    const e = document.createElementNS(SVGNS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function contourPath(contours) {
    let d = "";
    for (const c of contours) {
      d += `M${c[0][0][0]} ${-c[0][0][1]}`;
      for (const s of c) d += `C${s[1][0]} ${-s[1][1]} ${s[2][0]} ${-s[2][1]} ${s[3][0]} ${-s[3][1]}`;
      d += "Z";
    }
    return d;
  }

  function drawEditor() {
    document.querySelectorAll("#letters button").forEach((b) => {
      b.classList.toggle("on", b.dataset.name === current);
      b.classList.toggle("edited", !!(prm.edits && prm.edits[b.dataset.name]));
      b.classList.toggle("hand", prm.hand.includes(b.dataset.name));
    });
    const g = FontMaker.buildGlyphs(prm, { only: current }).glyphs[0];
    if (!g) return;
    const svg = $("ed-svg");
    // the view fits the letter, and stays put while a point is being dragged
    let top = g.H + g.A + 70, bottom = -g.D - 70, lo = 0, hi = g.advance;
    for (const st of g.skeleton) for (const p of st.points) {
      top = Math.max(top, p.y + 60); bottom = Math.min(bottom, p.y - 60);
      lo = Math.min(lo, p.x); hi = Math.max(hi, p.x);
    }
    let w = Math.max(hi - lo, g.H * 1.1) + 160, x0 = (lo + hi) / 2 - w / 2;
    if (drag && drag.view) [x0, top, w, bottom] = drag.view;
    else if (drag) drag.view = [x0, top, w, bottom];
    svg.setAttribute("viewBox", `${x0} ${-top} ${w} ${top - bottom}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    drawEditor.view = [x0, top, w, bottom];
    svg.textContent = "";
    const upp = (top - bottom) / (svg.clientHeight || 420); // font units per screen pixel
    for (const [y, main] of [[0, true], [g.H, true], [-g.D, false], [g.H + g.A, false]]) {
      el("line", { x1: x0, x2: x0 + w, y1: -y, y2: -y, class: main ? "guide main" : "guide" }, svg);
    }
    el("line", { x1: 0, x2: 0, y1: -top, y2: -bottom, class: "guide" }, svg);
    el("line", { x1: g.advance, x2: g.advance, y1: -top, y2: -bottom, class: "guide" }, svg);
    el("path", { d: contourPath(g.contours), class: "ink", "fill-rule": "nonzero" }, svg);
    g.skeleton.forEach((st, si) => {
      const P = st.points;
      let d = `M${P[0].x} ${-P[0].y}`, k = 1;
      for (const t of st.segs) {
        if (t === "L") { d += `L${P[k].x} ${-P[k].y}`; k += 1; }
        else { d += `C${P[k].x} ${-P[k].y} ${P[k + 1].x} ${-P[k + 1].y} ${P[k + 2].x} ${-P[k + 2].y}`; k += 3; }
      }
      el("path", { d, class: "bone" }, svg);
      // control points hang on the point of the line next to them
      P.forEach((p, pi) => {
        if (p.on) return;
        const a = P[pi - 1].on ? P[pi - 1] : P[pi + 1];
        el("line", { x1: a.x, y1: -a.y, x2: p.x, y2: -p.y, class: "arm" }, svg);
      });
    });
    g.skeleton.forEach((st, si) => {
      st.points.forEach((p, pi) => {
        // a corner with no rounding has its curve points on the corner: show just the corner
        if (!p.on && st.points.some((q, qi) => qi !== pi && q.on && Math.hypot(q.x - p.x, q.y - p.y) < 2)) return;
        el("circle", { cx: p.x, cy: -p.y, r: 20 * upp, class: "hit", "data-s": si, "data-p": pi }, svg);
        if (p.on) el("circle", { cx: p.x, cy: -p.y, r: 7 * upp, class: "pt", "pointer-events": "none" }, svg);
        else el("rect", { x: p.x - 5 * upp, y: -p.y - 5 * upp, width: 10 * upp, height: 10 * upp, class: "pt off", "pointer-events": "none" }, svg);
      });
    });
    drawEditor.glyph = g;
  }

  function fontPoint(ev) {
    const svg = $("ed-svg");
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const q = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [q.x, -q.y];
  }

  function startDrag(ev) {
    const t = ev.target;
    if (!t.classList || !t.classList.contains("hit")) return;
    ev.preventDefault();
    const si = Number(t.dataset.s), pi = Number(t.dataset.p);
    const sk = drawEditor.glyph.skeleton;
    // a point on the line takes its control points along, and the points of other strokes that
    // sit on it (where two strokes meet)
    const group = [];
    const take = (s, p) => {
      const pts = sk[s].points;
      group.push([s, p]);
      if (!pts[p].on) return;
      if (p > 0 && !pts[p - 1].on) group.push([s, p - 1]);
      if (p + 1 < pts.length && !pts[p + 1].on) group.push([s, p + 1]);
    };
    take(si, pi);
    const me = sk[si].points[pi];
    if (me.on) {
      sk.forEach((st, s) => st.points.forEach((q, p) => {
        if (s !== si && q.on && Math.hypot(q.x - me.x, q.y - me.y) < 4) take(s, p);
      }));
    }
    pushUndo();
    const ed = (prm.edits[current] = prm.edits[current] || {});
    if (!prm.hand.includes(current)) prm.hand.push(current);
    drag = {
      group, from: fontPoint(ev),
      base: group.map(([s, p]) => (ed[s + "." + p] || [0, 0]).slice()),
      slant: drawEditor.glyph.slant,
      view: drawEditor.view,
    };
    $("ed-svg").setPointerCapture(ev.pointerId);
  }

  function moveDrag(ev) {
    if (!drag) return;
    const [x, y] = fontPoint(ev);
    const dy = y - drag.from[1];
    const dx = x - drag.from[0] - dy * drag.slant;
    const ed = prm.edits[current];
    drag.group.forEach(([s, p], i) => {
      ed[s + "." + p] = [Math.round(drag.base[i][0] + dx), Math.round(drag.base[i][1] + dy)];
    });
    drawEditor();
  }

  function endDrag() {
    if (!drag) return;
    drag = null;
    const ed = prm.edits[current];
    for (const k in ed) if (!ed[k][0] && !ed[k][1]) delete ed[k];
    if (!Object.keys(ed).length) {
      delete prm.edits[current];
      prm.hand = prm.hand.filter((n) => n !== current);
    }
    if (undo.length && undo[undo.length - 1] === JSON.stringify({ edits: prm.edits, hand: prm.hand })) undo.pop();
    changed();
  }

  // ---------------------------------------------------------------- files

  function fileName(ext) {
    const fam = ($("family").value || "My Hebrew").replace(/[^A-Za-z0-9]+/g, "") || "MyHebrew";
    return fam + "-" + style() + ext;
  }

  function save(blob, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }

  function download() {
    const btn = $("download");
    btn.disabled = true;
    $("status").textContent = "בונה את הגופן… (כמה שניות)";
    setTimeout(() => {
      try {
        const buf = FontMaker.makeFont(prm, { family: $("family").value, style: style(), merge: true });
        save(new Blob([buf], { type: "font/otf" }), fileName(".otf"));
        $("status").textContent = "הגופן ירד: " + fileName(".otf");
      } catch (e) {
        $("status").textContent = "לא הצלחתי לבנות את הגופן: " + e.message;
      }
      btn.disabled = false;
    }, 30);
  }

  function saveSettings() {
    const data = { app: "font-maker", version: 1, family: $("family").value, style: style(), prm };
    save(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), fileName(".json"));
  }

  function loadSettings(ev) {
    const file = ev.target.files[0];
    if (!file) return;
    file.text().then((txt) => {
      const data = JSON.parse(txt);
      prm = sanitize(data.prm || data);
      if (data.family) $("family").value = data.family;
      if (data.style === "Bold" || data.style === "Regular") {
        document.querySelector(`input[name=style][value=${data.style}]`).checked = true;
      }
      markPreset(null);
      changed();
      $("status").textContent = "ההגדרות נטענו.";
    }).catch(() => {
      $("status").textContent = "הקובץ הזה אינו קובץ הגדרות של המחולל.";
    });
    ev.target.value = "";
  }

  // ---------------------------------------------------------------- start

  buildControls();
  load();
  syncControls();
  markPreset(SLIDERS.every((s) => prm[s.key] === D[s.key]) ? 0 : null);
  buildEditor();
  render();
})();
