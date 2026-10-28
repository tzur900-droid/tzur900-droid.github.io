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
    { key: "headShape", label: "צורת התג", help: "ריבוע ← טריז ← טיפה", min: 0, max: 1, step: 0.01, fmt: (v) => (v < 0.25 ? "ריבוע" : v < 0.75 ? "טריז" : "טיפה") },
    { key: "pen", label: "קולמוס עגול", help: "קצוות וחיבורים עגולים במקום חדים", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "heel", label: "העקב (ב, מ)", help: "כמה הבסיס בולט מעבר לקו העומד", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
    { key: "overhang", label: "בליטת הגג (ד, ה)", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%" },
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
    // mixing two styles
    for (const id of ["mix-a", "mix-b"]) {
      const sel = $(id);
      PRESETS.forEach((p, i) => {
        const o = document.createElement("option");
        o.value = i;
        o.textContent = p.name;
        sel.appendChild(o);
      });
      sel.addEventListener("change", mix);
    }
    $("mix-b").value = 4;
    $("mix-t").addEventListener("input", mix);
    $("family").addEventListener("input", store);
    document.querySelectorAll("input[name=style]").forEach((r) => r.addEventListener("change", store));
    $("size").addEventListener("input", () => document.documentElement.style.setProperty("--pv-size", $("size").value + "px"));
    $("download").addEventListener("click", download);
    $("save-settings").addEventListener("click", saveSettings);
    $("load-settings").addEventListener("change", loadSettings);
  }

  function mix() {
    const A = Object.assign({}, D, PRESETS[$("mix-a").value].prm);
    const B = Object.assign({}, D, PRESETS[$("mix-b").value].prm);
    const t = $("mix-t").value / 100;
    $("mix-v").textContent = Math.round(100 - t * 100) + "% / " + Math.round(t * 100) + "%";
    for (const sl of SLIDERS) {
      const v = A[sl.key] + (B[sl.key] - A[sl.key]) * t;
      prm[sl.key] = Math.round(v / sl.step) * sl.step;
    }
    markPreset(null);
    changed();
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
    p.headShape = r(0.2, 0.9);
    p.pen = Math.random() < 0.6 ? 0 : r(0.2, 0.8);
    p.heel = r(0.2, 0.8);
    p.overhang = r(0.25, 0.8);
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
  // shape the letter, and the move is added on top. Every point belongs to a part that the letters
  // share (the start of the roof, a corner, the foot of a stem); with "the same part in every
  // letter" on, the other letters follow the letters changed by hand while the point moves.

  const SVGNS = "http://www.w3.org/2000/svg";
  let current = "bet", drag = null, variants = [];
  const undo = [];
  const GLYPHS = FontMaker.editableGlyphs();
  const HEBREW = GLYPHS.slice(0, 27).map((g) => g.name);
  const charOf = (n) => (GLYPHS.find((g) => g.name === n) || {}).char || "";
  const nameOf = {};
  GLYPHS.forEach((g) => { nameOf[g.char] = g.name; });

  function buildEditor() {
    const box = $("letters");
    for (const g of GLYPHS) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = g.char;
      b.dataset.name = g.name;
      b.addEventListener("click", () => select(g.name));
      box.appendChild(b);
    }
    const svg = $("ed-svg");
    svg.addEventListener("pointerdown", startDrag);
    svg.addEventListener("pointermove", moveDrag);
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointercancel", endDrag);
    svg.addEventListener("pointerleave", () => { if (!drag) showPart(null); });
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
      derive();
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
    $("ed-sync").addEventListener("change", () => {
      if ($("ed-sync").checked && prm.hand.some((n) => HEBREW.includes(n))) {
        pushUndo();
        derive();
        changed();
      }
    });
    $("ed-words").addEventListener("input", drawLine);
    $("ed-more").addEventListener("click", () => { variants = makeVariants(false); drawVariants(); });
    $("ed-like").addEventListener("click", () => { variants = makeVariants(true); drawVariants(); });
    select(current);
  }

  function select(name) {
    current = name;
    variants = makeVariants(false);
    drawEditor();
  }

  function pushUndo() {
    undo.push(JSON.stringify({ edits: prm.edits, hand: prm.hand }));
    if (undo.length > 60) undo.shift();
  }

  // The other letters follow the Hebrew letters changed by hand.
  function derive() {
    if (!$("ed-sync").checked) return;
    const src = prm.hand.filter((n) => HEBREW.includes(n));
    if (src.length) prm.edits = FontMaker.styleFrom(prm, src);
    else for (const n of HEBREW) delete prm.edits[n];
  }

  function el(name, attrs, parent) {
    const e = document.createElementNS(SVGNS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function contourPath(contours, dx) {
    dx = dx || 0;
    let d = "";
    for (const c of contours) {
      d += `M${c[0][0][0] + dx} ${-c[0][0][1]}`;
      for (const s of c) d += `C${s[1][0] + dx} ${-s[1][1]} ${s[2][0] + dx} ${-s[2][1]} ${s[3][0] + dx} ${-s[3][1]}`;
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
    svg.setAttribute("viewBox", `${x0} ${-top} ${w} ${top - bottom}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    drawEditor.view = [x0, top, w, bottom];
    svg.textContent = "";
    const upp = (top - bottom) / (svg.clientHeight || 420); // font units per screen pixel
    drawEditor.upp = upp;
    // the lines a point snaps to: the middle of the roof and of the base, and the outer lines
    const lines = [[g.H - g.T / 2, "main"], [g.T / 2, "main"], [0, ""], [g.H, ""], [-g.D + g.T / 2, ""], [g.H + g.A - g.T / 2, ""]];
    drawEditor.snapY = lines.map((l) => l[0]);
    for (const [y, cls] of lines) {
      el("line", { x1: x0, x2: x0 + w, y1: -y, y2: -y, class: "guide " + cls }, svg);
    }
    el("line", { x1: 0, x2: 0, y1: -top, y2: -bottom, class: "guide" }, svg);
    el("line", { x1: g.advance, x2: g.advance, y1: -top, y2: -bottom, class: "guide" }, svg);
    el("path", { d: contourPath(g.contours), class: "ink", "fill-rule": "nonzero" }, svg);
    if (drag && drag.snapped) {
      const [sx, sy] = drag.snapped;
      if (sy !== null) el("line", { x1: x0, x2: x0 + w, y1: -sy, y2: -sy, class: "snap" }, svg);
      if (sx !== null) el("line", { x1: sx, x2: sx, y1: -top, y2: -bottom, class: "snap" }, svg);
    }
    g.skeleton.forEach((st) => {
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
        const on = (drag ? drag.group.some(([s, q]) => s === si && q === pi) : hover && hover[0] === si && hover[1] === pi) ? " drag" : "";
        if (p.on) el("circle", { cx: p.x, cy: -p.y, r: 7 * upp, class: "pt" + on, "pointer-events": "none" }, svg);
        else el("rect", { x: p.x - 5 * upp, y: -p.y - 5 * upp, width: 10 * upp, height: 10 * upp, class: "pt off" + on, "pointer-events": "none" }, svg);
      });
    });
    drawEditor.glyph = g;
    drawLine();
    if (!drag) {
      drawVariants();
      drawChecks();
    }
  }

  // The point nearest the pointer, if it is close enough: [stroke, point]. Points on the line
  // win over control points, so a corner is easy to take.
  let hover = null;
  function pick(ev) {
    const g = drawEditor.glyph;
    if (!g) return null;
    const [x, y] = fontPoint(ev);
    const reach = 18 * drawEditor.upp;
    let best = null, bd = Infinity;
    g.skeleton.forEach((st, si) => st.points.forEach((p, pi) => {
      if (!p.on && st.points.some((q, qi) => qi !== pi && q.on && Math.hypot(q.x - p.x, q.y - p.y) < 2)) return;
      const d = Math.hypot(p.x - x, p.y - y) + (p.on ? 0 : 4 * drawEditor.upp);
      if (d < bd) { bd = d; best = [si, pi]; }
    }));
    return bd < reach ? best : null;
  }

  // The name of the part under the pointer, and how many letters share it.
  function showPart(hit) {
    const box = $("ed-part");
    $("ed-svg").style.cursor = hit ? (drag ? "grabbing" : "grab") : "default";
    if (!hit) {
      box.textContent = "מצביעים על נקודה כדי לראות לאיזה חלק של האות היא שייכת.";
      return;
    }
    const k = hit[0] + "." + hit[1];
    if (!HEBREW.includes(current)) {
      box.textContent = "נקודה של " + charOf(current);
      return;
    }
    const R = FontMaker.pointRoles(prm);
    const role = R[current].roles[k];
    const others = HEBREW.filter((n) => n !== current && Object.values(R[n].roles).includes(role));
    let txt = FontMaker.partName(role);
    if ($("ed-sync").checked && others.length) {
      txt += " — משתנה יחד איתה ב־" + others.length + " אותיות: " + others.slice(0, 12).map(charOf).join(" ") + (others.length > 12 ? "…" : "");
    } else if (!others.length) txt += " — רק באות הזו";
    box.textContent = txt;
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
    const hit = pick(ev);
    if (!hit) return;
    ev.preventDefault();
    const [si, pi] = hit;
    showPart(hit);
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
    // where the point would snap sideways: above or below the other points of the letter
    const snapX = [];
    sk.forEach((st, s) => st.points.forEach((q, p) => {
      if (q.on && !(s === si && p === pi)) snapX.push(q.x);
    }));
    drag = {
      group, from: fontPoint(ev), p0: [me.x, me.y], snapX,
      base: group.map(([s, p]) => (ed[s + "." + p] || [0, 0]).slice()),
      slant: drawEditor.glyph.slant,
      view: drawEditor.view,
      snapped: null,
    };
    $("ed-svg").setPointerCapture(ev.pointerId);
  }

  function moveDrag(ev) {
    if (!drag) {
      const h = pick(ev);
      if (String(h) !== String(hover)) {
        hover = h;
        showPart(h);
        drawEditor();
      }
      return;
    }
    const [x, y] = fontPoint(ev);
    let Dx = x - drag.from[0], Dy = y - drag.from[1];
    // Shift: straight across or straight up and down only
    if (ev.shiftKey) {
      if (Math.abs(Dx) > Math.abs(Dy)) Dy = 0;
      else Dx = 0;
    }
    let sx = null, sy = null;
    if ($("ed-snap").checked) {
      const near = 9 * drawEditor.upp;
      const ny = drag.p0[1] + Dy, nx = drag.p0[0] + Dx;
      for (const ly of drawEditor.snapY) if (Math.abs(ny - ly) < near) { Dy = ly - drag.p0[1]; sy = ly; break; }
      for (const lx of drag.snapX) if (Math.abs(nx - lx) < near) { Dx = lx - drag.p0[0]; sx = lx; break; }
      // back to where it started
      if (Math.abs(Dx) < near && sx === null) Dx = 0;
      if (Math.abs(Dy) < near && sy === null) Dy = 0;
    }
    drag.snapped = [sx, sy];
    const dy = Dy, dx = Dx - Dy * drag.slant;
    const ed = prm.edits[current];
    drag.group.forEach(([s, p], i) => {
      ed[s + "." + p] = [Math.round(drag.base[i][0] + dx), Math.round(drag.base[i][1] + dy)];
    });
    if (HEBREW.includes(current)) derive();
    if (!drag.frame) {
      drag.frame = requestAnimationFrame(() => {
        if (drag) drag.frame = 0;
        drawEditor();
      });
    }
  }

  function endDrag() {
    if (!drag) return;
    drag = null;
    const ed = prm.edits[current];
    for (const k in ed) if (!ed[k][0] && !ed[k][1]) delete ed[k];
    if (!Object.keys(ed).length) {
      delete prm.edits[current];
      prm.hand = prm.hand.filter((n) => n !== current);
      derive();
    }
    if (undo.length && undo[undo.length - 1] === JSON.stringify({ edits: prm.edits, hand: prm.hand })) undo.pop();
    changed();
  }

  // The letter in a line of text, as it is being changed: control letters on both sides of it
  // (the way type designers check a letter) and words of your own.
  function drawLine() {
    const svg = $("ed-line");
    const L = charOf(current);
    const words = ($("ed-words").value || "").trim();
    const ctrl = HEBREW.includes(current) ? `הה${L}הה וו${L}וו` : `00${L}00 11${L}11`;
    const text = (ctrl + " " + words).replace(/\s+/g, " ");
    const need = [...new Set([...text].map((ch) => nameOf[ch]).filter(Boolean))];
    const gl = {};
    for (const g of FontMaker.buildGlyphs(prm, { only: need }).glyphs) gl[g.name] = g;
    const space = prm.height * 0.42 * Math.sqrt(prm.spacing);
    let x = 0, d = "", dCur = "";
    // right to left: the first letter on the right
    const items = [...text].map((ch) => ({ ch, g: gl[nameOf[ch]] }));
    const total = items.reduce((a, it) => a + (it.g ? it.g.advance : space), 0);
    for (const it of items) {
      const adv = it.g ? it.g.advance : space;
      const left = total - x - adv;
      if (it.g) {
        const p = contourPath(it.g.contours, left);
        if (it.g.name === current) dCur += p;
        else d += p;
      }
      x += adv;
    }
    const top = prm.height * (1 + prm.ascender) + 60, bottom = -prm.height * prm.descender - 60;
    svg.setAttribute("viewBox", `-40 ${-top} ${total + 80} ${top - bottom}`);
    svg.textContent = "";
    el("path", { d, class: "line-ink", "fill-rule": "nonzero" }, svg);
    el("path", { d: dCur, class: "line-cur", "fill-rule": "nonzero" }, svg);
  }

  // ---- options to choose from

  const r = (a, b) => a + Math.random() * (b - a);
  const pm = (a, b) => r(a, b) * (Math.random() < 0.5 ? -1 : 1); // a clear move, one way or the other

  // Ways a part of a letter can change, each for the points of one kind of part (and their
  // control points with them); the amounts are parts of the letter height.
  const MOVES = [
    { test: (z, e, d) => e && z.startsWith("top") && /R|L/.test(d), move: () => [r(-0.1, 0.03), r(-0.02, 0.18)] },  // head
    { test: (z, e, d) => e && z.startsWith("base") && /U|D/.test(d), move: () => [pm(0.05, 0.13), 0] },               // foot
    { test: (z, e, d) => e && z.startsWith("base") && /R|L/.test(d), move: (z) => [r(-0.04, 0.12) * (z.endsWith("L") ? -1 : 1), 0] }, // base
    { test: (z, e, d) => e && z.startsWith("desc"), move: () => [r(-0.13, 0.08), r(-0.06, 0.06)] },                  // tail
    { test: (z, e, d) => e && z.startsWith("asc"), move: () => [pm(0.03, 0.09), r(-0.05, 0.1)] },                     // lamed
    { test: (z, e) => !e && z.startsWith("top"), move: () => [pm(0.03, 0.07), pm(0.03, 0.07)] },                       // upper corner
    { test: (z, e) => !e && z.startsWith("base"), move: () => [pm(0.03, 0.07), r(-0.05, 0.05)] },                      // lower corner
    { test: (z, e) => e && z.startsWith("mid"), move: () => [pm(0.03, 0.08), r(-0.04, 0.04)] },                        // free ends
  ];

  function makeVariants(around) {
    if (!HEBREW.includes(current)) return [];
    const R = FontMaker.pointRoles(prm)[current].roles;
    const H = prm.height;
    const start = around ? Object.assign({}, prm.edits[current] || {}) : {};
    const out = [];
    for (let v = 0; v < 6; v++) {
      const e = {};
      for (const k in start) e[k] = start[k].slice();
      const scale = around ? 0.45 : 1;
      let used = 0;
      MOVES.forEach((m, mi) => {
        if (Math.random() < (around ? 0.4 : 0.5) || (mi >= MOVES.length - 2 && used < 2)) {
          let any = false;
          const amount = {};
          for (const k in R) {
            const [zone, dirs] = R[k].split("|");
            const [din, dout] = dirs.split(">");
            const end = din === "o" || dout === "o";
            const dir = end ? (din === "o" ? dout : din) : "";
            if (!m.test(zone, end, dir)) continue;
            // one amount for each part, so its control points move with it
            const key = zone + "|" + dirs;
            if (!amount[key]) amount[key] = m.move(zone);
            const [dx, dy] = amount[key];
            const cur = e[k] || [0, 0];
            e[k] = [Math.round(cur[0] + dx * H * scale), Math.round(cur[1] + dy * H * scale)];
            any = true;
          }
          if (any) used++;
        }
      });
      out.push(e);
    }
    return out;
  }

  function drawVariants() {
    const box = $("ed-variants");
    box.textContent = "";
    if (!variants.length) {
      box.innerHTML = '<p class="hint">אפשרויות מוכנות יש לאותיות העבריות.</p>';
      return;
    }
    variants.forEach((v) => {
      const edits = Object.assign({}, prm.edits, { [current]: v });
      const g = FontMaker.buildGlyphs(Object.assign({}, prm, { edits }), { only: current }).glyphs[0];
      const b = document.createElement("button");
      b.type = "button";
      b.className = "variant";
      b.title = "לבחור את הצורה הזו";
      const svg = el("svg", { viewBox: `${-40} ${-(g.H + g.A + 40)} ${g.advance + 80} ${g.H + g.A + g.D + 80}` });
      el("path", { d: contourPath(g.contours), class: "line-ink", "fill-rule": "nonzero" }, svg);
      b.appendChild(svg);
      b.addEventListener("click", () => {
        pushUndo();
        prm.edits[current] = JSON.parse(JSON.stringify(v));
        if (!prm.hand.includes(current)) prm.hand.push(current);
        derive();
        changed();
      });
      box.appendChild(b);
    });
  }

  function drawChecks() {
    const box = $("ed-checks");
    const list = FontMaker.checkLetters(prm);
    box.textContent = "";
    if (!list.length) return;
    const h = document.createElement("p");
    h.className = "hint";
    h.textContent = "כדאי לבדוק:";
    box.appendChild(h);
    for (const c of list.slice(0, 10)) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "check";
      b.textContent = charOf(c.name) + " — " + c.text;
      b.addEventListener("click", () => select(c.name));
      box.appendChild(b);
    }
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
