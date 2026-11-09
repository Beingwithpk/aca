let state = {
  token: localStorage.getItem("token") || null,
  user: JSON.parse(localStorage.getItem("user") || "null"),
  activeTab: "chat",
  courses: [],
  selectedCourse: null,
  authMode: "login",
  roster: []
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("attDate").valueAsDate = new Date();
  renderAuthHeader();
  if (state.token) {
    await fetchCurrentUser();
    await loadCourses();
  } else {
    openAuthModal();
  }
});

// --- API Client ---
async function api(endpoint, options = {}) {
  const headers = options.headers || {};
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(endpoint, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "API request failed.");
  }
  return data;
}

// --- Auth Operations ---
function renderAuthHeader() {
  const container = document.getElementById("authActions");
  const uploadContainer = document.getElementById("uploadContainer");
  const tabAttendance = document.getElementById("tabAttendance");
  const tabCourses = document.getElementById("tabCourses");

  if (state.user) {
    const roleBadgeColor = {
      admin: "bg-rose-900/60 text-rose-300 border-rose-700/50",
      faculty: "bg-amber-900/60 text-amber-300 border-amber-700/50",
      student: "bg-emerald-900/60 text-emerald-300 border-emerald-700/50"
    }[state.user.role] || "bg-slate-800 text-slate-300";

    container.innerHTML = `
      <div class="flex items-center space-x-3 text-xs">
        <div class="text-right">
          <p class="font-semibold text-white leading-tight">${state.user.full_name}</p>
          <span class="inline-block mt-0.5 px-2 py-0.2 rounded-full border text-[10px] font-mono uppercase ${roleBadgeColor}">
            ${state.user.role}
          </span>
        </div>
        <button onclick="logout()" class="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg" title="Sign Out">
          <i class="fa-solid fa-arrow-right-from-bracket"></i>
        </button>
      </div>
    `;

    // Role-based UI visibility
    if (["faculty", "admin"].includes(state.user.role)) {
      uploadContainer.classList.remove("hidden");
      tabAttendance.classList.remove("hidden");
    } else {
      uploadContainer.classList.add("hidden");
      tabAttendance.classList.add("hidden");
    }

    if (state.user.role === "admin") {
      tabCourses.classList.remove("hidden");
    } else {
      tabCourses.classList.add("hidden");
    }
  } else {
    container.innerHTML = `
      <button onclick="openAuthModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-xl">
        Sign In / Register
      </button>
    `;
    uploadContainer.classList.add("hidden");
    tabAttendance.classList.add("hidden");
    tabCourses.classList.add("hidden");
  }
}

function openAuthModal() {
  document.getElementById("authModal").classList.remove("hidden");
}

function closeAuthModal() {
  if (!state.token) return;
  document.getElementById("authModal").classList.add("hidden");
}

function toggleAuthMode(mode) {
  state.authMode = mode;
  const loginTab = document.getElementById("modalTabLogin");
  const signupTab = document.getElementById("modalTabSignup");
  const signupFields = document.getElementById("signupFields");
  const submitBtn = document.getElementById("authSubmitBtn");

  if (mode === "login") {
    loginTab.className = "flex-1 pb-3 text-sm font-semibold border-b-2 border-indigo-500 text-indigo-400";
    signupTab.className = "flex-1 pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-400 hover:text-slate-200";
    signupFields.classList.add("hidden");
    submitBtn.textContent = "Sign In";
  } else {
    signupTab.className = "flex-1 pb-3 text-sm font-semibold border-b-2 border-indigo-500 text-indigo-400";
    loginTab.className = "flex-1 pb-3 text-sm font-semibold border-b-2 border-transparent text-slate-400 hover:text-slate-200";
    signupFields.classList.remove("hidden");
    submitBtn.textContent = "Create Account";
  }
}

