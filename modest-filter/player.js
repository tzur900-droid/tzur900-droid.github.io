import { load, analyze } from "./detect.js";
import { exposure, garmentColor, garmentShapes, drawGarments, intimacy, Tracker, L } from "./modesty.js";

const $ = (id) => document.getElementById(id);
const video = $("src"), screen = $("screen"), sctx = screen.getContext("2d");
const frame = document.createElement("canvas"), fctx = frame.getContext("2d", { willReadFrequently: true });
const work = document.createElement("canvas"), wctx = work.getContext("2d", { willReadFrequently: true });
const WORK_W = 384, MAX_W = 1280;

// ---------- הגדרות (נשמרות) ----------

const DEFAULTS = { arms: true, legs: true, neck: true, intimate: true, scenes: true, strict: true,
  sensitivity: "normal", style: "garment", debug: false };
const THRESH = {
  low: { porn: 0.6, hentai: 0.7, sexy: 0.92 },
  normal: { porn: 0.35, hentai: 0.5, sexy: 0.78 },
  high: { porn: 0.2, hentai: 0.35, sexy: 0.55 }
};
const store = {
  async get() {
    try {
      if (globalThis.chrome?.storage) return (await chrome.storage.local.get("settings")).settings || {};
      return JSON.parse(localStorage.getItem("settings") || "{}");
    } catch { return {}; }
  },
  set(v) {
    try {
      if (globalThis.chrome?.storage) chrome.storage.local.set({ settings: v });
      else localStorage.setItem("settings", JSON.stringify(v));
    } catch {}
  }
};
const S = { ...DEFAULTS, ...(await store.get()) };
for (const el of document.querySelectorAll("[data-k]")) {
  const k = el.dataset.k;
  if (el.type === "checkbox") el.checked = !!S[k]; else el.value = S[k];
  el.onchange = () => {
    S[k] = el.type === "checkbox" ? el.checked : el.value;
    store.set(S);
    dirty = true;
  };
}

// ---------- טעינת מודלים ----------

let ready = false;
const status = (t) => ($("status").textContent = t);
load(status).then(() => {
  ready = true;
  status("מוכן");
  dirty = true;
}).catch((e) => {
  console.error(e);
  status("שגיאה בטעינת הזיהוי: " + e.message);
});

// ---------- פתיחת סרט ----------

function openUrl(url, title) {
  video.src = url;
  document.title = "נגן צנוע · " + title;
  $("open").classList.add("hidden");
  $("stage").classList.remove("hidden");
  video.addEventListener("loadedmetadata", () => {
    const scale = Math.min(1, MAX_W / video.videoWidth);
    frame.width = screen.width = Math.round(video.videoWidth * scale);
    frame.height = screen.height = Math.round(video.videoHeight * scale);
    work.width = WORK_W;
    work.height = Math.round(WORK_W * video.videoHeight / video.videoWidth);
    $("seek").max = Math.floor(video.duration * 10);
    dirty = true;
  }, { once: true });
  video.addEventListener("error", () => {
    alert("הדפדפן לא מצליח לנגן את הקובץ הזה. כרום מנגן MP4 ו-WebM (ולרוב גם MKV). קבצי AVI צריך להמיר קודם.");
  }, { once: true });
}

