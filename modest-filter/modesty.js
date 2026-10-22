// לוגיקת הצניעות: זיהוי עור חשוף לפי צבע הפנים של כל אדם, ציור "בגדים" מעליו,
// וזיהוי קרבה (נשיקה / חיבוק). פונקציות טהורות - בלי תלות במודלים.

export const L = {
  nose: 0, lEye: 2, rEye: 5, lEar: 7, rEar: 8, mouthL: 9, mouthR: 10,
  lSh: 11, rSh: 12, lEl: 13, rEl: 14, lWr: 15, rWr: 16,
  lHip: 23, rHip: 24, lKnee: 25, rKnee: 26, lAnk: 27, rAnk: 28
};

const lerp = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const mid = (a, b) => lerp(a, b, 0.5);
const vis = (p, min = 0.45) => p && (p.visibility ?? 1) >= min && p.x > -0.05 && p.x < 1.05 && p.y > -0.05 && p.y < 1.1;

function ycc(r, g, b) {
  return {
    y: 0.299 * r + 0.587 * g + 0.114 * b,
    cb: 128 - 0.168736 * r - 0.331264 * g + 0.5 * b,
    cr: 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
  };
}

// ממוצע צבע סביב נקודה (קואורדינטות 0..1)
export function sample(img, p, rad = 2) {
  const { width: w, height: h, data } = img;
  const cx = Math.round(p.x * w), cy = Math.round(p.y * h);
  let r = 0, g = 0, b = 0, n = 0;
  for (let y = cy - rad; y <= cy + rad; y++) {
    if (y < 0 || y >= h) continue;
    for (let x = cx - rad; x <= cx + rad; x++) {
      if (x < 0 || x >= w) continue;
      const i = (y * w + x) * 4;
      r += data[i]; g += data[i + 1]; b += data[i + 2]; n++;
    }
  }
  return n ? [r / n, g / n, b / n] : null;
}

// טווח עור כללי (כל גווני העור) במרחב YCbCr
function genericSkin(c) {
  return c.cb > 75 && c.cb < 135 && c.cr > 131 && c.cr < 182 && c.y > 35;
}

// צבע עור הייחוס של אדם: לחיים, מצח וסנטר
export function faceTone(img, lm) {
  const n = lm[L.nose];
  if (!vis(n, 0.5)) return null;
  const pts = [];
  for (const ear of [lm[L.lEar], lm[L.rEar]]) if (vis(ear, 0.3)) pts.push(lerp(n, ear, 0.38));
  const eyes = [lm[L.lEye], lm[L.rEye]].filter((e) => vis(e, 0.4));
  if (eyes.length === 2) pts.push(lerp(mid(eyes[0], eyes[1]), n, 0.5));
  if (vis(lm[L.mouthL], 0.4) && vis(lm[L.mouthR], 0.4)) {
    const m = mid(lm[L.mouthL], lm[L.mouthR]);
    pts.push({ x: m.x + (m.x - n.x) * 0.8, y: m.y + (m.y - n.y) * 0.8 });
  }
  const cs = pts.map((p) => sample(img, p, 2)).filter(Boolean).map((c) => ycc(...c)).filter(genericSkin);
  if (!cs.length) return null;
  const med = (k) => cs.map((c) => c[k]).sort((a, b) => a - b)[cs.length >> 1];
  return { y: med("y"), cb: med("cb"), cr: med("cr") };
}

export function isSkin(rgb, tone) {
  if (!rgb) return false;
  const c = ycc(...rgb);
  if (!genericSkin(c)) return false;
  if (!tone) return true;
  return Math.abs(c.cb - tone.cb) < 13 && Math.abs(c.cr - tone.cr) < 13 && c.y > tone.y * 0.35 && c.y < tone.y * 1.9;
}

function skinFraction(img, pts, tone, rad) {
  if (!pts.length) return 0;
  let s = 0;
  for (const p of pts) if (isSkin(sample(img, p, rad), tone)) s++;
  return s / pts.length;
}

const along = (a, b, ts) => ts.map((t) => lerp(a, b, t));

