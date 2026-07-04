const state = {
  mode: "login",
  token: localStorage.getItem("planwise_token"),
  user: JSON.parse(localStorage.getItem("planwise_user") || "null"),
  projects: [],
  archivedProjects: [],
  selectedProject: null,
  tasks: [],
  taskFilter: "all",
  showArchivedTasks: false,
  parentTask: null,
};

let refreshPromise = null;
let toastTimer = null;
const $ = (id) => document.getElementById(id);

const PROJECT_STATUS_LABELS = {
  planning: "规划中",
  active: "进行中",
  paused: "已暂停",
  completed: "已完成",
};

const TASK_STATUS_LABELS = {
  todo: "待处理",
  in_progress: "进行中",
  blocked: "受阻",
  done: "已完成",
  cancelled: "已取消",
};

const TASK_TRANSITIONS = {
  todo: ["todo", "in_progress", "done", "cancelled"],
  in_progress: ["in_progress", "blocked", "done", "cancelled"],
  blocked: ["blocked", "in_progress", "done", "cancelled"],
  done: ["done", "todo"],
  cancelled: ["cancelled", "todo"],
};

const PROJECT_TRANSITIONS = {
  planning: ["planning", "active"],
  active: ["active", "paused", "completed"],
  paused: ["paused", "active", "completed"],
  completed: ["completed", "active"],
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").classList.add("show");
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), 2200);
}

function setAuthMode(mode) {
  state.mode = mode;
  const registering = mode === "register";
  $("loginTab").classList.toggle("active", !registering);
  $("registerTab").classList.toggle("active", registering);
  $("authTitle").textContent = registering ? "创建账户" : "欢迎回来";
  $("authSubtitle").textContent = registering ? "从一个清晰的目标开始。" : "继续推进你的计划。";
  $("authSubmit").textContent = registering ? "注册并进入" : "登录";
  $("password").autocomplete = registering ? "new-password" : "current-password";
  $("authError").textContent = "";
}

function persistAuth(payload) {
  const token = payload?.accessToken || payload?.access_token;
  if (!token) throw new Error("认证响应缺少 access token");
  state.token = token;
  state.user = payload.user || state.user;
  localStorage.setItem("planwise_token", token);
  if (state.user) localStorage.setItem("planwise_user", JSON.stringify(state.user));
}

function clearAuth() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("planwise_token");
  localStorage.removeItem("planwise_user");
}

async function refreshToken() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || "登录已过期");
    }
    persistAuth(payload.data);
    return state.token;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function api(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);

  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error("无法连接后端服务");
  }

  if (response.status === 401 && retry) {
    try {
      await refreshToken();
      return api(path, options, false);
    } catch {
      clearAuth();
      showAuth();
      throw new Error("登录已过期，请重新登录");
    }
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    const details = Array.isArray(payload.data)
      ? payload.data.map((item) => item.message).join("；")
      : "";
    throw new Error(details || payload.message || "请求失败");
  }
  return payload.data;
}

function showAuth() {
  $("authView").classList.remove("hidden");
  $("appView").classList.add("hidden");
}