function onRoleChanged() {
  const role = document.getElementById("authRole").value;
  const extra = document.getElementById("studentExtraFields");
  if (role === "student") {
    extra.classList.remove("hidden");
  } else {
    extra.classList.add("hidden");
  }
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const errorEl = document.getElementById("authError");
  errorEl.classList.add("hidden");

  const email = document.getElementById("authEmail").value;
  const password = document.getElementById("authPassword").value;

  try {
    if (state.authMode === "login") {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      state.token = data.access_token;
      state.user = data.user;
      localStorage.setItem("token", state.token);
      localStorage.setItem("user", JSON.stringify(state.user));
    } else {
      const full_name = document.getElementById("authFullName").value;
      const role = document.getElementById("authRole").value;
      const branch = document.getElementById("authBranch").value;
      const scholar_no = document.getElementById("authScholarNo").value;

      await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name, role, branch, scholar_no })
      });

      // Auto login after registration
      const loginData = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      state.token = loginData.access_token;
      state.user = loginData.user;
      localStorage.setItem("token", state.token);
      localStorage.setItem("user", JSON.stringify(state.user));
    }

    closeAuthModal();
    renderAuthHeader();
    await loadCourses();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

async function fetchCurrentUser() {
  try {
    const user = await api("/api/auth/me");
    state.user = user;
    localStorage.setItem("user", JSON.stringify(user));
    renderAuthHeader();
  } catch {
    logout();
  }
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.clear();
  renderAuthHeader();
  openAuthModal();
}