$("file").onchange = (e) => e.target.files[0] && openFile(e.target.files[0]);
function openFile(f) { openUrl(URL.createObjectURL(f), f.name); }
const drop = $("drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) openFile(f); };

function driveId(text) {
  const m = /\/d\/([\w-]{20,})/.exec(text) || /[?&]id=([\w-]{20,})/.exec(text) || /^([\w-]{25,})$/.exec(text.trim());
  return m && m[1];
}

$("drive-go").onclick = () => {
  const id = driveId($("drive-link").value);
  if (!id) return alert("זה לא נראה כמו קישור לקובץ בדרייב.");
  openDrive(id);
};

async function openDrive(id) {
  const box = $("dl");
  box.classList.remove("hidden");
  const text = (t) => ($("dl-text").textContent = t);
  try {
    text("מתחבר לדרייב...");
    let url = `https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`;
    let r = await fetch(url, { credentials: "include" });
    if ((r.headers.get("content-type") || "").includes("text/html")) {
      // דף אישור של גוגל לקבצים גדולים, או דף התחברות
      const doc = new DOMParser().parseFromString(await r.text(), "text/html");
      const form = doc.querySelector("form[action*='download']");
      if (!form) throw new Error("אין גישה לקובץ. ודאו שאתם מחוברים בכרום לחשבון הגוגל שהקובץ שלו, ונסו שוב.");
      const u = new URL(form.getAttribute("action"), url);
      for (const inp of form.querySelectorAll("input[name]")) u.searchParams.set(inp.name, inp.value);
      r = await fetch(u, { credentials: "include" });
    }
    if (!r.ok) throw new Error("הדרייב החזיר שגיאה " + r.status);
    const total = Number(r.headers.get("content-length")) || 0;
    const name = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(r.headers.get("content-disposition") || "")?.[1];
    const reader = r.body.getReader(), chunks = [];
    let got = 0, t0 = performance.now();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      got += value.length;
      const mb = (got / 1048576).toFixed(0), sec = (performance.now() - t0) / 1000;
      $("dl-bar").style.width = total ? (100 * got / total).toFixed(1) + "%" : "50%";
      const left = total && got > 0 ? ((total - got) / (got / sec) / 60).toFixed(0) : "?";
      text(`מוריד את הסרט מהדרייב: ${mb} MB${total ? " מתוך " + (total / 1048576).toFixed(0) + " MB · עוד כ-" + left + " דקות" : ""}`);
    }
    const type = r.headers.get("content-type")?.startsWith("video") ? r.headers.get("content-type") : "video/mp4";
    openUrl(URL.createObjectURL(new Blob(chunks, { type })), decodeURIComponent(name || "סרט מהדרייב"));
  } catch (e) {
    text("❌ " + e.message);
  }
}

const params = new URLSearchParams(location.search);
if (params.get("drive")) openDrive(params.get("drive"));

// ---------- לולאת הסינון ----------

const tracker = new Tracker();
let dirty = false, people = [], skip = null, manualBlack = false, frames = 0, fpsT = performance.now(), fps = 0;
let sceneHits = 0, intimHits = 0, skippedCount = 0, lastRes = null;

function flagged(res) {
  let reason = null;
  if (S.intimate) {
    const kind = intimacy(res.people, res.faces);
    intimHits = kind ? intimHits + 1 : 0;
    if (intimHits >= 2) reason = kind === "kiss" ? "נשיקה" : "חיבוק";
  }
  if (S.scenes && res.scene) {
    const t = THRESH[S.sensitivity] || THRESH.normal, s = res.scene;
    if (s.porn > t.porn || s.hentai > t.hentai) { sceneHits = 2; reason = reason || "קטע לא צנוע"; }
    else if (s.sexy > t.sexy) { sceneHits++; if (sceneHits >= 2) reason = reason || "קטע לא צנוע"; }
    else sceneHits = 0;
  } else if (sceneHits >= 2) reason = reason || "קטע לא צנוע";
  return reason;
}

function updateSkip(reason) {
  if (reason) {
    if (!skip) {
      skip = { clear: 0, muted: video.muted };
      video.muted = true;
      skippedCount++;
    }
    skip.clear = 0;
    $("skip-text").textContent = `מדלג על ${reason}`;
    if (!video.paused) video.currentTime = Math.min(video.duration - 0.1, video.currentTime + 1.5);
  } else if (skip && ++skip.clear >= 3) {
    video.muted = skip.muted;
    skip = null;
  }
  $("skip-msg").classList.toggle("hidden", !skip && !manualBlack);
  if (manualBlack && !skip) $("skip-text").textContent = "מסך מוחשך (B להמשך)";
}

function render(src) {
  const W = screen.width, H = screen.height;
  if (skip || manualBlack) {
    sctx.fillStyle = "#000";
    sctx.fillRect(0, 0, W, H);
    return;
  }
  sctx.drawImage(src, 0, 0, W, H);
  for (const p of people) {
    const cover = {
      arms: S.arms ? p.cover.arms : [false, false],
      legs: S.legs ? p.cover.legs : [false, false],
      neck: S.neck && p.cover.neck, torso: S.neck && p.cover.torso
    };
    drawGarments(sctx, garmentShapes(p.lm, cover, W, H), p.color, S.style, src);
    if (S.debug) debugDraw(p, W, H);
  }
}

