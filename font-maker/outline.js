// Changing an existing font: the letters of a real font, made bolder or lighter, wider or
// narrower, slanted, taller, rounder, with more or less space, one letter or all of them.
//
// The outlines are moved exactly (an affine change moves the Bezier points); weight and roundness
// grow or shrink the outline with Clipper, and smooth curves are fitted back. The vowel points
// keep their places: the font's own anchors (its GPOS 'mark' and 'mkmk' tables) are read and
// moved with the letters, and its GDEF and GSUB tables are kept as they are (the glyphs keep
// their numbers).
(function () {
  "use strict";

  const G = FontMaker.geom;

  const SETTINGS = {
    weight: 0,     // -0.8 .. 1.5: thinner or bolder
    contrast: 0,   // -1 .. 1: thicker horizontal strokes than vertical ones, or the other way
    width: 1,      // 0.7 .. 1.4
    height: 1,     // 0.8 .. 1.25
    slant: 0,      // degrees
    spacing: 1,    // 0.6 .. 1.8
    round: 0,      // 0 .. 1: roundness of the corners
    letters: {},   // per glyph name: {width, height, weight, shift}
  };

  // ---------------------------------------------------------------- reading the font

  function u16(b, o) { return (b[o] << 8) | b[o + 1]; }
  function s16(b, o) { const v = u16(b, o); return v > 32767 ? v - 65536 : v; }
  function u32(b, o) { return ((b[o] << 24) >>> 0) + (b[o + 1] << 16) + (b[o + 2] << 8) + b[o + 3]; }

  function parseCoverage(b, o) {
    const fmt = u16(b, o), out = [];
    if (fmt === 1) {
      const n = u16(b, o + 2);
      for (let i = 0; i < n; i++) out.push(u16(b, o + 4 + i * 2));
    } else if (fmt === 2) {
      const n = u16(b, o + 2);
      for (let i = 0; i < n; i++) {
        const r = o + 4 + i * 6, start = u16(b, r), end = u16(b, r + 2);
        for (let g = start; g <= end; g++) out.push(g);
      }
    }
    return out;
  }

  function parseClassDef(b, o) {
    const out = {}, fmt = u16(b, o);
    if (fmt === 1) {
      const start = u16(b, o + 2), n = u16(b, o + 4);
      for (let i = 0; i < n; i++) out[start + i] = u16(b, o + 6 + i * 2);
    } else if (fmt === 2) {
      const n = u16(b, o + 2);
      for (let i = 0; i < n; i++) {
        const r = o + 4 + i * 6;
        for (let g = u16(b, r); g <= u16(b, r + 2); g++) out[g] = u16(b, r + 4);
      }
    }
    return out;
  }

  const anchorAt = (b, o) => [s16(b, o + 2), s16(b, o + 4)];

  // MarkBasePos and MarkMarkPos (format 1) have the same shape: marks with a class and an anchor,
  // and glyphs they attach to with one anchor per class.
  function parseAttach(b, o) {
    if (u16(b, o) !== 1) return null;
    const markCov = parseCoverage(b, o + u16(b, o + 2));
    const baseCov = parseCoverage(b, o + u16(b, o + 4));
    const classCount = u16(b, o + 6);
    const ma = o + u16(b, o + 8), ba = o + u16(b, o + 10);
    const marks = new Map(), bases = new Map();
    markCov.forEach((g, i) => {
      const r = ma + 2 + i * 4;
      marks.set(g, [u16(b, r), ...anchorAt(b, ma + u16(b, r + 2))]);
    });
    baseCov.forEach((g, i) => {
      const r = ba + 2 + i * classCount * 2, list = [];
      for (let c = 0; c < classCount; c++) {
        const off = u16(b, r + c * 2);
        list.push(off ? anchorAt(b, ba + off) : null);
      }
      bases.set(g, list);
    });
    return { classCount, marks, bases };
  }

  // The 'mark' and 'mkmk' lookups of a GPOS table.
  function parseGPOS(b) {
    const out = { mark: [], mkmk: [] };
    if (!b) return out;
    const fl = u16(b, 6), ll = u16(b, 8);
    const want = { mark: new Set(), mkmk: new Set() };
    for (let i = 0; i < u16(b, fl); i++) {
      const r = fl + 2 + i * 6;
      const tag = String.fromCharCode(b[r], b[r + 1], b[r + 2], b[r + 3]);
      if (!want[tag]) continue;
      const f = fl + u16(b, r + 4);
      for (let k = 0; k < u16(b, f + 2); k++) want[tag].add(u16(b, f + 4 + k * 2));
    }
    for (const tag of ["mark", "mkmk"]) {
      for (const li of [...want[tag]].sort((x, y) => x - y)) {
        const lo = ll + u16(b, ll + 2 + li * 2);
        let type = u16(b, lo);
        const flag = u16(b, lo + 2), n = u16(b, lo + 4);
        const filter = flag & 0x10 ? u16(b, lo + 6 + n * 2) : null;
        const subs = [];
        for (let k = 0; k < n; k++) {
          let so = lo + u16(b, lo + 6 + k * 2), t = type;
          if (t === 9) { t = u16(b, so + 2); so += u32(b, so + 4); }
          if (t === 4 || t === 6) {
            const sub = parseAttach(b, so);
            if (sub) subs.push(sub);
            type = t;
          }
        }
        if (subs.length) out[tag].push({ type, flag, filter, subs });
      }
    }
    return out;
  }

  // The outline of a glyph as cubic contours.
  function glyphContours(g) {
    const out = [];
    let cur = null, start = null, contour = null;
    for (const c of g.path.commands) {
      if (c.type === "M") {
        if (contour && contour.length) out.push(contour);
        contour = [];
        cur = start = [c.x, c.y];
      } else if (c.type === "L") {
        contour.push(G.lineSeg(cur, [c.x, c.y]));
        cur = [c.x, c.y];
      } else if (c.type === "Q") {
        const p = [c.x, c.y], q = [c.x1, c.y1];
        contour.push([cur, [cur[0] + (q[0] - cur[0]) * 2 / 3, cur[1] + (q[1] - cur[1]) * 2 / 3],
          [p[0] + (q[0] - p[0]) * 2 / 3, p[1] + (q[1] - p[1]) * 2 / 3], p]);
        cur = p;
      } else if (c.type === "C") {
        contour.push([cur, [c.x1, c.y1], [c.x2, c.y2], [c.x, c.y]]);
        cur = [c.x, c.y];
      } else if (c.type === "Z") {
        if (contour && cur && start && Math.hypot(cur[0] - start[0], cur[1] - start[1]) > 0.01) contour.push(G.lineSeg(cur, start));
        if (contour && contour.length) out.push(contour);
        contour = null;
        cur = start;
      }
    }
    if (contour && contour.length) out.push(contour);
    return out;
  }

  function bbox(contours) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const c of contours) for (const s of c) for (let i = 0; i <= 4; i++) {
      const p = G.cubicAt(s, i / 4);
      if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
    }
    return isFinite(x0) ? { x0, y0, x1, y1 } : null;
  }

  const isHebrewMark = (u) => u >= 0x591 && u <= 0x5c7 && ![0x5be, 0x5c0, 0x5c3, 0x5c6].includes(u);

  // Reads a font file into what the changes work on.
  function load(buffer, meta) {
    const font = opentype.parse(buffer);
    const tables = G.readTables(buffer);
    let classes = {};
    if (tables.GDEF) {
      const off = u16(tables.GDEF, 4);
      if (off) classes = parseClassDef(tables.GDEF, off);
    }
    const glyphs = [];
    for (let i = 0; i < font.glyphs.length; i++) {
      const g = font.glyphs.get(i);
      const unicodes = g.unicodes && g.unicodes.length ? g.unicodes.filter((u) => u !== undefined) : (g.unicode !== undefined ? [g.unicode] : []);
      glyphs.push({
        name: g.name || "glyph" + i,
        unicodes,
        advance: g.advanceWidth || 0,
        contours: glyphContours(g),
        mark: classes[i] === 3 || unicodes.some(isHebrewMark),
      });
    }
    const byChar = {};
    glyphs.forEach((g, i) => g.unicodes.forEach((u) => { byChar[u] = i; }));
    const he = byChar[0x5d4] !== undefined && bbox(glyphs[byChar[0x5d4]].contours);
    const name = (id) => {
      const n = font.names[id];
      return n ? (n.en || Object.values(n)[0] || "") : "";
    };
    return {
      meta: meta || {},
      upm: font.unitsPerEm,
      ascender: font.ascender,
      descender: font.descender,
      glyphs, byChar,
      H: he ? he.y1 : font.unitsPerEm * 0.6,
      gpos: parseGPOS(tables.GPOS),
      gdef: tables.GDEF || null,
      gsub: tables.GSUB || null,
      names: {
        family: name("fontFamily"), copyright: name("copyright"), designer: name("designer"),
        license: name("license"), licenseURL: name("licenseURL"), trademark: name("trademark"),
      },
    };
  }

  // ---------------------------------------------------------------- the changes

  function clamp(v, a, b) { return Math.min(b, Math.max(a, v)); }

  // The change of every glyph: an affine move (x' = sx x + k y' + dx, y' = sy y + dy),
  // the growth of its strokes, and its new width.
  function glyphChange(model, S, i) {
    const g = model.glyphs[i];
    const L = (S.letters && S.letters[g.name]) || {};
    const sx = S.width * (L.width || 1);
    const sy = S.height * (L.height || 1);
    const k = Math.tan((S.slant * Math.PI) / 180);
    const dsb = g.mark || !g.advance ? 0 : (S.spacing - 1) * 0.05 * model.upm;
    const dy = (L.shift || 0) * model.H;
    const unit = 0.03 * model.upm;
    const w = (S.weight + (L.weight || 0)) * (g.mark ? 0.6 : 1);
    // thinning eats the hairlines quickly, so it goes slower than thickening
    const soft = (v) => (v < 0 ? v * 0.45 : v) * unit;
    return {
      sx, sy, k, dx: dsb, dy,
      dv: soft(w - S.contrast * 0.5),  // grows the vertical strokes (sideways)
      dh: soft(w + S.contrast * 0.5),  // grows the horizontal strokes (up and down)
      r: S.round * 0.02 * model.upm,
      advance: g.advance ? Math.max(0, Math.round(g.advance * sx + 2 * dsb)) : 0,
    };
  }

  const movePoint = (t, p) => {
    const y = p[1] * t.sy + t.dy;
    return [p[0] * t.sx + y * t.k + t.dx, y];
  };

  // Grows the outline sideways by dv and up and down by dh (negative: shrinks), then rounds
  // its corners by r. Returns cubic contours, or polygons when fit is false.
  function growOutline(contours, t, fit) {
    const C = ClipperLib, SC = G.SCALE;
    let paths = contours.map(G.flatten);
    const clean = () => {
      const cl = new C.Clipper();
      cl.AddPaths(paths, C.PolyType.ptSubject, true);
      const sol = [];
      cl.Execute(C.ClipType.ctUnion, sol, C.PolyFillType.pftNonZero, C.PolyFillType.pftNonZero);
      paths = sol;
    };
    clean();
    // offset in a space stretched along the other axis, so it grows only one way
    const grow = (d, axis, join) => {
      if (Math.abs(d) < 0.3) return;
      const K = axis === "x" ? 6 : 1 / 6;
      const st = paths.map((p) => p.map((q) => ({ X: axis === "x" ? q.X : q.X / K, Y: axis === "x" ? q.Y * K : q.Y })));
      const co = new C.ClipperOffset(3, 0.2 * SC);
      co.AddPaths(st, join, C.EndType.etClosedPolygon);
      const sol = [];
      co.Execute(sol, d * SC);
      paths = sol.map((p) => p.map((q) => ({ X: axis === "x" ? q.X : Math.round(q.X * K), Y: axis === "x" ? Math.round(q.Y / K) : q.Y })));
    };
    grow(t.dv, "x", C.JoinType.jtMiter);
    grow(t.dh, "y", C.JoinType.jtMiter);
    if (t.r > 0.5) {
      const round = (d) => {
        const co = new C.ClipperOffset(2, 0.6 * SC);
        co.AddPaths(paths, C.JoinType.jtRound, C.EndType.etClosedPolygon);
        const sol = [];
        co.Execute(sol, d * SC);
        paths = sol;
      };
      round(-t.r); round(t.r);   // the outer corners
      round(t.r); round(-t.r);   // the inner corners
    }
    paths = C.Clipper.CleanPolygons(paths, 0.1 * SC).filter((p) => p.length > 2 && Math.abs(C.Clipper.Area(p)) > 4 * SC * SC);
    if (fit) {
      G.ensurePaper();
      return paths.map((p) => G.fitContour(p)).filter((c) => c && c.length);
    }
    return paths.map((p) => p.map((q, i) => G.lineSeg([q.X / SC, q.Y / SC], [p[(i + 1) % p.length].X / SC, p[(i + 1) % p.length].Y / SC])));
  }

  // ---------------------------------------------------------------- GPOS

  function writeGPOS(lookups, glyphChanges) {
    const B = G.Bytes;
    const subtable = (sub) => {
      const marks = [...sub.marks.keys()].sort((a, b) => a - b);
      const bases = [...sub.bases.keys()].sort((a, b) => a - b);
      const mc = G.coverage(marks), bc = G.coverage(bases);
      const ma = new B().u16(marks.length);
      let off = 2 + marks.length * 4;
      const anchors = [];
      for (const g of marks) {
        const [cls, x, y] = sub.marks.get(g);
        const p = glyphChanges[g] ? movePoint(glyphChanges[g], [x, y]) : [x, y];
        ma.u16(cls).u16(off);
        anchors.push(G.anchor(Math.round(p[0]), Math.round(p[1])));
        off += 6;
      }
      anchors.forEach((a) => ma.bytes(a));
      const ba = new B().u16(bases.length);
      off = 2 + bases.length * sub.classCount * 2;
      const banch = [];
      for (const g of bases) {
        for (const a of sub.bases.get(g)) {
          if (!a) { ba.u16(0); continue; }
          const p = glyphChanges[g] ? movePoint(glyphChanges[g], a) : a;
          ba.u16(off);
          banch.push(G.anchor(Math.round(p[0]), Math.round(p[1])));
          off += 6;
        }
      }
      banch.forEach((a) => ba.bytes(a));
      const h = 12;
      return new B().u16(1).u16(h).u16(h + mc.length).u16(sub.classCount).u16(h + mc.length + bc.length)
        .u16(h + mc.length + bc.length + ma.length).bytes(mc).bytes(bc).bytes(ma.a).bytes(ba.a).a;
    };
    // every lookup as an Extension lookup, so its subtables may be far away (32-bit offsets)
    const all = [...lookups.mark.map((l) => ["mark", l]), ...lookups.mkmk.map((l) => ["mkmk", l])];
    const lookupBytes = all.map(([, l]) => {
      const subs = l.subs.map(subtable);
      const n = subs.length;
      const head = 6 + n * 2 + (l.filter !== null ? 2 : 0);
      const lk = new B().u16(9).u16(l.flag).u16(n);
      for (let k = 0; k < n; k++) lk.u16(head + k * 8);
      if (l.filter !== null) lk.u16(l.filter);
      const exts = [];
      for (let k = 0; k < n; k++) {
        // the extension subtable k sits at head + k*8; its target after all of them
        const extStart = head + k * 8;
        const target = head + n * 8 + exts.reduce((a, s) => a + s.length, 0);
        lk.u16(1).u16(l.type).u32(target - extStart);
        exts.push(subs[k]);
      }
      exts.forEach((s) => lk.bytes(s));
      return lk.a;
    });
    const ll = new B().u16(lookupBytes.length);
    let off = 2 + lookupBytes.length * 2;
    for (const lb of lookupBytes) { ll.u16(off); off += lb.length; }
    lookupBytes.forEach((lb) => ll.bytes(lb));
    // features: mark and mkmk
    const feats = [];
    const markIdx = all.map((a, i) => (a[0] === "mark" ? i : -1)).filter((i) => i >= 0);
    const mkmkIdx = all.map((a, i) => (a[0] === "mkmk" ? i : -1)).filter((i) => i >= 0);
    if (markIdx.length) feats.push(["mark", markIdx]);
    if (mkmkIdx.length) feats.push(["mkmk", mkmkIdx]);
    const fl = new B().u16(feats.length);
    off = 2 + feats.length * 6;
    const fb = feats.map(([, idx]) => { const b = new B().u16(0).u16(idx.length); idx.forEach((i) => b.u16(i)); return b.a; });
    feats.forEach(([tag], i) => { fl.tag(tag).u16(off); off += fb[i].length; });
    fb.forEach((b) => fl.bytes(b));
    // scripts: DFLT, hebr and latn, all with every feature
    const ls = new B().u16(0).u16(0xffff).u16(feats.length);
    feats.forEach((f, i) => ls.u16(i));
    const script = new B().u16(4).u16(0).bytes(ls.a);
    const tags = ["DFLT", "hebr", "latn"];
    const sl = new B().u16(tags.length);
    tags.forEach((t, i) => sl.tag(t).u16(2 + tags.length * 6 + i * script.length));
    tags.forEach(() => sl.bytes(script.a));
    const gp = new B().u16(1).u16(0).u16(10).u16(10 + sl.length).u16(10 + sl.length + fl.length);
    gp.bytes(sl.a).bytes(fl.a).bytes(ll.a);
    return Uint8Array.from(gp.a);
  }

  // When a font has no anchors of its own: vowels under the middle of the letter, dots above.
  function makeAnchors(model) {
    const cls = (u) => (u === 0x5bc ? 1 : [0x5b9, 0x5ba, 0x5c2].includes(u) ? 2 : u === 0x5c1 ? 3 : [0x5bf, 0x5c4].includes(u) || (u >= 0x591 && u <= 0x5af && ![0x591, 0x596, 0x59b, 0x5a2, 0x5a3, 0x5a4, 0x5a5, 0x5a6, 0x5a7, 0x5aa].includes(u)) ? 4 : 0);
    const marks = new Map(), bases = new Map();
    const gap = model.H * 0.07;
    model.glyphs.forEach((g, i) => {
      const bb = bbox(g.contours);
      if (!bb) return;
      const cx = (bb.x0 + bb.x1) / 2;
      if (g.mark) {
        const c = cls(g.unicodes[0] || 0);
        const y = c === 0 ? bb.y1 : c === 1 ? (bb.y0 + bb.y1) / 2 : bb.y0;
        marks.set(i, [c, Math.round(cx), Math.round(y)]);
      } else if (g.unicodes.some((u) => u >= 0x5d0 && u <= 0x5ea)) {
        const w = bb.x1 - bb.x0;
        bases.set(i, [[cx, Math.min(0, bb.y0) - gap], [cx, model.H * 0.45], [bb.x0 + w * 0.12, model.H + gap], [bb.x1 - w * 0.12, model.H + gap], [cx, model.H + gap]]);
      }
    });
    return { mark: marks.size ? [{ type: 4, flag: 0, filter: null, subs: [{ classCount: 5, marks, bases }] }] : [], mkmk: [] };
  }

  // ---------------------------------------------------------------- the new font

  function asciiName(s, fallback) {
    const t = String(s || "").replace(/[^A-Za-z0-9 ]/g, "").replace(/\s+/g, " ").trim();
    return t || fallback;
  }

  // Builds the changed font. opts.only: glyph numbers that get the slow changes (weight,
  // roundness) for a quick preview; the others are only moved. opts.fit: smooth curves.
  function build(model, settings, opts) {
    opts = opts || {};
    const S = Object.assign({}, SETTINGS, settings || {});
    const family = asciiName(opts.family, "My Hebrew");
    const style = asciiName(opts.style, "Regular");
    const changes = model.glyphs.map((g, i) => glyphChange(model, S, i));
    let yMax = 0, yMin = 0;
    const otGlyphs = model.glyphs.map((g, i) => {
      const t = changes[i];
      let contours = g.contours.map((c) => c.map((s) => s.map((p) => movePoint(t, p))));
      const slow = Math.abs(t.dv) >= 0.3 || Math.abs(t.dh) >= 0.3 || t.r > 0.5;
      if (slow && contours.length && (!opts.only || opts.only.has(i))) {
        try { contours = growOutline(contours, t, opts.fit !== false); } catch (e) { /* keep it moved only */ }
      }
      const path = new opentype.Path();
      for (const c of contours) {
        const r = Math.round;
        path.moveTo(r(c[0][0][0]), r(c[0][0][1]));
        for (const s of c) {
          if (yMax < s[3][1]) yMax = s[3][1];
          if (yMin > s[3][1]) yMin = s[3][1];
          const line = Math.abs(s[1][0] - (s[0][0] * 2 + s[3][0]) / 3) < 0.5 && Math.abs(s[1][1] - (s[0][1] * 2 + s[3][1]) / 3) < 0.5 &&
            Math.abs(s[2][0] - (s[0][0] + s[3][0] * 2) / 3) < 0.5 && Math.abs(s[2][1] - (s[0][1] + s[3][1] * 2) / 3) < 0.5;
          if (line) path.lineTo(r(s[3][0]), r(s[3][1]));
          else path.curveTo(r(s[1][0]), r(s[1][1]), r(s[2][0]), r(s[2][1]), r(s[3][0]), r(s[3][1]));
        }
        path.close();
      }
      const og = new opentype.Glyph({ name: g.name, unicode: g.unicodes[0], advanceWidth: t.advance, path });
      for (const u of g.unicodes.slice(1)) og.addUnicode(u);
      return og;
    });
    const sy = S.height;
    const font = new opentype.Font({
      familyName: family,
      styleName: style,
      unitsPerEm: model.upm,
      ascender: Math.round(model.ascender * sy),
      descender: Math.round(model.descender * sy),
      designer: [model.names.designer, opts.designer].filter(Boolean).join(" / "),
      version: "1.000",
      glyphs: otGlyphs,
    });
    font.names.postScriptName = { en: (family + "-" + style).replace(/\s/g, "") };
    font.names.copyright = { en: [model.names.copyright, "Changed with the Hebrew font maker" + (opts.designer ? " by " + opts.designer : "") + "."].filter(Boolean).join(" ") };
    if (model.names.license) font.names.license = { en: model.names.license };
    if (model.names.licenseURL) font.names.licenseURL = { en: model.names.licenseURL };
    font.names.description = { en: "Based on " + (model.names.family || "a font") + "." };
    const bold = style.toLowerCase() === "bold";
    font.tables.os2 = {
      ulCodePageRange1: (1 << 0) | (1 << 5),
      usWeightClass: bold ? 700 : Math.round(clamp(400 + S.weight * 250, 100, 900) / 100) * 100,
      usWidthClass: S.width < 0.8 ? 3 : S.width < 0.92 ? 4 : S.width < 1.08 ? 5 : S.width < 1.2 ? 6 : 7,
      fsSelection: (bold ? 0x20 : 0x40) | 0x80,
      usWinAscent: Math.ceil(Math.max(yMax, model.ascender * sy) + model.upm * 0.05),
      usWinDescent: Math.ceil(Math.max(-yMin, -model.descender * sy) + model.upm * 0.05),
      achVendID: "HFMK",
    };
    const buf = font.toArrayBuffer();
    const anchors = model.gpos.mark.length ? model.gpos : makeAnchors(model);
    const extra = { GPOS: anchors.mark.length ? writeGPOS(anchors, changes) : null };
    // the glyphs keep their numbers, so these tables stay right; without variations
    if (model.gdef) {
      const d = model.gdef.slice();
      if (u16(d, 0) === 1 && u16(d, 2) >= 3) { d[2] = 0; d[3] = 2; }
      extra.GDEF = d;
    }
    if (model.gsub) {
      const d = model.gsub.slice();
      if (u16(d, 0) === 1 && u16(d, 2) >= 1) { d[2] = 0; d[3] = 0; }
      extra.GSUB = d;
    }
    return G.withTables(buf, extra, bold);
  }

  // The glyph numbers a text needs (for a quick preview of only these).
  function glyphsFor(model, text) {
    const out = new Set();
    for (const ch of text) {
      const i = model.byChar[ch.codePointAt(0)];
      if (i !== undefined) out.add(i);
    }
    return out;
  }

  FontMaker.Outline = { SETTINGS, load, build, glyphsFor, bbox };
})();