// --- Tabs Management ---
function switchTab(tab) {
  state.activeTab = tab;
  ["chat", "attendance", "courses"].forEach(t => {
    const view = document.getElementById(`view${t.charAt(0).toUpperCase() + t.slice(1)}`);
    const btn = document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`);
    if (t === tab) {
      view.classList.remove("hidden");
      btn.className = "py-3 border-b-2 border-indigo-500 text-indigo-400 flex items-center space-x-2";
    } else {
      view.classList.add("hidden");
      btn.className = "py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 flex items-center space-x-2";
    }
  });

  if (tab === "courses" && state.user?.role === "admin") {
    renderAdminCourses();
  }
}

// --- Courses ---
async function loadCourses() {
  try {
    state.courses = await api("/api/courses");
    const select1 = document.getElementById("courseSelect");
    const select2 = document.getElementById("attCourseSelect");

    const options = state.courses.map(c => `<option value="${c.code}">${c.code} - ${c.title}</option>`).join("");
    select1.innerHTML = `<option value="">-- Choose Subject --</option>` + options;
    select2.innerHTML = options;

    if (state.courses.length > 0 && !state.selectedCourse) {
      select1.value = state.courses[0].code;
      onCourseSelected();
    }
  } catch (err) {
    console.error("Course loading error:", err);
  }
}

async function onCourseSelected() {
  state.selectedCourse = document.getElementById("courseSelect").value;
  if (!state.selectedCourse) {
    document.getElementById("documentsList").innerHTML = `<p class="text-slate-500 italic">Select a subject to view indexed documents.</p>`;
    return;
  }
  await loadDocuments();
}

async function handleCreateCourse(e) {
  e.preventDefault();
  const code = document.getElementById("newCourseCode").value;
  const title = document.getElementById("newCourseTitle").value;
  const semester = parseInt(document.getElementById("newCourseSem").value, 10);

  try {
    await api("/api/courses", {
      method: "POST",
      body: JSON.stringify({ code, title, semester })
    });
    document.getElementById("newCourseCode").value = "";
    document.getElementById("newCourseTitle").value = "";
    await loadCourses();
    renderAdminCourses();
  } catch (err) {
    alert(err.message);
  }
}

function renderAdminCourses() {
  const container = document.getElementById("adminCoursesList");
  if (!state.courses.length) {
    container.innerHTML = `<p class="text-slate-500 text-xs italic">No courses created yet.</p>`;
    return;
  }
  container.innerHTML = state.courses.map(c => `
    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
      <div>
        <p class="font-bold text-white text-sm">${c.code}</p>
        <p class="text-xs text-slate-400">${c.title} • Semester ${c.semester}</p>
      </div>
      <button onclick="deleteCourse('${c.code}')" class="text-xs text-rose-400 hover:text-rose-300 p-2">
        <i class="fa-solid fa-trash"></i>
      </button>
    </div>
  `).join("");
}

async function deleteCourse(code) {
  if (!confirm(`Delete ${code} and all attached lecture documents?`)) return;
  try {
    await api(`/api/courses/${code}`, { method: "DELETE" });
    await loadCourses();
    renderAdminCourses();
  } catch (err) {
    alert(err.message);
  }
}

// --- Documents & Ingestion ---
async function loadDocuments() {
  const listEl = document.getElementById("documentsList");
  try {
    const docs = await api(`/api/documents/${state.selectedCourse}`);
    if (!docs.length) {
      listEl.innerHTML = `<p class="text-slate-500 italic">No documents indexed for ${state.selectedCourse} yet.</p>`;
      return;
    }
    listEl.innerHTML = docs.map(d => `
      <div class="bg-slate-950 border border-slate-800/80 rounded-xl p-2.5 flex items-center justify-between">
        <div class="truncate mr-2">
          <p class="font-medium text-slate-200 truncate">${d.filename}</p>
          <span class="text-[10px] text-slate-400">${d.doc_type}</span>
        </div>
        <i class="fa-solid fa-file-pdf text-rose-400"></i>
      </div>
    `).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="text-rose-400 text-xs">${err.message}</p>`;
  }
}

async function handlePdfUpload() {
  const fileInput = document.getElementById("pdfFileInput");
  const docType = document.getElementById("docTypeSelect").value;
  const statusEl = document.getElementById("uploadStatus");
  const uploadBtn = document.getElementById("uploadBtn");

  if (!state.selectedCourse) {
    alert("Please select a subject first.");
    return;
  }
  if (!fileInput.files.length) {
    alert("Please choose a PDF file.");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("course_id", state.selectedCourse);
  formData.append("doc_type", docType);

  uploadBtn.disabled = true;
  uploadBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Vectorizing...</span>`;
  statusEl.classList.remove("hidden");
  statusEl.textContent = "Parsing PDF pages & computing embeddings...";

  try {
    const res = await api("/api/documents/upload", {
      method: "POST",
      body: formData
    });
    statusEl.textContent = `Indexed ${res.chunks_indexed} chunks successfully!`;
    fileInput.value = "";
    await loadDocuments();
  } catch (err) {
    statusEl.textContent = `Upload failed: ${err.message}`;
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i><span>Vectorize & Index Material</span>`;
  }
}

// --- Chat ---
// --- Streaming Chat Implementation ---
async function handleSendMessage(e) {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  const messagesBox = document.getElementById("chatMessages");
  const sendBtn = document.getElementById("sendBtn");

  if (!query) return;
  if (!state.selectedCourse) {
    alert("Please select a subject on the left panel before asking a question.");
    return;
  }

  // 1. Render User Bubble
  messagesBox.innerHTML += `
    <div class="flex items-start justify-end space-x-3">
      <div class="bg-indigo-600 text-white rounded-2xl p-4 text-sm max-w-2xl leading-relaxed">
        ${escapeHtml(query)}
      </div>
    </div>
  `;
  input.value = "";
  messagesBox.scrollTop = messagesBox.scrollHeight;

  // 2. Render Empty Assistant Bubble ready for incoming tokens
  const tempId = "msg_" + Date.now();
  messagesBox.innerHTML += `
    <div id="${tempId}" class="flex items-start space-x-3">
      <div class="w-8 h-8 rounded-lg bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0">
        <i class="fa-solid fa-robot text-sm"></i>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-4 text-sm max-w-2xl leading-relaxed text-slate-100 flex-1">
        <div class="chat-content whitespace-pre-wrap"><i class="fa-solid fa-spinner fa-spin mr-2 text-indigo-400"></i>Retrieving course notes...</div>
        <div class="chat-sources mt-3 pt-3 border-t border-slate-700/60 text-[11px] space-y-1 hidden"></div>
      </div>
    </div>
  `;
  messagesBox.scrollTop = messagesBox.scrollHeight;
  sendBtn.disabled = true;

  const botCard = document.getElementById(tempId);
  const contentEl = botCard.querySelector(".chat-content");
  const sourcesEl = botCard.querySelector(".chat-sources");

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({
        course_id: state.selectedCourse,
        query: query
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Streaming request failed");
    }

    // 3. Attach Reader and Decoder
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";
    let buffer = "";
    let isFirstToken = true;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      // Decode the binary stream chunk
      buffer += decoder.decode(value, { stream: true });

      // SSE chunks are separated by double newlines \n\n
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Keep incomplete trailing fragment in buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const rawData = trimmed.replace("data:", "").trim();
        if (rawData === "[DONE]") {
          break;
        }

        try {
          const parsed = JSON.parse(rawData);

          if (parsed.type === "sources") {
            // Render source citations immediately
            if (parsed.data && parsed.data.length > 0) {
              sourcesEl.classList.remove("hidden");
              sourcesEl.innerHTML = `
                <p class="font-semibold text-slate-400 uppercase tracking-wider">Grounding Sources</p>
                ${parsed.data.map(s => `
                  <div class="text-slate-400">
                    <span class="text-indigo-400">[${s.doc_type} | Page ${s.page_number}]</span>
                    <span>${escapeHtml(s.content.substring(0, 110))}...</span>
                    <span class="text-slate-500 font-mono">(${Math.round(s.similarity * 100)}% match)</span>
                  </div>
                `).join("")}
              `;
            }
          } else if (parsed.type === "token") {
            if (isFirstToken) {
              contentEl.innerHTML = ""; // Clear the loading spinner
              isFirstToken = false;
            }
            accumulatedText += parsed.data;
            contentEl.textContent = accumulatedText;
            messagesBox.scrollTop = messagesBox.scrollHeight;
          } else if (parsed.type === "error") {
            contentEl.innerHTML += `<br><span class="text-rose-400 font-medium">Error: ${escapeHtml(parsed.data)}</span>`;
          }
        } catch (jsonErr) {
          console.warn("Could not parse SSE chunk:", rawData);
        }
      }
    }
  } catch (err) {
    contentEl.innerHTML = `<span class="text-rose-400">Failed: ${escapeHtml(err.message)}</span>`;
  } finally {
    sendBtn.disabled = false;
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }
}