function debugDraw(p, W, H) {
  sctx.save();
  sctx.fillStyle = "#0f0";
  for (const i of [L.nose, L.lSh, L.rSh, L.lEl, L.rEl, L.lHip, L.rHip, L.lKnee, L.rKnee]) {
    const q = p.lm[i];
    sctx.fillRect(q.x * W - 3, q.y * H - 3, 6, 6);
  }
  sctx.fillStyle = "#ff0";
  sctx.font = "14px sans-serif";
  const e = p.exp;
  sctx.fillText(`ידיים ${e.arms.map((v) => v.toFixed(1))} רגליים ${e.legs.map((v) => v.toFixed(1))} צוואר ${e.neck.toFixed(1)}`,
    p.lm[L.nose].x * W, p.lm[L.nose].y * H - 30);
  sctx.restore();
}

function process() {
  fctx.drawImage(video, 0, 0, frame.width, frame.height);
  wctx.drawImage(frame, 0, 0, work.width, work.height);
  const img = wctx.getImageData(0, 0, work.width, work.height);
  const res = analyze(work, S.scenes && frames % 2 === 0);
  const now = performance.now();
  for (const p of res.people) {
    p.exp = exposure(img, p.lm);
    p.color = garmentColor(img, p.lm);
  }
  tracker.update(res.people, now);
  people = res.people;
  lastRes = res;
  updateSkip(flagged(res));
  frames++;
  if (now - fpsT > 1000) {
    fps = frames * 1000 / (now - fpsT);
    frames = 0;
    fpsT = now;
    status(`מסנן פעיל · ${fps.toFixed(0)} פריימים בשנייה${skippedCount ? ` · דולגו ${skippedCount} קטעים` : ""}`);
  }
}

function loop() {
  if (ready && video.readyState >= 2 && (!video.paused || dirty)) {
    dirty = false;
    try {
      process();
      if (S.strict) render(frame);
    } catch (e) {
      console.error(e);
    }
  }
  if (!video.paused && "requestVideoFrameCallback" in video) video.requestVideoFrameCallback(loop);
  else requestAnimationFrame(loop);
}
loop();

// מצב לא-קפדני: וידאו חלק, הכיסוי מתעדכן לפי הזיהוי האחרון
(function smooth() {
  if (!S.strict && ready && video.readyState >= 2) render(video);
  requestAnimationFrame(smooth);
})();

// במצב קפדני לא מציגים כלום עד שהזיהוי מוכן
if (!ready) { sctx.fillStyle = "#000"; sctx.fillRect(0, 0, screen.width, screen.height); }

// ---------- פקדים ----------

const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const togglePlay = () => (video.paused ? video.play() : video.pause());
$("play").onclick = togglePlay;
screen.onclick = togglePlay;
$("back").onclick = () => { video.currentTime = Math.max(0, video.currentTime - 10); };
$("fwd").onclick = () => { video.currentTime = Math.min(video.duration, video.currentTime + 10); };
$("seek").oninput = (e) => { video.currentTime = e.target.value / 10; };
$("vol").oninput = (e) => { video.volume = e.target.value; };
$("mute").onclick = () => { if (skip) skip.muted = !skip.muted; else video.muted = !video.muted; };
$("full").onclick = () => (document.fullscreenElement ? document.exitFullscreen() : $("stage").requestFullscreen());
$("black").onclick = () => { manualBlack = !manualBlack; dirty = true; updateSkip(null); render(frame); };
video.onplay = () => { $("play").textContent = "⏸"; };
video.onpause = () => { $("play").textContent = "▶"; };
video.onseeked = () => { dirty = true; };
video.ontimeupdate = () => {
  $("time").textContent = `${fmt(video.currentTime)} / ${fmt(video.duration || 0)}`;
  $("seek").value = Math.floor(video.currentTime * 10);
  $("mute").textContent = video.muted && !skip ? "🔇" : "🔊";
};
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" && e.target.type === "url") return;
  if (e.code === "Space") { e.preventDefault(); togglePlay(); }
  else if (e.code === "ArrowLeft") video.currentTime -= 10;
  else if (e.code === "ArrowRight") video.currentTime += 10;
  else if (e.code === "KeyF") $("full").click();
  else if (e.code === "KeyB") $("black").click();
});

// לבדיקות ולאבחון תקלות מתוך כלי המפתחים
globalThis.modestDebug = { get people() { return people; }, get skip() { return skip; }, get fps() { return fps; }, get ready() { return ready; },
  get skipped() { return skippedCount; }, get faces() { return lastRes?.faces; }, get scene() { return lastRes?.scene; } };
