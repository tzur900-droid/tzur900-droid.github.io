"use strict";

/* ---------- Firebase ---------- */

const firebaseConfig = {
  apiKey: "AIzaSyAqc98gW-LulNziHNH-bw6FjGqQu9nP6QE",
  authDomain: "alfon-netanya.firebaseapp.com",
  projectId: "alfon-netanya",
  storageBucket: "alfon-netanya.firebasestorage.app",
  messagingSenderId: "446549495013",
  appId: "1:446549495013:web:213456ef23e2b6254b980c",
};
firebase.initializeApp(firebaseConfig);
const fsdb = firebase.firestore();
fsdb.enablePersistence({ synchronizeTabs: true }).catch(() => {});

const contactsCol = fsdb.collection("contacts");
const gemachCol = fsdb.collection("gemachim");
const announcementCol = fsdb.collection("announcements");
const torahCol = fsdb.collection("torahArticles");
const settingsDoc = fsdb.collection("settings").doc("main");

/* ---------- Groups ---------- */

const CLASS_GROUPS = ["א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט", "י"];
const GRADUATE_GROUP = "בוגר";
const RABBIS_GROUP = "רבנים";
const GROUPS = [...CLASS_GROUPS, GRADUATE_GROUP, RABBIS_GROUP];
const SPECIAL_GROUP_LABELS = {
  [GRADUATE_GROUP]: GRADUATE_GROUP,
  [RABBIS_GROUP]: RABBIS_GROUP,
  י: "שיעור י' ומעלה",
};

function groupLabel(g) {
  return SPECIAL_GROUP_LABELS[g] || `שיעור ${g}`;
}

const TORAH_CATEGORIES = [
  { value: "shabbat", label: "שבתות" },
  { value: "chagim", label: "חגים" },
  { value: "general", label: "כלליים" },
];

const MAX_ATTACHMENT_BYTES = 650 * 1024;

/* ---------- State ---------- */

let editingId = null;
let searchGroupFilter = "all";
let galleryGroupFilter = "all";
let torahCategoryFilter = "all";
let pendingPhotoDataUrl = null;

let contactsCache = [];
let gemachimCache = [];
let announcementsCache = [];
let torahCache = [];
let settingsCache = {};

/* ---------- Helpers ---------- */

function initials(name) {
  return (name || "?").trim().charAt(0);
}

function digitsOnly(phone) {
  return (phone || "").replace(/\D/g, "");
}

function toWhatsAppNumber(phone) {
  let d = digitsOnly(phone);
  if (d.startsWith("0")) d = "972" + d.slice(1);
  return d;
}

function fileToDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function resizeImageToDataURL(file, maxSize = 700, quality = 0.82) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const reader = new FileReader();
    reader.onload = () => { img.src = reader.result; };
    reader.onerror = reject;
    img.onload = () => {
      let { width, height } = img;
      if (width > height && width > maxSize) {
        height = Math.round(height * (maxSize / width));
        width = maxSize;
      } else if (height > maxSize) {
        width = Math.round(width * (maxSize / height));
        height = maxSize;
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", quality));
    };
    img.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.add("hidden"), 2200);
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/* ---------- Admin PIN lock (shared via Firestore settings) ---------- */

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function isPinSet() {
  return !!settingsCache.pinHash;
}

function isAdminUnlocked() {
  return sessionStorage.getItem("adminUnlocked") === "1";
}

function updateAdminLockUI() {
  const setupBox = document.getElementById("pin-setup");
  const lockBox = document.getElementById("pin-lock");
  const content = document.getElementById("admin-content");
  document.getElementById("pin-error").classList.add("hidden");
  if (!isPinSet()) {
    setupBox.classList.remove("hidden");
    lockBox.classList.add("hidden");
    content.classList.add("hidden");
  } else if (!isAdminUnlocked()) {
    setupBox.classList.add("hidden");
    lockBox.classList.remove("hidden");
    content.classList.add("hidden");
    document.getElementById("pin-lock-input").value = "";
  } else {
    setupBox.classList.add("hidden");
    lockBox.classList.add("hidden");
    content.classList.remove("hidden");
  }
}