// --- Attendance Roster ---
async function loadRoster() {
  const branch = document.getElementById("attBranch").value;
  const courseId = document.getElementById("attCourseSelect").value;
  const date = document.getElementById("attDate").value;
  const tbody = document.getElementById("rosterTbody");

  tbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading roster...</td></tr>`;

  try {
    const data = await api(`/api/attendance/roster?branch=${encodeURIComponent(branch)}&course_id=${encodeURIComponent(courseId)}&session_date=${date}`);
    state.roster = data.roster;

    if (!state.roster.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="py-8 text-center text-slate-500 italic">No students registered under branch '${branch}'.</td></tr>`;
      return;
    }

    renderRosterTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-rose-400">${err.message}</td></tr>`;
  }
}

function renderRosterTable() {
  const tbody = document.getElementById("rosterTbody");
  const statuses = ["present", "absent", "holiday", "GT"];

  tbody.innerHTML = state.roster.map((s, idx) => `
    <tr class="hover:bg-slate-800/30">
      <td class="py-3 px-4 font-mono text-xs text-slate-300">${s.scholar_no}</td>
      <td class="py-3 px-4 font-medium text-white">${s.full_name}</td>
      <td class="py-3 px-4 text-slate-400 text-xs">${s.email}</td>
      <td class="py-3 px-4 text-center">
        <div class="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800 space-x-1">
          ${statuses.map(st => `
            <button onclick="toggleStudentStatus(${idx}, '${st}')" class="px-2 py-1 text-[11px] rounded uppercase font-semibold ${
              s.status === st ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }">
              ${st}
            </button>
          `).join("")}
        </div>
      </td>
    </tr>
  `).join("");
}

function toggleStudentStatus(idx, newStatus) {
  state.roster[idx].status = newStatus;
  renderRosterTable();
}

async function saveAttendance() {
  if (!state.roster.length) {
    alert("No roster loaded.");
    return;
  }
  const course_id = document.getElementById("attCourseSelect").value;
  const branch = document.getElementById("attBranch").value;
  const session_date = document.getElementById("attDate").value;

  const records = state.roster.map(r => ({
    student_id: r.student_id,
    status: r.status
  }));

  try {
    const res = await api("/api/attendance/bulk", {
      method: "POST",
      body: JSON.stringify({ course_id, branch, session_date, records })
    });
    alert(res.message);
  } catch (err) {
    alert(`Failed to save attendance: ${err.message}`);
  }
}

function escapeHtml(str) {
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}