// Classic book letters: the proportions of the traditional Hebrew book type (like Frank Ruhl):
// narrow letters, a head on every roof, slanted arms in alef, tsadi and shin, a lamed whose
// tail sweeps down to the left, an ayin with a tail below the line.
(function () {
  "use strict";

  const W = {
    alef: 0.72, bet: 0.66, gimel: 0.44, dalet: 0.62, he: 0.65, vav: 0.26, zayin: 0.27, het: 0.66,
    tet: 0.70, yod: 0.30, finalkaf: 0.62, kaf: 0.62, lamed: 0.68, finalmem: 0.66, mem: 0.72,
    finalnun: 0.25, nun: 0.40, samekh: 0.66, ayin: 0.66, finalpe: 0.62, pe: 0.66, finaltsadi: 0.63,
    tsadi: 0.63, qof: 0.66, resh: 0.62, shin: 0.86, tav: 0.76,
  };

  // the leg under a roof starts clear of the head that hangs from the roof
  const legTop = (c, more) => c.H - c.T * 1.5 - c.T * 0.7 * c.s - c.H * (more || 0.12);

  const L = {
    alef(d, c) {
      const { t, b, H } = c, w = d.W;
      d.P(0, t).L(w * 0.24, t);
      d.head(0);
      d.P(w * 0.14, t).C(w * 0.36, H * 0.62, w * 0.6, H * 0.34, w * 0.88, b);
      d.P(w * 0.72, b).L(w, b);
      d.P(w * 0.7, t).L(w * 0.94, t);
      d.head(w * 0.7);
      d.P(w * 0.88, t).C(w * 0.88, H * 0.62, w * 0.76, H * 0.52, w * 0.56, H * 0.5);
      d.P(w * 0.42, H * 0.54).C(w * 0.3, H * 0.42, w * 0.2, H * 0.26, w * 0.2, b);
      d.P(0, b).L(w * 0.3, b);
      d.anchors.dagesh = [w * 0.5, H * 0.42];
    },
    bet(d, c) {
      const { t, b, S, H, r, s } = c, w = d.W;
      const heel = H * (0.01 + 0.16 * c.prm.heel) * (0.4 + 0.6 * s);
      const xr = w - heel - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(0, b).L(w, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.48, H * 0.5];
      d.anchors.below = [xr * 0.5, 0];
    },
    gimel(d, c) {
      const { t, b, S, H, r, s } = c, w = d.W;
      const xr = w - S / 2 - H * 0.06 * s;
      d.P(w * 0.2, t).R(xr, t, 0, -1, r * 0.4).L(xr, b);
      d.head(w * 0.2);
      d.P(xr, H * 0.5).C(xr - w * 0.3, H * 0.4, w * 0.14, H * 0.22, w * 0.04, b * 0.8);
      if (s > 0.01) d.P(xr - S / 2, b).L(w, b);
      d.anchors.dagesh = [w * 0.4, H * 0.68];
      d.anchors.below = [xr * 0.6, 0];
    },
    dalet(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - w * 0.26 * c.prm.overhang - S / 2;
      d.P(0, t).L(w, t);
      d.P(xr, t).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
      d.anchors.below = [xr * 0.55, 0];
    },
    he(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - w * 0.14 * c.prm.overhang - S / 2;
      const xl = S * 0.75 + w * 0.05;
      d.P(0, t).L(w, t);
      d.P(xr, t).L(xr, b);
      d.P(xl, legTop(c)).C(xl, H * 0.3, xl - w * 0.02, H * 0.15, xl - w * 0.02, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.45];
    },
    vav(d, c) {
      const { t, b, S, r, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr, 0];
    },
    zayin(d, c) {
      const { t, b, H } = c, w = d.W;
      const xm = w * 0.58;
      d.P(0, t).L(w, t);
      d.P(xm, t).C(xm, H * 0.5, xm - w * 0.1, H * 0.3, xm - w * 0.08, b);
      d.head(0);
      d.anchors.dagesh = [xm - c.S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xm, 0];
    },
    het(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S * 0.75 + w * 0.06;
      d.P(0, t).R(xr, t, 0, -1, r * 0.3).L(xr, b);
      d.P(xl, t).C(xl, H * 0.4, xl - w * 0.03, H * 0.2, xl - w * 0.04, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.52, H * 0.45];
    },
    tet(d, c) {
      const { t, b, S, H, T, r } = c, w = d.W;
      const xl = S / 2 + w * 0.02, xr = w - S / 2;
      const rb = Math.min(H * 0.42, r * 0.7 + H * 0.16);
      d.P(0, t).L(w * 0.18, t);
      d.head(0);
      d.P(xl, t).L(xl, b + rb * 0.5).R(xl, b, 1, 0, rb * 0.5).L(xr - rb, b).qh(xr, b + rb)
        .L(xr, H * 0.6).C(xr, H * 0.88, w * 0.8, t, w * 0.62, t)
        .C(w * 0.5, t, w * 0.44, H - T * 0.9, w * 0.44, H * 0.56);
      d.anchors.dagesh = [w * 0.62, H * 0.4];
    },
    yod(d, c) {
      const { t, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.74).C(xr, H * 0.6, xr - w * 0.1, H * 0.52, xr - w * 0.3, H * 0.47);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.3];
      d.anchors.below = [w * 0.6, H * 0.36];
    },
    kaf(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, rk = Math.max(r, H * 0.14);
      d.P(0, t).R(xr, t, 0, -1, rk).R(xr, b, -1, 0, rk).L(0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
    },
    finalkaf(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.1)).L(xr, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
      d.anchors.below = [w * 0.46, H * 0.42];
    },
    lamed(d, c) {
      const { t, b, S, H, T, r, A } = c, w = d.W;
      const xl = S / 2 + w * 0.04, xr = w - S / 2;
      d.P(0, H + A - T / 2).L(w * 0.2, H + A - T / 2);
      d.head(0, H + A);
      d.P(xl, H + A - T / 2).L(xl, t);
      d.P(xl - S / 2, t).R(xr, t, 0, -1, r).L(xr, H * 0.56)
        .C(xr, H * 0.32, w * 0.6, H * 0.2, w * 0.32, b * 0.7);
      d.anchors.dagesh = [w * 0.52, H * 0.5];
      d.anchors.aboveLeft = [w * 0.5, H];
    },
    mem(d, c) {
      const { t, b, S, H, r, s } = c, w = d.W;
      const heel = H * 0.08 * c.prm.heel * s;
      const xr = w - heel - S / 2, xl = S / 2 + w * 0.04;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(w * 0.36, b).L(w, b);
      d.P(xl, t).C(xl, H * 0.5, xl - w * 0.03, H * 0.25, xl - w * 0.02, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.48];
      d.anchors.below = [w * 0.56, 0];
    },
    finalmem(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.03;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(xl, t).L(xl, b);
      d.P(0, b).L(w, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
    },
    nun(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.6).R(xr, b, -1, 0, r * 0.3).L(0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.36, H * 0.5];
    },
    finalnun(d, c) {
      const { t, b, S, r, D, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, b - D);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr, 0];
    },
    samekh(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xl = S / 2 + w * 0.04, xr = w - S / 2 - w * 0.02;
      const ry = Math.min(H * 0.46, (xr - xl) * 0.5);
      d.P(0, t).L(w, t);
      d.P(xl, t).L(xl, b + ry).qv((xl + xr) / 2, b).qh(xr, b + ry).L(xr, t);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
    },
    ayin(d, c) {
      const { t, H } = c, w = d.W;
      const xr = w * 0.84;
      d.P(w * 0.62, t).L(w * 0.92, t);
      d.head(w * 0.62);
      d.P(xr, t).C(xr, H * 0.42, w * 0.74, H * 0.14, w * 0.52, H * 0.06).C(w * 0.32, 0, w * 0.14, -H * 0.06, 0, -H * 0.11);
      d.P(0, t).L(w * 0.24, t);
      d.head(0);
      d.P(w * 0.12, t).C(w * 0.22, H * 0.56, w * 0.44, H * 0.4, w * 0.74, H * 0.3);
      d.anchors.dagesh = [w * 0.56, H * 0.62];
    },
    pe(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2, rk = Math.max(r, H * 0.14);
      d.P(0, t).R(xr, t, 0, -1, rk).R(xr, b, -1, 0, rk).L(0, b);
      d.P(xl, t).L(xl, H * 0.5);
      d.P(0, H * 0.5).L(w * 0.24, H * 0.5);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.42];
    },
    finalpe(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.1)).L(xr, b - D);
      d.P(xl, t).L(xl, H * 0.5);
      d.P(0, H * 0.5).L(w * 0.24, H * 0.5);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.42];
      d.anchors.below = [w * 0.46, H * 0.36];
    },
    tsadi(d, c) {
      const { t, b, H } = c, w = d.W;
      d.P(0, t).L(w * 0.24, t);
      d.head(0);
      d.P(w * 0.12, t).C(w * 0.3, H * 0.56, w * 0.58, H * 0.28, w * 0.86, b);
      d.P(0, b).L(w, b);
      d.P(w * 0.64, t).L(w * 0.92, t);
      d.head(w * 0.64);
      d.P(w * 0.86, t).C(w * 0.86, H * 0.6, w * 0.72, H * 0.48, w * 0.5, H * 0.42);
      d.anchors.dagesh = [w * 0.68, H * 0.24];
    },
    finaltsadi(d, c) {
      const { t, b, H, D } = c, w = d.W;
      const xl = w * 0.2;
      d.P(0, t).L(w * 0.32, t);
      d.head(0);
      d.P(xl, t).C(xl, H * 0.3, xl + w * 0.03, 0, xl + w * 0.03, b - D);
      d.P(w * 0.64, t).L(w * 0.92, t);
      d.head(w * 0.64);
      d.P(w * 0.86, t).C(w * 0.86, H * 0.56, w * 0.62, H * 0.42, xl, H * 0.36);
      d.anchors.dagesh = [w * 0.56, H * 0.64];
      d.anchors.below = [w * 0.6, 0];
    },
    qof(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2, xl = S * 0.75 + w * 0.05;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, H * 0.48).C(xr, H * 0.28, w * 0.78, H * 0.18, w * 0.5, H * 0.1);
      d.P(xl, legTop(c, 0.16)).L(xl, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.5];
      d.anchors.below = [w * 0.62, 0];
    },
    resh(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2 - w * 0.02;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.2)).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
    },
    shin(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xl = S / 2 + w * 0.02;
      const rb = Math.min(H * 0.3, r * 0.6 + H * 0.08);
      d.P(0, t).L(w * 0.16, t);
      d.head(0);
      d.P(xl, t).L(xl, b + rb).qv(xl + rb, b).L(w * 0.86, b);
      d.P(w * 0.38, t).L(w * 0.56, t);
      d.head(w * 0.38);
      d.P(w * 0.5, t).C(w * 0.5, H * 0.5, w * 0.44, H * 0.3, w * 0.36, b);
      d.P(w * 0.76, t).L(w, t);
      d.head(w * 0.76);
      d.P(w * 0.94, t).C(w * 0.94, H * 0.55, w * 0.9, H * 0.3, w * 0.82, b);
      d.anchors.dagesh = [w * 0.66, H * 0.45];
      d.anchors.aboveRight = [w * 0.92, H];
      d.anchors.aboveLeft = [w * 0.08, H];
    },
    tav(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = w * 0.2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.6).L(xr, b);
      d.P(xl, t).C(xl, H * 0.45, xl - w * 0.02, H * 0.2, xl - w * 0.04, b);
      d.P(0, b).L(xl - w * 0.04 + S / 2, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.58, H * 0.45];
    },
  };

  FontMaker.addLetterSet("classic", {
    name: "ספר קלאסי",
    about: "כמו אותיות של ספר קודש מודפס",
    widths: W,
    letters: L,
    defaults: {},
  });
})();
