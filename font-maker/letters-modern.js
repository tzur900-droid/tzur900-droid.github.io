// Modern letters, without heads: even strokes and round corners, the shapes of the plain Hebrew
// type of signs and screens (like Arial Hebrew or Nachlieli). Wide letters, a straight alef,
// a shin whose middle arm reaches the base, a tav whose left leg ends in a small hook.
(function () {
  "use strict";

  const W = {
    alef: 0.8, bet: 0.78, gimel: 0.56, dalet: 0.76, he: 0.76, vav: 0.2, zayin: 0.4, het: 0.8,
    tet: 0.78, yod: 0.2, finalkaf: 0.64, kaf: 0.68, lamed: 0.72, finalmem: 0.8, mem: 0.78,
    finalnun: 0.2, nun: 0.42, samekh: 0.78, ayin: 0.78, finalpe: 0.7, pe: 0.74, finaltsadi: 0.76,
    tsadi: 0.78, qof: 0.76, resh: 0.68, shin: 0.98, tav: 0.9,
  };

  const legTop = (c, more) => c.H - c.T * 1.5 - c.T * 0.7 * c.s - c.H * (more || 0.16);

  const L = {
    alef(d, c) {
      const { t, b, H } = c, w = d.W;
      d.P(w * 0.06, t).L(w * 0.94, b);
      d.head(w * 0.06);
      const xr = w * 0.86;
      d.P(xr, t).L(xr, H * 0.72).C(xr, H * 0.58, w * 0.8, H * 0.5, w * 0.64, H * 0.46);
      d.P(w * 0.3, H * 0.6).C(w * 0.2, H * 0.48, w * 0.16, H * 0.3, w * 0.16, b);
      d.anchors.dagesh = [w * 0.5, H * 0.4];
    },
    bet(d, c) {
      const { t, b, S, H, r, s } = c, w = d.W;
      const heel = H * (0.02 + 0.14 * c.prm.heel) * (0.3 + 0.7 * s);
      const xr = w - heel - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(0, b).L(w, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.48, H * 0.5];
      d.anchors.below = [xr * 0.5, 0];
    },
    gimel(d, c) {
      const { t, b, H, r } = c, w = d.W;
      const xr = w * 0.64;
      d.P(w * 0.2, t).R(xr, t, 0, -1, r * 0.5).L(xr, H * 0.5).L(w * 0.86, b);
      d.P(xr - w * 0.04, H * 0.34).L(0, b);
      d.head(w * 0.2);
      d.anchors.dagesh = [w * 0.42, H * 0.66];
      d.anchors.below = [w * 0.5, 0];
    },
    dalet(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - w * 0.22 * c.prm.overhang - S / 2;
      d.P(0, t).L(w, t);
      d.P(xr, t).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
      d.anchors.below = [xr * 0.55, 0];
    },
    he(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.04;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(xl, legTop(c, 0.2)).L(xl, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.45];
    },
    vav(d, c) {
      const { t, b, S, r, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr, 0];
    },
    zayin(d, c) {
      const { t, b, H } = c, w = d.W;
      const xm = w * 0.5;
      d.P(0, t).L(w, t);
      d.P(xm, t).L(xm, b);
      d.head(0);
      d.anchors.dagesh = [xm - c.S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xm, 0];
    },
    het(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.02;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(xl, t).L(xl, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.45];
    },
    tet(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xl = S / 2, xr = w - S / 2;
      const rb = Math.min(H * 0.45, (xr - xl) * 0.5, r * 0.6 + H * 0.24);
      d.P(xl, t).L(xl, b + rb).qv(xl + rb, b).L(xr - rb, b).qh(xr, b + rb)
        .L(xr, t - r * 0.8).R(xr, t, -1, 0, r * 0.8).L(w * 0.5, t).R(w * 0.42, t, 0, -1, r * 0.4).L(w * 0.42, H * 0.56);
      d.head(0);
      d.anchors.dagesh = [w * 0.62, H * 0.38];
    },
    yod(d, c) {
      const { t, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.5).L(xr, H * 0.56);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.3];
      d.anchors.below = [w * 0.6, H * 0.4];
    },
    kaf(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).R(xr, b, -1, 0, r).L(0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
    },
    finalkaf(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.46, H * 0.5];
      d.anchors.below = [w * 0.46, H * 0.42];
    },
    lamed(d, c) {
      const { t, b, S, H, r, A } = c, w = d.W;
      const xl = S / 2, xr = w - S / 2 - w * 0.06;
      d.P(xl, H + A - c.T / 2).L(xl, t);
      d.head(0, H + A);
      d.P(0, t).R(xr, t, 0, -1, r * 0.4).L(xr, H * 0.45).C(xr, H * 0.15, w * 0.7, b, w * 0.46, b).L(w * 0.2, b);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
      d.anchors.aboveLeft = [w * 0.5, H];
    },
    mem(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.16, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(w * 0.36, b).L(xr + S / 2, b);
      d.P(w * 0.16, t).C(w * 0.12, H * 0.6, w * 0.06, H * 0.3, w * 0.04, b);
      d.P(0, t).L(w * 0.2, t);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.48];
      d.anchors.below = [w * 0.56, 0];
    },
    finalmem(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).R(xr, b, -1, 0, r).L(0, b);
      d.P(xl, t).L(xl, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
    },
    nun(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, r * 0.7).R(xr, b, -1, 0, r * 0.4).L(0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.36, H * 0.5];
    },
    finalnun(d, c) {
      const { t, b, S, D, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(xr, t).L(xr, b - D);
      d.P(0, t).L(xr, t);
      d.head(0);
      d.anchors.dagesh = [xr - S / 2 - H * 0.1, H * 0.5];
      d.anchors.below = [xr, 0];
    },
    samekh(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xl = S / 2, xr = w - S / 2;
      const rr = Math.min(H * 0.4, (xr - xl) * 0.45, r + H * 0.18);
      d.P(xl, t - r * 0.6).R(xl, t, 1, 0, r * 0.6).R(xr, t, 0, -1, r).L(xr, b + rr).qv(xr - rr, b).L(xl + rr, b).qh(xl, b + rr).L(xl, t - r * 0.6);
      d.head(0);
      d.anchors.dagesh = [w * 0.5, H * 0.5];
    },
    ayin(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(xr, t).L(xr, H * 0.42).C(xr, H * 0.16, w * 0.72, b, w * 0.42, b).L(0, b);
      d.P(w * 0.06, t).L(w * 0.36, b);
      d.head(w * 0.06);
      d.anchors.dagesh = [w * 0.6, H * 0.6];
    },
    pe(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).R(xr, b, -1, 0, r).L(0, b);
      d.P(xl, t).L(xl, H * 0.62).qv(xl + w * 0.12, H * 0.5).L(w * 0.3, H * 0.5);
      d.head(0);
      d.anchors.dagesh = [w * 0.62, H * 0.4];
    },
    finalpe(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b - D);
      d.P(xl, t).L(xl, H * 0.62).qv(xl + w * 0.12, H * 0.5).L(w * 0.3, H * 0.5);
      d.head(0);
      d.anchors.dagesh = [w * 0.62, H * 0.4];
      d.anchors.below = [w * 0.46, H * 0.36];
    },
    tsadi(d, c) {
      const { t, b, S, H } = c, w = d.W;
      const xr = w - S / 2;
      d.P(w * 0.06, t).L(w * 0.86, b);
      d.P(0, b).L(w, b);
      d.P(xr, t).L(xr, H * 0.66).C(xr, H * 0.5, w * 0.76, H * 0.42, w * 0.56, H * 0.42);
      d.head(w * 0.06);
      d.anchors.dagesh = [w * 0.68, H * 0.24];
    },
    finaltsadi(d, c) {
      const { t, b, S, H, D } = c, w = d.W;
      const xr = w - S / 2, xm = w * 0.42;
      d.P(w * 0.04, t).L(xm, H * 0.4).L(xm, b - D);
      d.P(xr, t).L(xr, H * 0.7).C(xr, H * 0.48, w * 0.7, H * 0.4, xm, H * 0.4);
      d.head(w * 0.04);
      d.anchors.dagesh = [w * 0.7, H * 0.62];
      d.anchors.below = [w * 0.6, 0];
    },
    qof(d, c) {
      const { t, b, S, H, r, D } = c, w = d.W;
      const xr = w - S / 2, xl = S / 2 + w * 0.02;
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b + r * 0.6).R(xr, b, -1, 0, r * 0.6).L(w * 0.44, b);
      d.P(xl, legTop(c, 0.22)).L(xl, b - D);
      d.head(0);
      d.anchors.dagesh = [w * 0.6, H * 0.5];
      d.anchors.below = [w * 0.62, 0];
    },
    resh(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2;
      d.P(0, t).R(xr, t, 0, -1, Math.max(r, H * 0.18)).L(xr, b);
      d.head(0);
      d.anchors.dagesh = [xr * 0.5, H * 0.45];
    },
    shin(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xl = S / 2, xr = w - S / 2;
      const rb = Math.min(H * 0.4, r + H * 0.12);
      d.P(xl, t).L(xl, b + rb).qv(xl + rb, b).L(xr - rb, b).qh(xr, b + rb).L(xr, t);
      d.P(w * 0.5, t).L(w * 0.5, H * 0.46).C(w * 0.5, H * 0.3, w * 0.44, H * 0.22, w * 0.3, H * 0.22);
      d.head(0);
      d.anchors.dagesh = [w * 0.68, H * 0.45];
      d.anchors.aboveRight = [w * 0.94, H];
      d.anchors.aboveLeft = [w * 0.06, H];
    },
    tav(d, c) {
      const { t, b, S, H, r } = c, w = d.W;
      const xr = w - S / 2, xl = w * 0.16;
      const rh = Math.min(w * 0.1, H * 0.1);
      d.P(0, t).R(xr, t, 0, -1, r).L(xr, b);
      d.P(xl, t).L(xl, b + rh).qv(xl - rh, b).L(0, b);
      d.head(0);
      d.anchors.dagesh = [w * 0.58, H * 0.45];
    },
  };

  FontMaker.addLetterSet("modern", {
    name: "מודרני נקי",
    about: "בלי תגים, קווים אחידים ופינות עגולות",
    widths: W,
    letters: L,
    defaults: { weight: 0.11, contrast: 1.15, round: 0.55, serif: 0, spacing: 1.05 },
  });
})();
