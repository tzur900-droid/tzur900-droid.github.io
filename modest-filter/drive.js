// מוסיף לדרייב כפתור "צפייה צנועה" כשפותחים קובץ וידאו.
(() => {
  const ID = /[\w-]{25,}/;
  function currentId() {
    const m = /\/file\/d\/([\w-]{20,})/.exec(location.pathname);
    if (m) return m[1];
    // תצוגה מקדימה שנפתחה מתוך תיקייה
    for (const f of document.querySelectorAll("iframe[src*='docid='], iframe[src*='/file/d/']")) {
      const s = f.getAttribute("src");
      const d = /docid=([\w-]{20,})/.exec(s) || /\/file\/d\/([\w-]{20,})/.exec(s);
      if (d) return d[1];
    }
    const dlg = document.querySelector("[role=dialog] [data-id], [role=dialog] a[href*='/file/d/']");
    if (dlg) {
      const v = dlg.getAttribute("data-id") || /\/file\/d\/([\w-]{20,})/.exec(dlg.href)?.[1];
      if (v && ID.test(v)) return v;
    }
    return null;
  }

  function isVideoPage() {
    return !!document.querySelector("video, iframe[src*='youtube.googleapis.com'], iframe[src*='docid=']") ||
      /\.(mp4|mkv|webm|mov|m4v|avi)\b/i.test(document.title);
  }

  const btn = document.createElement("button");
  btn.textContent = "🛡️ צפייה צנועה";
  btn.title = "פתח את הסרט בנגן הצנוע";
  Object.assign(btn.style, {
    position: "fixed", bottom: "24px", left: "24px", zIndex: 2147483647, padding: "12px 18px",
    font: "600 16px Arial, sans-serif", color: "#fff", background: "#5b3cc4", border: "none",
    borderRadius: "999px", boxShadow: "0 4px 16px rgba(0,0,0,.35)", cursor: "pointer", display: "none", direction: "rtl"
  });
  btn.onclick = () => {
    const id = currentId();
    if (!id) return;
    for (const v of document.querySelectorAll("video")) v.pause();
    chrome.runtime.sendMessage({ type: "open-drive", id });
  };
  document.documentElement.appendChild(btn);

  setInterval(() => {
    btn.style.display = currentId() && isVideoPage() ? "block" : "none";
  }, 1000);
})();
