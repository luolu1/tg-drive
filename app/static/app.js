console.log("app.js loaded - fixed double file picker");
const dropZone = document.getElementById("dropZone");
const filePicker = document.getElementById("filePicker");
const pickBtn = document.getElementById("pickBtn");
const uploadStatus = document.getElementById("uploadStatus");
const searchInput = document.getElementById("search");
const refreshBtn = document.getElementById("refreshBtn");
const shareExpire = document.getElementById("shareExpire");
const fileList = document.getElementById("fileList");
/* -----------------------------
   Utils
----------------------------- */
function setStatus(msg) {
  if (uploadStatus) uploadStatus.textContent = msg || "";
}
function fmtTime(iso) {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
async function safeCopy(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      alert("已复制到剪贴板");
    } else {
      throw new Error();
    }
  } catch {
    window.prompt("复制下面的链接：", text);
  }
}
/* -----------------------------
   API
----------------------------- */
async function fetchFiles() {
  const q = (searchInput?.value || "").trim();
  const res = await fetch(`/api/files?q=${encodeURIComponent(q)}`, {
    credentials: "include"
  });
  if (!res.ok) throw new Error("load files failed");
  return await res.json();
}
async function uploadOne(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/upload", {
    method: "POST",
    body: fd,
    credentials: "include"
  });
  if (!res.ok) throw new Error("Upload failed");
}
async function createShare(fileId) {
  const hours = Number(shareExpire?.value || "24");
  const fd = new FormData();
  fd.append("file_id", String(fileId));
  fd.append("expires_hours", String(hours));
  const res = await fetch("/api/share", {
    method: "POST",
    body: fd,
    credentials: "include"
  });
  if (!res.ok) throw new Error("Create share failed");
  return await res.json();
}
async function revokeShare(shareId) {
  const fd = new FormData();
  fd.append("share_id", String(shareId));
  const res = await fetch("/api/share/revoke", {
    method: "POST",
    body: fd,
    credentials: "include"
  });
  if (!res.ok) throw new Error("Revoke share failed");
}
async function deleteFile(fileId) {
  const res = await fetch(`/api/files/${fileId}`, {
    method: "DELETE",
    credentials: "include"
  });
  if (!res.ok) throw new Error("Delete failed");
}
/* -----------------------------
   Render
----------------------------- */
function renderShareList(shares) {
  if (!shares?.length) return "";
  const visible = shares.filter(s => !s.revoked);
  if (!visible.length) return "";
  return `
    <div class="mt-2 space-y-2">
      ${visible.map(s => `
        <div class="border rounded p-2 bg-gray-50 text-xs">
          <div class="flex justify-between">
            <div>
              ${s.active
                ? '<span class="text-green-700">active</span>'
                : '<span class="text-gray-400">inactive</span>'}
              · expires: ${fmtTime(s.expires_at)}
            </div>
            <div class="space-x-2">
              <button data-copy="${escapeHtml(s.url)}" class="text-blue-600">复制</button>
              <button data-revoke="${s.id}" class="text-red-600">撤销</button>
            </div>
          </div>
          <div class="mt-1 break-all">${escapeHtml(s.url)}</div>
        </div>
      `).join("")}
    </div>
  `;
}
async function loadFiles() {
  const files = await fetchFiles();
  fileList.innerHTML = "";
  files.forEach(f => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="p-3">
        <div class="font-medium">${escapeHtml(f.filename)}</div>
        <div class="text-xs text-gray-400">#${f.id}</div>
        ${renderShareList(f.shares)}
      </td>
      <td class="p-3">${fmtTime(f.created_at)}</td>
      <td class="p-3 space-x-3">
        <a href="${escapeHtml(f.download_url)}" target="_blank" class="text-blue-600">下载</a>
        <button data-share="${f.id}" class="text-green-700">分享</button>
        <button data-del="${f.id}" class="text-red-600">删除</button>
      </td>
    `;
    fileList.appendChild(tr);
  });
  fileList.querySelectorAll("[data-share]").forEach(btn => {
    btn.onclick = async () => {
      const id = Number(btn.dataset.share);
      const data = await createShare(id);
      await safeCopy(data.url);
      await loadFiles();
    };
  });
  fileList.querySelectorAll("[data-del]").forEach(btn => {
    btn.onclick = async () => {
      const id = Number(btn.dataset.del);
      if (!confirm("确认删除？")) return;
      await deleteFile(id);
      await loadFiles();
    };
  });
  fileList.querySelectorAll("[data-revoke]").forEach(btn => {
    btn.onclick = async () => {
      const id = Number(btn.dataset.revoke);
      if (!confirm("确认撤销分享？")) return;
      await revokeShare(id);
      await loadFiles();
    };
  });
  fileList.querySelectorAll("[data-copy]").forEach(btn => {
    btn.onclick = () => safeCopy(btn.dataset.copy);
  });
}
/* -----------------------------
   Upload
----------------------------- */
async function uploadFiles(files) {
  try {
    setStatus(`上传中：${files.length} 个文件`);
    for (const f of files) {
      setStatus(`上传中：${f.name}`);
      await uploadOne(f);
    }
    setStatus("上传完成");
    await loadFiles();
  } catch (e) {
    alert(e.message || "Upload failed");
  } finally {
    setTimeout(() => setStatus(""), 1500);
  }
}
/* -----------------------------
   Bindings（关键修复）
----------------------------- */
// 阻止浏览器默认拖拽行为
window.addEventListener("dragover", e => e.preventDefault());
window.addEventListener("drop", e => e.preventDefault());
// 🚫 dropZone 不再处理 click
if (dropZone) {
  dropZone.ondragover = e => {
    e.preventDefault();
    dropZone.classList.add("border-black");
  };
  dropZone.ondragleave = () => {
    dropZone.classList.remove("border-black");
  };
  dropZone.ondrop = async e => {
    e.preventDefault();
    dropZone.classList.remove("border-black");
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) await uploadFiles(files);
  };
}
// ✅ 只有按钮触发文件选择
if (pickBtn && filePicker) {
  pickBtn.onclick = () => {
    filePicker.value = "";
    filePicker.click();
  };
  filePicker.onchange = async () => {
    const files = Array.from(filePicker.files || []);
    if (files.length) await uploadFiles(files);
    filePicker.value = "";
  };
}
if (refreshBtn) refreshBtn.onclick = loadFiles;
if (searchInput) {
  let t;
  searchInput.oninput = () => {
    clearTimeout(t);
    t = setTimeout(loadFiles, 200);
  };
}
loadFiles();