function showApp() {
  $("authView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("navUsername").textContent = state.user?.username || "—";
}

async function loadProjects() {
  const [active, archived] = await Promise.all([
    api("/api/projects"),
    api("/api/projects?archived=true"),
  ]);
  state.projects = active || [];
  state.archivedProjects = archived || [];
  $("archiveCount").textContent = state.archivedProjects.length;

  if (!state.selectedProject || state.selectedProject.archived_time) {
    state.selectedProject =
      state.projects.find((project) => project.system_type === "inbox")
      || state.projects[0]
      || null;
  } else {
    state.selectedProject =
      state.projects.find((project) => project.project_id === state.selectedProject.project_id)
      || state.archivedProjects.find((project) => project.project_id === state.selectedProject.project_id)
      || state.projects[0]
      || null;
  }
  renderProjects();
  renderProjectHeader();
}

function projectButton(project) {
  const inbox = project.system_type === "inbox";
  const active = state.selectedProject?.project_id === project.project_id;
  return `
    <button class="project-item ${active ? "active" : ""}" data-project-id="${project.project_id}" type="button">
      <span class="project-symbol">${inbox ? "⌂" : escapeHtml(project.title.slice(0, 1).toUpperCase())}</span>
      <span class="project-name">${inbox ? "收件箱" : escapeHtml(project.title)}</span>
      <span class="project-count">${PROJECT_STATUS_LABELS[project.status] || ""}</span>
    </button>
  `;
}

function renderProjects(showArchived = false) {
  const projects = showArchived ? state.archivedProjects : state.projects;
  $("projectList").innerHTML = projects.map(projectButton).join("");
  $("archiveNavButton").classList.toggle("active", showArchived);
}

function renderProjectHeader() {
  const project = state.selectedProject;
  if (!project) {
    $("currentProjectTitle").textContent = "还没有项目";
    $("currentProjectGoal").textContent = "先创建一个项目，或重新登录生成 Inbox。";
    $("projectActions").classList.add("hidden");
    return;
  }
  const inbox = project.system_type === "inbox";
  const archived = Boolean(project.archived_time);
  $("projectActions").classList.remove("hidden");
  $("projectEyebrow").textContent = inbox ? "INBOX" : archived ? "ARCHIVED PROJECT" : "PROJECT";
  $("currentProjectTitle").textContent = inbox ? "收件箱" : project.title;
  $("currentProjectGoal").textContent = inbox
    ? "没有明确归属的事项会集中在这里。"
    : project.goal || project.description || "为这个项目补充一个清晰目标。";

  const statusSelect = $("projectStatusSelect");
  statusSelect.innerHTML = (PROJECT_TRANSITIONS[project.status] || [project.status])
    .map((value) => `<option value="${value}" ${value === project.status ? "selected" : ""}>${PROJECT_STATUS_LABELS[value]}</option>`)
    .join("");
  statusSelect.disabled = inbox || archived;
  $("archiveProjectButton").classList.toggle("hidden", inbox || archived);
  $("restoreProjectButton").classList.toggle("hidden", inbox || !archived);
}

async function selectProject(id) {
  const all = [...state.projects, ...state.archivedProjects];
  state.selectedProject = all.find((project) => project.project_id === Number(id)) || null;
  state.showArchivedTasks = false;
  $("toggleArchivedTasksButton").textContent = "查看归档任务";
  renderProjects(Boolean(state.selectedProject?.archived_time));
  renderProjectHeader();
  await loadTasks();
}

async function loadTasks() {
  if (!state.selectedProject) {
    state.tasks = [];
    renderTasks();
    return;
  }
  const query = new URLSearchParams({
    project_id: state.selectedProject.project_id,
    archived: state.showArchivedTasks,
  });
  state.tasks = await api(`/api/tasks?${query}`) || [];
  renderTasks();
}

function filteredTasks() {
  if (state.taskFilter === "done") {
    return state.tasks.filter((task) => task.status === "done");
  }
  if (state.taskFilter === "open") {
    return state.tasks.filter((task) => !["done", "cancelled"].includes(task.status));
  }
  return state.tasks;
}

function taskStatusOptions(task) {
  return (TASK_TRANSITIONS[task.status] || [task.status])
    .map((value) => `<option value="${value}" ${value === task.status ? "selected" : ""}>${TASK_STATUS_LABELS[value]}</option>`)
    .join("");
}

function renderTaskTree(tasks) {
  const visibleIds = new Set(tasks.map((task) => task.task_id));
  const children = new Map();
  tasks.forEach((task) => {
    const parent = visibleIds.has(task.parent_task_id) ? task.parent_task_id : null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(task);
  });
  children.forEach((items) => items.sort((a, b) => a.sort_order - b.sort_order || a.task_id - b.task_id));

  const visited = new Set();
  function walk(parentId, depth) {
    return (children.get(parentId) || []).map((task) => {
      if (visited.has(task.task_id)) return "";
      visited.add(task.task_id);
      const done = task.status === "done";
      const description = task.acceptance_criteria || task.description || "";
      return `
        <article class="task-row ${done ? "done" : ""}" style="--depth:${Math.min(depth, 6)}">
          <button class="task-check ${done ? "done" : ""}" data-complete-task="${task.task_id}" type="button" aria-label="${done ? "重新打开" : "完成任务"}" ${state.showArchivedTasks ? "disabled" : ""}>✓</button>
          <div class="task-copy">
            <div class="task-title">${escapeHtml(task.title)}</div>
            ${description ? `<p class="task-description">${escapeHtml(description)}</p>` : ""}
            <div class="task-tags">
              <span class="pill priority-${task.priority}">${escapeHtml(task.priority)}</span>
              <span class="pill">${TASK_STATUS_LABELS[task.status]}</span>
            </div>
          </div>
          <select data-task-status="${task.task_id}" aria-label="任务状态" ${state.showArchivedTasks ? "disabled" : ""}>${taskStatusOptions(task)}</select>
          <div class="task-row-actions">
            ${state.showArchivedTasks ? `<button data-restore-task="${task.task_id}" type="button">恢复</button>` : `
              ${["done", "cancelled"].includes(task.status) ? "" : `<button data-child-task="${task.task_id}" type="button">子任务</button>`}
              <button data-archive-task="${task.task_id}" type="button">归档</button>
            `}
          </div>
        </article>
        ${walk(task.task_id, depth + 1)}
      `;
    }).join("");
  }
  return walk(null, 0);
}

function renderTasks() {
  const tasks = filteredTasks();
  $("taskList").innerHTML = renderTaskTree(tasks);
  $("emptyState").classList.toggle("hidden", tasks.length > 0);

  const total = state.tasks.length;
  const done = state.tasks.filter((task) => ["done", "cancelled"].includes(task.status)).length;
  const active = state.tasks.filter((task) => ["in_progress", "blocked"].includes(task.status)).length;
  const progress = total ? Math.round((done / total) * 100) : 0;
  $("totalMetric").textContent = total;
  $("activeMetric").textContent = active;
  $("doneMetric").textContent = done;
  $("progressMetric").textContent = `${progress}%`;
  $("progressBar").style.width = `${progress}%`;
}

function resetTaskForm() {
  $("taskForm").reset();
  $("taskPriority").value = "medium";
  $("taskError").textContent = "";
  state.parentTask = null;
  $("parentContext").classList.add("hidden");
}

function openTaskForm(parentTask = null) {
  if (!state.selectedProject || state.selectedProject.archived_time) return;
  resetTaskForm();
  state.parentTask = parentTask;
  if (parentTask) {
    $("parentTaskTitle").textContent = parentTask.title;
    $("parentContext").classList.remove("hidden");
  }
  $("taskForm").classList.remove("hidden");
  $("taskTitle").focus();
}

async function changeTaskStatus(taskId, status) {
  await api(`/api/tasks/${taskId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  await loadTasks();
}

async function boot() {
  if (!state.token) {
    showAuth();
    return;
  }
  try {
    state.user = await api("/api/user/me");
    localStorage.setItem("planwise_user", JSON.stringify(state.user));
    showApp();
    await loadProjects();
    await loadTasks();
  } catch (error) {
    if (!state.token) return;
    showToast(error.message);
  }
}

$("loginTab").addEventListener("click", () => setAuthMode("login"));
$("registerTab").addEventListener("click", () => setAuthMode("register"));

$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("authError").textContent = "";
  $("authSubmit").disabled = true;
  try {
    const data = await api(`/api/auth/${state.mode}`, {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value.trim(),
        password: $("password").value,
      }),
    }, false);
    persistAuth(data);
    await boot();
  } catch (error) {
    $("authError").textContent = error.message;
  } finally {
    $("authSubmit").disabled = false;
  }
});

$("logoutButton").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" }, false);
  } catch {}
  clearAuth();
  showAuth();
});

$("showProjectFormButton").addEventListener("click", () => $("projectForm").classList.remove("hidden"));
$("cancelProjectButton").addEventListener("click", () => $("projectForm").classList.add("hidden"));
$("projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const project = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        title: $("projectTitle").value.trim(),
        goal: $("projectGoal").value.trim() || null,
      }),
    });
    $("projectForm").reset();
    $("projectForm").classList.add("hidden");
    state.selectedProject = project;
    await loadProjects();
    await loadTasks();
    showToast("项目已创建");
  } catch (error) {
    showToast(error.message);
  }
});

$("projectList").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-project-id]");
  if (!button) return;
  try {
    await selectProject(button.dataset.projectId);
  } catch (error) {
    showToast(error.message);
  }
});

$("archiveNavButton").addEventListener("click", () => {
  const showingArchived = !state.selectedProject?.archived_time;
  if (showingArchived && state.archivedProjects.length) {
    state.selectedProject = state.archivedProjects[0];
    renderProjects(true);
    renderProjectHeader();
    loadTasks().catch((error) => showToast(error.message));
  } else {
    state.selectedProject =
      state.projects.find((project) => project.system_type === "inbox")
      || state.projects[0]
      || null;
    renderProjects(false);
    renderProjectHeader();
    loadTasks().catch((error) => showToast(error.message));
  }
});

$("projectStatusSelect").addEventListener("change", async (event) => {
  const project = state.selectedProject;
  if (!project || event.target.value === project.status) return;
  try {
    await api(`/api/projects/${project.project_id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: event.target.value }),
    });
    await loadProjects();
    await loadTasks();
    showToast("项目状态已更新");
  } catch (error) {
    renderProjectHeader();
    showToast(error.message);
  }
});

