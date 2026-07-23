"use strict";

const CLASS_GROUPS = ["א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט", "י"];
const GRADUATE_GROUP = "בוגר";
const GROUPS = [...CLASS_GROUPS, GRADUATE_GROUP];

function groupLabel(g) {
  return g === GRADUATE_GROUP ? GRADUATE_GROUP : `שיעור ${g}`;
}
const DB_NAME = "alfonBeitElDB";
const DB_VERSION = 1;
const STORE = "contacts";

let db;
let editingId = null;
let searchGroupFilter = "all";
let galleryGroupFilter = "all";
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
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(storeName, mode) {
  return db.transaction(storeName, mode).objectStore(storeName);
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

async function refreshAll() {
  await Promise.all([renderSearch(), renderGallery(), renderManageList()]);
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
  const data = await Promise.all(
    all.map(async (c) => ({
      name: c.name,
      phone: c.phone,
      group: c.group,
      photo: c.photo ? await blobToDataURL(c.photo) : null,
    }))
  );
  const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), contacts: data })], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `גיבוי-אלפון-בית-אל-${new Date().toISOString().slice(0, 10)}.json`;
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
  if (!Array.isArray(contacts) || contacts.length === 0) {
    showToast("לא נמצאו אנשי קשר בקובץ");
    return;
  }
  if (!confirm(`ייבוא ${contacts.length} אנשי קשר יחליף את כל הנתונים הקיימים. להמשיך?`)) return;
  await clearAllContacts();
  photoUrlCache.clear();
  for (const c of contacts) {
    const photo = c.photo ? await dataURLToBlob(c.photo) : null;
    await saveContact({ name: c.name, phone: c.phone, group: c.group, photo });
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
