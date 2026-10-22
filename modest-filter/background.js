// לחיצה על סמל התוסף, או על הכפתור בדרייב, פותחת את הנגן.
const open = (id) => chrome.tabs.create({ url: chrome.runtime.getURL("player.html" + (id ? "?drive=" + id : "")) });

chrome.action.onClicked.addListener(() => open());
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type === "open-drive") open(msg.id);
});