$("archiveProjectButton").addEventListener("click", async () => {
  if (!state.selectedProject) return;
  try {
    await api(`/api/projects/${state.selectedProject.project_id}`, { method: "DELETE" });
    state.selectedProject = null;
    await loadProjects();
    await loadTasks();
    showToast("项目已归档");
  } catch (error) {
    showToast(error.message);
  }
});

$("restoreProjectButton").addEventListener("click", async () => {
  if (!state.selectedProject) return;
  try {
    const project = await api(`/api/projects/${state.selectedProject.project_id}/restore`, { method: "POST" });
    state.selectedProject = project;
    await loadProjects();
    await loadTasks();
    showToast("项目已恢复");
  } catch (error) {
    showToast(error.message);
  }
});

$("showTaskFormButton").addEventListener("click", () => openTaskForm());
$("cancelTaskButton").addEventListener("click", () => {
  resetTaskForm();
  $("taskForm").classList.add("hidden");
});
$("clearParentButton").addEventListener("click", () => openTaskForm());

$("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProject) return;
  $("taskError").textContent = "";
  try {
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        project_id: state.selectedProject.project_id,
        parent_task_id: state.parentTask?.task_id || null,
        title: $("taskTitle").value.trim(),
        description: $("taskDescription").value.trim() || null,
        acceptance_criteria: $("taskCriteria").value.trim() || null,
        priority: $("taskPriority").value,
      }),
    });
    resetTaskForm();
    $("taskForm").classList.add("hidden");
    await loadTasks();
    showToast("任务已创建");
  } catch (error) {
    $("taskError").textContent = error.message;
  }
});

