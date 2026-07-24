"use strict";

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
const DB_NAME = "alfonBeitElDB";
const DB_VERSION = 3;
const STORE = "contacts";
const GEMACH_STORE = "gemachim";
const ANNOUNCEMENT_STORE = "announcements";
const TORAH_STORE = "torahArticles";
const SINGLE_FILE_STORE = "singleFiles";
const LESSONS_IMAGE_KEY = "lessonsImage";

const TORAH_CATEGORIES = [
  { value: "shabbat", label: "שבתות" },
  { value: "chagim", label: "חגים" },
  { value: "general", label: "כלליים" },
];

let db;
let editingId = null;
let searchGroupFilter = "all";
let galleryGroupFilter = "all";
let torahCategoryFilter = "all";
let pendingPhotoBlob = null;

/* ---------- IndexedDB ---------- */

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const database = req.result;
      if (!database.objectStoreNames.contains(STORE)) {
        const store = database.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        store.createIndex("name", "name", { unique: false });
        store.createIndex("group", "group", { unique: false });
      }
      if (!database.objectStoreNames.contains(GEMACH_STORE)) {
        database.createObjectStore(GEMACH_STORE, { keyPath: "id", autoIncrement: true });
      }
      if (!database.objectStoreNames.contains(ANNOUNCEMENT_STORE)) {
        database.createObjectStore(ANNOUNCEMENT_STORE, { keyPath: "id", autoIncrement: true });
      }
      if (!database.objectStoreNames.contains(TORAH_STORE)) {
        database.createObjectStore(TORAH_STORE, { keyPath: "id", autoIncrement: true });
      }
      if (!database.objectStoreNames.contains(SINGLE_FILE_STORE)) {
        database.createObjectStore(SINGLE_FILE_STORE, { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(storeName, mode) {
  return db.transaction(storeName, mode).objectStore(storeName);
}

function getAllFromStore(storeName) {
  return new Promise((resolve, reject) => {
    const req = tx(storeName, "readonly").getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function addToStore(storeName, item) {
  return new Promise((resolve, reject) => {
    const req = tx(storeName, "readwrite").add(item);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function deleteFromStore(storeName, id) {
  return new Promise((resolve, reject) => {
    const req = tx(storeName, "readwrite").delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function clearStore(storeName) {
  return new Promise((resolve, reject) => {
    const req = tx(storeName, "readwrite").clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

/* ---------- Info text (localStorage) ---------- */

function getInfoText(key) {
  return localStorage.getItem("info_" + key) || "";
}

function setInfoText(key, value) {
  localStorage.setItem("info_" + key, value);
}

/* ---------- Single file storage (e.g. lessons schedule image) ---------- */

function putSingleFile(key, blob, type) {
  return new Promise((resolve, reject) => {
    const req = tx(SINGLE_FILE_STORE, "readwrite").put({ key, blob, type });
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function getSingleFile(key) {
  return new Promise((resolve, reject) => {
    const req = tx(SINGLE_FILE_STORE, "readonly").get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

function deleteSingleFile(key) {
  return new Promise((resolve, reject) => {
    const req = tx(SINGLE_FILE_STORE, "readwrite").delete(key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function getAllContacts() {
  return new Promise((resolve, reject) => {
    const req = tx(STORE, "readonly").getAll();
    req.onsuccess = () => resolve(req.result.sort((a, b) => a.name.localeCompare(b.name, "he")));
    req.onerror = () => reject(req.error);
  });
}

function saveContact(contact) {
  return new Promise((resolve, reject) => {
    const store = tx(STORE, "readwrite");
    const req = contact.id ? store.put(contact) : store.add(contact);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function deleteContactById(id) {
  return new Promise((resolve, reject) => {
    const req = tx(STORE, "readwrite").delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function clearAllContacts() {
  return new Promise((resolve, reject) => {
    const req = tx(STORE, "readwrite").clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

/* ---------- Admin PIN lock ---------- */

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function isPinSet() {
  return !!localStorage.getItem("pinHash");
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
    document.getElementById("pin-setup-input").value = "";
    document.getElementById("pin-setup-confirm").value = "";
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
  localStorage.setItem("pinHash", await sha256Hex(pin));
  sessionStorage.setItem("adminUnlocked", "1");
  showToast("הקוד הוגדר בהצלחה");
  updateAdminLockUI();
}

async function handlePinUnlock() {
  const pin = document.getElementById("pin-lock-input").value.trim();
  const hash = await sha256Hex(pin);
  if (hash === localStorage.getItem("pinHash")) {
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

function handleResetPin() {
  if (!confirm("שינוי הקוד ידרוש הגדרה מחדש. להמשיך?")) return;
  localStorage.removeItem("pinHash");
  sessionStorage.removeItem("adminUnlocked");
  updateAdminLockUI();
}

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

function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function dataURLToBlob(dataURL) {
  return fetch(dataURL).then((r) => r.blob());
}

function resizeImageToBlob(file, maxSize = 700, quality = 0.82) {
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
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", quality);
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

const photoUrlCache = new Map();
function photoUrl(contact) {
  if (!contact.photo) return null;
  if (photoUrlCache.has(contact.id)) return photoUrlCache.get(contact.id);
  const url = URL.createObjectURL(contact.photo);
  photoUrlCache.set(contact.id, url);
  return url;
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
    avatarWrap.src = photoUrl(contact);
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

async function renderSearch() {
  const all = await getAllContacts();
  const q = document.getElementById("search-input").value.trim();
  const filtered = all.filter((c) => {
    const matchesGroup = searchGroupFilter === "all" || c.group === searchGroupFilter;
    const matchesQuery = !q || c.name.includes(q);
    return matchesGroup && matchesQuery;
  });
  const list = document.getElementById("search-results");
  list.innerHTML = "";
  filtered.forEach((c) => list.appendChild(contactRow(c)));
  document.getElementById("search-empty").classList.toggle("hidden", filtered.length > 0);
}

async function renderGallery() {
  const all = await getAllContacts();
  const withPhotos = all.filter((c) => c.photo && (galleryGroupFilter === "all" || c.group === galleryGroupFilter));
  const grid = document.getElementById("gallery-grid");
  grid.innerHTML = "";
  withPhotos.forEach((c) => {
    const item = document.createElement("div");
    item.className = "gallery-item";
    item.innerHTML = `<img src="${photoUrl(c)}" alt="${c.name}"><div class="cap"></div>`;
    item.querySelector(".cap").textContent = c.name;
    item.onclick = () => openDetail(c);
    grid.appendChild(item);
  });
  document.getElementById("gallery-empty").classList.toggle("hidden", withPhotos.length > 0);
}

async function renderManageList() {
  const all = await getAllContacts();
  const q = document.getElementById("manage-search").value.trim();
  const filtered = q ? all.filter((c) => c.name.includes(q)) : all;
  const list = document.getElementById("manage-list");
  list.innerHTML = "";
  filtered.forEach((c) => list.appendChild(contactRow(c, { showActions: true })));
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" });
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

async function renderAnnouncements() {
  const all = await getAllFromStore(ANNOUNCEMENT_STORE);
  all.sort((a, b) => new Date(b.date) - new Date(a.date));
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
        await deleteFromStore(ANNOUNCEMENT_STORE, a.id);
        showToast("נמחק בהצלחה");
        await renderAnnouncements();
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

async function renderTorah() {
  const all = await getAllFromStore(TORAH_STORE);
  all.sort((a, b) => new Date(b.date) - new Date(a.date));
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
    if (t.fileBlob) {
      const link = document.createElement("a");
      link.className = "card-file";
      link.href = URL.createObjectURL(t.fileBlob);
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
        await deleteFromStore(TORAH_STORE, t.id);
        showToast("נמחק בהצלחה");
        await renderTorah();
      })
    );
  });
}

async function renderGemachim() {
  const all = await getAllFromStore(GEMACH_STORE);
  const list = document.getElementById("gemachim-list");
  list.innerHTML = "";
  all.forEach((g) => {
    const li = document.createElement("li");
    li.className = "card-item";
    li.textContent = g.text;
    list.appendChild(li);
  });
  document.getElementById("gemachim-empty").classList.toggle("hidden", all.length > 0);

  const adminList = document.getElementById("admin-gemachim-list");
  adminList.innerHTML = "";
  all.forEach((g) => {
    adminList.appendChild(
      adminListRow(g.text, "", async () => {
        if (!confirm("למחוק פריט זה?")) return;
        await deleteFromStore(GEMACH_STORE, g.id);
        showToast("נמחק בהצלחה");
        await renderGemachim();
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
    const value = getInfoText(key);
    document.getElementById(textId).textContent = value;
    document.getElementById(emptyId).classList.toggle("hidden", !!value);
    const adminField = document.getElementById(adminId);
    if (adminField && document.activeElement !== adminField) adminField.value = value;
  });
}

async function renderLessonsSchedule() {
  const text = getInfoText("lessons");
  document.getElementById("lessons-text").textContent = text;
  const adminField = document.getElementById("admin-lessons-text");
  if (document.activeElement !== adminField) adminField.value = text;

  const fileRec = await getSingleFile(LESSONS_IMAGE_KEY);
  const img = document.getElementById("lessons-image");
  const adminPreview = document.getElementById("admin-lessons-image-preview");
  const removeBtn = document.getElementById("remove-lessons-image-btn");
  const hasImage = !!(fileRec && fileRec.blob);
  if (hasImage) {
    const url = URL.createObjectURL(fileRec.blob);
    img.src = url;
    img.classList.remove("hidden");
    adminPreview.src = url;
    adminPreview.classList.remove("hidden");
    removeBtn.classList.remove("hidden");
  } else {
    img.classList.add("hidden");
    adminPreview.classList.add("hidden");
    removeBtn.classList.add("hidden");
  }
  document.getElementById("lessons-empty").classList.toggle("hidden", !!text || hasImage);
}

async function refreshAll() {
  await Promise.all([
    renderSearch(),
    renderGallery(),
    renderManageList(),
    renderAnnouncements(),
    renderTorah(),
    renderGemachim(),
    renderLessonsSchedule(),
  ]);
  renderInfoTexts();
}

/* ---------- Detail modal ---------- */

function openDetail(contact) {
  document.getElementById("modal-photo").src = contact.photo ? photoUrl(contact) : "icons/icon-192.png";
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

/* ---------- Form ---------- */

function startEdit(contact) {
  editingId = contact.id;
  document.getElementById("contact-id").value = contact.id;
  document.getElementById("field-name").value = contact.name;
  document.getElementById("field-phone").value = contact.phone;
  document.getElementById("field-group").value = contact.group;
  const preview = document.getElementById("photo-preview");
  if (contact.photo) {
    preview.src = photoUrl(contact);
    preview.classList.remove("hidden");
  } else {
    preview.classList.add("hidden");
  }
  pendingPhotoBlob = contact.photo || null;
  document.getElementById("cancel-edit-btn").classList.remove("hidden");
  document.getElementById("save-btn").textContent = "עדכון";
  switchView("view-add");
  document.getElementById("field-name").scrollIntoView({ behavior: "smooth", block: "center" });
}

function resetForm() {
  editingId = null;
  pendingPhotoBlob = null;
  document.getElementById("contact-form").reset();
  document.getElementById("contact-id").value = "";
  document.getElementById("photo-preview").classList.add("hidden");
  document.getElementById("cancel-edit-btn").classList.add("hidden");
  document.getElementById("save-btn").textContent = "שמירה";
}

async function removeContact(contact) {
  if (!confirm(`למחוק את ${contact.name}?`)) return;
  await deleteContactById(contact.id);
  photoUrlCache.delete(contact.id);
  showToast("נמחק בהצלחה");
  await refreshAll();
}

/* ---------- View switching ---------- */

function switchView(viewId) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === viewId));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === viewId));
}

/* ---------- Backup / restore ---------- */

async function exportBackup() {
  const all = await getAllContacts();
  const contacts = await Promise.all(
    all.map(async (c) => ({
      name: c.name,
      phone: c.phone,
      group: c.group,
      photo: c.photo ? await blobToDataURL(c.photo) : null,
    }))
  );
  const gemachim = (await getAllFromStore(GEMACH_STORE)).map((g) => ({ text: g.text }));
  const announcements = (await getAllFromStore(ANNOUNCEMENT_STORE)).map((a) => ({
    title: a.title,
    text: a.text,
    date: a.date,
  }));
  const torahArticles = await Promise.all(
    (await getAllFromStore(TORAH_STORE)).map(async (t) => ({
      title: t.title,
      category: t.category,
      text: t.text,
      date: t.date,
      file: t.fileBlob ? await blobToDataURL(t.fileBlob) : null,
      fileName: t.fileName || null,
      fileType: t.fileType || null,
    }))
  );
  const infoTexts = {
    prayer: getInfoText("prayer"),
    lessons: getInfoText("lessons"),
    office: getInfoText("office"),
  };
  const lessonsImageRec = await getSingleFile(LESSONS_IMAGE_KEY);
  const lessonsImage = lessonsImageRec
    ? { data: await blobToDataURL(lessonsImageRec.blob), type: lessonsImageRec.type }
    : null;
  const blob = new Blob(
    [
      JSON.stringify({
        exportedAt: new Date().toISOString(),
        contacts,
        gemachim,
        announcements,
        torahArticles,
        infoTexts,
        lessonsImage,
      }),
    ],
    { type: "application/json" }
  );
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

async function importBackup(file) {
  const text = await file.text();
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    showToast("קובץ לא תקין");
    return;
  }
  const contacts = parsed.contacts || [];
  if (!confirm(`ייבוא הקובץ יחליף את כל הנתונים הקיימים (אנשי קשר, גמ"חים, מודעות, דברי תורה ומידע כללי). להמשיך?`)) return;

  await clearAllContacts();
  photoUrlCache.clear();
  for (const c of contacts) {
    const photo = c.photo ? await dataURLToBlob(c.photo) : null;
    await saveContact({ name: c.name, phone: c.phone, group: c.group, photo });
  }

  await clearStore(GEMACH_STORE);
  for (const g of parsed.gemachim || []) {
    await addToStore(GEMACH_STORE, { text: g.text });
  }

  await clearStore(ANNOUNCEMENT_STORE);
  for (const a of parsed.announcements || []) {
    await addToStore(ANNOUNCEMENT_STORE, { title: a.title, text: a.text, date: a.date });
  }

  await clearStore(TORAH_STORE);
  for (const t of parsed.torahArticles || []) {
    const record = { title: t.title, category: t.category, text: t.text, date: t.date };
    if (t.file) {
      record.fileBlob = await dataURLToBlob(t.file);
      record.fileName = t.fileName;
      record.fileType = t.fileType;
    }
    await addToStore(TORAH_STORE, record);
  }

  if (parsed.infoTexts) {
    setInfoText("prayer", parsed.infoTexts.prayer || "");
    setInfoText("lessons", parsed.infoTexts.lessons || "");
    setInfoText("office", parsed.infoTexts.office || "");
  }

  if (parsed.lessonsImage) {
    await putSingleFile(LESSONS_IMAGE_KEY, await dataURLToBlob(parsed.lessonsImage.data), parsed.lessonsImage.type);
  } else {
    await deleteSingleFile(LESSONS_IMAGE_KEY);
  }

  showToast("הייבוא הושלם בהצלחה");
  await refreshAll();
}

/* ---------- Init ---------- */

async function init() {
  db = await openDB();

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

  document.getElementById("save-prayer-btn").addEventListener("click", () => {
    setInfoText("prayer", document.getElementById("admin-prayer-text").value.trim());
    renderInfoTexts();
    showToast("נשמר בהצלחה");
  });
  let pendingLessonsImage = null;
  document.getElementById("admin-lessons-image").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    pendingLessonsImage = file;
    const preview = document.getElementById("admin-lessons-image-preview");
    preview.src = URL.createObjectURL(file);
    preview.classList.remove("hidden");
    document.getElementById("remove-lessons-image-btn").classList.remove("hidden");
  });
  document.getElementById("remove-lessons-image-btn").addEventListener("click", async () => {
    if (!confirm("להסיר את תמונת מערכת השעות?")) return;
    pendingLessonsImage = "remove";
    await deleteSingleFile(LESSONS_IMAGE_KEY);
    document.getElementById("admin-lessons-image").value = "";
    showToast("התמונה הוסרה");
    await renderLessonsSchedule();
  });
  document.getElementById("save-lessons-btn").addEventListener("click", async () => {
    setInfoText("lessons", document.getElementById("admin-lessons-text").value.trim());
    if (pendingLessonsImage && pendingLessonsImage !== "remove") {
      await putSingleFile(LESSONS_IMAGE_KEY, pendingLessonsImage, pendingLessonsImage.type);
      pendingLessonsImage = null;
    }
    await renderLessonsSchedule();
    showToast("נשמר בהצלחה");
  });
  document.getElementById("save-office-btn").addEventListener("click", () => {
    setInfoText("office", document.getElementById("admin-office-text").value.trim());
    renderInfoTexts();
    showToast("נשמר בהצלחה");
  });

  document.getElementById("add-announcement-btn").addEventListener("click", async () => {
    const title = document.getElementById("new-announcement-title").value.trim();
    const text = document.getElementById("new-announcement-text").value.trim();
    if (!title || !text) { showToast("יש למלא כותרת ותוכן"); return; }
    await addToStore(ANNOUNCEMENT_STORE, { title, text, date: new Date().toISOString() });
    document.getElementById("new-announcement-title").value = "";
    document.getElementById("new-announcement-text").value = "";
    showToast("ההודעה פורסמה");
    await renderAnnouncements();
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

  document.getElementById("public-torah-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    const nameEl = document.getElementById("public-torah-file-name");
    if (file) {
      pendingTorahFile = file;
      nameEl.textContent = "📎 " + file.name;
      nameEl.classList.remove("hidden");
    } else {
      pendingTorahFile = null;
      nameEl.classList.add("hidden");
    }
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
      record.fileBlob = pendingTorahFile;
      record.fileName = pendingTorahFile.name;
      record.fileType = pendingTorahFile.type;
    }
    await addToStore(TORAH_STORE, record);
    showToast("דבר התורה פורסם בהצלחה");
    resetPublicTorahForm();
    await renderTorah();
  });

  document.getElementById("add-gemach-btn").addEventListener("click", async () => {
    const text = document.getElementById("new-gemach-text").value.trim();
    if (!text) return;
    await addToStore(GEMACH_STORE, { text });
    document.getElementById("new-gemach-text").value = "";
    showToast("נוסף בהצלחה");
    await renderGemachim();
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
    const blob = await resizeImageToBlob(file);
    pendingPhotoBlob = blob;
    const preview = document.getElementById("photo-preview");
    preview.src = URL.createObjectURL(blob);
    preview.classList.remove("hidden");
  });

  document.getElementById("cancel-edit-btn").addEventListener("click", resetForm);

  document.getElementById("contact-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("field-name").value.trim();
    const phone = document.getElementById("field-phone").value.trim();
    const group = document.getElementById("field-group").value;
    if (!name || !phone || !group) return;
    const contact = { name, phone, group, photo: pendingPhotoBlob };
    if (editingId) contact.id = editingId;
    await saveContact(contact);
    showToast(editingId ? "עודכן בהצלחה" : "נשמר בהצלחה");
    resetForm();
    await refreshAll();
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

  await refreshAll();
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  });
}

init();