// לכל אדם: אילו אזורים חשופים (0..1 = שיעור נקודות עור)
export function exposure(img, lm) {
  const tone = faceTone(img, lm);
  const sh = [lm[L.lSh], lm[L.rSh]], hips = [lm[L.lHip], lm[L.rHip]];
  const sw = vis(sh[0]) && vis(sh[1]) ? dist(sh[0], sh[1]) : 0.1;
  const rad = Math.max(1, Math.round(sw * img.width * 0.03));
  const out = { tone: !!tone, arms: [0, 0], legs: [0, 0], neck: 0, torso: 0 };

  [[L.lSh, L.lEl], [L.rSh, L.rEl]].forEach(([s, e], i) => {
    if (vis(lm[s]) && vis(lm[e])) out.arms[i] = skinFraction(img, along(lm[s], lm[e], [0.3, 0.45, 0.6, 0.75, 0.88]), tone, rad);
  });
  [[L.lHip, L.lKnee], [L.rHip, L.rKnee]].forEach(([h, k], i) => {
    if (vis(lm[h]) && vis(lm[k])) {
      const pts = along(lm[h], lm[k], [0.55, 0.7, 0.85, 1.0]);
      if (vis(lm[k + 2], 0.3)) pts.push(lerp(lm[k], lm[k + 2], 0.12));
      out.legs[i] = skinFraction(img, pts, tone, rad);
    }
  });
  if (vis(sh[0]) && vis(sh[1])) {
    const neck = mid(sh[0], sh[1]);
    const down = vis(hips[0], 0.3) && vis(hips[1], 0.3) ? mid(hips[0], hips[1]) : { x: neck.x, y: neck.y + sw * 1.4 };
    out.neck = skinFraction(img, [0.07, 0.13, 0.19, 0.25].flatMap((t) => {
      const c = lerp(neck, down, t);
      return [c, { x: c.x - sw * 0.12, y: c.y }, { x: c.x + sw * 0.12, y: c.y }];
    }), tone, rad);
    out.torso = skinFraction(img, along(neck, down, [0.45, 0.6, 0.75, 0.9]), tone, rad);
  }
  return out;
}

// ---------- מעקב והחלקה בין פריימים ----------

export class Tracker {
  constructor() { this.tracks = []; this.nextId = 1; }

  update(people, now) {
    const used = new Set();
    for (const p of people) {
      const c = center(p.lm);
      let best = null, bd = 0.15;
      for (const t of this.tracks) {
        if (used.has(t)) continue;
        const d = Math.hypot(t.c.x - c.x, t.c.y - c.y);
        if (d < bd) { bd = d; best = t; }
      }
      if (!best) {
        best = { id: this.nextId++, ema: { arms: [0, 0], legs: [0, 0], neck: 0, torso: 0 }, until: {} };
        this.tracks.push(best);
      }
      used.add(best);
      best.c = c;
      best.seen = now;
      const e = p.exp, a = 0.5;
      best.ema.arms = best.ema.arms.map((v, i) => v * (1 - a) + e.arms[i] * a);
      best.ema.legs = best.ema.legs.map((v, i) => v * (1 - a) + e.legs[i] * a);
      best.ema.neck = best.ema.neck * (1 - a) + e.neck * a;
      best.ema.torso = best.ema.torso * (1 - a) + e.torso * a;
      // מספיק פריים אחד חשוף כדי לכסות שנייה שלמה (עדיף לכסות יותר מדי)
      const hit = (k, v) => { if (v >= 0.5) best.until[k] = now + 1200; };
      e.arms.forEach((v, i) => hit("arm" + i, v));
      e.legs.forEach((v, i) => hit("leg" + i, v));
      hit("neck", e.neck);
      hit("torso", e.torso);
      p.cover = {
        arms: [0, 1].map((i) => best.ema.arms[i] > 0.4 || (best.until["arm" + i] || 0) > now),
        legs: [0, 1].map((i) => best.ema.legs[i] > 0.4 || (best.until["leg" + i] || 0) > now),
        neck: best.ema.neck > 0.4 || (best.until.neck || 0) > now,
        torso: best.ema.torso > 0.4 || (best.until.torso || 0) > now
      };
    }
    this.tracks = this.tracks.filter((t) => now - t.seen < 1500);
  }
}

function center(lm) {
  const pts = [lm[L.lSh], lm[L.rSh], lm[L.nose]].filter((p) => vis(p, 0.3));
  if (!pts.length) return { x: lm[0].x, y: lm[0].y };
  return { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length };
}

// ---------- קרבה: נשיקה / חיבוק ----------