async function handlePinSetup() {
  const pin = document.getElementById("pin-setup-input").value.trim();
  const confirmPin = document.getElementById("pin-setup-confirm").value.trim();
  if (pin.length < 4) { showToast("הקוד חייב להכיל לפחות 4 תווים"); return; }
  if (pin !== confirmPin) { showToast("הקודים אינם תואמים"); return; }
  await settingsDoc.set({ pinHash: await sha256Hex(pin) }, { merge: true });
  sessionStorage.setItem("adminUnlocked", "1");
  document.getElementById("pin-setup-input").value = "";
  document.getElementById("pin-setup-confirm").value = "";
  showToast("הקוד הוגדר בהצלחה");
  updateAdminLockUI();
}

async function handlePinUnlock() {
  const pin = document.getElementById("pin-lock-input").value.trim();
  const hash = await sha256Hex(pin);
  if (hash === settingsCache.pinHash) {
    sessionStorage.setItem("adminUnlocked", "1");
    updateAdminLockUI();
  } else {
    document.getElementById("pin-error").classList.remove("hidden");
  }
}

function handleLock() {
  sessionStorage.removeItem("adminUnlocked");
  updateAdminLockUI();
  switchView("view-search");
}

async function handleResetPin() {
  if (!confirm("שינוי הקוד ידרוש הגדרה מחדש. להמשיך?")) return;
  await settingsDoc.set({ pinHash: firebase.firestore.FieldValue.delete() }, { merge: true });
  sessionStorage.removeItem("adminUnlocked");
  updateAdminLockUI();
}

/* ---------- Rendering ---------- */

function buildGroupChips(container, selected, onSelect) {
  container.innerHTML = "";
  const all = [{ label: "הכל", value: "all" }, ...GROUPS.map((g) => ({ label: groupLabel(g), value: g }))];
  for (const item of all) {
    const chip = document.createElement("button");
    chip.className = "chip" + (item.value === selected ? " active" : "");
    chip.textContent = item.label;
    chip.onclick = () => onSelect(item.value);
    container.appendChild(chip);
  }
}

function contactRow(contact, { showActions = false } = {}) {
  const li = document.createElement("li");
  li.className = "contact-row";

  const avatarWrap = document.createElement(contact.photo ? "img" : "div");
  avatarWrap.className = "contact-avatar";
  if (contact.photo) {
    avatarWrap.src = contact.photo;
  } else {
    avatarWrap.textContent = initials(contact.name);
  }

  const info = document.createElement("div");
  info.className = "contact-info";
  info.innerHTML = `<div class="contact-name"></div><div class="contact-sub"></div>`;
  info.querySelector(".contact-name").textContent = contact.name;
  info.querySelector(".contact-sub").textContent = `${groupLabel(contact.group)} · ${contact.phone}`;

  li.appendChild(avatarWrap);
  li.appendChild(info);

  if (showActions) {
    const actions = document.createElement("div");
    actions.className = "contact-actions";
    const editBtn = document.createElement("button");
    editBtn.className = "icon-btn";
    editBtn.textContent = "✏️";
    editBtn.onclick = (e) => { e.stopPropagation(); startEdit(contact); };
    const delBtn = document.createElement("button");
    delBtn.className = "icon-btn danger";
    delBtn.textContent = "🗑️";
    delBtn.onclick = (e) => { e.stopPropagation(); removeContact(contact); };
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
    li.appendChild(actions);
  }

  li.onclick = () => openDetail(contact);
  return li;
}

function renderSearch() {
  const q = document.getElementById("search-input").value.trim();
  const filtered = contactsCache.filter((c) => {
    const matchesGroup = searchGroupFilter === "all" || c.group === searchGroupFilter;
    const matchesQuery = !q || c.name.includes(q);
    return matchesGroup && matchesQuery;
  });
  const list = document.getElementById("search-results");
  list.innerHTML = "";
  filtered.forEach((c) => list.appendChild(contactRow(c)));
  document.getElementById("search-empty").classList.toggle("hidden", filtered.length > 0);
}

