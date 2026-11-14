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
  ["chat", "attendance", "courses", "paper"].forEach(t => {
    const view = document.getElementById(`view${t.charAt(0).toUpperCase() + t.slice(1)}`);
    const btn = document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`);
    if (!view || !btn) return;
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

// --- PDF Modal Viewer Functions ---
function openPdfModal(url, filename, pageNumber) {
  if (!url) {
    alert("PDF link unavailable for this document.");
    return;
  }
  const modal = document.getElementById("pdfViewerModal");
  const title = document.getElementById("pdfViewerTitle");
  const subtitle = document.getElementById("pdfViewerSubtitle");
  const externalLink = document.getElementById("pdfViewerExternalLink");
  const frame = document.getElementById("pdfFrame");

  title.textContent = filename || "Course Material";
  subtitle.textContent = pageNumber ? `Viewing Page ${pageNumber}` : "Document Preview";
  externalLink.href = url;
  frame.src = url;

  modal.classList.remove("hidden");
}

function closePdfModal() {
  const modal = document.getElementById("pdfViewerModal");
  const frame = document.getElementById("pdfFrame");
  frame.src = "about:blank"; // Stop memory consumption
  modal.classList.add("hidden");
}

// Close modal on Escape key press
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closePdfModal();
  }
});

// --- Chat ---
// --- Streaming Chat Implementation ---
// --- Streaming Chat Implementation with Markdown & KaTeX Math Rendering ---
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
        <div class="chat-content prose prose-invert max-w-none text-sm leading-relaxed"><i class="fa-solid fa-spinner fa-spin mr-2 text-indigo-400"></i>Retrieving course notes...</div>
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

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";
    let buffer = "";
    let isFirstToken = true;

    // Helper: Safely renders Markdown and math formulas into the container
    const finalizeFormatting = () => {
      if (window.marked) {
        contentEl.innerHTML = marked.parse(accumulatedText);
      } else {
        contentEl.textContent = accumulatedText;
      }
      if (window.renderMathInElement) {
        renderMathInElement(contentEl, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
            { left: "\\[", right: "\\]", display: true },
            { left: "\\(", right: "\\)", display: false }
          ],
          throwOnError: false
        });
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Retain incomplete fragment

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const rawData = trimmed.replace("data:", "").trim();
        if (rawData === "[DONE]") {
          finalizeFormatting();
          break;
        }

        try {
          const parsed = JSON.parse(rawData);

          if (parsed.type === "sources") {
            if (parsed.data && parsed.data.length > 0) {
              sourcesEl.classList.remove("hidden");
              sourcesEl.innerHTML = `
                <div class="flex items-center space-x-2 mb-2">
                  <i class="fa-solid fa-bookmark text-indigo-400 text-xs"></i>
                  <p class="font-semibold text-slate-300 uppercase tracking-wider text-[10px]">Verified Grounding Sources</p>
                </div>
                <div class="grid grid-cols-1 gap-2">
                  ${parsed.data.map(s => {
                    const cleanFileName = escapeHtml(s.filename || "Document.pdf");
                    const safeUrl = s.pdf_url ? encodeURI(s.pdf_url) : "";
                    const page = s.page_number || 1;
                    return `
                      <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-2.5 flex items-start justify-between gap-3 hover:border-slate-700 transition">
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center space-x-2 text-[11px] mb-1">
                            <span class="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/60 font-medium">
                              ${escapeHtml(s.doc_type)}
                            </span>
                            <span class="text-slate-400 truncate max-w-[180px]">${cleanFileName}</span>
                            <span class="text-slate-500 font-mono text-[10px]">• ${Math.round(s.similarity * 100)}% match</span>
                          </div>
                          <p class="text-slate-400 text-xs line-clamp-2 italic leading-relaxed">
                            "${escapeHtml(s.content.substring(0, 140))}..."
                          </p>
                        </div>
                        ${s.pdf_url ? `
                          <button 
                            type="button" 
                            onclick="openPdfModal('${safeUrl}', '${cleanFileName}', ${page})" 
                            class="shrink-0 mt-0.5 px-2.5 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition"
                            title="Open exact cited page"
                          >
                            <i class="fa-solid fa-book-open text-[10px]"></i>
                            <span>Page ${page}</span>
                          </button>
                        ` : ''}
                      </div>
                    `;
                  }).join("")}
                </div>
              `;
            }
          } else if (parsed.type === "token") {
            if (isFirstToken) {
              contentEl.innerHTML = "";
              isFirstToken = false;
            }
            accumulatedText += parsed.data;
            // Plain text during live streaming for raw speed
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

    // Ensure Markdown & KaTeX render even if [DONE] was dropped by the network
    finalizeFormatting();

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

// --- Sample Paper Generation ---
async function handleGeneratePaper() {
  const outputEl = document.getElementById("paperOutput");
  const genBtn = document.getElementById("genPaperBtn");
  const courseCode = document.getElementById("paperCourseSelect").value;

  if (!courseCode) {
    alert("Please choose a semester and select a course first.");
    return;
  }

  const examType = document.getElementById("paperExamType").value;
  const totalMarks = parseInt(document.getElementById("paperMarks").value, 10);
  const difficulty = document.getElementById("paperDifficulty").value;
  const includeSolutions = document.getElementById("paperSolutions").checked;

  genBtn.disabled = true;
  genBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-2"></i>Synthesizing Paper...`;
  outputEl.innerHTML = `<p class="text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2 text-indigo-400"></i>Reviewing syllabus boundaries, PYQ patterns, and lecture modules for ${courseCode}...</p>`;

  try {
    const response = await fetch("/api/chat/generate-paper", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${state.token}`
      },
      body: JSON.stringify({
        course_id: courseCode,
        exam_type: examType,
        total_marks: totalMarks,
        difficulty: difficulty,
        include_solutions: includeSolutions
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Paper generation failed");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";
    let buffer = "";

    const finalizePaperFormatting = () => {
      if (window.marked) {
        outputEl.innerHTML = marked.parse(accumulatedText);
      } else {
        outputEl.textContent = accumulatedText;
      }
      if (window.renderMathInElement) {
        renderMathInElement(outputEl, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
            { left: "\\[", right: "\\]", display: true },
            { left: "\\(", right: "\\)", display: false }
          ],
          throwOnError: false
        });
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const rawData = trimmed.replace("data:", "").trim();
        if (rawData === "[DONE]") {
          finalizePaperFormatting();
          break;
        }

        try {
          const parsed = JSON.parse(rawData);
          if (parsed.type === "token") {
            accumulatedText += parsed.data;
            outputEl.textContent = accumulatedText;
          } else if (parsed.type === "error") {
            outputEl.innerHTML += `<br><span class="text-rose-400">Error: ${escapeHtml(parsed.data)}</span>`;
          }
        } catch (e) {
          // Incomplete chunk
        }
      }
    }

    finalizePaperFormatting();

  } catch (err) {
    outputEl.innerHTML = `<span class="text-rose-400">Generation failed: ${escapeHtml(err.message)}</span>`;
  } finally {
    genBtn.disabled = false;
    genBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles mr-2"></i>Synthesize Exam Paper`;
  }
}
function printGeneratedPaper() {
  const content = document.getElementById("paperOutput").innerHTML;
  const printWindow = window.open("", "_blank");
  printWindow.document.write(`
    <html>
      <head>
        <title>Academic Examination Paper - ${state.selectedCourse || ''}</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
        <style>
          body { font-family: 'Times New Roman', serif; padding: 40px; color: #111; line-height: 1.5; }
          h1, h2, h3 { text-align: center; margin-bottom: 5px; }
          hr { margin: 20px 0; border: 0; border-top: 1px solid #333; }
        </style>
      </head>
      <body>
        ${content}
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => printWindow.print(), 500);
}

// --- Cascading Semester -> Course Filter for Paper Generator ---
function onPaperSemChanged() {
  const semVal = document.getElementById("paperSemSelect").value;
  const courseSelect = document.getElementById("paperCourseSelect");

  if (!semVal) {
    courseSelect.innerHTML = `<option value="">-- Select Semester First --</option>`;
    courseSelect.disabled = true;
    return;
  }

  const selectedSem = parseInt(semVal, 10);
  const filteredCourses = state.courses.filter(c => Number(c.semester) === selectedSem);

  if (filteredCourses.length === 0) {
    courseSelect.innerHTML = `<option value="">-- No Courses in Semester ${selectedSem} --</option>`;
    courseSelect.disabled = true;
    return;
  }

  courseSelect.innerHTML = `<option value="">-- Choose Subject --</option>` +
    filteredCourses.map(c => `<option value="${c.code}">${c.code} - ${c.title}</option>`).join("");
  courseSelect.disabled = false;
}
let selectedFilesCache = [];
let availableCoursesCache = [];

const DOC_TYPES = [
  "Lecture Notes",
  "Syllabus",
  "Previous Year Questions",
  "Lab Manual",
  "Reference Book"
];

async function handleFilesSelected() {
  const fileInput = document.getElementById("pdfFileInput");
  const spinner = document.getElementById("predictionSpinner");
  const reviewList = document.getElementById("predictionReviewList");
  const confirmBtn = document.getElementById("confirmUploadBtn");
  const statusEl = document.getElementById("uploadStatus");

  if (!fileInput.files || fileInput.files.length === 0) return;

  selectedFilesCache = Array.from(fileInput.files);
  reviewList.innerHTML = "";
  reviewList.classList.add("hidden");
  confirmBtn.classList.add("hidden");
  statusEl.classList.add("hidden");
  spinner.classList.remove("hidden");

  const formData = new FormData();
  selectedFilesCache.forEach((file) => formData.append("files", file));

  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const res = await fetch("/api/documents/predict", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Prediction failed");
    }

    const data = await res.json();
    availableCoursesCache = data.available_courses || [];
    renderPredictionReview(data.predictions);
  } catch (err) {
    statusEl.classList.remove("hidden", "text-emerald-400");
    statusEl.classList.add("text-red-400");
    statusEl.textContent = `Analysis error: ${err.message}`;
  } finally {
    spinner.classList.add("hidden");
  }
}

function renderPredictionReview(predictions) {
  const reviewList = document.getElementById("predictionReviewList");
  const confirmBtn = document.getElementById("confirmUploadBtn");
  reviewList.innerHTML = "";

  predictions.forEach((item, index) => {
    if (!item.valid) {
      const errDiv = document.createElement("div");
      errDiv.className = "p-2 bg-red-950/40 border border-red-800 rounded-lg text-[11px] text-red-300";
      errDiv.textContent = `${item.filename}: ${item.error}`;
      reviewList.appendChild(errDiv);
      return;
    }

    const card = document.createElement("div");
    card.className = "bg-slate-900 border border-slate-700/80 rounded-lg p-2.5 flex flex-col space-y-2 text-xs";
    card.dataset.filename = item.filename;

    const courseOptions = availableCoursesCache.map(c => 
      `<option value="${c.code}" ${c.code === item.predicted_course_id ? 'selected' : ''}>${c.code} - ${c.title || ''}</option>`
    ).join("");

    const typeOptions = DOC_TYPES.map(t => 
      `<option value="${t}" ${t === item.predicted_doc_type ? 'selected' : ''}>${t}</option>`
    ).join("");

    card.innerHTML = `
      <div class="flex items-center justify-between text-slate-300">
        <span class="truncate font-medium max-w-[200px]" title="${item.filename}">${item.filename}</span>
        <span class="text-[10px] text-slate-500 font-mono">${item.page_count} pages</span>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-[10px] uppercase font-semibold text-slate-500">Subject</label>
          <select class="course-select w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-300 text-[11px] mt-0.5">
            ${courseOptions}
          </select>
        </div>
        <div>
          <label class="text-[10px] uppercase font-semibold text-slate-500">Category</label>
          <select class="type-select w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-300 text-[11px] mt-0.5">
            ${typeOptions}
          </select>
        </div>
      </div>
    `;
    reviewList.appendChild(card);
  });

  reviewList.classList.remove("hidden");
  confirmBtn.classList.remove("hidden");
}

async function confirmAndUploadBatch() {
  const confirmBtn = document.getElementById("confirmUploadBtn");
  const confirmText = document.getElementById("confirmUploadBtnText");
  const statusEl = document.getElementById("uploadStatus");
  const reviewCards = document.querySelectorAll("#predictionReviewList > div[data-filename]");

  if (reviewCards.length === 0) return;

  const metadata = [];
  reviewCards.forEach((card) => {
    const filename = card.dataset.filename;
    const course_id = card.querySelector(".course-select").value;
    const doc_type = card.querySelector(".type-select").value;
    metadata.push({ filename, course_id, doc_type });
  });

  const formData = new FormData();
  selectedFilesCache.forEach((file) => formData.append("files", file));
  formData.append("metadata", JSON.stringify(metadata));

  confirmBtn.disabled = true;
  confirmBtn.classList.add("opacity-50", "cursor-not-allowed");
  confirmText.textContent = "Vectorizing & Ingesting...";
  statusEl.classList.remove("hidden", "text-red-400", "text-emerald-400");
  statusEl.classList.add("text-slate-400");
  statusEl.textContent = "Generating ONNX embeddings and committing to pgvector...";

  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const res = await fetch("/api/documents/upload-batch", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData
    });

    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || "Upload batch failed");

    statusEl.classList.remove("text-slate-400");
    statusEl.classList.add("text-emerald-400");
    statusEl.textContent = result.message;

    // Reset view
    document.getElementById("pdfFileInput").value = "";
    document.getElementById("predictionReviewList").classList.add("hidden");
    confirmBtn.classList.add("hidden");

    // Refresh active course document list if helper exists
    if (typeof loadCourseDocuments === "function" && window.currentCourseCode) {
      loadCourseDocuments(window.currentCourseCode);
    }
  } catch (err) {
    statusEl.classList.remove("text-slate-400");
    statusEl.classList.add("text-red-400");
    statusEl.textContent = `Ingestion error: ${err.message}`;
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.classList.remove("opacity-50", "cursor-not-allowed");
    confirmText.textContent = "Confirm & Ingest Batch";
  }
}


// 1. Coming Soon Handler for Attendance Roster
function showAttendanceComingSoon() {
  const toast = document.getElementById("comingSoonToast");
  if (!toast) {
    alert("Attendance Roster: Coming Soon!");
    return;
  }
  toast.classList.remove("hidden");
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => {
    toast.classList.add("hidden");
  }, 3500);
}

// 2. Tab Switcher (Academic Assistant vs Exam Paper Generator)
function switchTab(tabName) {
  // 1. Update Navigation Button Active States
  const tabMap = {
    chat: document.getElementById("tabChat"),
    paper: document.getElementById("tabPaper"),
    courses: document.getElementById("tabCourses"),
  };

  Object.entries(tabMap).forEach(([key, btn]) => {
    if (!btn) return;
    if (key === tabName) {
      btn.className = "py-3 border-b-2 border-indigo-500 text-indigo-400 flex items-center space-x-2";
    } else {
      btn.className = "py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 flex items-center space-x-2";
    }
  });

  // 2. Toggle Main Content Sections
  const viewMap = {
    chat: document.getElementById("viewChat") || document.getElementById("chatSection"),
    paper: document.getElementById("viewPaper") || document.getElementById("paperSection"),
    courses: document.getElementById("viewCourses") || document.getElementById("coursesSection"),
  };

  Object.entries(viewMap).forEach(([key, section]) => {
    if (!section) {
      console.warn(`Missing container element for tab: ${key}`);
      return;
    }
    section.classList.toggle("hidden", key !== tabName);
  });
}

// Ensure global access for inline onclick="..." handlers
window.switchTab = switchTab;

// 3. Render Subject Knowledge Base with View & Download Buttons
function renderCourseDocuments(documents) {
  const listEl = document.getElementById("documentsList");
  const isStaff =
    window.currentUser &&
    (window.currentUser.role === "admin" || window.currentUser.role === "faculty");

  if (!documents || documents.length === 0) {
    listEl.innerHTML = `<p class="text-slate-500 italic">No study material indexed for this subject yet.</p>`;
    return;
  }

  listEl.innerHTML = documents
    .map(
      (doc) => `
    <div class="bg-slate-900/90 border border-slate-800 hover:border-slate-700 rounded-lg p-2.5 flex items-center justify-between gap-2 transition">
      <div class="min-w-0 flex-1">
        <p class="text-slate-200 font-medium truncate text-xs" title="${doc.filename}">
          <i class="fa-regular fa-file-pdf text-rose-400 mr-1.5"></i>${doc.filename}
        </p>
        <span class="inline-block mt-1 text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/50">
          ${doc.doc_type}
        </span>
      </div>
      <div class="flex items-center space-x-1.5 shrink-0">
        <button 
          onclick="openOrDownloadDoc('${doc.id}', false)" 
          title="View PDF"
          class="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md transition"
        >
          <i class="fa-solid fa-eye text-[11px]"></i>
        </button>
        <button 
          onclick="openOrDownloadDoc('${doc.id}', true)" 
          title="Download PDF"
          class="p-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-md transition"
        >
          <i class="fa-solid fa-download text-[11px]"></i>
        </button>
        ${
          isStaff
            ? `<button 
                onclick="deleteDocument('${doc.id}')" 
                title="Delete Document"
                class="admin-only-action p-1.5 bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white rounded-md transition"
              >
                <i class="fa-solid fa-trash text-[11px]"></i>
              </button>`
            : ""
        }
      </div>
    </div>
  `
    )
    .join("");
}

// 4. Fetch Signed URL & Open/Download File
async function openOrDownloadDoc(docId, forceDownload = false) {
  try {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const res = await fetch(`/api/documents/download/${docId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to fetch file");

    if (forceDownload) {
      const a = document.createElement("a");
      a.href = data.url;
      a.download = data.filename || "material.pdf";
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } else {
      window.open(data.url, "_blank", "noopener,noreferrer");
    }
  } catch (err) {
    alert(`File error: ${err.message}`);
  }
}

// 5. Role-based UI Visibility on Login
window.currentUser = null;

function applyRolePermissions(user) {
  window.currentUser = user;
  const isStaff = user && (user.role === "admin" || user.role === "faculty");

  // 1. Manage Subjects Tab (Admin/Faculty ONLY)
  const tabCourses = document.getElementById("tabCourses");
  if (tabCourses) {
    tabCourses.classList.toggle("hidden", !isStaff);
  }

  // 2. Document Upload Panel (Admin/Faculty ONLY)
  const uploadContainer = document.getElementById("uploadContainer");
  if (uploadContainer) {
    uploadContainer.classList.toggle("hidden", !isStaff);
  }

  // 3. Delete buttons on existing documents (Admin/Faculty ONLY)
  document.querySelectorAll(".admin-only-action").forEach((el) => {
    el.classList.toggle("hidden", !isStaff);
  });
}

function switchTab(tabName) {
  const isStaff =
    window.currentUser &&
    (window.currentUser.role === "admin" || window.currentUser.role === "faculty");

  // Block students from ever opening 'courses'
  if (tabName === "courses" && !isStaff) {
    console.warn("Access denied: Students cannot access Manage Subjects.");
    return;
  }

  // 1. Update Navigation Button Active Styles (preserving 'hidden' for non-staff)
  const tabMap = {
    chat: document.getElementById("tabChat"),
    paper: document.getElementById("tabPaper"),
    courses: document.getElementById("tabCourses"),
  };

  Object.entries(tabMap).forEach(([key, btn]) => {
    if (!btn) return;

    const isActive = key === tabName;
    btn.classList.toggle("border-indigo-500", isActive);
    btn.classList.toggle("text-indigo-400", isActive);
    btn.classList.toggle("border-transparent", !isActive);
    btn.classList.toggle("text-slate-400", !isActive);
    btn.classList.toggle("hover:text-slate-200", !isActive);

    // Keep Manage Subjects hidden if user is a student
    if (key === "courses") {
      btn.classList.toggle("hidden", !isStaff);
    }
  });

  // 2. Toggle Content Sections
  const viewMap = {
    chat: document.getElementById("viewChat") || document.getElementById("chatSection"),
    paper: document.getElementById("viewPaper") || document.getElementById("paperSection"),
    courses: document.getElementById("viewCourses") || document.getElementById("coursesSection"),
  };

  Object.entries(viewMap).forEach(([key, section]) => {
    if (!section) return;
    if (key === "courses" && !isStaff) {
      section.classList.add("hidden");
      return;
    }
    section.classList.toggle("hidden", key !== tabName);
  });
}

window.switchTab = switchTab;
window.applyRolePermissions = applyRolePermissions;