export function intimacy(people, faces) {
  // שני פרצופים כמעט נוגעים
  for (let i = 0; i < faces.length; i++) {
    for (let j = i + 1; j < faces.length; j++) {
      const a = faces[i], b = faces[j];
      const d = Math.hypot(a.cx - b.cx, a.cy - b.cy);
      if (d < 1.15 * Math.max(a.w, b.w)) return "kiss";
    }
  }
  for (let i = 0; i < people.length; i++) {
    for (let j = i + 1; j < people.length; j++) {
      const A = people[i].lm, B = people[j].lm;
      const swA = vis(A[L.lSh]) && vis(A[L.rSh]) ? dist(A[L.lSh], A[L.rSh]) : 0;
      const swB = vis(B[L.lSh]) && vis(B[L.rSh]) ? dist(B[L.lSh], B[L.rSh]) : 0;
      const sw = Math.max(swA, swB, 0.05);
      if (vis(A[L.nose], 0.5) && vis(B[L.nose], 0.5) && dist(A[L.nose], B[L.nose]) < sw * 0.45) return "kiss";
      // חיבוק: יד של אחד מונחת על הגב/כתף של השני, והגופים צמודים
      if (swA && swB && dist(mid(A[L.lSh], A[L.rSh]), mid(B[L.lSh], B[L.rSh])) < sw * 0.9) {
        const box = torsoBox(B, sw), box2 = torsoBox(A, sw);
        const inA = [A[L.lWr], A[L.rWr]].some((w) => vis(w, 0.5) && inBox(w, box));
        const inB = [B[L.lWr], B[L.rWr]].some((w) => vis(w, 0.5) && inBox(w, box2));
        if (inA || inB) return "hug";
      }
    }
  }
  return null;
}

function torsoBox(lm, sw) {
  const pts = [lm[L.lSh], lm[L.rSh], lm[L.lHip], lm[L.rHip]].filter((p) => vis(p, 0.3));
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  return { x0: Math.min(...xs) - sw * 0.15, x1: Math.max(...xs) + sw * 0.15, y0: Math.min(...ys) - sw * 0.1, y1: Math.max(...ys) };
}
const inBox = (p, b) => p.x > b.x0 && p.x < b.x1 && p.y > b.y0 && p.y < b.y1;

// ---------- ציור הבגדים ----------

const FALLBACK = [44, 62, 80];

// צבע הבגד: לוקחים את צבע החולצה של האדם (אם הגוף לא חשוף), כדי שהכיסוי ייראה כהמשך של הבגד
export function garmentColor(img, lm) {
  if (!(vis(lm[L.lSh]) && vis(lm[L.rSh]))) return FALLBACK;
  const neck = mid(lm[L.lSh], lm[L.rSh]);
  const hip = vis(lm[L.lHip], 0.3) && vis(lm[L.rHip], 0.3) ? mid(lm[L.lHip], lm[L.rHip]) : { x: neck.x, y: neck.y + 0.2 };
  const tone = faceTone(img, lm);
  const cs = [0.3, 0.42, 0.55].map((t) => sample(img, lerp(neck, hip, t), 3)).filter((c) => c && !isSkin(c, tone));
  if (!cs.length) return FALLBACK;
  return [0, 1, 2].map((k) => cs.reduce((s, c) => s + c[k], 0) / cs.length);
}

// מחזיר רשימת צורות לכיסוי (בפיקסלים של קנבס התצוגה)
export function garmentShapes(lm, cover, W, H) {
  const P = (i) => ({ x: lm[i].x * W, y: lm[i].y * H });
  const shapes = [];
  const ls = P(L.lSh), rs = P(L.rSh);
  const sw = dist(ls, rs) || W * 0.08;

  [[L.lSh, L.lEl, L.lWr], [L.rSh, L.rEl, L.rWr]].forEach(([s, e, w], i) => {
    if (!cover.arms[i] || !vis(lm[s]) || !vis(lm[e])) return;
    const S = P(s), E = P(e);
    const end = lerp(S, E, 1.18); // מעבר למרפק
    const width = Math.max(sw * 0.42, dist(S, E) * 0.42);
    shapes.push({ type: "limb", pts: [lerp(mid(ls, rs), S, 0.75), S, end], width });
  });

  if (cover.neck || cover.torso) {
    const neck = mid(ls, rs);
    const hipsOk = vis(lm[L.lHip], 0.3) && vis(lm[L.rHip], 0.3);
    const lh = hipsOk ? P(L.lHip) : { x: ls.x, y: ls.y + sw * 1.5 };
    const rh = hipsOk ? P(L.rHip) : { x: rs.x, y: rs.y + sw * 1.5 };
    const depth = cover.torso ? 1.05 : 0.38;
    const out = (p, c, k) => ({ x: p.x + (p.x - c.x) * k, y: p.y + (p.y - c.y) * k });
    const nose = vis(lm[L.nose], 0.4) ? P(L.nose) : { x: neck.x, y: neck.y - sw * 0.6 };
    const collar = lerp(neck, nose, 0.28);
    shapes.push({
      type: "poly",
      pts: [
        out(ls, neck, 0.12), lerp(ls, collar, 0.6), collar, lerp(rs, collar, 0.6), out(rs, neck, 0.12),
        out(lerp(rs, rh, depth), mid(rh, lh), 0.15), out(lerp(ls, lh, depth), mid(rh, lh), 0.15)
      ].reverse()
    });
  }

  [[L.lHip, L.lKnee, L.lAnk], [L.rHip, L.rKnee, L.rAnk]].forEach(([h, k, a], i) => {
    if (!cover.legs[i] || !vis(lm[h], 0.3) || !vis(lm[k])) return;
    const Hp = P(h), K = P(k);
    const below = vis(lm[a], 0.3) ? lerp(K, P(a), 0.3) : lerp(Hp, K, 1.3);
    const hw = vis(lm[L.lHip], 0.3) && vis(lm[L.rHip], 0.3) ? dist(P(L.lHip), P(L.rHip)) : sw * 0.7;
    shapes.push({ type: "limb", pts: [Hp, K, below], width: Math.max(hw * 0.75, dist(Hp, K) * 0.38) });
  });
  return shapes;
}