function renderGallery() {
  const withPhotos = contactsCache.filter((c) => c.photo && (galleryGroupFilter === "all" || c.group === galleryGroupFilter));
  const grid = document.getElementById("gallery-grid");
  grid.innerHTML = "";
  withPhotos.forEach((c) => {
    const item = document.createElement("div");
    item.className = "gallery-item";
    item.innerHTML = `<img src="${c.photo}" alt="${c.name}"><div class="cap"></div>`;
    item.querySelector(".cap").textContent = c.name;
    item.onclick = () => openDetail(c);
    grid.appendChild(item);
  });
  document.getElementById("gallery-empty").classList.toggle("hidden", withPhotos.length > 0);
}

function renderManageList() {
  const q = document.getElementById("manage-search").value.trim();
  const filtered = q ? contactsCache.filter((c) => c.name.includes(q)) : contactsCache;
  const list = document.getElementById("manage-list");
  list.innerHTML = "";
  filtered.forEach((c) => list.appendChild(contactRow(c, { showActions: true })));
}

function adminListRow(primaryText, secondaryText, onDelete) {
  const li = document.createElement("li");
  li.className = "contact-row";
  li.innerHTML = `<div class="contact-info"><div class="contact-name"></div><div class="contact-sub"></div></div>`;
  li.querySelector(".contact-name").textContent = primaryText;
  li.querySelector(".contact-sub").textContent = secondaryText || "";
  const actions = document.createElement("div");
  actions.className = "contact-actions";
  const delBtn = document.createElement("button");
  delBtn.className = "icon-btn danger";
  delBtn.textContent = "🗑️";
  delBtn.onclick = onDelete;
  actions.appendChild(delBtn);
  li.appendChild(actions);
  return li;
}

function renderAnnouncements() {
  const all = [...announcementsCache].sort((a, b) => new Date(b.date) - new Date(a.date));
  const list = document.getElementById("announcements-list");
  list.innerHTML = "";
  all.forEach((a) => {
    const li = document.createElement("li");
    li.className = "card-item";
    li.innerHTML = `<h3></h3><div class="card-date"></div><p class="card-body"></p>`;
    li.querySelector("h3").textContent = a.title;
    li.querySelector(".card-date").textContent = formatDate(a.date);
    li.querySelector(".card-body").textContent = a.text;
    list.appendChild(li);
  });
  document.getElementById("announcements-empty").classList.toggle("hidden", all.length > 0);

  const adminList = document.getElementById("admin-announcements-list");
  adminList.innerHTML = "";
  all.forEach((a) => {
    adminList.appendChild(
      adminListRow(a.title, formatDate(a.date), async () => {
        if (!confirm(`למחוק את ההודעה "${a.title}"?`)) return;
        await announcementCol.doc(a.id).delete();
        showToast("נמחק בהצלחה");
      })
    );
  });
}

function torahCategoryLabel(v) {
  const found = TORAH_CATEGORIES.find((c) => c.value === v);
  return found ? found.label : v;
}

function buildTorahChips() {
  const container = document.getElementById("torah-category-chips");
  container.innerHTML = "";
  const all = [{ value: "all", label: "הכל" }, ...TORAH_CATEGORIES];
  all.forEach((c) => {
    const chip = document.createElement("button");
    chip.className = "chip" + (c.value === torahCategoryFilter ? " active" : "");
    chip.textContent = c.label;
    chip.onclick = () => {
      torahCategoryFilter = c.value;
      buildTorahChips();
      renderTorah();
    };
    container.appendChild(chip);
  });
}

