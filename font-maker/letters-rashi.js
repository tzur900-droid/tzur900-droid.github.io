// Rashi script: the half-cursive letters of the commentaries. Round letters whose right side
// curls down and to the left, a small drop at the start of each roof, an alef whose left arm
// rises above the line, a looped final pe, a tsadi that sweeps below the line.
(function () {
  "use strict";

  const W = {
    alef: 0.66, bet: 0.68, gimel: 0.38, dalet: 0.58, he: 0.66, vav: 0.28, zayin: 0.3, het: 0.68,
    tet: 0.78, yod: 0.28, finalkaf: 0.62, kaf: 0.62, lamed: 0.46, finalmem: 0.7, mem: 0.7,
    finalnun: 0.24, nun: 0.36, samekh: 0.7, ayin: 0.7, finalpe: 0.6, pe: 0.62, finaltsadi: 0.42,
    tsadi: 0.6, qof: 0.66, resh: 0.62, shin: 0.66, tav: 0.74,
  };

  // the right side of a roof that comes down and curls to the left, ending at height y
  const curl = (p, xr, c, w, y) => p.C(xr, c.H * 0.45, xr - w * 0.08, c.H * 0.22, xr - w * 0.26, y);

  const L = {
    alef(d, c) {
      const { t, b, S, H, r, A } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.46, H + A * 0.85).C(w * 0.2, H * 1.1, w * 0.1, H * 0.8, w * 0.1, b);
      curl(d.P(w * 0.12, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)), xr, c, w, b);
      d.anchors.dagesh = [w * 0.55, H * 0.45];
      d.anchors.aboveLeft = [w * 0.6, H];
    },
    bet(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2 - w * 0.04;
      d.P(0, t).R(xr, t, 0, -1, r * 0.6).L(xr, H * 0.6).C(xr, H * 0.5, xr - w * 0.06, H * 0.46, xr - w * 0.1, H * 0.44)
        .C(xr + w * 0.06, H * 0.4, w, H * 0.25, w * 0.82, H * 0.1).C(w * 0.66, b * 0.6, w * 0.3, b, 0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.44, H * 0.55];
    },
    gimel(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w * 0.7;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).C(xr, H * 0.5, xr + w * 0.06, H * 0.2, w, b);
      d.P(xr - w * 0.02, H * 0.3).C(xr - w * 0.2, H * 0.16, w * 0.12, H * 0.08, 0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.4, H * 0.62];
    },
    dalet(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.14)).C(xr, H * 0.45, w * 0.62, H * 0.2, w * 0.28, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.55];
    },
    he(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.06;
      curl(d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.18)), xr, c, w, H * 0.2);
      d.P(xl, H * 0.66).L(xl, b + H * 0.08).qv(xl + w * 0.14, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.52, H * 0.45];
    },
    vav(d, c) {
      const { t, b, S, r, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).C(xr, H * 0.4, xr - w * 0.08, H * 0.18, xr - w * 0.3, b);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr * 0.8, 0];
    },
    zayin(d, c) {
      const { t, b, H } = c, w = d.W;
      const xm = w * 0.56;
      d.P(0, t - H * 0.04).L(w, t + H * 0.02);
      d.P(xm, t).C(xm, H * 0.5, xm - w * 0.1, H * 0.3, xm - w * 0.12, b);
      d.head(0, H - H * 0.04);
      d.anchors.dagesh = [xm - c.S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xm, 0];
    },
    het(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.04;
      curl(d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)), xr, c, w, b);
      d.P(xl, t).C(xl, H * 0.4, xl - w * 0.02, H * 0.2, xl - w * 0.03, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.45];
    },
    tet(d, c) {
      const { t, b, S, H, T } = c, w = d.W;
      const xl = S / 2 + w * 0.04, xr = w - S / 2;
      d.P(xl + w * 0.12, t).C(xl, H * 0.8, xl, H * 0.4, xl, H * 0.2).C(xl, -H * 0.04, w * 0.3, b, w * 0.5, b)
        .C(w * 0.8, b, xr, H * 0.3, xr, H * 0.62).C(xr, H * 0.9, w * 0.78, t, w * 0.64, t)
        .C(w * 0.52, t, w * 0.46, H - T * 0.9, w * 0.46, H * 0.56);
      d.anchors.dagesh = [w * 0.62, H * 0.36];
    },
    yod(d, c) {
      const { t, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).C(xr, H * 0.72, xr - w * 0.1, H * 0.6, xr - w * 0.3, H * 0.52);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.3];
      d.anchors.below = [w * 0.6, H * 0.4];
    },
    kaf(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)).L(xr, H * 0.42).C(xr, H * 0.12, w * 0.62, b, 0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
    },
    finalkaf(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)).L(xr, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
      d.anchors.below = [w * 0.46, H * 0.42];
    },
    lamed(d, c) {
      const { b, S, H, A } = c, w = d.W;
      const xl = S / 2 + w * 0.06, xr = w - S / 2;
      d.P(xl, H + A - c.T / 2).L(xl, H * 0.4).qv(xl + (xr - xl) * 0.5, b).qh(xr, H * 0.42).C(xr, H * 0.6, xr - w * 0.06, H * 0.7, xr - w * 0.2, H * 0.74);
      d.P(0, H + A - c.T / 2).L(xl, H + A - c.T / 2);
      d.head(0, H + A);
      d.anchors.dagesh = [w * 0.6, H * 0.4];
      d.anchors.aboveLeft = [w * 0.7, H];
    },
    mem(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.04, b).C(w * 0.14, H * 0.4, w * 0.2, H * 0.7, w * 0.32, H * 0.86)
        .C(w * 0.42, t, w * 0.56, t, w * 0.7, t).C(w * 0.92, t, xr, H * 0.66, xr, H * 0.5)
        .C(xr, H * 0.34, w * 0.82, H * 0.24, w * 0.62, H * 0.22);
      d.P(w * 0.18, H * 0.88).L(w * 0.3, H * 0.86);
      d.anchors.dagesh = [w * 0.58, H * 0.56];
      d.anchors.below = [w * 0.5, 0];
    },
    finalmem(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xl = S / 2 + w * 0.04, xr = w - S / 2, m = (xl + xr) / 2;
      d.P(m, t).qh(xr, H * 0.5).qv(m, b).qh(xl, H * 0.5).qv(m, t);
      d.P(xl, t).L(xl, b - H * 0.06);
      d.P(0, t).L(xl, t);
      d.head(0);
      d.anchors.dagesh = [w * 0.54, H * 0.5];
    },
    nun(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).L(xr, H * 0.42).C(xr, H * 0.12, w * 0.6, b, 0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.36, H * 0.5];
    },
    finalnun(d, c) {
      const { t, b, S, r, D, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).C(xr, H * 0.3, xr - w * 0.06, 0, xr - w * 0.06, b - D);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr, 0];
    },
    samekh(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xl = S / 2 + w * 0.04, xr = w - S / 2, m = (xl + xr) / 2;
      d.P(m, t).qh(xr, H * 0.5).qv(m, b).qh(xl, H * 0.5).qv(m, t);
      d.P(0, t).L(m, t);
      d.head(0);
      d.anchors.dagesh = [w * 0.54, H * 0.5];
    },
    ayin(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.86, H * 1.0).C(xr + w * 0.06, H * 0.7, xr, H * 0.3, w * 0.74, H * 0.16).C(w * 0.56, 0, w * 0.26, b, 0, b);
      d.P(w * 0.12, t).C(w * 0.3, H * 0.7, w * 0.42, H * 0.4, w * 0.44, H * 0.12);
      d.head(w * 0.12);
      d.anchors.dagesh = [w * 0.62, H * 0.6];
    },
    pe(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.06;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)).L(xr, H * 0.42).C(xr, H * 0.12, w * 0.62, b, 0, b);
      d.P(xl, t).C(xl, H * 0.7, xl - w * 0.02, H * 0.56, xl + w * 0.12, H * 0.52);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.42];
    },
    finalpe(d, c) {
      const { b, S, H, D } = c, w = d.W;
      const xr = w - S / 2;
      d.P(xr, b - D).C(xr + w * 0.04, H * 0.2, xr, H * 0.5, xr, H * 0.62)
        .C(xr, H * 1.02, w * 0.12, H * 1.02, w * 0.1, H * 0.66).C(w * 0.08, H * 0.42, w * 0.34, H * 0.38, w * 0.48, H * 0.44);
      d.anchors.dagesh = [w * 0.52, H * 0.66];
      d.anchors.below = [w * 0.5, H * 0.3];
    },
    tsadi(d, c) {
      const { t, b, S, H, D } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.92, H * 1.04).C(w * 0.86, H * 0.9, w * 0.74, H * 0.84, w * 0.6, H * 0.78);
      d.P(w * 0.1, t).C(w * 0.3, H * 0.8, w * 0.6, H * 0.6, xr, H * 0.4)
        .C(xr + w * 0.04, H * 0.1, w * 0.6, -D * 0.6, 0, b - D * 0.7);
      d.head(w * 0.1);
      d.anchors.dagesh = [w * 0.6, H * 0.5];
    },
    finaltsadi(d, c) {
      const { t, b, S, H, D } = c, w = d.W;
      const xm = w * 0.48;
      d.P(0, t - H * 0.04).L(w, t + H * 0.04);
      d.P(xm, t).C(xm, H * 0.3, xm + w * 0.04, 0, xm + w * 0.02, b - D);
      d.head(0, H - H * 0.04);
      d.anchors.dagesh = [xm - c.S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xm, 0];
    },
    qof(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.06;
      curl(d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)), xr, c, w, H * 0.12);
      d.P(xl, H * 0.62).C(xl - w * 0.02, H * 0.2, xl, 0, xl + w * 0.02, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.5];
      d.anchors.below = [w * 0.62, 0];
    },
    resh(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      curl(d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.22)), xr, c, w, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.48];
    },
    shin(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xl = S / 2 + w * 0.06;
      d.P(0, t).L(w * 0.62, t).C(w * 0.78, t, w * 0.82, H * 0.92, w * 0.78, H * 0.84);
      d.P(xl, t).L(xl, b + H * 0.06).qv(xl + w * 0.12, b).L(w * 0.6, b)
        .C(w * 0.86, b, w * 0.96, H * 0.24, w * 0.86, H * 0.42);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
      d.anchors.aboveRight = [w * 0.8, H];
      d.anchors.aboveLeft = [w * 0.1, H];
    },
    tav(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = w * 0.24;
      curl(d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)), xr, c, w, b);
      d.P(xl, t).C(xl - w * 0.06, H * 0.6, xl, H * 0.3, xl + w * 0.04, H * 0.1).C(xl + w * 0.06, -H * 0.04, w * 0.1, -H * 0.06, 0, -H * 0.04);
      d.head(0);
      d.anchors.dagesh = [w * 0.58, H * 0.45];
    },
  };

  FontMaker.addLetterSet("rashi", {
    name: "כתב רש״י",
    about: "אותיות עגולות של פירושים, חצי־כתב־יד",
    widths: W,
    letters: L,
    defaults: { weight: 0.12, contrast: 1.7, round: 0.8, serif: 0.45, headShape: 1, pen: 0.5, descender: 0.36 },
  });
})();