$("statusFilters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.taskFilter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
  renderTasks();
});

$("toggleArchivedTasksButton").addEventListener("click", async () => {
  state.showArchivedTasks = !state.showArchivedTasks;
  $("toggleArchivedTasksButton").textContent = state.showArchivedTasks ? "查看当前任务" : "查看归档任务";
  try {
    await loadTasks();
  } catch (error) {
    showToast(error.message);
  }
});

$("taskList").addEventListener("change", async (event) => {
  const select = event.target.closest("[data-task-status]");
  if (!select) return;
  try {
    await changeTaskStatus(select.dataset.taskStatus, select.value);
  } catch (error) {
    showToast(error.message);
    await loadTasks();
  }
});

$("taskList").addEventListener("click", async (event) => {
  const completeButton = event.target.closest("[data-complete-task]");
  const childButton = event.target.closest("[data-child-task]");
  const archiveButton = event.target.closest("[data-archive-task]");
  const restoreButton = event.target.closest("[data-restore-task]");
  try {
    if (completeButton) {
      const task = state.tasks.find((item) => item.task_id === Number(completeButton.dataset.completeTask));
      const targetStatus = ["done", "cancelled"].includes(task.status) ? "todo" : "done";
      await changeTaskStatus(task.task_id, targetStatus);
    } else if (childButton) {
      const task = state.tasks.find((item) => item.task_id === Number(childButton.dataset.childTask));
      openTaskForm(task);
    } else if (archiveButton) {
      await api(`/api/tasks/${archiveButton.dataset.archiveTask}`, { method: "DELETE" });
      await loadTasks();
      showToast("任务已归档");
    } else if (restoreButton) {
      await api(`/api/tasks/${restoreButton.dataset.restoreTask}/restore`, { method: "POST" });
      await loadTasks();
      showToast("任务已恢复");
    }
  } catch (error) {
    showToast(error.message);
  }
});

boot();
