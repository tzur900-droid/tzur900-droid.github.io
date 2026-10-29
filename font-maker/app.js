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

  // Changing an existing font (outline.js): its settings, and the settings of single letters.
  const OUTLINE_SLIDERS = [
    { key: "weight", aiStep: 0.3, label: "עובי", help: "0 = כמו הגופן המקורי", min: -0.8, max: 1.5, step: 0.05, fmt: (v) => (v > 0 ? "+" : "") + Math.round(v * 100), about: "0 is the original weight; 1 is bold, -0.5 light." },
    { key: "contrast", aiStep: 0.3, label: "ניגודיות", help: "ימינה: קווים שוכבים עבים יותר. שמאלה: עומדים עבים יותר", min: -1, max: 1, step: 0.05, fmt: (v) => (v > 0 ? "+" : "") + Math.round(v * 100), about: "Positive: thicker horizontal strokes than vertical ones (traditional Hebrew); negative: the other way." },
    { key: "width", aiStep: 0.1, label: "רוחב", min: 0.7, max: 1.4, step: 0.01, fmt: (v) => Math.round(v * 100) + "%", about: "1 is the original width." },
    { key: "height", aiStep: 0.06, label: "גובה", min: 0.8, max: 1.25, step: 0.01, fmt: (v) => Math.round(v * 100) + "%", about: "1 is the original height of the letters." },
    { key: "slant", aiStep: 8, label: "נטייה", min: -15, max: 15, step: 0.5, fmt: (v) => v + "°", about: "Degrees; 0 is upright." },
    { key: "spacing", aiStep: 0.15, label: "ריווח בין האותיות", min: 0.6, max: 1.8, step: 0.01, fmt: (v) => Math.round(v * 100) + "%", about: "1 is the original spacing." },
    { key: "round", aiStep: 0.3, label: "עיגול הפינות", min: 0, max: 1, step: 0.01, fmt: (v) => Math.round(v * 100) + "%", about: "0 keeps the corners as they are; 1 rounds them a lot." },
  ];
  const LETTER_KEYS = [
    { key: "width", label: "רוחב האות", min: 0.6, max: 1.6, step: 0.08, base: 1, fmt: (v) => Math.round(v * 100) + "%", about: "Multiplies the width of this letter." },
    { key: "height", label: "גובה האות", min: 0.7, max: 1.4, step: 0.06, base: 1, fmt: (v) => Math.round(v * 100) + "%", about: "Multiplies the height of this letter, from the line up." },
    { key: "weight", label: "עובי האות", min: -1, max: 1, step: 0.25, base: 0, fmt: (v) => (v > 0 ? "+" : "") + Math.round(v * 100), about: "Added to the weight of the whole font, for this letter." },
    { key: "depth", label: "אורך הזנב (מתחת לשורה)", min: 0.5, max: 1.8, step: 0.15, base: 1, fmt: (v) => Math.round(v * 100) + "%", about: "Multiplies how far this letter goes below the line (the tails of ך ן ף ץ ק)." },
    { key: "shift", label: "הזזה למעלה / למטה", min: -0.3, max: 0.3, step: 0.04, base: 0, fmt: (v) => (v > 0 ? "+" : "") + Math.round(v * 100), about: "Moves this letter up (positive) or down, in parts of the letter height." },
  ];

  const STORE = "font-maker-settings";
  let prm = Object.assign({}, D, { edits: {}, hand: [] });
  let mode = "outline";                 // "outline": change an existing font; "draw": draw from nothing
  let src = { id: "frankruhl" };        // the font changed: {id} from the library, or {file} from the computer
  let ol = olDefaults();                // the changes to it
  let model = null;                     // the font changed, as read by outline.js
  let olUndo = [];

  function olDefaults() {
    return Object.assign({}, FontMaker.Outline.SETTINGS, { letters: {}, points: {}, parts: {} });
  }

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
      if (saved && saved.ol) ol = sanitizeOutline(saved.ol);
      // settings saved before there was a choice were made by drawing
      if (saved && (saved.mode === "draw" || (!saved.mode && saved.prm && Object.keys(saved.prm.edits || {}).length))) mode = "draw";
      if (saved && saved.src && FontMaker.library.some((f) => f.id === saved.src.id)) src = { id: saved.src.id };
    } catch (e) { /* no storage: start from the defaults */ }
  }

  function store() {
    try {
      localStorage.setItem(STORE, JSON.stringify({ prm, mode, src: src.id ? src : null, ol, family: $("family").value, style: style() }));
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
    const ids = FontMaker.letterSets().map((x) => x.id);
    // settings saved before there was a choice of letters were made on the square letters
    const old = p && !p.base && p.edits && Object.keys(p.edits).length;
    out.base = p && ids.includes(p.base) ? p.base : old ? "square" : "classic";
    out.hand = Array.isArray(p && p.hand) ? p.hand.filter((n) => typeof n === "string" && out.edits[n]) : [];
    return out;
  }

  function sanitizeOutline(p) {
    const out = olDefaults();
    for (const s of OUTLINE_SLIDERS) {
      const v = Number(p && p[s.key]);
      if (isFinite(v)) out[s.key] = Math.min(s.max, Math.max(s.min, v));
    }
    const P = p && p.points;
    if (P && typeof P === "object") {
      for (const g in P) for (const k in P[g]) {
        const v = P[g][k];
        if (/^\d+\.\d+(\.[ab])?$/.test(k) && Array.isArray(v) && isFinite(v[0]) && isFinite(v[1])) (out.points[g] = out.points[g] || {})[k] = [Number(v[0]), Number(v[1])];
      }
    }
    const PA = p && p.parts;
    if (PA && typeof PA === "object") {
      for (const g in PA) {
        const list = (Array.isArray(PA[g]) ? PA[g] : []).filter((x) => x && (x.type === "cut" ? Array.isArray(x.rect) && x.rect.length === 4 : Array.isArray(x.polys)));
        if (list.length) out.parts[g] = list.map((x) => (x.type === "cut" ? { type: "cut", rect: x.rect.map(Number) } :
          { type: "add", polys: x.polys, dx: Number(x.dx) || 0, dy: Number(x.dy) || 0, s: Number(x.s) || 1 }));
      }
    }
    const L = p && p.letters;
    if (L && typeof L === "object") {
      for (const g in L) {
        for (const k of LETTER_KEYS) {
          const v = Number(L[g] && L[g][k.key]);
          if (isFinite(v) && v !== k.base) (out.letters[g] = out.letters[g] || {})[k.key] = Math.min(k.max, Math.max(k.min, v));
        }
      }
    }
    return out;
  }

  function style() {
    return document.querySelector("input[name=style]:checked").value;
  }

  // ---------------------------------------------------------------- controls

  const sliders = () => (mode === "outline" ? OUTLINE_SLIDERS : SLIDERS);
  const target = () => (mode === "outline" ? ol : prm);

  function buildSliders() {
    const box = $("sliders");
    box.textContent = "";
    for (const s of sliders()) {
      const wrap = document.createElement("div");
      wrap.className = "slider";
      wrap.innerHTML = `<label class="lbl" for="s-${s.key}"><span>${s.label}</span><span class="val" id="v-${s.key}"></span></label>
        <input type="range" id="s-${s.key}" min="${s.min}" max="${s.max}" step="${s.step}">` +
        (s.help ? `<small>${s.help}</small>` : "");
      box.appendChild(wrap);
      const input = wrap.querySelector("input");
      input.addEventListener("input", () => {
        target()[s.key] = Number(input.value);
        markPreset(null);
        changed();
      });
    }
  }

  function buildControls() {
    buildSliders();
    const chips = $("presets");
    PRESETS.forEach((p, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = p.name;
      b.dataset.i = i;
      b.addEventListener("click", () => {
        prm = Object.assign({}, D, p.prm, { base: prm.base, edits: prm.edits, hand: prm.hand });
        markPreset(i);
        syncControls();
        changed();
      });
      chips.appendChild(b);
    });
    $("surprise").addEventListener("click", () => {
      if (mode === "outline") ol = Object.assign(surpriseOutline(), { letters: ol.letters, points: ol.points, parts: ol.parts });
      else prm = Object.assign(surprise(), { base: prm.base, edits: prm.edits, hand: prm.hand });
      markPreset(null);
      syncControls();
      changed();
    });
    $("reset").addEventListener("click", () => {
      if (mode === "outline") ol = Object.assign(olDefaults(), { letters: ol.letters, points: ol.points, parts: ol.parts });
      else prm = Object.assign({}, D, setDefaults(prm.base), { base: prm.base, edits: prm.edits, hand: prm.hand });
      markPreset(null);
      syncControls();
      changed();
    });
    document.querySelectorAll("input[name=mode]").forEach((r) => r.addEventListener("change", () => setMode(r.value)));
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
    $("upload").addEventListener("change", uploadFont);
    $("license-dl").addEventListener("click", downloadLicense);
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

  // ---- the letters to start from

  function setDefaults(id) {
    const s = FontMaker.letterSets().find((x) => x.id === id);
    return s ? s.defaults : {};
  }

  // A word drawn in the letters of some settings, as an SVG path.
  function wordPath(p, text) {
    const names = { "א": "alef", "ב": "bet", "ג": "gimel", "ד": "dalet", "ה": "he", "ו": "vav", "ז": "zayin", "ח": "het", "ט": "tet", "י": "yod",
      "ך": "finalkaf", "כ": "kaf", "ל": "lamed", "ם": "finalmem", "מ": "mem", "ן": "finalnun", "נ": "nun", "ס": "samekh", "ע": "ayin",
      "ף": "finalpe", "פ": "pe", "ץ": "finaltsadi", "צ": "tsadi", "ק": "qof", "ר": "resh", "ש": "shin", "ת": "tav" };
    const chars = [...text];
    const gl = {};
    for (const g of FontMaker.buildGlyphs(p, { only: [...new Set(chars.map((c) => names[c]).filter(Boolean))] }).glyphs) gl[g.name] = g;
    const space = (p.height || D.height) * 0.42;
    const total = chars.reduce((a, c) => a + (gl[names[c]] ? gl[names[c]].advance : space), 0);
    let x = 0, d = "";
    for (const ch of chars) {
      const g = gl[names[ch]];
      const adv = g ? g.advance : space;
      if (g) {
        const dx = total - x - adv;
        for (const c of g.contours) {
          d += `M${c[0][0][0] + dx} ${-c[0][0][1]}`;
          for (const s of c) d += `C${s[1][0] + dx} ${-s[1][1]} ${s[2][0] + dx} ${-s[2][1]} ${s[3][0] + dx} ${-s[3][1]}`;
          d += "Z";
        }
      }
      x += adv;
    }
    return { d, width: total };
  }

  function buildBases() {
    const box = $("bases");
    for (const s of FontMaker.letterSets()) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "base";
      b.dataset.id = s.id;
      const p = Object.assign({}, D, s.defaults, { base: s.id, edits: {} });
      const w = wordPath(p, "שלום עולם");
      const H = p.height;
      b.innerHTML = `<svg viewBox="-20 ${-(H * 1.5)} ${w.width + 40} ${H * 1.95}" aria-hidden="true"><path d="${w.d}"/></svg>
        <span class="base-name">${s.name}</span><span class="base-about">${s.about || ""}</span>`;
      b.addEventListener("click", () => chooseBase(s.id));
      box.appendChild(b);
    }
  }

  function chooseBase(id) {
    if (id === prm.base) return;
    if (Object.keys(prm.edits).length && !confirm("לעבור לאותיות אחרות? השינויים שעשית בעריכת האותיות יימחקו.")) return;
    prm = Object.assign({}, D, setDefaults(id), { base: id, edits: {}, hand: [] });
    undo.length = 0;
    markPreset(null);
    select(current);
    changed();
  }

  function markBase() {
    document.querySelectorAll(".base").forEach((b) => b.classList.toggle("on", b.dataset.id === prm.base));
  }

  function markPreset(i) {
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", String(i) === c.dataset.i));
  }

  function syncControls() {
    const t = target();
    for (const s of sliders()) {
      if (!$("s-" + s.key)) continue;
      $("s-" + s.key).value = t[s.key];
      $("v-" + s.key).textContent = s.fmt(t[s.key]);
    }
  }

  function surpriseOutline() {
    const r = (a, b) => a + Math.random() * (b - a);
    return sanitizeOutline({
      weight: r(-0.25, 0.8),
      contrast: Math.random() < 0.5 ? 0 : r(-0.4, 0.6),
      width: r(0.9, 1.12),
      slant: Math.random() < 0.85 ? 0 : Math.round(r(5, 9)),
      spacing: r(0.95, 1.15),
      round: Math.random() < 0.6 ? 0 : r(0.2, 0.7),
    });
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
    markBase();
    if (mode === "outline") drawOutlineEditor();
    else drawEditor();
    store();
    clearTimeout(timer);
    timer = setTimeout(render, 60);
  }

  async function render() {
    if (busy) { again = true; return; }
    busy = true;
    try {
      let buf;
      if (mode === "outline") {
        if (!model) { busy = false; return; }
        // only the letters on the screen get the slow changes, so the preview keeps up
        const text = [...document.querySelectorAll(".pv")].map((e) => e.textContent).join("") + "אבגדהוזחטיכךלמםנןסעפףצץקרשת0123456789";
        buf = FontMaker.Outline.build(model, ol, { family: "Preview", only: FontMaker.Outline.glyphsFor(model, text), fit: false });
      } else {
        buf = FontMaker.makeFont(prm, { family: "Preview" });
      }
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
      if (mode === "outline") { olUndoLast(); return; }
      if (!undo.length) return;
      const u = JSON.parse(undo.pop());
      prm.edits = u.edits;
      prm.hand = u.hand;
      changed();
    });
    $("ed-reset").addEventListener("click", () => {
      if (mode === "outline") {
        const g = glyphOf(charOf(current));
        if (g && (ol.letters[g] || ol.points[g] || ol.parts[g])) {
          olPush();
          delete ol.letters[g]; delete ol.points[g]; delete ol.parts[g];
          olSel.clear(); selPart = -1;
          changed();
        }
        return;
      }
      if (!prm.edits[current]) return;
      pushUndo();
      delete prm.edits[current];
      prm.hand = prm.hand.filter((n) => n !== current);
      derive();
      changed();
    });
    $("ed-reset-all").addEventListener("click", () => {
      if (mode === "outline") {
        if ((Object.keys(ol.letters).length || Object.keys(ol.points).length || Object.keys(ol.parts).length) &&
          confirm("להחזיר את כל האותיות שערכת לצורה של הגופן?")) {
          olPush();
          ol.letters = {}; ol.points = {}; ol.parts = {};
          olSel.clear(); selPart = -1;
          changed();
        }
        return;
      }
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
    $("ed-words").addEventListener("input", () => (mode === "outline" ? drawOutlineEditor() : drawLine()));
    $("ed-more").addEventListener("click", () => { variants = makeVariants(false); drawVariants(); });
    $("ed-like").addEventListener("click", () => { variants = makeVariants(true); drawVariants(); });
    select(current);
  }

  function select(name) {
    current = name;
    if (mode === "outline") { olSel.clear(); selPart = -1; borrow.letterSet = false; borrow.rect = null; drawOutlineEditor(); return; }
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

  // ---------------------------------------------------------------- starting from a font

  function setMode(m) {
    mode = m;
    document.body.classList.toggle("mode-outline", m === "outline");
    document.body.classList.toggle("mode-draw", m === "draw");
    document.querySelector(`input[name=mode][value=${m}]`).checked = true;
    buildSliders();
    if (m === "outline" && !model) chooseFont(src.id || "frankruhl");
    else {
      if (m === "draw") select(current);
      changed();
    }
  }

  // The library: cards with the name of each font written in it.
  let libraryShown = false;
  function buildLibrary() {
    const box = $("library");
    const groups = {};
    for (const f of FontMaker.library) (groups[f.group] = groups[f.group] || []).push(f);
    let first = true;
    for (const g in groups) {
      const det = document.createElement("details");
      det.className = "lib-group";
      det.open = first;
      first = false;
      const h = document.createElement("summary");
      h.textContent = g + " (" + groups[g].length + ")";
      det.appendChild(h);
      box.appendChild(det);
      const grid = document.createElement("div");
      grid.className = "lib-grid";
      for (const f of groups[g]) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "lib";
        b.dataset.id = f.id;
        b.innerHTML = `<span class="lib-sample" style="font-family:'lib-${f.id}',serif">אבגד שלום</span><span class="lib-name">${f.name}</span><span class="lib-about">${f.about} · ${f.license}</span>`;
        b.addEventListener("click", () => chooseFont(f.id));
        grid.appendChild(b);
      }
      det.appendChild(grid);
    }
  }

  // The cards show each font in itself; the fonts load in the background.
  async function showLibraryFonts() {
    if (libraryShown) return;
    libraryShown = true;
    for (const f of FontMaker.library) {
      try {
        const ff = new FontFace("lib-" + f.id, await FontMaker.libraryFile(f.file));
        await ff.load();
        document.fonts.add(ff);
      } catch (e) { /* the card keeps the name only */ }
    }
  }

  function markLibrary() {
    document.querySelectorAll(".lib").forEach((b) => b.classList.toggle("on", !!src.id && b.dataset.id === src.id));
  }

  async function chooseFont(id) {
    const f = FontMaker.library.find((x) => x.id === id) || FontMaker.library[0];
    $("status").textContent = "טוען את " + f.name + "…";
    try {
      const buf = await FontMaker.libraryFile(f.file);
      // on the first load the saved hand edits are for this font; after that, another font drops them
      const hadModel = !!model;
      const fresh = hadModel && (!model.meta.library || model.meta.library.id !== f.id);
      if (fresh && (Object.keys(ol.points).length || Object.keys(ol.parts).length) && model &&
        !confirm("לעבור לגופן אחר? הנקודות שהזזת והחלקים שהוספת שייכים לגופן הזה, והם יימחקו.")) { afterFont(); return; }
      model = FontMaker.Outline.load(buf, { library: f });
      src = { id: f.id };
      dropMissingLetters(fresh);
      $("status").textContent = "";
    } catch (e) {
      $("status").textContent = "לא הצלחתי לטעון את הגופן: " + e.message;
    }
    afterFont();
  }

  async function uploadFont(ev) {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file) return;
    try {
      const buf = await file.arrayBuffer();
      const m = FontMaker.Outline.load(buf, { file: file.name });
      if (!Object.keys(m.byChar).some((u) => u >= 0x5d0 && u <= 0x5ea)) {
        if (!confirm("בגופן הזה אין אותיות עבריות. להמשיך בכל זאת?")) return;
      }
      model = m;
      src = { file: file.name };
      dropMissingLetters(true);
      $("status").textContent = "הגופן נטען: " + file.name;
    } catch (e) {
      $("status").textContent = "לא הצלחתי לקרוא את הקובץ (צריך TTF, OTF או WOFF): " + e.message;
    }
    afterFont();
  }

  // Hand edits belong to the glyphs of one font; another font starts without them.
  function dropMissingLetters(newFont) {
    for (const g in ol.letters) if (!model.glyphs.some((x) => x.name === g)) delete ol.letters[g];
    if (newFont) { ol.points = {}; ol.parts = {}; olStack.length = 0; }
  }

  // What license the font has, from the library or from the font itself.
  function licenseOf() {
    if (!model) return null;
    const lib = model.meta.library;
    if (lib) return { kind: lib.license, file: lib.licenseFile };
    const t = (model.names.license + " " + model.names.licenseURL + " " + model.names.copyright).toLowerCase();
    if (/open font license|scripts\.sil\.org\/ofl|openfontlicense|\bofl\b/.test(t)) return { kind: "OFL" };
    if (/gnu|\bgpl\b/.test(t)) return { kind: "GPL" };
    if (/apache license/.test(t)) return { kind: "Apache" };
    return { kind: null };
  }

  function afterFont() {
    markLibrary();
    const info = $("src-info"), note = $("license-note");
    if (!model) { info.textContent = ""; return; }
    const lic = licenseOf();
    const orig = model.names.family || (model.meta.file || "");
    info.innerHTML = "";
    const b = document.createElement("b");
    b.textContent = "הגופן שמשנים: " + orig;
    info.appendChild(b);
    const known = lic && lic.kind;
    $("rights-wrap").classList.toggle("hidden", !!known);
    note.textContent = known
      ? `הגופן המקורי ברישיון ${lic.kind}. הגופן החדש יישאר ברישיון הזה: מותר להשתמש בו ולשתף אותו, עם שם חדש, ועם קובץ הרישיון.`
      : "לא זיהיתי את הרישיון של הגופן הזה. שנה אותו רק אם מותר לך (למשל גופן שעיצבת בעצמך, או שהרישיון שלו מתיר שינויים).";
    if (model.names.license && !model.meta.library) {
      const p = document.createElement("small");
      p.className = "src-license";
      p.textContent = "מה כתוב בגופן: " + model.names.license.slice(0, 220) + (model.names.license.length > 220 ? "…" : "");
      info.appendChild(p);
    }
    if (FontMaker.Outline && current && !HEBREW.includes(current)) current = "bet";
    changed();
  }

  async function downloadLicense() {
    const lic = licenseOf();
    if (!lic) return;
    let text = "";
    if (lic.file) {
      const buf = await FontMaker.libraryFile(lic.file);
      text = new TextDecoder().decode(buf);
      if (lic.file === "LICENSE-Culmus.txt") text += "\n\n" + new TextDecoder().decode(await FontMaker.libraryFile("GNU-GPL.txt"));
    } else {
      text = [model.names.copyright, model.names.license, model.names.licenseURL].filter(Boolean).join("\n\n");
    }
    save(new Blob([text], { type: "text/plain;charset=utf-8" }), fileName("-LICENSE.txt").replace("-Regular", "").replace("-Bold", ""));
  }

  // ---- single letters of the font

  const glyphOf = (ch) => (model && model.byChar[ch.codePointAt(0)] !== undefined ? model.glyphs[model.byChar[ch.codePointAt(0)]].name : null);

  function drawOutlineEditor() {
    document.querySelectorAll("#letters button").forEach((b) => {
      const g = glyphOf(charOf(b.dataset.name));
      b.classList.toggle("on", b.dataset.name === current);
      const ed = !!(g && (ol.letters[g] || ol.points[g] || ol.parts[g]));
      b.classList.toggle("edited", ed);
      b.classList.toggle("hand", ed);
      b.disabled = !g;
    });
    const box = $("ol-letter");
    const ch = charOf(current);
    const g = glyphOf(ch);
    if (!g) { box.textContent = model ? "האות הזו לא נמצאת בגופן." : ""; $("ol-svg").textContent = ""; return; }
    const L = ol.letters[g] || {};
    if (box.dataset.for !== g) {
      box.dataset.for = g;
      box.innerHTML = LETTER_KEYS.map((k) => `<div class="slider"><label class="lbl" for="l-${k.key}"><span>${k.label}</span><span class="val" id="lv-${k.key}"></span></label>
        <input type="range" id="l-${k.key}" min="${k.min}" max="${k.max}" step="0.01"></div>`).join("");
      for (const k of LETTER_KEYS) {
        $("l-" + k.key).addEventListener("input", (ev) => {
          const v = Number(ev.target.value);
          const e = (ol.letters[g] = ol.letters[g] || {});
          if (Math.abs(v - k.base) < 0.005) delete e[k.key];
          else e[k.key] = v;
          if (!Object.keys(e).length) delete ol.letters[g];
          changed();
        });
        $("l-" + k.key).addEventListener("pointerdown", olPush);
      }
    }
    for (const k of LETTER_KEYS) {
      const v = L[k.key] !== undefined ? L[k.key] : k.base;
      $("l-" + k.key).value = v;
      $("lv-" + k.key).textContent = k.fmt(v);
    }
    drawOutlineSVG();
    drawBorrow();
    // the letter among others, in the preview font
    const words = ($("ed-words").value || "").trim();
    const line = $("ol-line");
    line.textContent = "";
    for (const part of [`הה${ch}הה וו${ch}וו `, words]) {
      for (const c of part) {
        if (c === ch) {
          const sp = document.createElement("span");
          sp.className = "cur";
          sp.textContent = c;
          line.appendChild(sp);
        } else line.appendChild(document.createTextNode(c));
      }
    }
  }

  // ---- dragging points of a letter of an existing font, cutting areas, taking parts

  const olSel = new Set();        // selected points ("contour.segment", ".a", ".b")
  let selPart = -1, olDrag = null, olTool = "move", olView = null;
  const olStack = [];             // undo: the hand edits before each change
  const borrowModels = {};        // fonts parts are taken from, by library id
  let borrow = { id: null, letter: null, rect: null, drag: null };

  function olPush() {
    olStack.push(JSON.stringify({ letters: ol.letters, points: ol.points, parts: ol.parts }));
    if (olStack.length > 80) olStack.shift();
  }

  function olUndoLast() {
    if (!olStack.length) return;
    const u = JSON.parse(olStack.pop());
    ol.letters = u.letters; ol.points = u.points; ol.parts = u.parts;
    olSel.clear(); selPart = -1;
    changed();
  }

  const curGlyph = () => {
    const ch = charOf(current);
    const i = model && model.byChar[ch.codePointAt(0)];
    return i === undefined || i === null ? -1 : i;
  };

  function svgPoint(svg, ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const q = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [q.x, -q.y];
  }

  function pathOf(contours) {
    let d = "";
    for (const c of contours) {
      if (!c.length) continue;
      d += `M${c[0][0][0]} ${-c[0][0][1]}`;
      for (const s of c) d += `C${s[1][0]} ${-s[1][1]} ${s[2][0]} ${-s[2][1]} ${s[3][0]} ${-s[3][1]}`;
      d += "Z";
    }
    return d;
  }

  function polyPath(polys) {
    return polys.map((p) => "M" + p.map((q) => q[0] + " " + -q[1]).join("L") + "Z").join("");
  }

  function insidePoly(polys, x, y) {
    let inside = false;
    for (const p of polys) {
      for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
        if ((p[i][1] > y) !== (p[j][1] > y) && x < ((p[j][0] - p[i][0]) * (y - p[i][1])) / (p[j][1] - p[i][1]) + p[i][0]) inside = !inside;
      }
    }
    return inside;
  }

  function drawOutlineSVG() {
    const svg = $("ol-svg");
    const gi = curGlyph();
    if (!model || gi < 0) { svg.textContent = ""; return; }
    const gname = model.glyphs[gi].name;
    const v = FontMaker.Outline.editView(model, ol, gi);
    olView = v;
    const mv = v.move;
    const H = model.H, upm = model.upm;
    // guides: the line, the top of the letters, and how far letters go below and above
    const qof = model.byChar[0x5e7], lamed = model.byChar[0x5dc];
    const bbQ = qof !== undefined && FontMaker.Outline.bbox(model.glyphs[qof].contours);
    const bbL = lamed !== undefined && FontMaker.Outline.bbox(model.glyphs[lamed].contours);
    const lines = [[0, "main"], [H, "main"], [bbQ ? bbQ.y0 : -H * 0.4, ""], [bbL ? bbL.y1 : H * 1.4, ""]].map(([y, c]) => [mv([0, y])[1], c]);
    let top = Math.max(...lines.map((l) => l[0])) + upm * 0.08, bottom = Math.min(...lines.map((l) => l[0])) - upm * 0.08;
    let lo = 0, hi = v.t.advance || H;
    for (const p of v.points) { const q = mv([p.x, p.y]); lo = Math.min(lo, q[0]); hi = Math.max(hi, q[0]); top = Math.max(top, q[1] + 40); bottom = Math.min(bottom, q[1] - 40); }
    let w = Math.max(hi - lo, H * 1.2) + upm * 0.16, x0 = (lo + hi) / 2 - w / 2;
    if (olDrag && olDrag.view) [x0, top, w, bottom] = olDrag.view;
    svg.setAttribute("viewBox", `${x0} ${-top} ${w} ${top - bottom}`);
    svg.textContent = "";
    const upp = (top - bottom) / (svg.clientHeight || 440);
    v.upp = upp;
    v.view = [x0, top, w, bottom];
    v.snapY = lines.map((l) => l[0]);
    for (const [y, c] of lines) el("line", { x1: x0, x2: x0 + w, y1: -y, y2: -y, class: "guide " + c }, svg);
    el("line", { x1: 0, x2: 0, y1: -top, y2: -bottom, class: "guide" }, svg);
    if (v.t.advance) el("line", { x1: v.t.advance, x2: v.t.advance, y1: -top, y2: -bottom, class: "guide" }, svg);
    el("path", { d: pathOf(v.final), class: "ink", "fill-rule": "nonzero" }, svg);
    // the parts taken from other letters, and the areas cut away
    const parts = ol.parts[gname] || [];
    parts.forEach((p, i) => {
      if (p.type === "add") {
        el("path", { d: polyPath(v.parts[i].map((poly) => poly.map(mv))), class: "piece" + (i === selPart ? " sel" : ""), "fill-rule": "nonzero" }, svg);
      } else {
        const [a, b, c, d] = p.rect;
        const q = [[a, b], [c, b], [c, d], [a, d]].map(mv);
        el("path", { d: "M" + q.map((z) => z[0] + " " + -z[1]).join("L") + "Z", class: "cutzone" + (i === selPart ? " sel" : "") }, svg);
      }
    });
    el("path", { d: pathOf(v.edited.map((c) => c.map((s) => s.map(mv)))), class: "line" }, svg);
    if (olDrag && olDrag.snapped) {
      const [sx, sy] = olDrag.snapped;
      if (sy !== null) el("line", { x1: x0, x2: x0 + w, y1: -sy, y2: -sy, class: "snap" }, svg);
      if (sx !== null) el("line", { x1: sx, x2: sx, y1: -top, y2: -bottom, class: "snap" }, svg);
    }
    for (const p of v.points) {
      if (p.on) continue;
      const a = mv(p.to), b = mv([p.x, p.y]);
      el("line", { x1: a[0], y1: -a[1], x2: b[0], y2: -b[1], class: "arm" }, svg);
    }
    for (const p of v.points) {
      const q = mv([p.x, p.y]);
      const sel = olSel.has(p.id) ? " sel" : "";
      if (p.on) el("circle", { cx: q[0], cy: -q[1], r: 5 * upp, class: "pt" + sel }, svg);
      else el("rect", { x: q[0] - 3.5 * upp, y: -q[1] - 3.5 * upp, width: 7 * upp, height: 7 * upp, class: "pt off" + sel }, svg);
    }
    if (olDrag && olDrag.band) {
      const [a, b] = olDrag.band;
      el("rect", { x: Math.min(a[0], b[0]), y: -Math.max(a[1], b[1]), width: Math.abs(a[0] - b[0]), height: Math.abs(a[1] - b[1]), class: "band" + (olDrag.kind === "cut" ? " cut" : "") }, svg);
    }
    // the controls of the selected part
    const ctl = $("ol-part-ctl");
    const sp = parts[selPart];
    ctl.classList.toggle("hidden", !sp);
    if (sp) {
      $("ol-part-s").disabled = sp.type !== "add";
      $("ol-part-s").value = sp.s || 1;
      $("ol-part-v").textContent = sp.type === "add" ? Math.round((sp.s || 1) * 100) + "%" : "אזור מחוק";
    }
    $("ol-hint").textContent = olTool === "cut" ? "גוררים מלבן על האזור שרוצים למחוק מהאות." :
      olSel.size ? `${olSel.size} נקודות מסומנות — גוררים אחת מהן כדי להזיז את כולן.` :
      sp ? "החלק מסומן: גוררים אותו כדי להזיז, משנים את הגודל למטה." : "לוחצים על נקודה וגוררים, או גוררים מלבן כדי לסמן כמה נקודות.";
  }

  function olPick(x, y) {
    const v = olView;
    let best = null, bd = Infinity;
    for (const p of v.points) {
      const q = v.move([p.x, p.y]);
      const d = Math.hypot(q[0] - x, q[1] - y) + (p.on ? 0 : 3 * v.upp);
      if (d < bd) { bd = d; best = p; }
    }
    return bd < 12 * v.upp ? best : null;
  }

  function olPartAt(x, y) {
    const gname = model.glyphs[curGlyph()].name;
    const parts = ol.parts[gname] || [];
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      if (p.type === "add" && insidePoly(olView.parts[i].map((poly) => poly.map(olView.move)), x, y)) return i;
      if (p.type === "cut") {
        const [a, b, c, d] = p.rect;
        if (insidePoly([[[a, b], [c, b], [c, d], [a, d]].map(olView.move)], x, y)) return i;
      }
    }
    return -1;
  }

  function olDown(ev) {
    if (!olView) return;
    const svg = $("ol-svg");
    svg.focus();
    const [x, y] = svgPoint(svg, ev);
    const gname = model.glyphs[curGlyph()].name;
    svg.setPointerCapture(ev.pointerId);
    if (olTool === "cut") {
      olDrag = { kind: "cut", band: [[x, y], [x, y]], view: olView.view };
      return;
    }
    const p = olPick(x, y);
    if (p) {
      if (ev.shiftKey) { if (olSel.has(p.id)) olSel.delete(p.id); else olSel.add(p.id); }
      else if (!olSel.has(p.id)) { olSel.clear(); olSel.add(p.id); }
      selPart = -1;
      olPush();
      const ed = (ol.points[gname] = ol.points[gname] || {});
      const ids = [...olSel];
      olDrag = {
        kind: "points", from: [x, y], ids, base: ids.map((id) => (ed[id] || [0, 0]).slice()),
        p0: olView.move([p.x, p.y]), view: olView.view, snapped: null,
        others: olView.points.filter((q) => q.on && !olSel.has(q.id)).map((q) => olView.move([q.x, q.y])[0]),
      };
      drawOutlineSVG();
      return;
    }
    const pi = olPartAt(x, y);
    if (pi >= 0) {
      selPart = pi;
      olSel.clear();
      const part = ol.parts[gname][pi];
      olPush();
      olDrag = { kind: "part", from: [x, y], base: [part.dx || 0, part.dy || 0], view: olView.view };
      drawOutlineSVG();
      return;
    }
    if (!ev.shiftKey) olSel.clear();
    selPart = -1;
    olDrag = { kind: "band", band: [[x, y], [x, y]], view: olView.view };
    drawOutlineSVG();
  }

  function olMove(ev) {
    if (!olDrag) return;
    const svg = $("ol-svg");
    const [x, y] = svgPoint(svg, ev);
    const gname = model.glyphs[curGlyph()].name;
    if (olDrag.band) {
      olDrag.band[1] = [x, y];
    } else {
      let Dx = x - olDrag.from[0], Dy = y - olDrag.from[1];
      if (ev.shiftKey) { if (Math.abs(Dx) > Math.abs(Dy)) Dy = 0; else Dx = 0; }
      let sx = null, sy = null;
      if (olDrag.kind === "points" && $("ol-snap").checked) {
        const near = 8 * olView.upp;
        for (const ly of olView.snapY) if (Math.abs(olDrag.p0[1] + Dy - ly) < near) { Dy = ly - olDrag.p0[1]; sy = ly; break; }
        for (const lx of olDrag.others) if (Math.abs(olDrag.p0[0] + Dx - lx) < near) { Dx = lx - olDrag.p0[0]; sx = lx; break; }
      }
      olDrag.snapped = [sx, sy];
      const [dx, dy] = olView.unmove(Dx, Dy);
      if (olDrag.kind === "points") {
        const ed = ol.points[gname];
        olDrag.ids.forEach((id, i) => { ed[id] = [Math.round(olDrag.base[i][0] + dx), Math.round(olDrag.base[i][1] + dy)]; });
      } else if (olDrag.kind === "part") {
        const part = ol.parts[gname][selPart];
        part.dx = Math.round(olDrag.base[0] + dx);
        part.dy = Math.round(olDrag.base[1] + dy);
      }
    }
    if (!olDrag.frame) olDrag.frame = requestAnimationFrame(() => { if (olDrag) olDrag.frame = 0; drawOutlineSVG(); });
  }

  function olUp() {
    if (!olDrag) return;
    const d = olDrag;
    olDrag = null;
    const gname = model.glyphs[curGlyph()].name;
    if (d.kind === "band") {
      const [a, b] = d.band;
      const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
      for (const p of olView.points) {
        const q = olView.move([p.x, p.y]);
        if (q[0] >= x0 && q[0] <= x1 && q[1] >= y0 && q[1] <= y1) olSel.add(p.id);
      }
      drawOutlineSVG();
      return;
    }
    if (d.kind === "cut") {
      const [a, b] = d.band;
      if (Math.abs(a[0] - b[0]) < 6 * olView.upp || Math.abs(a[1] - b[1]) < 6 * olView.upp) { drawOutlineSVG(); return; }
      // the corners in the font before its changes
      const t = olView.t;
      const back = (q) => { const yy = (q[1] - t.dy) / t.sy; return [(q[0] - t.dx - q[1] * t.k) / t.sx, yy]; };
      const cs = [[a[0], a[1]], [b[0], a[1]], [b[0], b[1]], [a[0], b[1]]].map(back);
      const rect = [Math.min(...cs.map((c) => c[0])), Math.min(...cs.map((c) => c[1])), Math.max(...cs.map((c) => c[0])), Math.max(...cs.map((c) => c[1]))].map(Math.round);
      olPush();
      (ol.parts[gname] = ol.parts[gname] || []).push({ type: "cut", rect });
      selPart = ol.parts[gname].length - 1;
      changed();
      return;
    }
    if (d.kind === "points") {
      const ed = ol.points[gname];
      for (const k in ed) if (!ed[k][0] && !ed[k][1]) delete ed[k];
      if (!Object.keys(ed).length) delete ol.points[gname];
    }
    changed();
  }

  function olKey(ev) {
    if (!olView || mode !== "outline") return;
    const gname = model.glyphs[curGlyph()].name;
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") { ev.preventDefault(); olUndoLast(); return; }
    if ((ev.key === "Delete" || ev.key === "Backspace") && selPart >= 0) {
      ev.preventDefault();
      olPush();
      ol.parts[gname].splice(selPart, 1);
      if (!ol.parts[gname].length) delete ol.parts[gname];
      selPart = -1;
      changed();
      return;
    }
    if (ev.key === "Escape") { olSel.clear(); selPart = -1; drawOutlineSVG(); return; }
    const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
    if (arrows[ev.key] && (olSel.size || selPart >= 0)) {
      ev.preventDefault();
      const step = (ev.shiftKey ? 20 : 4) * model.upm / 1000;
      const [dx, dy] = olView.unmove(arrows[ev.key][0] * step, arrows[ev.key][1] * step);
      olPush();
      if (selPart >= 0) {
        const p = ol.parts[gname][selPart];
        if (p.type === "add") { p.dx = Math.round((p.dx || 0) + dx); p.dy = Math.round((p.dy || 0) + dy); }
      } else {
        const ed = (ol.points[gname] = ol.points[gname] || {});
        for (const id of olSel) { const e = ed[id] || [0, 0]; ed[id] = [Math.round(e[0] + dx), Math.round(e[1] + dy)]; }
      }
      changed();
    }
  }

  // ---- the letter parts are taken from

  async function borrowModel(id) {
    if (id === "self") return model;
    if (!borrowModels[id]) {
      const f = FontMaker.library.find((x) => x.id === id);
      borrowModels[id] = FontMaker.Outline.load(await FontMaker.libraryFile(f.file), { library: f });
    }
    return borrowModels[id];
  }

  function buildBorrow() {
    const fs = $("bor-font");
    const o0 = document.createElement("option");
    o0.value = "self";
    o0.textContent = "הגופן שאני עורך (אות אחרת)";
    fs.appendChild(o0);
    for (const f of FontMaker.library) {
      const o = document.createElement("option");
      o.value = f.id;
      o.textContent = f.name;
      fs.appendChild(o);
    }
    fs.value = "notoserif";
    const ls = $("bor-letter");
    for (const ch of "אבגדהוזחטיכךלמםנןסעפףצץקרשת") {
      const o = document.createElement("option");
      o.value = ch;
      o.textContent = ch;
      ls.appendChild(o);
    }
    fs.addEventListener("change", () => { borrow.rect = null; drawBorrow(); });
    ls.addEventListener("change", () => { borrow.rect = null; borrow.letterSet = true; drawBorrow(); });
    const svg = $("bor-svg");
    svg.addEventListener("pointerdown", (ev) => {
      if (!borrow.view) return;
      svg.setPointerCapture(ev.pointerId);
      const p = svgPoint(svg, ev);
      borrow.drag = [p, p];
      drawBorrowRect();
    });
    svg.addEventListener("pointermove", (ev) => {
      if (!borrow.drag) return;
      borrow.drag[1] = svgPoint(svg, ev);
      drawBorrowRect();
    });
    const up = () => {
      if (!borrow.drag) return;
      const [a, b] = borrow.drag;
      borrow.drag = null;
      const k = borrow.view.k;
      borrow.rect = Math.abs(a[0] - b[0]) > 4 && Math.abs(a[1] - b[1]) > 4 ?
        [Math.min(a[0], b[0]) / k, Math.min(a[1], b[1]) / k, Math.max(a[0], b[0]) / k, Math.max(a[1], b[1]) / k] : null;
      drawBorrowRect();
    };
    svg.addEventListener("pointerup", up);
    svg.addEventListener("pointercancel", up);
    $("bor-add").addEventListener("click", addBorrowed);
  }

  async function drawBorrow() {
    if (!model) return;
    const svg = $("bor-svg");
    if (!borrow.letterSet) $("bor-letter").value = charOf(current) || "א";
    const id = $("bor-font").value, ch = $("bor-letter").value;
    let bm;
    try { bm = await borrowModel(id); } catch (e) { svg.textContent = ""; return; }
    const gi = bm.byChar[ch.codePointAt(0)];
    if (gi === undefined) { svg.textContent = ""; borrow.view = null; return; }
    // shown at the size of the letters of my font
    const k = model.H / bm.H;
    const contours = bm.glyphs[gi].contours.map((c) => c.map((s) => s.map((p) => [p[0] * k, p[1] * k])));
    const bb = FontMaker.Outline.bbox(contours) || { x0: 0, x1: model.H, y0: 0, y1: model.H };
    const pad = model.H * 0.15;
    const top = Math.max(bb.y1, model.H) + pad, bottom = Math.min(bb.y0, 0) - pad;
    const x0 = bb.x0 - pad, w = Math.max(bb.x1 - bb.x0 + 2 * pad, (top - bottom) * 1.2);
    svg.setAttribute("viewBox", `${x0 - (w - (bb.x1 - bb.x0 + 2 * pad)) / 2} ${-top} ${w} ${top - bottom}`);
    borrow.view = { k, gi, bm, contours };
    svg.textContent = "";
    el("line", { x1: -10000, x2: 10000, y1: 0, y2: 0, class: "guide" }, svg);
    el("path", { d: pathOf(contours), class: "ink", "fill-rule": "nonzero" }, svg);
    borrow.rectEl = el("rect", { class: "band hidden" }, svg);
    drawBorrowRect();
  }

  function drawBorrowRect() {
    const r = borrow.rectEl;
    if (!r) return;
    const k = borrow.view ? borrow.view.k : 1;
    let a, b;
    if (borrow.drag) [a, b] = borrow.drag;
    else if (borrow.rect) { a = [borrow.rect[0] * k, borrow.rect[1] * k]; b = [borrow.rect[2] * k, borrow.rect[3] * k]; }
    r.classList.toggle("hidden", !a);
    $("bor-add").disabled = !borrow.rect;
    if (!a) return;
    r.setAttribute("x", Math.min(a[0], b[0]));
    r.setAttribute("y", -Math.max(a[1], b[1]));
    r.setAttribute("width", Math.abs(a[0] - b[0]));
    r.setAttribute("height", Math.abs(a[1] - b[1]));
  }

  function addBorrowed() {
    const gi = curGlyph();
    if (!borrow.rect || !borrow.view || gi < 0) return;
    const { bm, k } = borrow.view;
    const src = FontMaker.Outline.editedContours(bm, bm === model ? ol : {}, borrow.view.gi, false);
    let polys = FontMaker.Outline.cutOut(src, borrow.rect);
    if (!polys.length) { $("ol-hint").textContent = "במלבן שסימנת אין חלק מהאות. סמן מלבן שעובר על הקווים."; return; }
    polys = polys.map((p) => p.map((q) => [Math.round(q[0] * k), Math.round(q[1] * k)]));
    const gname = model.glyphs[gi].name;
    olPush();
    (ol.parts[gname] = ol.parts[gname] || []).push({ type: "add", polys, dx: 0, dy: 0, s: 1 });
    selPart = ol.parts[gname].length - 1;
    olSel.clear();
    changed();
    $("ol-svg").scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function buildOutlineEditor() {
    const svg = $("ol-svg");
    svg.addEventListener("pointerdown", olDown);
    svg.addEventListener("pointermove", olMove);
    svg.addEventListener("pointerup", olUp);
    svg.addEventListener("pointercancel", olUp);
    svg.addEventListener("keydown", olKey);
    document.querySelectorAll("input[name=oltool]").forEach((r) => r.addEventListener("change", () => {
      olTool = r.value;
      drawOutlineSVG();
    }));
    $("ol-part-s").addEventListener("pointerdown", olPush);
    $("ol-part-s").addEventListener("input", () => {
      const gname = model.glyphs[curGlyph()].name;
      const p = (ol.parts[gname] || [])[selPart];
      if (p && p.type === "add") { p.s = Number($("ol-part-s").value); changed(); }
    });
    $("ol-part-del").addEventListener("click", () => {
      const gname = model.glyphs[curGlyph()].name;
      if (!ol.parts[gname] || selPart < 0) return;
      olPush();
      ol.parts[gname].splice(selPart, 1);
      if (!ol.parts[gname].length) delete ol.parts[gname];
      selPart = -1;
      changed();
    });
    buildBorrow();
  }

  // ---------------------------------------------------------------- asking in words

  const KEY_STORE = "font-maker-ai-key";
  let aiHistory = [];

  function aiContext() {
    if (mode === "outline") {
      const lettersNow = Object.entries(ol.letters).map(([g, v]) => {
        const i = model ? model.glyphs.findIndex((x) => x.name === g) : -1;
        const ch = i >= 0 && model.glyphs[i].unicodes.length ? String.fromCodePoint(model.glyphs[i].unicodes[0]) : g;
        return ch + " " + JSON.stringify(v);
      }).join("; ");
      return {
        about: `The font is based on the existing font "${model ? model.names.family : ""}". The settings change it; at their neutral values it is the original font.`,
        keys: OUTLINE_SLIDERS.map((k) => ({ key: k.key, label: k.label, fmt: k.fmt, min: k.min, max: k.max, step: k.aiStep, value: ol[k.key], neutral: FontMaker.Outline.SETTINGS[k.key], about: k.about })),
        letterKeys: LETTER_KEYS.map((k) => ({ key: k.key, label: k.label, fmt: k.fmt, min: k.min, max: k.max, step: k.step, base: k.base, about: k.about })),
        fonts: FontMaker.library.map((f) => ({ id: f.id, name: f.name, family: f.file.replace(/[-.].*$/, "") })),
        letterValue: (L, key) => {
          const g = glyphOf(L);
          const k = LETTER_KEYS.find((x) => x.key === key);
          return g && ol.letters[g] && ol.letters[g][key] !== undefined ? ol.letters[g][key] : k.base;
        },
        letterNow: () => lettersNow,
      };
    }
    return {
      about: "The letters are drawn by the program from a skeleton with a broad pen; the settings shape every letter.",
      keys: SLIDERS.map((k) => ({ key: k.key, label: k.label, fmt: k.fmt, min: k.min, max: k.max, step: (k.max - k.min) / 6, value: prm[k.key], neutral: D[k.key], about: k.help || "" })),
      letterKeys: null,
    };
  }

  function aiApply(res) {
    const t = target();
    for (const c of res.settings) t[c.key] = c.value;
    if (mode === "outline") {
      for (const c of res.letters) {
        const g = glyphOf(c.letter);
        if (!g) continue;
        const k = LETTER_KEYS.find((x) => x.key === c.key);
        const e = (ol.letters[g] = ol.letters[g] || {});
        if (Math.abs(c.value - k.base) < 0.005) delete e[c.key];
        else e[c.key] = c.value;
        if (!Object.keys(e).length) delete ol.letters[g];
      }
    }
    markPreset(null);
    changed();
  }

  // What was changed, in words.
  function describeChanges(res) {
    const parts = [];
    for (const c of res.settings) {
      const k = sliders().find((x) => x.key === c.key);
      if (k) parts.push(k.label + ": " + k.fmt(c.value));
    }
    // one change of several letters is said once: "ך ן ף — אורך הזנב: 115%"
    const same = new Map();
    for (const c of res.letters) {
      const k = LETTER_KEYS.find((x) => x.key === c.key);
      if (!k) continue;
      const t = k.label + ": " + k.fmt(c.value);
      same.set(t, (same.get(t) || []).concat(c.letter));
    }
    for (const [t, ls] of same) parts.push(ls.join(" ") + " — " + t);
    return parts.join(" · ");
  }

  async function aiGo() {
    const text = $("ai-text").value.trim();
    if (!text) return;
    if (mode === "outline" && !model) return;
    const key = $("ai-key").value.trim();
    try {
      if ($("ai-remember").checked && key) localStorage.setItem(KEY_STORE, key);
      else localStorage.removeItem(KEY_STORE);
    } catch (e) { /* ignore */ }
    const ctx = aiContext();
    $("ai-go").disabled = true;
    $("ai-msg").textContent = key ? "Claude חושב…" : "";
    const before = { ol: JSON.stringify(ol), prm: JSON.stringify(prm) };
    let res;
    try {
      res = key ? await FontMaker.AI.ask(text, ctx, key, aiHistory) : FontMaker.AI.simple(text, ctx);
    } catch (e) {
      const m = String((e && e.message) || e);
      $("ai-msg").textContent = /401|authentication|api.key|x-api-key/i.test(m) ? "המפתח לא התקבל. בדוק שהעתקת אותו נכון." :
        /429|rate/i.test(m) ? "יותר מדי בקשות כרגע. נסה שוב בעוד רגע." :
        /fetch|network|Failed/i.test(m) ? "אין חיבור לאינטרנט (בלי חיבור אפשר להשתמש בבקשות פשוטות, בלי מפתח)." : "שגיאה: " + m;
      $("ai-go").disabled = false;
      return;
    }
    $("ai-go").disabled = false;
    if (res.undo) {
      const last = $("ai-log").querySelector("li:not(.undone) button");
      if (last) { last.click(); $("ai-msg").textContent = "ביטלתי את השינוי האחרון."; }
      else $("ai-msg").textContent = "אין שינוי לבטל.";
      $("ai-text").value = "";
      return;
    }
    if (res.font && mode === "outline") await chooseFont(res.font.id);
    if (!res.settings.length && !res.letters.length && !res.font) {
      $("ai-msg").textContent = res.explanation || "לא היה מה לשנות.";
      return;
    }
    olUndo.push(before);
    aiApply(res);
    const done = (res.font ? "גופן: " + res.font.name + (res.settings.length || res.letters.length ? " · " : "") : "") + describeChanges(res);
    $("ai-msg").textContent = "";
    aiHistory.push({ text, explanation: res.explanation || done });
    const li = document.createElement("li");
    li.innerHTML = `<b></b><span></span><button type="button" class="btn ghost small">↶ ביטול</button>`;
    li.querySelector("b").textContent = text;
    li.querySelector("span").textContent = key && res.explanation ? res.explanation + " (" + done + ")" : done;
    li.querySelector("button").addEventListener("click", () => {
      ol = sanitizeOutline(JSON.parse(before.ol));
      prm = sanitize(JSON.parse(before.prm));
      li.classList.add("undone");
      li.querySelector("button").remove();
      changed();
    });
    $("ai-log").prepend(li);
    $("ai-text").value = "";
  }

  function buildAI() {
    try {
      const k = localStorage.getItem(KEY_STORE);
      if (k) $("ai-key").value = k;
    } catch (e) { /* ignore */ }
    $("ai-go").addEventListener("click", aiGo);
    $("ai-text").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); aiGo(); }
    });
    const sum = () => { $("ai-key-sum").textContent = $("ai-key").value.trim() ? "✓ Claude מחובר (מפתח API)" : "רוצה שגם בקשות מסובכות יובנו? Claude (לא חובה)"; };
    $("ai-key").addEventListener("input", sum);
    sum();
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

  // A name of the original font may not be kept (the OFL asks for a new one).
  function nameProblem() {
    if (!model) return "";
    const norm = (x) => String(x || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const mine = norm($("family").value), orig = norm(model.names.family);
    if (!mine) return "צריך לתת לגופן שם באותיות אנגליות.";
    if (orig && (mine.includes(orig) || orig.includes(mine))) return `צריך שם חדש, שונה מהשם של הגופן המקורי (${model.names.family}).`;
    return "";
  }

  function download() {
    if (mode === "outline") return downloadOutline();
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

  function downloadOutline() {
    if (!model) return;
    const problem = nameProblem();
    if (problem) { $("status").textContent = problem; $("family").focus(); return; }
    const lic = licenseOf();
    if (!(lic && lic.kind) && !$("rights").checked) {
      $("status").textContent = "סמן שיש לך זכות לשנות את הגופן הזה.";
      return;
    }
    const btn = $("download");
    btn.disabled = true;
    $("status").textContent = "בונה את הגופן… (זה יכול לקחת חצי דקה)";
    setTimeout(() => {
      try {
        const buf = FontMaker.Outline.build(model, ol, { family: $("family").value, style: style(), fit: true });
        save(new Blob([buf], { type: "font/otf" }), fileName(".otf"));
        $("status").textContent = "הגופן ירד: " + fileName(".otf") + (lic && lic.kind ? ". כשמשתפים אותו, מצרפים את קובץ הרישיון." : "");
      } catch (e) {
        $("status").textContent = "לא הצלחתי לבנות את הגופן: " + e.message;
      }
      btn.disabled = false;
    }, 30);
  }

  function saveSettings() {
    const data = { app: "font-maker", version: 2, family: $("family").value, style: style(), mode, src: src.id ? src : null, ol, prm };
    save(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), fileName(".json"));
  }

  function loadSettings(ev) {
    const file = ev.target.files[0];
    if (!file) return;
    file.text().then((txt) => {
      const data = JSON.parse(txt);
      prm = sanitize(data.prm || data);
      if (data.ol) ol = sanitizeOutline(data.ol);
      if (data.mode === "outline" || data.mode === "draw") {
        if (data.src && data.src.id) src = { id: data.src.id };
        if (data.mode === "outline" && data.src && data.src.id && data.src.id !== (model && model.meta.library && model.meta.library.id)) {
          mode = "outline";
          chooseFont(data.src.id);
        }
        setMode(data.mode);
      }
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
  buildBases();
  buildLibrary();
  buildAI();
  buildOutlineEditor();
  load();
  buildEditor();
  markPreset(SLIDERS.every((s) => prm[s.key] === D[s.key]) ? 0 : null);
  setMode(mode);
  showLibraryFonts();
})();
