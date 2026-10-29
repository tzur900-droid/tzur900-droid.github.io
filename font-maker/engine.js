// Font engine of the font maker: draws every glyph from a few settings and builds an OpenType font.
//
// Each letter is a skeleton (the centre line of its strokes), drawn with a broad pen, the way a
// scribe writes square Hebrew: the pen is a short line, so a stroke is the area the line sweeps.
// Two pens together give the contrast of Hebrew letters: a tall one makes the horizontal strokes
// thick, a short flat one keeps the vertical strokes thin. The sweep of a straight pen along a
// curve is exact with Bezier curves: the curve moved by +half the pen, then back by -half the pen.
//
// Needs opentype.js and paper.js (paper.js joins the overlapping strokes into one outline).

(function (global) {
  "use strict";

  const UPM = 1000;
  const K = 0.5523; // control-point length of a quarter circle

  const DEFAULTS = {
    height: 540,   // height of the letters
    weight: 0.13,  // thickness of the horizontal strokes, part of the height
    contrast: 2.4, // thick strokes / thin strokes
    width: 1.0,    // width of the letters
    round: 0.35,   // roundness of the corners
    serif: 0.7,    // size of the heads (the little wedge at the top left of the letters)
    angle: 0,      // tilt of the pen, degrees
    slant: 0,      // slant of the letters, degrees
    spacing: 1.0,  // space between letters
    descender: 0.42, // length of the final letters below the line, part of the height
    ascender: 0.42,  // height of lamed above the letters, part of the height
    pen: 0,          // roundness of the pen: 0 a flat rectangle, 1 an oval (round ends and joins)
    heel: 0.5,       // length of the heel of bet and mem, beyond the stem
    overhang: 0.5,   // how far the roof of dalet and he reaches past the stem
    headShape: 0.5,  // shape of the head: 0 a square block, 0.5 a wedge, 1 a round drop
    base: "classic", // the set of letter drawings to start from (see addLetterSet)
  };

  // ---------------------------------------------------------------- paths

  // A stroke path: a start point and segments ({L:[x,y]} or {C:[x1,y1,x2,y2,x,y]}).
  class Pth {
    constructor(x, y) {
      this.start = [x, y];
      this.cur = [x, y];
      this.segs = [];
    }
    L(x, y) {
      this.segs.push({ t: "L", p: [x, y] });
      this.cur = [x, y];
      return this;
    }
    C(x1, y1, x2, y2, x, y) {
      this.segs.push({ t: "C", p: [x1, y1, x2, y2, x, y] });
      this.cur = [x, y];
      return this;
    }
    // Quarter curve that leaves horizontally and arrives vertically.
    qh(x, y) {
      const [cx, cy] = this.cur;
      return this.C(cx + (x - cx) * K, cy, x, y - (y - cy) * K, x, y);
    }
    // Quarter curve that leaves vertically and arrives horizontally.
    qv(x, y) {
      const [cx, cy] = this.cur;
      return this.C(cx, cy + (y - cy) * K, x - (x - cx) * K, y, x, y);
    }
    // Rounded corner at (cx, cy); the path then goes on in the direction (dx, dy).
    R(cx, cy, dx, dy, r) {
      const [px, py] = this.cur;
      let ix = cx - px, iy = cy - py;
      const li = Math.hypot(ix, iy) || 1;
      ix /= li; iy /= li;
      const lo = Math.hypot(dx, dy) || 1;
      dx /= lo; dy /= lo;
      r = Math.max(0, Math.min(r, li * 0.95));
      // (a corner with no rounding keeps its curve, of no length, so the points of a letter
      // are always the same ones and changes made by hand stay on the right point)
      const ax = cx - ix * r, ay = cy - iy * r;
      const bx = cx + dx * r, by = cy + dy * r;
      this.L(ax, ay);
      return this.C(ax + ix * r * K, ay + iy * r * K, bx - dx * r * K, by - dy * r * K, bx, by);
    }
    map(f) {
      const p = new Pth(...f(this.start));
      for (const s of this.segs) {
        if (s.t === "L") p.L(...f(s.p));
        else p.C(...f([s.p[0], s.p[1]]), ...f([s.p[2], s.p[3]]), ...f([s.p[4], s.p[5]]));
      }
      return p;
    }
  }

  // Closed shapes are lists of contours; a contour is a list of cubic pieces [p0, p1, p2, p3].
  function lineSeg(a, b) {
    return [a, [a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3],
      [a[0] + (b[0] - a[0]) * 2 / 3, a[1] + (b[1] - a[1]) * 2 / 3], b];
  }

  function polygon(pts) {
    const c = [];
    for (let i = 0; i < pts.length; i++) c.push(lineSeg(pts[i], pts[(i + 1) % pts.length]));
    return c;
  }

  function ellipse(cx, cy, rx, ry) {
    const kx = rx * K, ky = ry * K;
    return [
      [[cx + rx, cy], [cx + rx, cy + ky], [cx + kx, cy + ry], [cx, cy + ry]],
      [[cx, cy + ry], [cx - kx, cy + ry], [cx - rx, cy + ky], [cx - rx, cy]],
      [[cx - rx, cy], [cx - rx, cy - ky], [cx - kx, cy - ry], [cx, cy - ry]],
      [[cx, cy - ry], [cx + kx, cy - ry], [cx + rx, cy - ky], [cx + rx, cy]],
    ];
  }

  function splitCubic(c, t) {
    const lerp = (a, b) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    const ab = lerp(c[0], c[1]), bc = lerp(c[1], c[2]), cd = lerp(c[2], c[3]);
    const abc = lerp(ab, bc), bcd = lerp(bc, cd), m = lerp(abc, bcd);
    return [[c[0], ab, abc, m], [m, bcd, cd, c[3]]];
  }

  function cubicAt(c, t) {
    const u = 1 - t;
    return [
      u * u * u * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t * t * t * c[3][0],
      u * u * u * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t * t * t * c[3][1],
    ];
  }

  function cubicTangent(c, t) {
    const u = 1 - t;
    const d = (i) => 3 * u * u * (c[1][i] - c[0][i]) + 6 * u * t * (c[2][i] - c[1][i]) + 3 * t * t * (c[3][i] - c[2][i]);
    return [d(0), d(1)];
  }

  // The stroke path as cubic pieces.
  function pathCubics(p) {
    const out = [];
    let cur = p.start;
    for (const s of p.segs) {
      if (s.t === "L") {
        if (Math.hypot(s.p[0] - cur[0], s.p[1] - cur[1]) > 0.01) out.push({ line: true, c: lineSeg(cur, s.p) });
        cur = s.p;
      } else {
        const c = [cur, [s.p[0], s.p[1]], [s.p[2], s.p[3]], [s.p[4], s.p[5]]];
        out.push({ line: false, c });
        cur = c[3];
      }
    }
    return out;
  }

  // Area swept by the pen (a straight line of vector n, centred) along the stroke path.
  // Wherever the path runs parallel to the pen the sweep has no width there, so the path is cut
  // into runs on which it crosses the pen always from the same side; each run is a simple shape.
  function sweep(path, n) {
    const ln = Math.hypot(n[0], n[1]);
    if (ln < 0.5) return [];
    const cross = (d) => (d[0] * n[1] - d[1] * n[0]) / ln;
    const pieces = [];
    for (const seg of pathCubics(path)) {
      const c = seg.c;
      if (seg.line) {
        const d = [c[3][0] - c[0][0], c[3][1] - c[0][1]];
        const s = cross(d);
        pieces.push({ c, sign: Math.abs(s) < 0.02 * Math.hypot(d[0], d[1]) + 0.01 ? 0 : Math.sign(s) });
        continue;
      }
      // cross(B'(t), n) = a t^2 + b t + c
      const p = [0, 1, 2, 3].map((i) => cross(c[i]));
      const A = -p[0] + 3 * p[1] - 3 * p[2] + p[3];
      const B = 2 * (p[0] - 2 * p[1] + p[2]);
      const C0 = p[1] - p[0];
      const roots = [];
      if (Math.abs(A) < 1e-9) {
        if (Math.abs(B) > 1e-9) roots.push(-C0 / B);
      } else {
        const disc = B * B - 4 * A * C0;
        if (disc >= 0) {
          const q = Math.sqrt(disc);
          roots.push((-B - q) / (2 * A), (-B + q) / (2 * A));
        }
      }
      const ts = roots.filter((t) => t > 0.01 && t < 0.99).sort((a, b) => a - b);
      let rest = c, done = 0;
      const parts = [];
      for (const t of ts) {
        const [a, b] = splitCubic(rest, (t - done) / (1 - done));
        parts.push(a);
        rest = b;
        done = t;
      }
      parts.push(rest);
      for (const part of parts) {
        const s = cross(cubicTangent(part, 0.5));
        pieces.push({ c: part, sign: Math.abs(s) < 0.01 ? 0 : Math.sign(s) });
      }
    }
    // Group the pieces into runs.
    const runs = [];
    let run = null;
    for (const pc of pieces) {
      if (pc.sign === 0) { run = null; continue; }
      if (!run || run.sign !== pc.sign) {
        run = { sign: pc.sign, cs: [] };
        runs.push(run);
      }
      run.cs.push(pc.c);
    }
    const hx = n[0] / 2, hy = n[1] / 2;
    const mv = (pt, k) => [pt[0] + hx * k, pt[1] + hy * k];
    return runs.map((r) => {
      const contour = [];
      for (const c of r.cs) contour.push(c.map((pt) => mv(pt, 1)));
      const last = r.cs[r.cs.length - 1][3];
      contour.push(lineSeg(mv(last, 1), mv(last, -1)));
      for (let i = r.cs.length - 1; i >= 0; i--) {
        const c = r.cs[i];
        contour.push([mv(c[3], -1), mv(c[2], -1), mv(c[1], -1), mv(c[0], -1)]);
      }
      const first = r.cs[0][0];
      contour.push(lineSeg(mv(first, -1), mv(first, 1)));
      return contour;
    });
  }

  function contourArea(contour) {
    let a = 0;
    for (const c of contour) {
      let prev = c[0];
      for (let i = 1; i <= 8; i++) {
        const p = cubicAt(c, i / 8);
        a += prev[0] * p[1] - p[0] * prev[1];
        prev = p;
      }
    }
    return a / 2;
  }

  function reverseContour(contour) {
    return contour.slice().reverse().map((c) => [c[3], c[2], c[1], c[0]]);
  }

  // ---------------------------------------------------------------- the letters

  // Everything a glyph drawing needs: the measurements from the settings and the drawing tools.
  function makeCtx(prm) {
    const H = prm.height;
    const T = Math.max(8, H * prm.weight);
    const S = Math.max(6, T / Math.max(1, prm.contrast));
    const ctx = {
      H, T, S,
      t: H - T / 2,         // centre line of the roof
      b: T / 2,             // centre line of the base
      r: prm.round * 0.32 * H, // corner radius
      D: prm.descender * H,
      A: prm.ascender * H,
      s: prm.serif,
      gap: 0.07 * H,
      prm,
    };
    return ctx;
  }

  // Drawing of one glyph: stroke paths, filled shapes and anchors for the vowel points.
  class Drawing {
    constructor(ctx, width) {
      this.ctx = ctx;
      this.W = width;
      this.strokes = [];   // {path, swap} swap: pens turned for Latin-like digits
      this.shapes = [];    // closed contours
      this.anchors = {};
      this.links = [];     // heads that move with the start of a stroke
      this.swap = false;
    }
    P(x, y) {
      const p = new Pth(x, y);
      this.strokes.push({ path: p, swap: this.swap });
      return p;
    }
    shape(contour) { this.shapes.push(contour); return this.shapes.length - 1; }
    // The head: a wedge hanging under the left end of a roof whose top is at y.
    head(x, y) {
      const { T, S, s } = this.ctx;
      if (s <= 0.01) return;
      const y0 = y === undefined ? this.ctx.H : y;
      const xa = x - S / 2;            // where the roof really ends (the pen reaches past its path)
      const hw = S + T * 1.1 * s;      // along the roof
      const hd = T * 0.7 * s;          // below the roof
      const yb = y0 - T + 1;           // underside of the roof
      const hs = this.ctx.prm.headShape;
      // the tip: almost square for a block, round for a drop
      const rr = hs <= 0.5 ? Math.max(1, Math.min(S * 0.6, hw * 0.3) * (hs / 0.5)) : Math.min(S * 0.6, hw * 0.3) + (hw * 0.5 - Math.min(S * 0.6, hw * 0.3)) * (hs - 0.5) * 2;
      // the underside: straight for a block, a hollow curve for a wedge, a full curve for a drop
      const f = hs <= 0.5 ? 0.9 + (0.3 - 0.9) * (hs / 0.5) : 0.3 - 0.3 * (hs - 0.5) * 2;
      const xt = xa + S * 0.12;
      // the head moves with the roof it hangs on
      const roof = this.strokes.findIndex((st) => Math.abs(st.path.start[0] - x) < 1 && Math.abs(st.path.start[1] - (y0 - T / 2)) < 1);
      const i = this.shape([
        lineSeg([xa, y0], [xt, yb - hd + rr]),
        [[xt, yb - hd + rr], [xt, yb - hd + rr * 0.45], [xt + rr * 0.45, yb - hd], [xt + rr, yb - hd]],
        [[xt + rr, yb - hd], [xt + rr + (hw - rr) * f, yb - hd * (hs > 0.5 ? 1 : 0.9)], [xa + hw * (hs > 0.5 ? 0.95 : 0.6), yb - hd * (hs > 0.5 ? (hs - 0.5) * 1.2 : 0)], [xa + hw, yb]],
        lineSeg([xa + hw, yb], [xa + hw, y0]),
        lineSeg([xa + hw, y0], [xa, y0]),
      ]);
      if (roof >= 0) this.links.push({ shape: i, stroke: roof });
    }
    dot(x, y, rad) { this.shape(ellipse(x, y, rad, rad)); }
  }

  // Width of every letter, part of the height.
  const HEBREW = [
    ["alef", 0x5d0, 0.92], ["bet", 0x5d1, 0.86], ["gimel", 0x5d2, 0.58], ["dalet", 0x5d3, 0.84],
    ["he", 0x5d4, 0.86], ["vav", 0x5d5, 0.30], ["zayin", 0x5d6, 0.38], ["het", 0x5d7, 0.86],
    ["tet", 0x5d8, 0.86], ["yod", 0x5d9, 0.30], ["finalkaf", 0x5da, 0.78], ["kaf", 0x5db, 0.78],
    ["lamed", 0x5dc, 0.78], ["finalmem", 0x5dd, 0.84], ["mem", 0x5de, 0.90], ["finalnun", 0x5df, 0.30],
    ["nun", 0x5e0, 0.52], ["samekh", 0x5e1, 0.86], ["ayin", 0x5e2, 0.88], ["finalpe", 0x5e3, 0.78],
    ["pe", 0x5e4, 0.82], ["finaltsadi", 0x5e5, 0.80], ["tsadi", 0x5e6, 0.82], ["qof", 0x5e7, 0.86],
    ["resh", 0x5e8, 0.80], ["shin", 0x5e9, 1.0], ["tav", 0x5ea, 0.90],
  ];

  // Sets of letter drawings to start from. Each has the widths of its letters (parts of the
  // height), a drawing for every letter, and the settings it looks best with.
  const SETS = {};
  function addLetterSet(id, set) { SETS[id] = set; }
  function letterSet(prm) { return SETS[prm.base] || SETS.classic || SETS.square; }
  function letterSets() {
    return Object.keys(SETS).map((id) => ({ id, name: SETS[id].name, about: SETS[id].about, defaults: SETS[id].defaults || {} }));
  }

  const LETTERS = {
    alef(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      d.P(0, t).L(W * 0.24, t);
      d.head(0);
      d.P(W * 0.14, t).C(W * 0.40, H * 0.66, W * 0.62, H * 0.34, W * 0.90, b);
      d.P(W * 0.74, b).L(W, b);
      const xr = W - S / 2;
      d.P(W * 0.66, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.66).C(xr, H * 0.50, W * 0.74, H * 0.47, W * 0.58, H * 0.49);
      d.head(W * 0.66);
      d.P(W * 0.42, H * 0.56).C(W * 0.30, H * 0.40, W * 0.22, H * 0.25, W * 0.22, b);
      d.P(0, b).L(W * 0.30, b);
      d.anchors.dagesh = [W * 0.5, H * 0.42];
    },
    bet(d, c) {
      const { t, b, S, H, r, s } = c, W = d.W;
      const heel = H * (0.01 + 0.2 * c.prm.heel) * (0.4 + 0.6 * s);
      const xr = W - heel - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(0, b).L(W, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.48, H * 0.5];
      d.anchors.below = [xr * 0.5, 0];
    },
    gimel(d, c) {
      const { t, b, S, H, r, s } = c, W = d.W;
      const xr = W - S / 2 - H * 0.04 * s;
      d.P(W * 0.12, t).R(xr, t, 0, -1, r * 0.4).L(xr, c.b);
      d.head(W * 0.12);
      d.P(xr, H * 0.46).C(xr - W * 0.25, H * 0.36, W * 0.12, H * 0.22, W * 0.06, b * 0.6);
      if (s > 0.01) d.P(xr - S / 2, b).L(W, b);
      d.anchors.dagesh = [W * 0.42, H * 0.66];
      d.anchors.below = [xr * 0.6, 0];
    },
    dalet(d, c) {
      const { t, S, H } = c, W = d.W;
      const xr = W - W * 0.26 * c.prm.overhang - S / 2;
      d.P(0, t).L(W, t);
      d.P(xr, t).L(xr, c.b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
      d.anchors.below = [xr * 0.55, 0];
    },
    he(d, c) {
      const { t, S, H, T } = c, W = d.W;
      const xr = W - W * 0.14 * c.prm.overhang - S / 2;
      d.P(0, t).L(W, t);
      d.P(xr, t).L(xr, c.b);
      const xl = S * 0.75 + W * 0.04;
      d.P(xl, H - T * 1.5 - T * 0.7 * c.s - H * 0.12).L(xl, c.b); // clear of the head above it
      d.head(0);
      d.anchors.dagesh = [W * 0.48, H * 0.45];
    },
    vav(d, c) {
      const { t, S, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, c.b);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - c.H * 0.1, c.H * 0.5];
      d.anchors.below = [xr, 0];
    },
    zayin(d, c) {
      const { t } = c, W = d.W;
      const xm = W * 0.55;
      d.P(0, t).L(W, t);
      d.P(xm, t).C(xm, c.H * 0.5, xm - W * 0.05, c.H * 0.25, xm - W * 0.05, c.b);
      d.head(0);
      d.anchors.dagesh = [xm - c.S / 2 - c.H * 0.1, c.H * 0.5];
      d.anchors.below = [xm, 0];
    },
    het(d, c) {
      const { t, S, H, r } = c, W = d.W;
      const xr = W - S / 2, xl = S * 0.75 + W * 0.03;
      d.P(0, t).R(xr, t, 0, -1, r * 0.3).L(xr, c.b);
      d.P(xl, t).L(xl, c.b);
      d.head(0);
      d.anchors.dagesh = [W * 0.5, H * 0.45];
    },
    tet(d, c) {
      const { t, b, S, H, T, r } = c, W = d.W;
      const xl = S / 2 + W * 0.02, xr = W - S / 2;
      const rb = Math.min(H * 0.4, r * 0.7 + H * 0.12);
      d.P(0, t).L(W * 0.2, t);
      d.head(0);
      d.P(xl, t).L(xl, b + rb * 0.3).R(xl, b, 1, 0, rb * 0.3).L(xr - rb, b).qh(xr, b + rb)
        .L(xr, H * 0.6).C(xr, H * 0.86, W * 0.82, t, W * 0.62, t)
        .C(W * 0.5, t, W * 0.44, H - T * 0.9, W * 0.44, H * 0.6);
      d.anchors.dagesh = [W * 0.6, H * 0.42];
    },
    yod(d, c) {
      const { t, S, H, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.5);
      d.head(0);
      d.anchors.dagesh = [W * 0.5, H * 0.32];
      d.anchors.below = [W * 0.6, H * 0.36];
    },
    kaf(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).R(xr, b, -1, 0, r).L(0, b);
      d.head(0);
      d.anchors.dagesh = [W * 0.46, H * 0.5];
    },
    finalkaf(d, c) {
      const { t, S, H, r, D } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, c.b - D);
      d.head(0);
      d.anchors.dagesh = [W * 0.46, H * 0.5];
      d.anchors.below = [W * 0.46, H * 0.42];
    },
    lamed(d, c) {
      const { t, b, S, H, T, r, A } = c, W = d.W;
      const xl = S / 2 + W * 0.02, xr = W - S / 2;
      d.P(0, H + A - T / 2).L(W * 0.2, H + A - T / 2);
      d.head(0, H + A);
      d.P(xl, H + A - T / 2).L(xl, t);
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, H * 0.46).C(xr, H * 0.16, W * 0.72, b, W * 0.46, b).L(W * 0.2, b);
      d.anchors.dagesh = [W * 0.5, H * 0.48];
      d.anchors.aboveLeft = [W * 0.48, H];
    },
    mem(d, c) {
      const { t, b, S, H, r, s } = c, W = d.W;
      const heel = H * 0.08 * c.prm.heel * s;
      const xr = W - heel - S / 2, xl = S / 2 + W * 0.03;
      d.P(W * 0.36, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(W * 0.36, b).L(W, b);
      d.P(0, t).L(W * 0.18, t);
      d.head(0);
      d.P(xl, t).L(xl + W * 0.05, c.b);
      d.P(W * 0.40, t).C(W * 0.34, H * 0.70, W * 0.18, H * 0.62, xl + W * 0.02, H * 0.58);
      d.anchors.dagesh = [W * 0.6, H * 0.48];
      d.anchors.below = [W * 0.55, 0];
    },
    finalmem(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2, xl = S / 2 + W * 0.02;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(xl, t).L(xl, b);
      d.P(0, b).L(W, b);
      d.head(0);
      d.anchors.dagesh = [W * 0.5, H * 0.5];
    },
    nun(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.6).R(xr, b, -1, 0, r * 0.25).L(0, b);
      d.head(0);
      d.anchors.dagesh = [W * 0.38, H * 0.5];
    },
    finalnun(d, c) {
      const { t, S, r, D } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, c.b - D);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - c.H * 0.1, c.H * 0.5];
      d.anchors.below = [xr, 0];
    },
    samekh(d, c) {
      const { t, b, S, H } = c, W = d.W;
      const xl = S / 2 + W * 0.05, xr = W - S / 2 - W * 0.04;
      const ry = Math.min(H * 0.42, (xr - xl) * 0.5);
      d.P(0, t).L(W, t);
      d.P(xl, t).L(xl, b + ry).qv((xl + xr) / 2, b).qh(xr, b + ry).L(xr, t);
      d.head(0);
      d.anchors.dagesh = [W * 0.5, H * 0.48];
    },
    ayin(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(W * 0.66, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.42).C(xr, H * 0.12, W * 0.78, b, W * 0.52, b).L(0, b);
      d.head(W * 0.66);
      d.P(0, t).L(W * 0.24, t);
      d.head(0);
      d.P(W * 0.12, t).C(W * 0.24, H * 0.52, W * 0.46, H * 0.34, xr - S * 0.3, H * 0.30);
      d.anchors.dagesh = [W * 0.6, H * 0.6];
    },
    pe(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).R(xr, b, -1, 0, r).L(0, b);
      d.P(xl, t).L(xl, H * 0.56);
      d.head(0);
      d.anchors.dagesh = [W * 0.56, H * 0.5];
    },
    finalpe(d, c) {
      const { t, S, H, r, D } = c, W = d.W;
      const xr = W - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, c.b - D);
      d.P(xl, t).L(xl, H * 0.56);
      d.head(0);
      d.anchors.dagesh = [W * 0.56, H * 0.5];
      d.anchors.below = [W * 0.46, H * 0.4];
    },
    tsadi(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2;
      d.P(0, t).L(W * 0.24, t);
      d.head(0);
      d.P(W * 0.12, t).C(W * 0.30, H * 0.56, W * 0.58, H * 0.26, W * 0.86, b);
      d.P(0, b).L(W, b);
      d.P(W * 0.64, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.68).C(xr, H * 0.48, W * 0.72, H * 0.42, W * 0.5, H * 0.42);
      d.head(W * 0.64);
      d.anchors.dagesh = [W * 0.66, H * 0.26];
    },
    finaltsadi(d, c) {
      const { t, S, H, r, D } = c, W = d.W;
      const xr = W - S / 2, xl = W * 0.22;
      d.P(0, t).L(W * 0.34, t);
      d.head(0);
      d.P(xl, t).L(xl + W * 0.02, c.b - D);
      d.P(W * 0.64, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.66).C(xr, H * 0.46, W * 0.62, H * 0.38, xl, H * 0.38);
      d.head(W * 0.64);
      d.anchors.dagesh = [W * 0.56, H * 0.62];
      d.anchors.below = [W * 0.6, 0];
    },
    qof(d, c) {
      const { t, S, H, r } = c, W = d.W;
      const xr = W - S / 2, xl = S * 0.75 + W * 0.04;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, c.b);
      d.P(xl, H - c.T * 1.5 - c.T * 0.7 * c.s - H * 0.14).L(xl, c.b - c.D);
      d.head(0);
      d.anchors.dagesh = [W * 0.55, H * 0.45];
      d.anchors.below = [W * 0.6, 0];
    },
    resh(d, c) {
      const { t, S, H, r } = c, W = d.W;
      const xr = W - S / 2 - W * 0.02;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.16)).L(xr, c.b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
    },
    shin(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xl = S / 2 + W * 0.02, xr = W - S / 2;
      const rb = Math.min(H * 0.3, r * 0.6 + H * 0.06);
      d.P(0, t).L(W * 0.18, t);
      d.head(0);
      d.P(xl, t).L(xl, b + rb).qv(xl + rb, b).L(xr - S * 0.2, b);
      d.P(W * 0.80, t).R(xr, t, 0, -1, r * 0.3).L(xr, b);
      d.head(W * 0.80);
      d.P(W * 0.40, t).L(W * 0.56, t);
      d.head(W * 0.40);
      d.P(W * 0.48, t).C(W * 0.50, H * 0.52, W * 0.56, H * 0.32, W * 0.70, b);
      d.anchors.dagesh = [W * 0.32, H * 0.45];
      d.anchors.aboveRight = [W * 0.9, H];
      d.anchors.aboveLeft = [W * 0.1, H];
    },
    tav(d, c) {
      const { t, b, S, H, r } = c, W = d.W;
      const xr = W - S / 2, xl = W * 0.13 + S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.6).L(xr, c.b);
      d.P(xl, t).L(xl, b);
      d.P(0, b).L(xl + S / 2, b);
      d.head(0);
      d.anchors.dagesh = [W * 0.56, H * 0.45];
    },
  };

  // Digits and punctuation, with the pens turned (thick verticals, thin horizontals).
  const DIGITS = {
    zero(d, c) {
      const { H, b, t } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(m, t).qh(x1, H / 2).qv(m, b).qh(x0, H / 2).qv(m, t);
    },
    one(d, c) {
      const { H, t, b } = c, W = d.W, m = W * 0.56;
      d.P(m, H - c.S / 2).L(m, c.S / 2);
      d.P(m, t).L(m - W * 0.34, H * 0.78);
      if (c.s > 0.01) d.P(m - W * 0.3, b * 0.7).L(m + W * 0.3, b * 0.7);
    },
    two(d, c) {
      const { H, t, b } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(x0, H * 0.72).qv(m, t).qh(x1, H * 0.70).C(x1, H * 0.46, W * 0.3, H * 0.25, x0, b * 0.7);
      d.P(x0, b * 0.7).L(W, b * 0.7);
    },
    three(d, c) {
      const { H, t, b } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(x0, H * 0.76).qv(m, t).qh(x1 - W * 0.05, H * 0.76).qv(m - W * 0.06, H * 0.54);
      d.P(m - W * 0.06, H * 0.54).qh(x1, H * 0.27).qv(m, b).qh(x0, H * 0.24);
    },
    four(d, c) {
      const { H, b } = c, W = d.W, x0 = c.S * 0.4;
      const xs = W * 0.70;
      d.P(xs, H - c.S / 2).L(x0, H * 0.3).L(W, H * 0.3);
      d.P(xs, H - c.S / 2).L(xs, c.S / 2);
    },
    five(d, c) {
      const { H, t, b } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(x1, t).L(W * 0.26, t).L(W * 0.2, H * 0.56);
      d.P(W * 0.2, H * 0.56).C(W * 0.34, H * 0.62, x1, H * 0.66, x1, H * 0.32).qv(m, b).qh(x0, H * 0.22);
    },
    six(d, c) {
      const { H, t, b } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(x1 - W * 0.06, H * 0.9).C(W * 0.5, t, x0, H * 0.82, x0, H * 0.34).qv(m, b).qh(x1, H * 0.3).qv(m, H * 0.6).qh(x0, H * 0.32);
    },
    seven(d, c) {
      const { H, t } = c, W = d.W, x0 = c.S * 0.4;
      d.P(x0, t).L(W, t);
      d.P(W - c.S * 0.5, t).C(W * 0.6, H * 0.6, W * 0.44, H * 0.3, W * 0.42, c.S / 2);
    },
    eight(d, c) {
      const { H, t, b } = c, W = d.W, x0 = c.S * 0.7, x1 = W - c.S * 0.7, m = W / 2;
      d.P(m, t).qh(x1 - W * 0.06, H * 0.77).qv(m, H * 0.54).qh(x0 + W * 0.06, H * 0.77).qv(m, t);
      d.P(m, H * 0.54).qh(x1, H * 0.27).qv(m, b).qh(x0, H * 0.27).qv(m, H * 0.54);
    },
    nine(d, c) {
      DIGITS.six(d, c);
      const W = d.W, H = c.H;
      d.strokes = d.strokes.map((s) => ({ path: s.path.map(([x, y]) => [W - x, H - y]), swap: s.swap }));
    },
  };

  function punct(name, uni, width, draw, latin) {
    return { name, uni, width, draw, latin };
  }

  const dotR = (c) => Math.max(c.T, c.S) * 0.56;

  const PUNCT = [
    punct("period", 0x2e, (c) => dotR(c) * 2, (d, c) => d.dot(dotR(c), dotR(c), dotR(c))),
    punct("comma", 0x2c, (c) => dotR(c) * 2, (d, c) => {
      const r = dotR(c);
      d.dot(r, r, r);
      d.shape([lineSeg([r * 2, r], [r * 0.6, -r * 2.2]), lineSeg([r * 0.6, -r * 2.2], [r * 0.1, -r * 2.0]),
        lineSeg([r * 0.1, -r * 2.0], [r, r])]);
    }),
    punct("colon", 0x3a, (c) => dotR(c) * 2, (d, c) => {
      const r = dotR(c);
      d.dot(r, r, r);
      d.dot(r, c.H * 0.56, r);
    }),
    punct("semicolon", 0x3b, (c) => dotR(c) * 2, (d, c) => {
      PUNCT[1].draw(d, c);
      d.dot(dotR(c), c.H * 0.56, dotR(c));
    }),
    punct("sofpasuq", 0x5c3, (c) => dotR(c) * 2, (d, c) => {
      const r = dotR(c);
      d.dot(r, r, r);
      d.dot(r, c.H * 0.56, r);
    }),
    punct("exclam", 0x21, (c) => dotR(c) * 2, (d, c) => {
      const r = dotR(c);
      d.dot(r, r, r);
      d.shape(polygon([[r * 0.45, c.H * 0.32], [r * 1.55, c.H * 0.32], [r * 1.9, c.H], [r * 0.1, c.H]]));
    }),
    punct("question", 0x3f, (c) => c.H * 0.44, (d, c) => {
      const r = dotR(c), W = d.W, H = c.H;
      d.dot(W * 0.5, r, r);
      d.swap = true;
      d.P(c.S * 0.7, H * 0.74).qv(W * 0.5, c.t).qh(W - c.S * 0.7, H * 0.72).C(W - c.S * 0.7, H * 0.5, W * 0.5, H * 0.52, W * 0.5, H * 0.3);
    }),
    punct("quotesingle", 0x27, (c) => c.S * 1.6, (d, c) => {
      d.swap = true;
      d.P(c.S * 0.8, c.H).L(c.S * 0.8, c.H * 0.68);
    }),
    punct("quotedbl", 0x22, (c) => c.S * 1.6 + c.H * 0.16, (d, c) => {
      d.swap = true;
      d.P(c.S * 0.8, c.H).L(c.S * 0.8, c.H * 0.68);
      d.P(c.S * 0.8 + c.H * 0.16, c.H).L(c.S * 0.8 + c.H * 0.16, c.H * 0.68);
    }),
    punct("geresh", 0x5f3, (c) => c.H * 0.16, (d, c) => {
      const W = d.W, H = c.H, w = Math.max(c.S, c.T * 0.6);
      d.shape(polygon([[W - w, H], [W, H], [w * 0.4, H * 0.66], [0, H * 0.7]]));
    }),
    punct("gershayim", 0x5f4, (c) => c.H * 0.34, (d, c) => {
      const W = d.W, H = c.H, w = Math.max(c.S, c.T * 0.6);
      d.shape(polygon([[W - w, H], [W, H], [W - H * 0.16 + w * 0.4, H * 0.66], [W - H * 0.16, H * 0.7]]));
      d.shape(polygon([[H * 0.16 - w, H], [H * 0.16, H], [w * 0.4, H * 0.66], [0, H * 0.7]]));
    }),
    punct("hyphen", 0x2d, (c) => c.H * 0.36, (d, c) => {
      d.P(0, c.H * 0.42).L(d.W, c.H * 0.42);
    }),
    punct("maqaf", 0x5be, (c) => c.H * 0.36, (d, c) => {
      d.P(0, c.H - c.T / 2).L(d.W, c.H - c.T / 2);
    }),
    punct("parenleft", 0x28, (c) => c.H * 0.28, (d, c) => {
      d.swap = true;
      const W = d.W, H = c.H;
      d.P(W, H * 1.08).C(W * 0.1, H * 0.8, W * 0.1, H * 0.0, W, -H * 0.22);
    }),
    punct("parenright", 0x29, (c) => c.H * 0.28, (d, c) => {
      d.swap = true;
      const W = d.W, H = c.H;
      d.P(0, H * 1.08).C(W * 0.9, H * 0.8, W * 0.9, H * 0.0, 0, -H * 0.22);
    }),
    punct("bracketleft", 0x5b, (c) => c.H * 0.26, (d, c) => {
      d.swap = true;
      const W = d.W, H = c.H, x = c.T * 0.45;
      d.P(x, H * 1.08).L(x, -H * 0.22);
      d.swap = false;
      d.P(0, H * 1.08 - c.S / 2).L(W, H * 1.08 - c.S / 2);
      d.P(0, -H * 0.22 + c.S / 2).L(W, -H * 0.22 + c.S / 2);
    }),
    punct("bracketright", 0x5d, (c) => c.H * 0.26, (d, c) => {
      d.swap = true;
      const W = d.W, H = c.H, x = W - c.T * 0.45;
      d.P(x, H * 1.08).L(x, -H * 0.22);
      d.swap = false;
      d.P(0, H * 1.08 - c.S / 2).L(W, H * 1.08 - c.S / 2);
      d.P(0, -H * 0.22 + c.S / 2).L(W, -H * 0.22 + c.S / 2);
    }),
    punct("slash", 0x2f, (c) => c.H * 0.4, (d, c) => {
      d.swap = true;
      d.P(d.W, c.H * 1.05).L(0, -c.H * 0.12);
    }),
  ];

  // Vowel points. Each is drawn around its anchor point (0, 0):
  // below the line for the vowels under the letter, above it for the dots on top.
  const MARK_CLASSES = ["below", "dagesh", "aboveLeft", "aboveRight", "above"];

  function markShapes(c) {
    const r = Math.max(c.T, c.S) * 0.42 + c.H * 0.012;
    const bt = r * 1.25;                 // thickness of a bar
    const bw = c.H * 0.17;               // half the length of a bar
    const sp = c.H * 0.13;               // space between dots
    const bar = (x, y, hw, th) => polygon([[x - hw, y], [x + hw, y], [x + hw, y - th], [x - hw, y - th]]);
    const kamatz = (x) => [bar(x, 0, bw, bt), bar(x, -bt + 1, bt * 0.36, c.H * 0.13 + 1)];
    const segol = (x) => [ellipse(x - sp * 0.55, -r, r, r), ellipse(x + sp * 0.55, -r, r, r), ellipse(x, -r - sp * 0.95, r, r)];
    const shva = (x) => [ellipse(x, -r, r, r), ellipse(x, -r - sp * 0.95, r, r)];
    return {
      sheva: [0x5b0, "below", shva(0)],
      hatafsegol: [0x5b1, "below", [...segol(sp * 0.7), ...shva(-sp * 1.15)]],
      hatafpatah: [0x5b2, "below", [bar(sp * 0.55, 0, bw * 0.85, bt), ...shva(-sp * 1.25)]],
      hatafqamats: [0x5b3, "below", [bar(sp * 0.55, 0, bw * 0.85, bt), bar(sp * 0.55, -bt + 1, bt * 0.36, c.H * 0.13 + 1), ...shva(-sp * 1.25)]],
      hiriq: [0x5b4, "below", [ellipse(0, -r, r, r)]],
      tsere: [0x5b5, "below", [ellipse(-sp * 0.6, -r, r, r), ellipse(sp * 0.6, -r, r, r)]],
      segol: [0x5b6, "below", segol(0)],
      patah: [0x5b7, "below", [bar(0, 0, bw, bt)]],
      qamats: [0x5b8, "below", kamatz(0)],
      holam: [0x5b9, "aboveLeft", [ellipse(0, r, r, r)]],
      holamhaserforvav: [0x5ba, "aboveLeft", [ellipse(0, r, r, r)]],
      qubuts: [0x5bb, "below", [ellipse(-sp * 0.75, -r, r, r), ellipse(0, -r - sp * 0.5, r, r), ellipse(sp * 0.75, -r - sp, r, r)]],
      dagesh: [0x5bc, "dagesh", [ellipse(0, 0, r * 0.95, r * 0.95)]],
      meteg: [0x5bd, "below", [bar(0, 0, bt * 0.36, c.H * 0.16)]],
      rafe: [0x5bf, "above", [bar(0, bt, bw * 0.8, bt)]],
      shindot: [0x5c1, "aboveRight", [ellipse(0, r, r, r)]],
      sindot: [0x5c2, "aboveLeft", [ellipse(0, r, r, r)]],
      qamatsqatan: [0x5c7, "below", kamatz(0)],
    };
  }

  // ---------------------------------------------------------------- glyph building

  // The pen: a rectangle (tall and thin for Hebrew, turned for the digits). With little contrast
  // its corners are cut off, an octagon, so slanted strokes stay as thick as straight ones.
  // The pen is kept as the line segments whose sum it is (a zonotope); its edges are what sweep.
  function penEdges(ctx, swap) {
    const a = (ctx.prm.angle * Math.PI) / 180;
    const rot = (v) => [v[0] * Math.cos(a) - v[1] * Math.sin(a), v[0] * Math.sin(a) + v[1] * Math.cos(a)];
    const { T, S } = ctx;
    const tall = swap ? T * 0.8 : T, wide = swap ? T * 0.8 : S;
    // the pen is a mix of a rectangle and an oval of the same size (an oval made of 8 short lines);
    // with little contrast it is a little round anyway, so slanted strokes stay as thick as the rest
    const q = Math.max(ctx.prm.pen || 0, Math.min(1, Math.max(0, (1.8 - ctx.prm.contrast) / 0.8)) * 0.6);
    const pw = swap ? tall : wide, ph = swap ? S : tall;
    const gens = [[pw * (1 - q), 0], [0, ph * (1 - q)]];
    if (q > 0.01) {
      const n = 8, k = 2 * Math.sin(Math.PI / (2 * n)) / 2;
      for (let i = 0; i < n; i++) {
        const t = (i * Math.PI) / n + Math.PI / (2 * n);
        gens.push([pw * q * k * Math.cos(t) * 1.0, ph * q * k * Math.sin(t)]);
      }
    }
    const g = gens.filter((v) => Math.hypot(v[0], v[1]) > 0.3).map(rot);
    // Vertices of the zonotope, in order around it.
    const dirs = [];
    for (const v of g) dirs.push(v, [-v[0], -v[1]]);
    dirs.sort((p, q) => Math.atan2(p[1], p[0]) - Math.atan2(q[1], q[0]));
    let x = 0, y = 0;
    const verts = [];
    for (const v of dirs) { verts.push([x, y]); x += v[0]; y += v[1]; }
    const cx = verts.reduce((s, p) => s + p[0], 0) / verts.length;
    const cy = verts.reduce((s, p) => s + p[1], 0) / verts.length;
    const vs = verts.map((p) => [p[0] - cx, p[1] - cy]);
    const edges = [];
    for (let i = 0; i < vs.length; i++) {
      const p = vs[i], q = vs[(i + 1) % vs.length];
      edges.push({ mid: [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2], v: [q[0] - p[0], q[1] - p[1]] });
    }
    return { edges, poly: vs };
  }

  // Area the pen covers along a stroke path: the pen at both ends, and every edge of the pen
  // swept along the path (moved to where that edge sits on the pen).
  function penStroke(path, pen) {
    const out = [];
    const ends = [path.start, path.cur];
    for (const e of ends) out.push(polygon(pen.poly.map((p) => [p[0] + e[0], p[1] + e[1]])));
    for (const ed of pen.edges) {
      const moved = path.map(([x, y]) => [x + ed.mid[0], y + ed.mid[1]]);
      out.push(...sweep(moved, ed.v));
    }
    return out;
  }

  // Outline contours of a drawing (overlapping, all turning the same way).
  function drawingContours(d) {
    const out = [];
    const pens = { false: penEdges(d.ctx, false), true: penEdges(d.ctx, true) };
    for (const st of d.strokes) out.push(...penStroke(st.path, pens[st.swap]));
    out.push(...d.shapes);
    return out
      .filter((c) => Math.abs(contourArea(c)) > 2)
      .map((c) => (contourArea(c) < 0 ? reverseContour(c) : c));
  }

  function transform(contours, f) {
    return contours.map((c) => c.map((seg) => seg.map(f)));
  }

  // The points of a stroke path that can be moved by hand, in order: the start, then the end of
  // a line, or the two control points and the end of a curve.
  function pathPoints(p) {
    const out = [{ get: () => p.start, set: (v) => { p.start = v; }, on: true }];
    for (const s of p.segs) {
      const k = s.t === "L" ? [0] : [0, 2, 4];
      k.forEach((j, n) => out.push({
        get: () => [s.p[j], s.p[j + 1]],
        set: (v) => { s.p[j] = v[0]; s.p[j + 1] = v[1]; },
        on: s.t === "L" || n === 2,
      }));
    }
    return out;
  }

  // Changes made by hand: {"stroke.point": [dx, dy]}, moves from where the settings put the point.
  function applyEdits(d, edits) {
    d.strokes.forEach((st, si) => {
      const pts = pathPoints(st.path);
      pts.forEach((pt, pi) => {
        const e = edits[si + "." + pi];
        if (!e) return;
        const v = pt.get();
        pt.set([v[0] + e[0], v[1] + e[1]]);
      });
      const last = pts[pts.length - 1].get();
      st.path.cur = [last[0], last[1]];
    });
    for (const l of d.links) {
      const e = edits[l.stroke + ".0"];
      if (e) d.shapes[l.shape] = d.shapes[l.shape].map((sg) => sg.map((p) => [p[0] + e[0], p[1] + e[1]]));
    }
  }

  // The part of the letter every point belongs to, in words common to all the letters: where it
  // is (top, base, below the line, above the letters; right, middle, left) and which way its
  // stroke goes from it. A change made to a part of one letter can then be made to the same part
  // of the others: the head at the start of a roof, a rounded corner, the foot of a stem...
  function dirClass(dx, dy) {
    if (Math.hypot(dx, dy) < 0.5) return "o";
    const a = Math.atan2(dy, dx) / (Math.PI / 4);
    return ["R", "UR", "U", "UL", "L", "DL", "D", "DR"][((Math.round(a) % 8) + 8) % 8];
  }

  function pointRoles(prmIn) {
    const prm = Object.assign({}, DEFAULTS, prmIn || {});
    const c = makeCtx(prm);
    const out = {};
    const set = letterSet(prm);
    for (const [name] of HEBREW) {
      const W = set.widths[name] * c.H * prm.width;
      const d = new Drawing(c, W);
      set.letters[name](d, c);
      const roles = {};
      d.strokes.forEach((st, si) => {
        const P = pathPoints(st.path).map((p) => ({ v: p.get(), on: p.on }));
        const zone = (v) => {
          const y = v[1], x = v[0] / W;
          const vz = y > c.H + c.H * 0.1 ? "asc" : y < -c.H * 0.1 ? "desc" : y > c.H * 0.72 ? "top" : y < c.H * 0.28 ? "base" : "mid";
          return vz + (x < 0.3 ? "L" : x > 0.7 ? "R" : "C");
        };
        // direction from point i towards the next point that is somewhere else
        const toward = (i, step) => {
          for (let j = i + step; j >= 0 && j < P.length; j += step) {
            const dx = P[j].v[0] - P[i].v[0], dy = P[j].v[1] - P[i].v[1];
            if (Math.hypot(dx, dy) > 0.5) return dirClass(dx, dy);
          }
          return "o";
        };
        const onKey = P.map((p, i) => (p.on ? zone(p.v) + "|" + toward(i, -1) + ">" + toward(i, 1) : null));
        P.forEach((p, i) => {
          if (p.on) roles[si + "." + i] = onKey[i];
          else if (P[i - 1] && P[i - 1].on) roles[si + "." + i] = onKey[i - 1] + "|c1";
          else roles[si + "." + i] = onKey[i + 1] + "|c2";
        });
      });
      out[name] = { W, roles };
    }
    return out;
  }

  // Makes the other letters like the ones changed by hand: every part that was moved in the
  // letters of `sources` is moved the same way in every other letter that has that part
  // (sideways moves grow with the width of the letter). Returns the new hand changes.
  function styleFrom(prm, sources) {
    const R = pointRoles(prm);
    const moves = {};
    for (const name of sources) {
      const ed = prm.edits && prm.edits[name];
      if (!ed || !R[name]) continue;
      for (const k in ed) {
        const role = R[name].roles[k];
        if (!role) continue;
        (moves[role] = moves[role] || []).push([ed[k][0] / R[name].W, ed[k][1]]);
      }
    }
    const edits = Object.assign({}, prm.edits);
    for (const name in R) {
      if (sources.includes(name)) continue;
      const e = {};
      for (const k in R[name].roles) {
        const m = moves[R[name].roles[k]];
        if (!m) continue;
        const dx = m.reduce((a, v) => a + v[0], 0) / m.length * R[name].W;
        const dy = m.reduce((a, v) => a + v[1], 0) / m.length;
        if (Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5) e[k] = [Math.round(dx), Math.round(dy)];
      }
      if (Object.keys(e).length) edits[name] = e;
      else delete edits[name];
    }
    return edits;
  }

  // Letters, digits and signs whose points can be moved by hand.
  function editableGlyphs() {
    return HEBREW.map(([n, u]) => ({ name: n, char: String.fromCharCode(u) }))
      .concat(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"].map((n, i) => ({ name: n, char: String(i) })))
      .concat(PUNCT.filter((p) => ["question", "parenleft", "parenright", "bracketleft", "bracketright", "slash", "hyphen", "maqaf"]
        .includes(p.name)).map((p) => ({ name: p.name, char: String.fromCharCode(p.uni) })));
  }

  // A name for a part of a letter, from its role (see pointRoles), for the letter editor.
  function partName(role) {
    if (!role) return "";
    const [zone, dirs, ctl] = role.split("|");
    const [din, dout] = dirs.split(">");
    const side = { L: "משמאל", R: "מימין", C: "באמצע" }[zone.slice(-1)];
    const z = zone.slice(0, -1);
    const end = din === "o" || dout === "o";
    const d = end ? (din === "o" ? dout : din) : "";
    const flat = d === "R" || d === "L";
    let name;
    if (end) {
      if (z === "asc") name = "ראש הלמ״ד";
      else if (z === "desc") name = "קצה הזנב";
      else if (z === "top") name = flat ? "קצה הגג " + side : "ראש הקו " + side;
      else if (z === "base") name = flat ? "קצה הבסיס " + side : "רגל " + side;
      else name = "קצה הקו " + side;
    } else if (z === "top") name = "הפינה העליונה " + side;
    else if (z === "base") name = "הפינה התחתונה " + side;
    else name = "כיפוף " + side;
    return ctl ? "העיקול של " + name : name;
  }

  // Checks of the letters against the usual shape of Hebrew letters, for the letter editor:
  // a letter much wider or narrower than its usual width, or reaching out of its lines.
  function checkLetters(prmIn) {
    const prm = Object.assign({}, DEFAULTS, prmIn || {});
    const names = Object.keys(prm.edits || {}).filter((n) => HEBREW.some((h) => h[0] === n));
    if (!names.length) return [];
    const now = buildGlyphs(prm, { only: names, bare: true }).glyphs;
    const was = buildGlyphs(Object.assign({}, prm, { edits: {} }), { only: names, bare: true }).glyphs;
    const H = prm.height, out = [];
    const bounds = (g) => {
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      for (const c of g.contours) for (const sg of c) for (const p of sg) {
        x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]);
      }
      return { w: x1 - x0, y0, y1 };
    };
    now.forEach((g, i) => {
      const a = bounds(g), b = bounds(was[i]);
      const r = a.w / b.w;
      if (r > 1.3) out.push({ name: g.name, text: "רחבה בהרבה מהרגיל (" + Math.round(r * 100) + "%)" });
      else if (r < 0.75) out.push({ name: g.name, text: "צרה בהרבה מהרגיל (" + Math.round(r * 100) + "%)" });
      if (a.y1 > b.y1 + H * 0.2) out.push({ name: g.name, text: "בולטת מעל השורה" });
      if (a.y0 < b.y0 - H * 0.2) out.push({ name: g.name, text: "יורדת מתחת לשורה" });
    });
    return out;
  }

  // All glyphs of the font with their outlines (overlapping contours) and anchors.
  // opts.only: build just this glyph (for the letter editor), with its skeleton; or a list of
  // glyphs, without skeletons. opts.bare: no marks, space or .notdef.
  function buildGlyphs(prmIn, opts) {
    opts = opts || {};
    const list = Array.isArray(opts.only) ? opts.only : null;
    const only = list ? null : opts.only;
    const skip = (name) => (list ? !list.includes(name) : only && name !== only);
    const bare = !!(only || list || opts.bare);
    const prm = Object.assign({}, DEFAULTS, prmIn || {});
    const c = makeCtx(prm);
    const sb = Math.round((0.045 * c.H + 0.3 * c.T) * prm.spacing);
    const sl = Math.tan((prm.slant * Math.PI) / 180);
    const skew = (p) => [p[0] + p[1] * sl, p[1]];
    const glyphs = [];

    function add(name, uni, width, draw, opts) {
      opts = opts || {};
      if (skip(name)) return;
      const cc = opts.swap ? Object.assign({}, c, { t: c.H - c.S / 2, b: c.S / 2 }) : c;
      const d = new Drawing(cc, width);
      if (opts.swap) d.swap = true;
      draw(d, cc);
      const edits = prm.edits && prm.edits[name];
      if (edits) applyEdits(d, edits);
      let contours = drawingContours(d);
      // the side bearings are measured from the ink
      let x0 = Infinity, x1 = -Infinity;
      for (const ct of contours) for (const sg of ct) for (let i = 0; i <= 6; i++) {
        const x = cubicAt(sg, i / 6)[0];
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
      }
      if (!isFinite(x0)) { x0 = 0; x1 = width; }
      const left = sb - x0;
      width = x1 - x0;
      contours = transform(contours, (p) => skew([p[0] + left, p[1]]));
      const anchors = {};
      const below = d.anchors.below || [d.W / 2, 0];
      anchors.below = [below[0], below[1] - c.gap];
      anchors.dagesh = d.anchors.dagesh || [d.W / 2, c.H * 0.45];
      const al = d.anchors.aboveLeft || [Math.min(d.W * 0.15, c.H * 0.1), c.H];
      anchors.aboveLeft = [al[0], al[1] + c.gap];
      const ar = d.anchors.aboveRight || [d.W - Math.min(d.W * 0.15, c.H * 0.1), c.H];
      anchors.aboveRight = [ar[0], ar[1] + c.gap];
      anchors.above = [d.W / 2, c.H + c.gap];
      for (const k in anchors) anchors[k] = skew([anchors[k][0] + left, anchors[k][1]]).map(Math.round);
      const g = {
        name, unicode: uni, advance: Math.round(width + 2 * sb), contours,
        anchors: opts.base ? anchors : null,
      };
      if (only) {
        // the skeleton, where it is drawn: [{x, y, on}] per stroke, and how to turn a move on
        // the screen back into a move of the point
        g.skeleton = d.strokes.map((st) => ({
          points: pathPoints(st.path).map((pt) => {
            const [x, y] = skew([pt.get()[0] + left, pt.get()[1]]);
            return { x, y, on: pt.on };
          }),
          segs: st.path.segs.map((sg) => sg.t),
        }));
        g.slant = sl;
        g.T = c.T;
        g.H = c.H;
        g.D = c.D;
        g.A = c.A;
      }
      glyphs.push(g);
    }

    // .notdef: an empty box
    if (!bare) {
      const w = c.H * 0.6, th = Math.max(20, c.S);
      glyphs.push({
        name: ".notdef", unicode: undefined, advance: Math.round(w + 2 * sb),
        contours: transform([
          polygon([[0, 0], [w, 0], [w, c.H], [0, c.H]]),
          reverseContour(polygon([[th, th], [w - th, th], [w - th, c.H - th], [th, c.H - th]])),
        ], (p) => [p[0] + sb, p[1]]),
        anchors: null,
      });
    }
    if (!bare) glyphs.push({ name: "space", unicode: 0x20, advance: Math.round(c.H * 0.42 * prm.spacing ** 0.5), contours: [], anchors: null });

    const set = letterSet(prm);
    for (const [name, uni] of HEBREW) {
      add(name, uni, set.widths[name] * c.H * prm.width, set.letters[name], { base: true });
    }
    const dn = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
    dn.forEach((n, i) => add(n, 0x30 + i, c.H * 0.6 * prm.width, DIGITS[n], { swap: true }));
    for (const p of PUNCT) add(p.name, p.uni, p.width(c), p.draw);

    // Vowel points: no width of their own; they are placed on the letter by the 'mark' feature.
    const marks = bare ? {} : markShapes(c);
    for (const name in marks) {
      const [uni, cls, shapes] = marks[name];
      glyphs.push({
        name, unicode: uni, advance: 0, mark: cls,
        contours: transform(shapes.map((s) => (contourArea(s) < 0 ? reverseContour(s) : s)), skew),
        anchors: null,
      });
    }
    return { glyphs, ctx: c, prm };
  }

  // ---------------------------------------------------------------- outlines

  // The strokes overlap; the font gets one clean outline. The contours are turned into fine
  // polygons, joined with Clipper (exact, in integers), and smooth curves are fitted back onto them.

  let paperReady = false;
  function ensurePaper() {
    if (!paperReady) {
      paper.setup(new paper.Size(10, 10));
      paperReady = true;
    }
  }

  const SCALE = 64;

  function isLineSeg(s) {
    const dx = s[3][0] - s[0][0], dy = s[3][1] - s[0][1];
    const l = Math.hypot(dx, dy) || 1;
    const off = (p) => Math.abs((p[0] - s[0][0]) * dy - (p[1] - s[0][1]) * dx) / l;
    return off(s[1]) < 0.05 && off(s[2]) < 0.05;
  }

  function flatten(contour) {
    const pts = [];
    for (const s of contour) {
      if (isLineSeg(s)) {
        pts.push(s[3]);
        continue;
      }
      const len = Math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) + Math.hypot(s[2][0] - s[1][0], s[2][1] - s[1][1]) +
        Math.hypot(s[3][0] - s[2][0], s[3][1] - s[2][1]);
      const n = Math.max(2, Math.min(96, Math.ceil(len / 4)));
      for (let i = 1; i <= n; i++) pts.push(cubicAt(s, i / n));
    }
    return pts.map((p) => ({ X: Math.round(p[0] * SCALE), Y: Math.round(p[1] * SCALE) }));
  }

  // Smooth curves through a closed polygon: straight edges stay straight, sharp corners stay
  // sharp, and the runs of short edges in between become curves.
  function fitContour(poly) {
    const P = poly.map((p) => [p.X / SCALE, p.Y / SCALE]);
    const n = P.length;
    if (n < 3) return null;
    const len = (i) => { const a = P[i], b = P[(i + 1) % n]; return Math.hypot(b[0] - a[0], b[1] - a[1]); };
    const isBreak = new Array(n).fill(false);
    for (let i = 0; i < n; i++) {
      const a = P[(i - 1 + n) % n], b = P[i], c = P[(i + 1) % n];
      const d1 = [b[0] - a[0], b[1] - a[1]], d2 = [c[0] - b[0], c[1] - b[1]];
      const ang = Math.abs(Math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1]));
      if (ang > 0.45 || len(i) > 9 || len((i - 1 + n) % n) > 9) isBreak[i] = true;
    }
    let first = isBreak.indexOf(true);
    if (first < 0) {
      // no corner at all (a dot): break at the leftmost and rightmost points
      let lo = 0, hi = 0;
      for (let i = 0; i < n; i++) {
        if (P[i][0] < P[lo][0]) lo = i;
        if (P[i][0] > P[hi][0]) hi = i;
      }
      isBreak[lo] = isBreak[hi] = true;
      first = Math.min(lo, hi);
    }
    const out = [];
    let i = first;
    do {
      let j = (i + 1) % n;
      const run = [P[i]];
      while (!isBreak[j]) { run.push(P[j]); j = (j + 1) % n; }
      run.push(P[j]);
      if (run.length <= 3) {
        for (let k = 0; k + 1 < run.length; k++) out.push(lineSeg(run[k], run[k + 1]));
      } else {
        const p = new paper.Path({ segments: run.map((q) => new paper.Point(q[0], q[1])), insert: false });
        p.simplify(0.35);
        const sg = p.segments;
        for (let k = 0; k + 1 < sg.length; k++) {
          const a = sg[k], b = sg[k + 1];
          out.push([[a.point.x, a.point.y], [a.point.x + a.handleOut.x, a.point.y + a.handleOut.y],
            [b.point.x + b.handleIn.x, b.point.y + b.handleIn.y], [b.point.x, b.point.y]]);
        }
      }
      i = j;
    } while (i !== first);
    return out;
  }

  function unite(contours) {
    if (contours.length === 0) return contours;
    ensurePaper();
    try {
      const C = ClipperLib;
      const cl = new C.Clipper();
      cl.AddPaths(contours.map(flatten), C.PolyType.ptSubject, true);
      const sol = [];
      cl.Execute(C.ClipType.ctUnion, sol, C.PolyFillType.pftNonZero, C.PolyFillType.pftNonZero);
      const clean = C.Clipper.CleanPolygons(sol, 0.1 * SCALE);
      const out = [];
      for (const poly of clean) {
        if (Math.abs(C.Clipper.Area(poly)) < 4 * SCALE * SCALE) continue;
        const c = fitContour(poly);
        if (c && c.length) out.push(c);
      }
      return out.length ? out : contours;
    } catch (e) {
      return contours;
    }
  }

  // ---------------------------------------------------------------- the font file

  function asciiName(s, fallback) {
    const t = String(s || "").replace(/[^A-Za-z0-9 ]/g, "").replace(/\s+/g, " ").trim();
    return t || fallback;
  }

  // Builds the font. merge: join the overlapping strokes (slower, for the file to download).
  function makeFont(prmIn, opts) {
    opts = opts || {};
    const { glyphs, ctx } = buildGlyphs(prmIn);
    const family = asciiName(opts.family, "My Hebrew");
    const style = asciiName(opts.style, "Regular");
    const otGlyphs = glyphs.map((g) => {
      const contours = opts.merge ? unite(g.contours) : g.contours;
      const path = new opentype.Path();
      for (const c of contours) {
        const r = (v) => Math.round(v);
        path.moveTo(r(c[0][0][0]), r(c[0][0][1]));
        for (const s of c) {
          const isLine = Math.abs((s[1][0] - s[0][0]) * (s[3][1] - s[0][1]) - (s[1][1] - s[0][1]) * (s[3][0] - s[0][0])) < 1 &&
            Math.abs((s[2][0] - s[0][0]) * (s[3][1] - s[0][1]) - (s[2][1] - s[0][1]) * (s[3][0] - s[0][0])) < 1;
          if (isLine) path.lineTo(r(s[3][0]), r(s[3][1]));
          else path.curveTo(r(s[1][0]), r(s[1][1]), r(s[2][0]), r(s[2][1]), r(s[3][0]), r(s[3][1]));
        }
        path.close();
      }
      return new opentype.Glyph({ name: g.name, unicode: g.unicode, advanceWidth: g.advance, path });
    });
    const ascender = Math.round(ctx.H + Math.max(ctx.A, ctx.H * 0.34) + ctx.H * 0.08);
    const descender = -Math.round(Math.max(ctx.D, ctx.H * 0.36) + ctx.H * 0.08);
    const font = new opentype.Font({
      familyName: family,
      styleName: style,
      unitsPerEm: UPM,
      ascender,
      descender,
      designer: opts.designer || "",
      version: "1.000",
      glyphs: otGlyphs,
    });
    font.names.postScriptName = { en: (family + "-" + style).replace(/\s/g, "") };
    font.names.copyright = { en: opts.copyright || ("Made with the Hebrew font maker. Free to use.") };
    const bold = style.toLowerCase() === "bold";
    let yMax = ascender, yMin = descender;
    for (const g of glyphs) for (const c of g.contours) for (const sg of c) for (const p of sg) {
      if (p[1] > yMax) yMax = p[1];
      if (p[1] < yMin) yMin = p[1];
    }
    const wd = ctx.prm.width;
    font.tables.os2 = {
      ulCodePageRange1: (1 << 0) | (1 << 5), // Latin 1, Hebrew
      usWeightClass: bold ? 700 : Math.round(Math.min(900, Math.max(100, (ctx.prm.weight - 0.05) / 0.2 * 800 + 100)) / 100) * 100,
      usWidthClass: wd < 0.8 ? 3 : wd < 0.92 ? 4 : wd < 1.08 ? 5 : wd < 1.2 ? 6 : 7,
      fsSelection: (bold ? 0x20 : 0x40) | 0x80, // bold or regular; use the typo metrics
      usWinAscent: Math.ceil(yMax + ctx.H * 0.12),
      usWinDescent: Math.ceil(-yMin + ctx.H * 0.06),
      achVendID: "HFMK",
    };
    let buf = font.toArrayBuffer();
    buf = addLayoutTables(buf, glyphs, bold);
    return buf;
  }

  // ---------------------------------------------------------------- GDEF and GPOS

  class Bytes {
    constructor() { this.a = []; }
    u16(v) { v &= 0xffff; this.a.push(v >> 8, v & 0xff); return this; }
    s16(v) { return this.u16(v < 0 ? v + 0x10000 : v); }
    u32(v) { this.u16((v >>> 16) & 0xffff); return this.u16(v & 0xffff); }
    tag(s) { for (let i = 0; i < 4; i++) this.a.push(s.charCodeAt(i)); return this; }
    bytes(b) { for (const x of b) this.a.push(x); return this; }
    get length() { return this.a.length; }
  }

  function coverage(gids) {
    const b = new Bytes().u16(1).u16(gids.length);
    gids.forEach((g) => b.u16(g));
    return b.a;
  }

  function anchor(x, y) { return new Bytes().u16(1).s16(x).s16(y).a; }

  function makeGDEF(glyphs) {
    // Glyph classes: 1 base, 3 mark.
    const b = new Bytes().u16(1).u16(0).u16(12).u16(0).u16(0).u16(0);
    b.u16(1).u16(0).u16(glyphs.length);
    glyphs.forEach((g) => b.u16(g.mark ? 3 : g.anchors ? 1 : 0));
    return b.a;
  }

  function makeGPOS(glyphs) {
    const marks = [], bases = [];
    glyphs.forEach((g, i) => {
      if (g.mark) marks.push(i);
      else if (g.anchors) bases.push(i);
    });
    const nCls = MARK_CLASSES.length;
    // MarkBasePos format 1
    const markCov = coverage(marks);
    const baseCov = coverage(bases);
    // MarkArray
    const markArr = new Bytes().u16(marks.length);
    let off = 2 + marks.length * 4;
    const markAnchors = [];
    for (const gi of marks) {
      markArr.u16(MARK_CLASSES.indexOf(glyphs[gi].mark)).u16(off);
      const a = anchor(0, 0);
      markAnchors.push(a);
      off += a.length;
    }
    markAnchors.forEach((a) => markArr.bytes(a));
    // BaseArray
    const baseArr = new Bytes().u16(bases.length);
    off = 2 + bases.length * nCls * 2;
    const baseAnchors = [];
    for (const gi of bases) {
      for (const cls of MARK_CLASSES) {
        const p = glyphs[gi].anchors[cls];
        baseArr.u16(off);
        const a = anchor(p[0], p[1]);
        baseAnchors.push(a);
        off += a.length;
      }
    }
    baseAnchors.forEach((a) => baseArr.bytes(a));
    const sub = new Bytes();
    const hdr = 12;
    sub.u16(1).u16(hdr).u16(hdr + markCov.length).u16(nCls)
      .u16(hdr + markCov.length + baseCov.length)
      .u16(hdr + markCov.length + baseCov.length + markArr.length);
    sub.bytes(markCov).bytes(baseCov).bytes(markArr.a).bytes(baseArr.a);

    // Lookup list with one lookup
    const lookup = new Bytes().u16(4).u16(0).u16(1).u16(8).bytes(sub.a);
    const lookupList = new Bytes().u16(1).u16(4).bytes(lookup.a);
    // Feature list: 'mark' -> lookup 0
    const feature = new Bytes().u16(0).u16(1).u16(0);
    const featureList = new Bytes().u16(1).tag("mark").u16(8).bytes(feature.a);
    // Script list: DFLT and hebr, each with a default LangSys using feature 0
    const langSys = new Bytes().u16(0).u16(0xffff).u16(1).u16(0);
    const script = new Bytes().u16(4).u16(0).bytes(langSys.a);
    const scriptList = new Bytes().u16(2);
    const sOff1 = 2 + 2 * 6;
    scriptList.tag("DFLT").u16(sOff1).tag("hebr").u16(sOff1 + script.length);
    scriptList.bytes(script.a).bytes(script.a);

    const gpos = new Bytes();
    const h = 10;
    gpos.u16(1).u16(0).u16(h).u16(h + scriptList.length).u16(h + scriptList.length + featureList.length);
    gpos.bytes(scriptList.a).bytes(featureList.a).bytes(lookupList.a);
    return gpos.a;
  }

  // Adds GDEF and GPOS to the font file made by opentype.js.
  function addLayoutTables(buf, glyphs, bold) {
    const dv = new DataView(buf);
    const numTables = dv.getUint16(4);
    const tables = [];
    for (let i = 0; i < numTables; i++) {
      const o = 12 + i * 16;
      const tag = String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3));
      const offset = dv.getUint32(o + 8), length = dv.getUint32(o + 12);
      tables.push({ tag, data: new Uint8Array(buf, offset, length).slice() });
    }
    tables.push({ tag: "GDEF", data: Uint8Array.from(makeGDEF(glyphs)) });
    tables.push({ tag: "GPOS", data: Uint8Array.from(makeGPOS(glyphs)) });
    tables.sort((a, b) => (a.tag < b.tag ? -1 : a.tag > b.tag ? 1 : 0));
    const head = tables.find((t) => t.tag === "head");
    head.data[8] = head.data[9] = head.data[10] = head.data[11] = 0;
    if (bold) head.data[45] |= 1; // macStyle: bold

    const n = tables.length;
    let size = 12 + n * 16;
    for (const t of tables) size += (t.data.length + 3) & ~3;
    const out = new ArrayBuffer(size);
    const o = new DataView(out);
    const bytes = new Uint8Array(out);
    o.setUint32(0, dv.getUint32(0));
    o.setUint16(4, n);
    let es = 0;
    while ((1 << (es + 1)) <= n) es++;
    o.setUint16(6, (1 << es) * 16);
    o.setUint16(8, es);
    o.setUint16(10, n * 16 - (1 << es) * 16);
    const sum = (data) => {
      let s = 0;
      const len = (data.length + 3) & ~3;
      for (let i = 0; i < len; i += 4) {
        s = (s + (((data[i] || 0) << 24) | ((data[i + 1] || 0) << 16) | ((data[i + 2] || 0) << 8) | (data[i + 3] || 0))) >>> 0;
      }
      return s;
    };
    let pos = 12 + n * 16;
    tables.forEach((t, i) => {
      const r = 12 + i * 16;
      for (let k = 0; k < 4; k++) bytes[r + k] = t.tag.charCodeAt(k);
      o.setUint32(r + 4, sum(t.data));
      o.setUint32(r + 8, pos);
      o.setUint32(r + 12, t.data.length);
      bytes.set(t.data, pos);
      t.pos = pos;
      pos += (t.data.length + 3) & ~3;
    });
    const total = sum(bytes);
    o.setUint32(head.pos + 8, (0xb1b0afba - total) >>> 0);
    return out;
  }

  addLetterSet("square", {
    name: "מרובע",
    about: "אותיות ישרות ומרובעות, כמו שלט",
    widths: Object.fromEntries(HEBREW.map(([n, , f]) => [n, f])),
    letters: LETTERS,
    defaults: { round: 0.2, serif: 0.5, headShape: 0.3 },
  });

  global.FontMaker = { DEFAULTS, buildGlyphs, makeFont, unite, editableGlyphs, styleFrom, pointRoles, partName, checkLetters, addLetterSet, letterSets };
})(typeof window !== "undefined" ? window : globalThis);