function renderTorah() {
  const all = [...torahCache].sort((a, b) => new Date(b.date) - new Date(a.date));
  const filtered = torahCategoryFilter === "all" ? all : all.filter((t) => t.category === torahCategoryFilter);
  const list = document.getElementById("torah-list");
  list.innerHTML = "";
  filtered.forEach((t) => {
    const li = document.createElement("li");
    li.className = "card-item";
    li.innerHTML = `<span class="card-tag"></span><h3></h3><p class="card-body"></p>`;
    li.querySelector(".card-tag").textContent = torahCategoryLabel(t.category);
    li.querySelector("h3").textContent = t.title;
    li.querySelector(".card-body").textContent = t.text;
    if (t.file) {
      const link = document.createElement("a");
      link.className = "card-file";
      link.href = t.file;
      link.download = t.fileName || "קובץ מצורף";
      link.textContent = "📎 " + (t.fileName || "קובץ מצורף");
      li.appendChild(link);
    }
    list.appendChild(li);
  });
  document.getElementById("torah-empty").classList.toggle("hidden", filtered.length > 0);

  const adminList = document.getElementById("admin-torah-list");
  adminList.innerHTML = "";
  all.forEach((t) => {
    adminList.appendChild(
      adminListRow(t.title, torahCategoryLabel(t.category), async () => {
        if (!confirm(`למחוק את "${t.title}"?`)) return;
        await torahCol.doc(t.id).delete();
        showToast("נמחק בהצלחה");
      })
    );
  });
}

function renderGemachim() {
  const list = document.getElementById("gemachim-list");
  list.innerHTML = "";
  gemachimCache.forEach((g) => {
    const li = document.createElement("li");
    li.className = "card-item";
    li.textContent = g.text;
    list.appendChild(li);
  });
  document.getElementById("gemachim-empty").classList.toggle("hidden", gemachimCache.length > 0);

  const adminList = document.getElementById("admin-gemachim-list");
  adminList.innerHTML = "";
  gemachimCache.forEach((g) => {
    adminList.appendChild(
      adminListRow(g.text, "", async () => {
        if (!confirm("למחוק פריט זה?")) return;
        await gemachCol.doc(g.id).delete();
        showToast("נמחק בהצלחה");
      })
    );
  });
}

function renderInfoTexts() {
  const map = [
    ["prayer", "prayer-text", "prayer-empty", "admin-prayer-text"],
    ["office", "office-text", "office-empty", "admin-office-text"],
  ];
  map.forEach(([key, textId, emptyId, adminId]) => {
    const value = settingsCache[key] || "";
    document.getElementById(textId).textContent = value;
    document.getElementById(emptyId).classList.toggle("hidden", !!value);
    const adminField = document.getElementById(adminId);
    if (adminField && document.activeElement !== adminField) adminField.value = value;
  });
}

function renderLessonsSchedule() {
  const text = settingsCache.lessons || "";
  document.getElementById("lessons-text").textContent = text;
  const adminField = document.getElementById("admin-lessons-text");
  if (document.activeElement !== adminField) adminField.value = text;

  const img = document.getElementById("lessons-image");
  const adminPreview = document.getElementById("admin-lessons-image-preview");
  const removeBtn = document.getElementById("remove-lessons-image-btn");
  const hasImage = !!settingsCache.lessonsImage;
  if (hasImage) {
    img.src = settingsCache.lessonsImage;
    img.classList.remove("hidden");
    adminPreview.src = settingsCache.lessonsImage;
    adminPreview.classList.remove("hidden");
    removeBtn.classList.remove("hidden");
  } else {
    img.classList.add("hidden");
    adminPreview.classList.add("hidden");
    removeBtn.classList.add("hidden");
  }
  document.getElementById("lessons-empty").classList.toggle("hidden", !!text || hasImage);
}

/* ---------- Detail modal ---------- */