export function drawGarments(ctx, shapes, rgb, style, frame) {
  if (!shapes.length) return;
  ctx.save();
  const path = new Path2D();
  for (const s of shapes) {
    if (s.type === "poly") {
      path.moveTo(s.pts[0].x, s.pts[0].y);
      for (const p of s.pts.slice(1)) path.lineTo(p.x, p.y);
      path.closePath();
    }
  }
  // גפיים: מסלול עבה עם קצוות מעוגלים
  const limbs = shapes.filter((s) => s.type === "limb");
  if (style === "blur") {
    ctx.beginPath();
    ctx.clip(outline(path, limbs));
    ctx.filter = "blur(18px)";
    ctx.drawImage(frame, 0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.filter = "none";
  } else {
    const [r, g, b] = rgb;
    const fill = `rgb(${r | 0},${g | 0},${b | 0})`;
    const dark = `rgb(${(r * 0.72) | 0},${(g * 0.72) | 0},${(b * 0.72) | 0})`;
    ctx.fillStyle = fill;
    ctx.strokeStyle = fill;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.shadowColor = "rgba(0,0,0,0.35)";
    ctx.shadowBlur = 6;
    ctx.fill(path);
    ctx.lineWidth = sw0(shapes);
    ctx.stroke(path); // פינות מעוגלות, שייראה כמו בד ולא כמו מלבן
    for (const s of limbs) {
      ctx.lineWidth = s.width;
      ctx.beginPath();
      ctx.moveTo(s.pts[0].x, s.pts[0].y);
      for (const p of s.pts.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
    // קפלים עדינים לתחושת בד
    ctx.shadowBlur = 0;
    ctx.strokeStyle = dark;
    ctx.globalAlpha = 0.35;
    for (const s of limbs) {
      ctx.lineWidth = Math.max(1, s.width * 0.08);
      ctx.beginPath();
      ctx.moveTo(s.pts[0].x, s.pts[0].y);
      for (const p of s.pts.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
  }
  ctx.restore();
}

const sw0 = (shapes) => Math.max(4, ...shapes.filter((s) => s.type === "limb").map((s) => s.width * 0.35), 12);

function outline(path, limbs) {
  const p = new Path2D(path);
  for (const s of limbs) {
    for (let i = 0; i < s.pts.length - 1; i++) {
      const a = s.pts[i], b = s.pts[i + 1], r = s.width / 2;
      const ang = Math.atan2(b.y - a.y, b.x - a.x), nx = Math.sin(ang) * r, ny = -Math.cos(ang) * r;
      p.moveTo(a.x + nx, a.y + ny); p.lineTo(b.x + nx, b.y + ny); p.lineTo(b.x - nx, b.y - ny); p.lineTo(a.x - nx, a.y - ny); p.closePath();
      p.moveTo(a.x + r, a.y); p.arc(a.x, a.y, r, 0, Math.PI * 2);
      p.moveTo(b.x + r, b.y); p.arc(b.x, b.y, r, 0, Math.PI * 2);
    }
  }
  return p;
}