function openDetail(contact) {
  document.getElementById("modal-photo").src = contact.photo || "icons/icon-192.png";
  document.getElementById("modal-name").textContent = contact.name;
  document.getElementById("modal-group").textContent = groupLabel(contact.group);
  document.getElementById("modal-phone").textContent = contact.phone;
  document.getElementById("modal-call").href = "tel:" + digitsOnly(contact.phone);
  document.getElementById("modal-sms").href = "sms:" + digitsOnly(contact.phone);
  document.getElementById("modal-whatsapp").href = "https://wa.me/" + toWhatsAppNumber(contact.phone);
  document.getElementById("detail-modal").classList.remove("hidden");
}

function closeDetail() {
  document.getElementById("detail-modal").classList.add("hidden");
}

/* ---------- Contact form ---------- */

function startEdit(contact) {
  editingId = contact.id;
  document.getElementById("contact-id").value = contact.id;
  document.getElementById("field-name").value = contact.name;
  document.getElementById("field-phone").value = contact.phone;
  document.getElementById("field-group").value = contact.group;
  const preview = document.getElementById("photo-preview");
  if (contact.photo) {
    preview.src = contact.photo;
    preview.classList.remove("hidden");
  } else {
    preview.classList.add("hidden");
  }
  pendingPhotoDataUrl = contact.photo || null;
  document.getElementById("cancel-edit-btn").classList.remove("hidden");
  document.getElementById("save-btn").textContent = "עדכון";
  switchView("view-add");
  document.getElementById("field-name").scrollIntoView({ behavior: "smooth", block: "center" });
}

function resetForm() {
  editingId = null;
  pendingPhotoDataUrl = null;
  document.getElementById("contact-form").reset();
  document.getElementById("contact-id").value = "";
  document.getElementById("photo-preview").classList.add("hidden");
  document.getElementById("cancel-edit-btn").classList.add("hidden");
  document.getElementById("save-btn").textContent = "שמירה";
}

async function removeContact(contact) {
  if (!confirm(`למחוק את ${contact.name}?`)) return;
  await contactsCol.doc(contact.id).delete();
  showToast("נמחק בהצלחה");
}

/* ---------- View switching ---------- */

function switchView(viewId) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === viewId));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === viewId));
}

/* ---------- Backup / restore ---------- */

async function exportBackup() {
  const data = {
    exportedAt: new Date().toISOString(),
    contacts: contactsCache.map((c) => ({ name: c.name, phone: c.phone, group: c.group, photo: c.photo || null })),
    gemachim: gemachimCache.map((g) => ({ text: g.text })),
    announcements: announcementsCache.map((a) => ({ title: a.title, text: a.text, date: a.date })),
    torahArticles: torahCache.map((t) => ({
      title: t.title,
      category: t.category,
      text: t.text,
      date: t.date,
      file: t.file || null,
      fileName: t.fileName || null,
      fileType: t.fileType || null,
    })),
    infoTexts: {
      prayer: settingsCache.prayer || "",
      lessons: settingsCache.lessons || "",
      office: settingsCache.office || "",
    },
    lessonsImage: settingsCache.lessonsImage ? { data: settingsCache.lessonsImage, type: settingsCache.lessonsImageType } : null,
  };
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `גיבוי-אלפון-נתניה-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast("הגיבוי הורד בהצלחה");
}

async function deleteAllInCollection(col) {
  const snap = await col.get();
  const batches = [];
  let batch = fsdb.batch();
  let count = 0;
  snap.docs.forEach((doc) => {
    batch.delete(doc.ref);
    count++;
    if (count === 400) {
      batches.push(batch.commit());
      batch = fsdb.batch();
      count = 0;
    }
  });
  if (count > 0) batches.push(batch.commit());
  await Promise.all(batches);
}

async function importBackup(file) {
  const text = await file.text();
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    showToast("קובץ לא תקין");
    return;
  }
  if (!confirm(`ייבוא הקובץ יחליף את כל הנתונים הקיימים (אנשי קשר, גמ"חים, מודעות, דברי תורה ומידע כללי) עבור כולם. להמשיך?`)) return;

  await deleteAllInCollection(contactsCol);
  for (const c of parsed.contacts || []) {
    await contactsCol.add({ name: c.name, phone: c.phone, group: c.group, photo: c.photo || null });
  }

  await deleteAllInCollection(gemachCol);
  for (const g of parsed.gemachim || []) {
    await gemachCol.add({ text: g.text });
  }

  await deleteAllInCollection(announcementCol);
  for (const a of parsed.announcements || []) {
    await announcementCol.add({ title: a.title, text: a.text, date: a.date });
  }

  await deleteAllInCollection(torahCol);
  for (const t of parsed.torahArticles || []) {
    await torahCol.add({
      title: t.title,
      category: t.category,
      text: t.text,
      date: t.date,
      file: t.file || null,
      fileName: t.fileName || null,
      fileType: t.fileType || null,
    });
  }

  const settingsUpdate = {};
  if (parsed.infoTexts) {
    settingsUpdate.prayer = parsed.infoTexts.prayer || "";
    settingsUpdate.lessons = parsed.infoTexts.lessons || "";
    settingsUpdate.office = parsed.infoTexts.office || "";
  }
  if (parsed.lessonsImage) {
    settingsUpdate.lessonsImage = parsed.lessonsImage.data;
    settingsUpdate.lessonsImageType = parsed.lessonsImage.type;
  } else {
    settingsUpdate.lessonsImage = firebase.firestore.FieldValue.delete();
    settingsUpdate.lessonsImageType = firebase.firestore.FieldValue.delete();
  }
  await settingsDoc.set(settingsUpdate, { merge: true });

  showToast("הייבוא הושלם בהצלחה");
}

/* ---------- Init ---------- */

function init() {
  const groupSelect = document.getElementById("field-group");
  GROUPS.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = groupLabel(g);
    groupSelect.appendChild(opt);
  });

  function setSearchGroup(v) {
    searchGroupFilter = v;
    buildGroupChips(document.getElementById("search-group-chips"), searchGroupFilter, setSearchGroup);
    renderSearch();
  }
  buildGroupChips(document.getElementById("search-group-chips"), searchGroupFilter, setSearchGroup);

  function setGalleryGroup(v) {
    galleryGroupFilter = v;
    buildGroupChips(document.getElementById("gallery-group-chips"), galleryGroupFilter, setGalleryGroup);
    renderGallery();
  }
  buildGroupChips(document.getElementById("gallery-group-chips"), galleryGroupFilter, setGalleryGroup);

  const INFO_PANELS = [
    { id: "panel-announcements", label: "לוח מודעות" },
    { id: "panel-prayer", label: "שעות תפילה" },
    { id: "panel-lessons", label: "מערכת שיעורים" },
    { id: "panel-torah", label: "דברי תורה" },
    { id: "panel-gemachim", label: 'גמ"חים' },
    { id: "panel-office", label: "יצירת קשר עם המשרד" },
  ];
  function showInfoPanel(panelId) {
    INFO_PANELS.forEach((p) => document.getElementById(p.id).classList.toggle("hidden", p.id !== panelId));
    document.querySelectorAll("#info-subnav .chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.panel === panelId);
    });
  }
  const infoSubnav = document.getElementById("info-subnav");
  INFO_PANELS.forEach((p, i) => {
    const chip = document.createElement("button");
    chip.className = "chip" + (i === 0 ? " active" : "");
    chip.textContent = p.label;
    chip.dataset.panel = p.id;
    chip.onclick = () => showInfoPanel(p.id);
    infoSubnav.appendChild(chip);
  });

  const publicTorahCategorySelect = document.getElementById("public-torah-category");
  TORAH_CATEGORIES.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.value;
    opt.textContent = c.label;
    publicTorahCategorySelect.appendChild(opt);
  });
  buildTorahChips();

  document.getElementById("save-prayer-btn").addEventListener("click", async () => {
    await settingsDoc.set({ prayer: document.getElementById("admin-prayer-text").value.trim() }, { merge: true });
    showToast("נשמר בהצלחה");
  });

  let pendingLessonsImage = null;
  let removeLessonsImageFlag = false;
  document.getElementById("admin-lessons-image").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const dataUrl = await resizeImageToDataURL(file);
    pendingLessonsImage = { dataUrl, type: "image/jpeg" };
    removeLessonsImageFlag = false;
    const preview = document.getElementById("admin-lessons-image-preview");
    preview.src = dataUrl;
    preview.classList.remove("hidden");
    document.getElementById("remove-lessons-image-btn").classList.remove("hidden");
  });
  document.getElementById("remove-lessons-image-btn").addEventListener("click", () => {
    if (!confirm("להסיר את תמונת מערכת השעות? (השינוי יישמר בלחיצה על שמירה)")) return;
    pendingLessonsImage = null;
    removeLessonsImageFlag = true;
    document.getElementById("admin-lessons-image").value = "";
    document.getElementById("admin-lessons-image-preview").classList.add("hidden");
    document.getElementById("remove-lessons-image-btn").classList.add("hidden");
  });
  document.getElementById("save-lessons-btn").addEventListener("click", async () => {
    const update = { lessons: document.getElementById("admin-lessons-text").value.trim() };
    if (pendingLessonsImage) {
      update.lessonsImage = pendingLessonsImage.dataUrl;
      update.lessonsImageType = pendingLessonsImage.type;
      pendingLessonsImage = null;
    } else if (removeLessonsImageFlag) {
      update.lessonsImage = firebase.firestore.FieldValue.delete();
      update.lessonsImageType = firebase.firestore.FieldValue.delete();
      removeLessonsImageFlag = false;
    }
    await settingsDoc.set(update, { merge: true });
    showToast("נשמר בהצלחה");
  });

  document.getElementById("save-office-btn").addEventListener("click", async () => {
    await settingsDoc.set({ office: document.getElementById("admin-office-text").value.trim() }, { merge: true });
    showToast("נשמר בהצלחה");
  });

  document.getElementById("add-announcement-btn").addEventListener("click", async () => {
    const title = document.getElementById("new-announcement-title").value.trim();
    const text = document.getElementById("new-announcement-text").value.trim();
    if (!title || !text) { showToast("יש למלא כותרת ותוכן"); return; }
    await announcementCol.add({ title, text, date: new Date().toISOString() });
    document.getElementById("new-announcement-title").value = "";
    document.getElementById("new-announcement-text").value = "";
    showToast("ההודעה פורסמה");
  });

  let pendingTorahFile = null;

  function resetPublicTorahForm() {
    document.getElementById("public-torah-title").value = "";
    document.getElementById("public-torah-text").value = "";
    document.getElementById("public-torah-file").value = "";
    document.getElementById("public-torah-file-name").classList.add("hidden");
    pendingTorahFile = null;
    document.getElementById("public-torah-form").classList.add("hidden");
  }

  document.getElementById("open-torah-form-btn").addEventListener("click", () => {
    document.getElementById("public-torah-form").classList.toggle("hidden");
  });
  document.getElementById("public-torah-cancel").addEventListener("click", resetPublicTorahForm);

  document.getElementById("public-torah-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    const nameEl = document.getElementById("public-torah-file-name");
    if (!file) {
      pendingTorahFile = null;
      nameEl.classList.add("hidden");
      return;
    }
    if (file.size > MAX_ATTACHMENT_BYTES) {
      showToast("הקובץ גדול מדי (מקסימום כ-650 קילובייט)");
      e.target.value = "";
      pendingTorahFile = null;
      nameEl.classList.add("hidden");
      return;
    }
    const dataUrl = await fileToDataURL(file);
    pendingTorahFile = { dataUrl, name: file.name, type: file.type };
    nameEl.textContent = "📎 " + file.name;
    nameEl.classList.remove("hidden");
  });

  document.getElementById("public-torah-submit").addEventListener("click", async () => {
    const title = document.getElementById("public-torah-title").value.trim();
    const category = document.getElementById("public-torah-category").value;
    const text = document.getElementById("public-torah-text").value.trim();
    if (!title || (!text && !pendingTorahFile)) {
      showToast("יש למלא כותרת, ולפחות תוכן או קובץ מצורף");
      return;
    }
    const record = { title, category, text, date: new Date().toISOString() };
    if (pendingTorahFile) {
      record.file = pendingTorahFile.dataUrl;
      record.fileName = pendingTorahFile.name;
      record.fileType = pendingTorahFile.type;
    }
    await torahCol.add(record);
    showToast("דבר התורה פורסם בהצלחה");
    resetPublicTorahForm();
  });

  document.getElementById("add-gemach-btn").addEventListener("click", async () => {
    const text = document.getElementById("new-gemach-text").value.trim();
    if (!text) return;
    await gemachCol.add({ text });
    document.getElementById("new-gemach-text").value = "";
    showToast("נוסף בהצלחה");
  });

  document.getElementById("search-input").addEventListener("input", renderSearch);
  document.getElementById("manage-search").addEventListener("input", renderManageList);

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      switchView(btn.dataset.view);
      if (btn.dataset.view === "view-add") updateAdminLockUI();
    });
  });

  document.getElementById("pin-setup-btn").addEventListener("click", handlePinSetup);
  document.getElementById("pin-unlock-btn").addEventListener("click", handlePinUnlock);
  document.getElementById("lock-btn").addEventListener("click", handleLock);
  document.getElementById("reset-pin-btn").addEventListener("click", handleResetPin);
  document.getElementById("pin-setup-confirm").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handlePinSetup();
  });
  document.getElementById("pin-lock-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handlePinUnlock();
  });

  document.getElementById("modal-close").addEventListener("click", closeDetail);
  document.getElementById("detail-modal").addEventListener("click", (e) => {
    if (e.target.id === "detail-modal") closeDetail();
  });

  document.getElementById("field-photo").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const dataUrl = await resizeImageToDataURL(file);
    pendingPhotoDataUrl = dataUrl;
    const preview = document.getElementById("photo-preview");
    preview.src = dataUrl;
    preview.classList.remove("hidden");
  });

  document.getElementById("cancel-edit-btn").addEventListener("click", resetForm);

  document.getElementById("contact-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("field-name").value.trim();
    const phone = document.getElementById("field-phone").value.trim();
    const group = document.getElementById("field-group").value;
    if (!name || !phone || !group) return;
    const contact = { name, phone, group, photo: pendingPhotoDataUrl || null };
    if (editingId) {
      await contactsCol.doc(editingId).set(contact);
    } else {
      await contactsCol.add(contact);
    }
    showToast(editingId ? "עודכן בהצלחה" : "נשמר בהצלחה");
    resetForm();
  });

  document.getElementById("export-btn").addEventListener("click", exportBackup);
  document.getElementById("import-btn").addEventListener("click", () => {
    document.getElementById("import-file").click();
  });
  document.getElementById("import-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) importBackup(file);
    e.target.value = "";
  });

  /* ---------- Live data subscriptions ---------- */

  contactsCol.onSnapshot((snap) => {
    contactsCache = snap.docs
      .map((d) => ({ id: d.id, ...d.data() }))
      .sort((a, b) => a.name.localeCompare(b.name, "he"));
    renderSearch();
    renderGallery();
    renderManageList();
  });

  gemachCol.onSnapshot((snap) => {
    gemachimCache = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
    renderGemachim();
  });

  announcementCol.onSnapshot((snap) => {
    announcementsCache = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
    renderAnnouncements();
  });

  torahCol.onSnapshot((snap) => {
    torahCache = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
    renderTorah();
  });

  settingsDoc.onSnapshot((doc) => {
    settingsCache = doc.data() || {};
    renderInfoTexts();
    renderLessonsSchedule();
    updateAdminLockUI();
  });
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  });
}

init();
