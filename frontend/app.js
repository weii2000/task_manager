const AGENT_SESSION_STORAGE_KEY = "planwise_agent_session_id";
const AGENT_RECOVERY_ATTEMPTS = 30;
const AGENT_RECOVERY_INTERVAL_MS = 2000;
const storedAgentSessionId = Number(
  localStorage.getItem(AGENT_SESSION_STORAGE_KEY),
);

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
  collapsedTaskIds: new Set(),
  parentTask: null,
  editingTask: null,
  agentSessionId: Number.isInteger(storedAgentSessionId)
    && storedAgentSessionId > 0
    ? storedAgentSessionId
    : null,
  planningState: null,
  agentPendingMessage: null,
  agentSending: false,
  activeMemories: [],
  pendingMemories: [],
  memoryStatus: "active",
  editingMemoryId: null,
  memoryLoading: false,
  memoryMutatingId: null,
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
  pending: "待处理",
  in_progress: "进行中",
  blocked: "受阻",
  completed: "已完成",
  cancelled: "已取消",
};

const TASK_PRIORITY_LABELS = {
  low: "低",
  medium: "中",
  high: "高",
  urgent: "紧急",
};

const REVIEW_CATEGORY_LABELS = {
  conflict: "冲突",
  completeness: "完整性",
  feasibility: "可行性",
  schedule: "时间安排",
  duplication: "重复项",
};

const REVIEW_SEVERITY_LABELS = {
  info: "信息",
  warning: "提醒",
  blocking: "需修改",
};

const MEMORY_CATEGORY_LABELS = {
  profile: "个人信息",
  preference: "偏好",
  constraint: "约束",
  long_term_goal: "长期目标",
};

const MEMORY_SOURCE_LABELS = {
  manual: "手动添加",
  conversation: "对话提取",
};

const TASK_TRANSITIONS = {
  pending: ["pending", "in_progress", "completed", "cancelled"],
  in_progress: ["in_progress", "blocked", "completed", "cancelled"],
  blocked: ["blocked", "in_progress", "completed", "cancelled"],
  completed: ["completed", "pending"],
  cancelled: ["cancelled", "pending"],
};

const PROJECT_TRANSITIONS = {
  planning: ["planning", "active"],
  active: ["active", "paused", "completed"],
  paused: ["paused", "active", "completed"],
  completed: ["completed", "active"],
};

const ICONS = {
  edit: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20h9"/>
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-5 1 1-5Z"/>
    </svg>
  `,
  child: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 4v7a4 4 0 0 0 4 4h8"/>
      <path d="M15 12l3 3-3 3"/>
      <path d="M18 6v4M16 8h4"/>
    </svg>
  `,
  archive: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16l-1 13H5Z"/>
      <path d="M3 4h18v3H3Z"/>
      <path d="M9 11h6"/>
    </svg>
  `,
  restore: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16l-1 13H5Z"/>
      <path d="M3 4h18v3H3Z"/>
      <path d="M8 14a4 4 0 0 1 7-2"/>
      <path d="M15 9v3h-3"/>
    </svg>
  `,
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function padDatePart(value) {
  return String(value).padStart(2, "0");
}

function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dateToDatetimeLocalValue(value) {
  const date = parseDate(value);
  if (!date) return "";
  return [
    date.getFullYear(),
    padDatePart(date.getMonth() + 1),
    padDatePart(date.getDate()),
  ].join("-")
    + "T"
    + [
      padDatePart(date.getHours()),
      padDatePart(date.getMinutes()),
    ].join(":");
}

function datetimeLocalToApi(value) {
  if (!value) return null;
  const date = parseDate(value);
  if (!date) throw new Error("时间格式不正确");
  return date.toISOString();
}

function isSameLocalDate(left, right) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function formatClock(date) {
  return `${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}`;
}

function formatDateTimeLabel(value) {
  const date = parseDate(value);
  if (!date) return "";
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  let dayLabel;
  if (isSameLocalDate(date, today)) {
    dayLabel = "今天";
  } else if (isSameLocalDate(date, tomorrow)) {
    dayLabel = "明天";
  } else if (isSameLocalDate(date, yesterday)) {
    dayLabel = "昨天";
  } else if (date.getFullYear() === today.getFullYear()) {
    dayLabel = `${date.getMonth() + 1}月${date.getDate()}日`;
  } else {
    dayLabel = `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
  }
  return `${dayLabel} ${formatClock(date)}`;
}

function dueDateInfo(task, finished) {
  const date = parseDate(task.due_time);
  if (!date) return null;
  const now = new Date();
  if (finished) {
    return { tone: "done", label: `截止 ${formatDateTimeLabel(task.due_time)}` };
  }
  if (date < now) {
    return { tone: "overdue", label: `已逾期 ${formatDateTimeLabel(task.due_time)}` };
  }
  if (isSameLocalDate(date, now)) {
    return { tone: "today", label: `今天截止 ${formatClock(date)}` };
  }
  return { tone: "upcoming", label: `截止 ${formatDateTimeLabel(task.due_time)}` };
}

function renderTaskSchedule(task, finished) {
  const items = [];
  if (task.start_time) {
    items.push(`<span class="task-date start">开始 ${escapeHtml(formatDateTimeLabel(task.start_time))}</span>`);
  }
  const due = dueDateInfo(task, finished);
  if (due) {
    items.push(`<span class="task-date due ${due.tone}">${escapeHtml(due.label)}</span>`);
  }
  return items.length ? `<div class="task-schedule">${items.join("")}</div>` : "";
}

function validateTaskDateRange(startValue, dueValue) {
  const start = parseDate(startValue);
  const due = parseDate(dueValue);
  if (startValue && !start) throw new Error("开始时间格式不正确");
  if (dueValue && !due) throw new Error("截止时间格式不正确");
  if (start && due && due < start) throw new Error("截止时间不能早于开始时间");
}

function isDefaultProject(project) {
  return project?.system_type === "inbox";
}

function createPlanningState() {
  return {
    messages: [],
    memory_summary: null,
    summarized_message_count: 0,
    phase: "planning",
    available_tools: [],
    info: {
      goal: null,
      constraints: null,
      acceptance_criteria: null,
    },
    draft: {
      project: null,
      tasks: [],
    },
    review: null,
    human_decision: null,
    execution: null,
    next_action: "plan",
    pending_tool_calls: [],
    tool_results: [],
    revision_count: 0,
  };
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
  state.agentSessionId = null;
  state.planningState = null;
  state.agentPendingMessage = null;
  state.agentSending = false;
  state.activeMemories = [];
  state.pendingMemories = [];
  state.memoryStatus = "active";
  state.editingMemoryId = null;
  state.memoryLoading = false;
  state.memoryMutatingId = null;
  state.collapsedTaskIds.clear();
  localStorage.removeItem("planwise_token");
  localStorage.removeItem("planwise_user");
  localStorage.removeItem(AGENT_SESSION_STORAGE_KEY);
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
    const error = new Error("无法连接后端服务");
    error.isNetworkError = true;
    throw error;
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
    const error = new Error(
      details || payload.message || "请求失败",
    );
    error.status = response.status;
    throw error;
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

function closeDialog(dialog) {
  if (dialog.open) dialog.close();
}

function updatePendingMemoryBadge() {
  const count = state.pendingMemories.length;
  $("pendingMemoryBadge").textContent = count;
  $("pendingMemoryBadge").classList.toggle("hidden", count === 0);
  $("pendingMemoryTabCount").textContent = count;
}

function memoryCategoryOptions(selectedCategory) {
  return Object.entries(MEMORY_CATEGORY_LABELS)
    .map(([value, label]) => (
      `<option value="${value}" ${value === selectedCategory ? "selected" : ""}>${label}</option>`
    ))
    .join("");
}

function renderMemoryCard(memory) {
  const isPending = memory.status === "pending";
  const isEditing = !isPending && state.editingMemoryId === memory.memory_id;
  const isMutating = state.memoryMutatingId === memory.memory_id;
  const category = MEMORY_CATEGORY_LABELS[memory.category] || memory.category;
  const source = MEMORY_SOURCE_LABELS[memory.source] || memory.source;
  const updatedAt = formatDateTimeLabel(memory.updated_time);

  if (isEditing) {
    return `
      <article class="memory-card">
        <form class="memory-edit-form" data-memory-edit-form="${memory.memory_id}">
          <label>
            <span>分类</span>
            <select name="category">${memoryCategoryOptions(memory.category)}</select>
          </label>
          <label>
            <span>记忆内容</span>
            <textarea name="content" maxlength="1000" required>${escapeHtml(memory.content)}</textarea>
          </label>
          <div class="memory-edit-actions">
            <button class="text-button" data-cancel-memory-edit="${memory.memory_id}" type="button">取消</button>
            <button class="primary-button" type="submit" ${isMutating ? "disabled" : ""}>${isMutating ? "保存中…" : "保存"}</button>
          </div>
        </form>
      </article>
    `;
  }

  return `
    <article class="memory-card ${isPending ? "pending" : ""}">
      <div class="memory-card-head">
        <div class="memory-card-meta">
          <span class="memory-category">${escapeHtml(category)}</span>
          <span>${escapeHtml(source)}</span>
        </div>
        <span class="memory-card-meta">${escapeHtml(updatedAt)}</span>
      </div>
      <p class="memory-card-content">${escapeHtml(memory.content)}</p>
      <div class="memory-card-actions">
        ${isPending ? `
          <button class="text-button memory-reject" data-reject-memory="${memory.memory_id}" type="button" ${isMutating ? "disabled" : ""}>忽略</button>
          <button class="text-button memory-approve" data-approve-memory="${memory.memory_id}" type="button" ${isMutating ? "disabled" : ""}>${isMutating ? "处理中…" : "确认记住"}</button>
        ` : `
          <button class="text-button" data-edit-memory="${memory.memory_id}" type="button">编辑</button>
          <button class="text-button memory-archive" data-archive-memory="${memory.memory_id}" type="button" ${isMutating ? "disabled" : ""}>归档</button>
        `}
      </div>
    </article>
  `;
}

function renderMemories() {
  updatePendingMemoryBadge();
  const memories = state.memoryStatus === "pending"
    ? state.pendingMemories
    : state.activeMemories;

  document.querySelectorAll("[data-memory-status]").forEach((button) => {
    const active = button.dataset.memoryStatus === state.memoryStatus;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $("memoryListSummary").textContent = `${memories.length} 条记忆`;
  $("memoryList").innerHTML = state.memoryLoading
    ? `<div class="memory-loading"><i></i><span>正在读取记忆…</span></div>`
    : memories.map(renderMemoryCard).join("");

  const empty = !state.memoryLoading && memories.length === 0;
  $("memoryEmpty").classList.toggle("hidden", !empty);
  $("memoryEmptyTitle").textContent = state.memoryStatus === "pending"
    ? "没有待确认的记忆"
    : "还没有长期记忆";
  $("memoryEmptyDescription").textContent = state.memoryStatus === "pending"
    ? "Agent 从对话中提取的候选记忆会出现在这里。"
    : "用自然语言告诉 Agent 你的长期偏好或约束。";
}

async function refreshPendingMemories() {
  state.pendingMemories = await api("/api/memories?status=pending") || [];
  updatePendingMemoryBadge();
  if ($("memoryDialog").open && state.memoryStatus === "pending") {
    renderMemories();
  }
}

async function loadMemories() {
  state.memoryLoading = true;
  $("memoryListError").textContent = "";
  renderMemories();
  try {
    const [activeMemories, pendingMemories] = await Promise.all([
      api("/api/memories?status=active"),
      api("/api/memories?status=pending"),
    ]);
    state.activeMemories = activeMemories || [];
    state.pendingMemories = pendingMemories || [];
  } finally {
    state.memoryLoading = false;
    renderMemories();
  }
}

function openMemoryDialog() {
  state.editingMemoryId = null;
  $("memoryIngestError").textContent = "";
  $("memoryListError").textContent = "";
  renderMemories();
  $("memoryDialog").showModal();
  loadMemories().catch((error) => {
    $("memoryListError").textContent = error.message;
  });
}

function memoryIngestSummary(result) {
  const created = result?.created?.length || 0;
  const updated = result?.updated?.length || 0;
  if (created && updated) return `新增 ${created} 条，更新 ${updated} 条长期记忆`;
  if (created) return `已保存 ${created} 条长期记忆`;
  if (updated) return `已更新 ${updated} 条长期记忆`;
  return "没有发现需要新增或更新的长期记忆";
}

function renderAgentList(values, emptyText = "尚未确认") {
  if (values === null || values === undefined) return escapeHtml(emptyText);
  if (values.length === 0) return "无特殊要求";
  return `<ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>`;
}

function renderAgentText(value, emptyText = "尚未确认") {
  if (value === null || value === undefined || value === "") return escapeHtml(emptyText);
  return escapeHtml(value);
}

function agentMessageLabel(role) {
  if (role === "user") return "你";
  if (role === "tool") return "工具";
  return "Agent";
}

function getAgentPhase(planningState) {
  if (planningState.next_action === "use_tool") {
    return { label: "查询中", tone: "working" };
  }
  const phases = {
    planning: { label: "规划中", tone: "working" },
    reviewing: { label: "评审中", tone: "reviewing" },
    confirming: { label: "待确认", tone: "attention" },
    executing: { label: "创建中", tone: "working" },
    completed: { label: "已创建", tone: "ready" },
  };
  return phases[planningState.phase] || { label: "规划中", tone: "working" };
}

function isAgentConversationLocked(planningState) {
  return ["confirming", "executing", "completed"].includes(planningState.phase);
}

function renderAgentReviewFindings(findings = []) {
  if (!findings.length) {
    return `<li class="agent-review-empty">未发现需要特别处理的问题。</li>`;
  }
  return findings.map((finding) => {
    const category = REVIEW_CATEGORY_LABELS[finding.category] || finding.category;
    const severity = REVIEW_SEVERITY_LABELS[finding.severity] || finding.severity;
    return `
      <li class="agent-review-finding severity-${escapeHtml(finding.severity)}">
        <div>
          <span>${escapeHtml(category)}</span>
          <span>${escapeHtml(severity)}</span>
        </div>
        <p>${escapeHtml(finding.description)}</p>
        ${finding.suggestion ? `<small>建议：${escapeHtml(finding.suggestion)}</small>` : ""}
      </li>
    `;
  }).join("");
}

function renderAgentTaskList(tasks = []) {
  return tasks.map((task) => `
    <li>
      <strong>${escapeHtml(task.title)}</strong>
      ${task.description ? `<p>${escapeHtml(task.description)}</p>` : ""}
      ${task.acceptance_criteria ? `<small>完成标准：${escapeHtml(task.acceptance_criteria)}</small>` : ""}
      <small>优先级：${escapeHtml(TASK_PRIORITY_LABELS[task.priority] || task.priority || "低")}</small>
      ${task.start_time ? `<small>开始：${escapeHtml(formatDateTimeLabel(task.start_time))}</small>` : ""}
      ${task.due_time ? `<small>截止：${escapeHtml(formatDateTimeLabel(task.due_time))}</small>` : ""}
      ${task.subtasks?.length ? `<ol>${renderAgentTaskList(task.subtasks)}</ol>` : ""}
    </li>
  `).join("");
}

function validateAgentSession(session) {
  if (
    !session?.state
    || !Number.isInteger(session.session_id)
    || session.session_id <= 0
  ) {
    throw new Error("Agent 返回的数据不完整，请稍后重试");
  }
  return session;
}

function applyAgentSession(session) {
  const validSession = validateAgentSession(session);
  state.agentSessionId = validSession.session_id;
  state.planningState = validSession.state;
  localStorage.setItem(
    AGENT_SESSION_STORAGE_KEY,
    String(validSession.session_id),
  );
  $("agentConfirmFeedback").value = "";
  $("agentConfirmError").textContent = "";
  return validSession;
}

function forgetAgentSession() {
  state.agentSessionId = null;
  localStorage.removeItem(AGENT_SESSION_STORAGE_KEY);
}

function applyAgentTurnResult(result) {
  return applyAgentSession(result?.session);
}

function agentStateFingerprint(planningState) {
  return JSON.stringify(planningState || null);
}

function waitForAgentRecovery() {
  return new Promise((resolve) => {
    setTimeout(resolve, AGENT_RECOVERY_INTERVAL_MS);
  });
}

function shouldRecoverAgentSession(error) {
  return Boolean(
    error?.isNetworkError
    || error?.status === 409
    || error?.status === 504,
  );
}

async function requestAgentSession() {
  if (!state.agentSessionId) return null;
  const session = await api(
    `/api/agent/${encodeURIComponent(state.agentSessionId)}`,
  );
  return validateAgentSession(session);
}

async function synchronizeAgentSession() {
  try {
    const session = await requestAgentSession();
    return session ? applyAgentSession(session) : null;
  } catch (error) {
    if (error.status === 404) {
      forgetAgentSession();
      state.planningState = null;
      return null;
    }
    throw error;
  }
}

async function recoverAgentSession(previousStateFingerprint) {
  for (let attempt = 0; attempt < AGENT_RECOVERY_ATTEMPTS; attempt += 1) {
    if (!state.agentSessionId || !state.token) return null;
    try {
      const session = await requestAgentSession();
      if (
        session
        && agentStateFingerprint(session.state)
          !== previousStateFingerprint
      ) {
        return applyAgentSession(session);
      }
    } catch (error) {
      if (error.status === 404) {
        forgetAgentSession();
        return null;
      }
    }
    if (attempt < AGENT_RECOVERY_ATTEMPTS - 1) {
      await waitForAgentRecovery();
    }
  }
  return null;
}

function getExecutedProjectIdFromState(executionState) {
  const projectId = executionState?.execution?.plan_id;
  if (
    executionState?.phase !== "completed"
    || !Number.isInteger(projectId)
    || projectId <= 0
  ) {
    throw new Error("项目尚未完成创建，请稍后重试");
  }
  return projectId;
}

function getExecutedProjectId(result) {
  return getExecutedProjectIdFromState(result?.session?.state);
}

async function showExecutedAgentProject(projectId) {
  try {
    await loadProjects();
    await selectProject(projectId);
    showToast("项目与任务已创建");
  } catch {
    showToast("项目已创建，请刷新项目列表");
  }
  closeDialog($("agentDialog"));
}

function renderAgent() {
  const planningState = state.planningState || createPlanningState();
  const messages = planningState.messages || [];
  const messageHtml = messages.map((message) => `
    <article class="agent-message ${message.role}">
      <span>${agentMessageLabel(message.role)}</span>
      <p>${escapeHtml(message.content).replaceAll("\n", "<br>")}</p>
    </article>
  `);

  if (state.agentPendingMessage) {
    messageHtml.push(`
      <article class="agent-message user pending">
        <span>你</span>
        <p>${escapeHtml(state.agentPendingMessage).replaceAll("\n", "<br>")}</p>
      </article>
      <article class="agent-message assistant loading">
        <span>Agent</span>
        <p><i></i><i></i><i></i></p>
      </article>
    `);
  }

  $("agentMessages").innerHTML = messageHtml.length
    ? messageHtml.join("")
    : `
      <div class="agent-empty">
        <span>…</span>
        <strong>从一个目标开始</strong>
        <p>不需要一次说清楚全部信息，Agent 会逐轮询问。</p>
      </div>
    `;

  const info = planningState.info || {};
  $("agentGoal").textContent = info.goal || "尚未确认";
  $("agentConstraints").innerHTML = renderAgentList(info.constraints);
  $("agentCriteria").innerHTML = renderAgentText(info.acceptance_criteria);
  $("agentMessageCount").textContent = `${messages.length} 条消息`;
  const phase = getAgentPhase(planningState);
  $("agentPhase").textContent = phase.label;
  $("agentPhase").className = `agent-phase ${phase.tone}`;

  const draft = planningState.draft;
  const draftTasks = draft?.tasks || [];
  $("agentDraftCard").classList.toggle("hidden", draftTasks.length === 0);
  if (draft) {
    const projectTitle = draft.project?.title;
    $("agentDraftSummary").textContent = draftTasks.length
      ? `${projectTitle ? `项目“${projectTitle}”，` : ""}包含 ${draftTasks.length} 个顶层任务。`
      : "";
    $("agentDraftTasks").innerHTML = renderAgentTaskList(draftTasks);
  }

  const review = planningState.review;
  const reviewFindings = review?.findings || [];
  $("agentReviewCard").classList.toggle("hidden", !review);
  $("agentReviewSummary").textContent = review?.summary || "";
  $("agentReviewCount").textContent = `${reviewFindings.length} 项发现`;
  $("agentReviewFindings").innerHTML = renderAgentReviewFindings(reviewFindings);

  const awaitingConfirmation = planningState.phase === "confirming";
  const conversationLocked = isAgentConversationLocked(planningState);
  $("agentForm").classList.toggle("hidden", conversationLocked);
  $("agentConfirmBar").classList.toggle("hidden", !awaitingConfirmation);

  $("agentMessage").disabled = state.agentSending || conversationLocked;
  $("agentSubmitButton").disabled = state.agentSending || conversationLocked;
  $("resetAgentButton").disabled = state.agentSending;
  $("agentSubmitButton").textContent = state.agentSending ? "处理中…" : "发送";
  $("agentConfirmFeedback").disabled = state.agentSending;
  $("rejectAgentButton").disabled = state.agentSending;
  $("approveAgentButton").disabled = state.agentSending;
  $("rejectAgentButton").textContent = state.agentSending ? "处理中…" : "退回修改";
  $("approveAgentButton").textContent = state.agentSending ? "创建中…" : "通过并创建";
  $("agentMessages").scrollTop = $("agentMessages").scrollHeight;
}

function focusAgentControl() {
  const phase = state.planningState?.phase;
  if (phase === "confirming") {
    $("approveAgentButton").focus();
  } else if (!["executing", "completed"].includes(phase)) {
    $("agentMessage").focus();
  }
}

function openAgentDialog() {
  if (!state.planningState) state.planningState = createPlanningState();
  $("agentError").textContent = "";
  renderAgent();
  $("agentDialog").showModal();
  focusAgentControl();

  if (!state.agentSessionId) return;
  state.agentSending = true;
  renderAgent();
  synchronizeAgentSession()
    .then((session) => {
      if (!session) state.planningState = createPlanningState();
    })
    .catch((error) => {
      $("agentError").textContent = error.message;
    })
    .finally(() => {
      state.agentSending = false;
      renderAgent();
      if ($("agentDialog").open) focusAgentControl();
    });
}

function resetAgentSession() {
  forgetAgentSession();
  state.planningState = createPlanningState();
  state.agentPendingMessage = null;
  $("agentMessage").value = "";
  $("agentCharacterCount").textContent = "0 / 5000";
  $("agentError").textContent = "";
  $("agentConfirmFeedback").value = "";
  $("agentConfirmError").textContent = "";
  renderAgent();
  focusAgentControl();
}

async function submitAgentConfirmation(approved) {
  if (state.agentSending || !state.agentSessionId) return;

  const feedback = $("agentConfirmFeedback").value.trim();
  if (!approved && !feedback) {
    $("agentConfirmError").textContent = "退回计划时请填写修改意见。";
    $("agentConfirmFeedback").focus();
    return;
  }

  $("agentConfirmError").textContent = "";
  state.agentSending = true;
  const previousStateFingerprint = agentStateFingerprint(
    state.planningState,
  );
  renderAgent();

  try {
    const result = await api(
      `/api/agent/${encodeURIComponent(state.agentSessionId)}/confirmation`,
      {
        method: "POST",
        body: JSON.stringify({
          approved,
          feedback: approved ? null : feedback,
        }),
      },
    );
    const projectId = approved ? getExecutedProjectId(result) : null;
    applyAgentTurnResult(result);
    refreshPendingMemories().catch(() => {});
    if (approved) {
      await showExecutedAgentProject(projectId);
    } else {
      showToast("计划已退回并重新评审");
    }
  } catch (error) {
    let recoveredSession = null;
    if (
      state.agentSessionId
      && shouldRecoverAgentSession(error)
    ) {
      $("agentConfirmError").textContent = "连接中断，正在同步会话状态…";
      recoveredSession = await recoverAgentSession(
        previousStateFingerprint,
      );
    }

    if (recoveredSession) {
      refreshPendingMemories().catch(() => {});
      if (
        approved
        && recoveredSession.state.phase === "completed"
      ) {
        const projectId = getExecutedProjectIdFromState(
          recoveredSession.state,
        );
        await showExecutedAgentProject(projectId);
      } else {
        $("agentConfirmError").textContent = "";
        showToast("已同步会话最新状态");
      }
    } else {
      $("agentConfirmError").textContent = error.message;
    }
  } finally {
    state.agentSending = false;
    renderAgent();
    if ($("agentDialog").open) focusAgentControl();
  }
}

function openProfileDialog() {
  $("profileUsername").value = state.user?.username || "";
  $("profileEmail").value = state.user?.email || "";
  $("profileBio").value = state.user?.bio || "";
  $("profileError").textContent = "";
  $("profileDialog").showModal();
}

function openProjectDialog() {
  const project = state.selectedProject;
  if (!project || isDefaultProject(project) || project.archived_time) return;
  $("editProjectTitle").value = project.title;
  $("editProjectGoal").value = project.goal || "";
  $("editProjectDescription").value = project.description || "";
  $("projectEditError").textContent = "";
  $("projectDialog").showModal();
}

async function loadProjects() {
  const [active, archived] = await Promise.all([
    api("/api/plans"),
    api("/api/plans?archived=true"),
  ]);
  state.projects = active || [];
  state.archivedProjects = archived || [];
  $("archiveCount").textContent = state.archivedProjects.length;

  if (!state.selectedProject || state.selectedProject.archived_time) {
    state.selectedProject =
      state.projects.find(isDefaultProject)
      || state.projects[0]
      || null;
  } else {
    state.selectedProject =
      state.projects.find((project) => project.plan_id === state.selectedProject.plan_id)
      || state.archivedProjects.find((project) => project.plan_id === state.selectedProject.plan_id)
      || state.projects[0]
      || null;
  }
  renderProjects();
  renderProjectHeader();
}

function projectButton(project) {
  const inbox = isDefaultProject(project);
  const active = state.selectedProject?.plan_id === project.plan_id;
  return `
    <button class="project-item ${active ? "active" : ""}" data-project-id="${project.plan_id}" type="button">
      <span class="project-symbol">${inbox ? "⌂" : escapeHtml(project.title.slice(0, 1).toUpperCase())}</span>
      <span class="project-name">${inbox ? "待整理" : escapeHtml(project.title)}</span>
      <span class="project-count">${inbox ? "" : PROJECT_STATUS_LABELS[project.status] || ""}</span>
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
    $("currentProjectGoal").textContent = "先创建一个项目，或重新登录生成默认项目。";
    $("projectActions").classList.add("hidden");
    return;
  }
  const inbox = isDefaultProject(project);
  const archived = Boolean(project.archived_time);
  $("projectActions").classList.toggle("hidden", inbox);
  $("projectEyebrow").textContent = inbox ? "CAPTURE" : archived ? "ARCHIVED PROJECT" : "PROJECT";
  $("currentProjectTitle").textContent = inbox ? "待整理" : project.title;
  $("currentProjectGoal").textContent = inbox
    ? "尚未归类的目标和任务会集中在这里，稍后再整理。"
    : project.goal || project.description || "为这个项目补充一个清晰目标。";

  const statusSelect = $("projectStatusSelect");
  statusSelect.innerHTML = (PROJECT_TRANSITIONS[project.status] || [project.status])
    .map((value) => `<option value="${value}" ${value === project.status ? "selected" : ""}>${PROJECT_STATUS_LABELS[value]}</option>`)
    .join("");
  statusSelect.disabled = inbox || archived;
  statusSelect.classList.toggle("hidden", inbox || archived);
  $("editProjectButton").classList.toggle("hidden", inbox || archived);
  $("archiveProjectButton").classList.toggle("hidden", inbox || archived);
  $("restoreProjectButton").classList.toggle("hidden", inbox || !archived);
}

async function selectProject(id) {
  const all = [...state.projects, ...state.archivedProjects];
  const project = all.find((item) => item.plan_id === Number(id));
  if (!project) throw new Error("项目列表中未找到目标项目");
  state.selectedProject = project;
  state.tasks = [];
  state.showArchivedTasks = false;
  state.collapsedTaskIds.clear();
  $("toggleArchivedTasksButton").textContent = "查看归档任务";
  $("toggleArchivedTasksButton").classList.remove("active");
  renderProjects(Boolean(state.selectedProject?.archived_time));
  renderProjectHeader();
  renderTasks();
  await loadTasks();
}

async function loadTasks() {
  if (!state.selectedProject) {
    state.tasks = [];
    renderTasks();
    return;
  }
  const query = new URLSearchParams({
    plan_id: state.selectedProject.plan_id,
    archived: state.showArchivedTasks,
  });
  state.tasks = await api(`/api/tasks?${query}`) || [];
  renderTasks();
}

function filteredTasks() {
  if (state.taskFilter === "done") {
    return state.tasks.filter((task) => task.status === "completed");
  }
  if (state.taskFilter === "open") {
    return state.tasks.filter((task) => !["completed", "cancelled"].includes(task.status));
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
  const maxLevel = Math.max(1, ...tasks.map((task) => Math.max(1, Math.min(task.level, 3))));
  const children = new Map();
  tasks.forEach((task) => {
    const parent = visibleIds.has(task.parent_task_id) ? task.parent_task_id : null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(task);
  });
  children.forEach((items) => items.sort((a, b) => a.sort_order - b.sort_order || a.task_id - b.task_id));

  const statsCache = new Map();
  function descendantStats(taskId, ancestors = new Set()) {
    if (statsCache.has(taskId)) return statsCache.get(taskId);
    if (ancestors.has(taskId)) return { total: 0, done: 0 };
    const nextAncestors = new Set(ancestors);
    nextAncestors.add(taskId);

    const result = (children.get(taskId) || []).reduce((stats, child) => {
      const nested = descendantStats(child.task_id, nextAncestors);
      return {
        total: stats.total + 1 + nested.total,
        done: stats.done + (["completed", "cancelled"].includes(child.status) ? 1 : 0) + nested.done,
      };
    }, { total: 0, done: 0 });
    statsCache.set(taskId, result);
    return result;
  }

  const visited = new Set();
  function walk(parentId) {
    return (children.get(parentId) || []).map((task) => {
      if (visited.has(task.task_id)) return "";
      visited.add(task.task_id);
      const level = Math.max(1, Math.min(task.level, 3));
      const indentRatio = maxLevel === 1 ? 0 : (level - 1) / (maxLevel - 1);
      const checkDone = task.status === "completed";
      const finished = ["completed", "cancelled"].includes(task.status);
      const childTasks = children.get(task.task_id) || [];
      const hasChildren = childTasks.length > 0;
      const hasVisibleParent = visibleIds.has(task.parent_task_id);
      const collapsed = hasChildren && state.collapsedTaskIds.has(task.task_id);
      const stats = hasChildren ? descendantStats(task.task_id) : null;
      return `
        <article class="task-row ${finished ? "done" : ""} ${hasVisibleParent ? "is-child" : ""} ${hasChildren ? "has-children" : ""} ${collapsed ? "collapsed" : ""}" data-level="${level}" style="--desktop-indent:${indentRatio * 96}px; --mobile-indent:${indentRatio * 48}px">
          <div class="task-leading">
            ${hasChildren ? `
              <button class="task-disclosure" data-toggle-children="${task.task_id}" type="button" aria-label="${collapsed ? "展开子任务" : "收起子任务"}" aria-expanded="${!collapsed}">
                ${collapsed ? "›" : "⌄"}
              </button>
            ` : `<span class="task-disclosure-placeholder" aria-hidden="true"></span>`}
            <button class="task-check ${checkDone ? "done" : ""}" data-complete-task="${task.task_id}" type="button" aria-label="${finished ? "重新打开" : "完成任务"}" ${state.showArchivedTasks ? "disabled" : ""}>✓</button>
          </div>
          <div class="task-copy">
            <div class="task-title-row">
              <div class="task-title">${escapeHtml(task.title)}</div>
              ${hasChildren ? `<span class="task-progress">${stats.done}/${stats.total}</span>` : ""}
            </div>
            ${task.description ? `<p class="task-description">${escapeHtml(task.description)}</p>` : ""}
            ${task.acceptance_criteria ? `<p class="task-criteria"><strong>完成标准：</strong>${escapeHtml(task.acceptance_criteria)}</p>` : ""}
            ${renderTaskSchedule(task, finished)}
            <div class="task-tags">
              <span class="pill priority-${task.priority}">${TASK_PRIORITY_LABELS[task.priority] || escapeHtml(task.priority)}</span>
              <span class="pill">${TASK_STATUS_LABELS[task.status]}</span>
            </div>
          </div>
          <select data-task-status="${task.task_id}" aria-label="任务状态" ${state.showArchivedTasks ? "disabled" : ""}>${taskStatusOptions(task)}</select>
          <div class="task-row-actions">
            ${state.showArchivedTasks ? `
              <button class="icon-button" data-restore-task="${task.task_id}" type="button" aria-label="恢复任务" title="恢复任务">${ICONS.restore}</button>
            ` : `
              <button class="icon-button" data-edit-task="${task.task_id}" type="button" aria-label="编辑任务" title="编辑任务">${ICONS.edit}</button>
              ${["completed", "cancelled"].includes(task.status) ? "" : `<button class="icon-button" data-child-task="${task.task_id}" type="button" aria-label="添加子任务" title="添加子任务">${ICONS.child}</button>`}
              <button class="icon-button danger" data-archive-task="${task.task_id}" type="button" aria-label="归档任务" title="归档任务">${ICONS.archive}</button>
            `}
          </div>
        </article>
        ${collapsed ? "" : walk(task.task_id)}
      `;
    }).join("");
  }
  return walk(null);
}

function renderTasks() {
  const tasks = filteredTasks();
  $("taskList").innerHTML = renderTaskTree(tasks);
  $("emptyState").classList.toggle("hidden", tasks.length > 0);

  const total = state.tasks.length;
  const done = state.tasks.filter((task) => ["completed", "cancelled"].includes(task.status)).length;
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
  state.editingTask = null;
  $("taskFormTitle").textContent = "添加任务";
  $("taskFormHint").textContent = "创建一个清晰、可执行的行动。";
  $("taskSubmitButton").textContent = "创建任务";
  $("parentContext").classList.add("hidden");
}

function openTaskForm(parentTask = null, editingTask = null) {
  if (!state.selectedProject || state.selectedProject.archived_time) return;
  resetTaskForm();
  state.parentTask = parentTask;
  state.editingTask = editingTask;
  if (parentTask) {
    $("parentTaskTitle").textContent = parentTask.title;
    $("parentContext").classList.remove("hidden");
  }
  if (editingTask) {
    $("taskFormTitle").textContent = "编辑任务";
    $("taskFormHint").textContent = "修改任务内容不会改变当前状态。";
    $("taskSubmitButton").textContent = "保存修改";
    $("taskTitle").value = editingTask.title;
    $("taskPriority").value = editingTask.priority;
    $("taskStartTime").value = dateToDatetimeLocalValue(editingTask.start_time);
    $("taskDueTime").value = dateToDatetimeLocalValue(editingTask.due_time);
    $("taskDescription").value = editingTask.description || "";
    $("taskCriteria").value = editingTask.acceptance_criteria || "";
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
    if (state.agentSessionId) {
      try {
        await synchronizeAgentSession();
      } catch (error) {
        showToast(`会话状态恢复失败：${error.message}`);
      }
    }
    refreshPendingMemories().catch(() => {});
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

$("profileButton").addEventListener("click", openProfileDialog);
$("closeProfileButton").addEventListener("click", () => closeDialog($("profileDialog")));
$("cancelProfileButton").addEventListener("click", () => closeDialog($("profileDialog")));
$("profileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("profileError").textContent = "";
  $("profileSubmitButton").disabled = true;
  try {
    state.user = await api("/api/user/me", {
      method: "PATCH",
      body: JSON.stringify({
        email: $("profileEmail").value.trim() || null,
        bio: $("profileBio").value.trim() || null,
      }),
    });
    localStorage.setItem("planwise_user", JSON.stringify(state.user));
    $("navUsername").textContent = state.user.username;
    closeDialog($("profileDialog"));
    showToast("个人资料已更新");
  } catch (error) {
    $("profileError").textContent = error.message;
  } finally {
    $("profileSubmitButton").disabled = false;
  }
});

$("openMemoryButton").addEventListener("click", openMemoryDialog);
$("closeMemoryButton").addEventListener("click", () => closeDialog($("memoryDialog")));

$("memoryIngestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("memoryText").value.trim();
  if (!text) return;

  $("memoryIngestError").textContent = "";
  $("memoryIngestButton").disabled = true;
  $("memoryIngestButton").textContent = "提取中…";
  try {
    const result = await api("/api/memories/ingest", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    $("memoryIngestForm").reset();
    state.memoryStatus = "active";
    state.editingMemoryId = null;
    await loadMemories();
    showToast(memoryIngestSummary(result));
  } catch (error) {
    $("memoryIngestError").textContent = error.message;
  } finally {
    $("memoryIngestButton").disabled = false;
    $("memoryIngestButton").textContent = "提取并保存";
  }
});

$("memoryDialog").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-memory-status]");
  if (!tab) return;
  state.memoryStatus = tab.dataset.memoryStatus;
  state.editingMemoryId = null;
  $("memoryListError").textContent = "";
  renderMemories();
});

$("memoryList").addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-memory-edit-form]");
  if (!form) return;
  event.preventDefault();

  const memoryId = Number(form.dataset.memoryEditForm);
  const category = form.elements.category.value;
  const content = form.elements.content.value.trim();
  if (!content) return;

  state.memoryMutatingId = memoryId;
  $("memoryListError").textContent = "";
  renderMemories();
  try {
    await api(`/api/memories/${memoryId}`, {
      method: "PATCH",
      body: JSON.stringify({
        category,
        content,
      }),
    });
    state.editingMemoryId = null;
    await loadMemories();
    showToast("长期记忆已更新");
  } catch (error) {
    $("memoryListError").textContent = error.message;
  } finally {
    state.memoryMutatingId = null;
    renderMemories();
  }
});

$("memoryList").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-memory]");
  const cancelButton = event.target.closest("[data-cancel-memory-edit]");
  const approveButton = event.target.closest("[data-approve-memory]");
  const rejectButton = event.target.closest("[data-reject-memory]");
  const archiveButton = event.target.closest("[data-archive-memory]");

  if (editButton) {
    state.editingMemoryId = Number(editButton.dataset.editMemory);
    renderMemories();
    return;
  }
  if (cancelButton) {
    state.editingMemoryId = null;
    renderMemories();
    return;
  }

  const memoryId = Number(
    approveButton?.dataset.approveMemory
    || rejectButton?.dataset.rejectMemory
    || archiveButton?.dataset.archiveMemory,
  );
  if (!memoryId || state.memoryMutatingId !== null) return;
  if (archiveButton && !window.confirm("归档后这条记忆将不再参与规划，确定继续吗？")) return;

  state.memoryMutatingId = memoryId;
  $("memoryListError").textContent = "";
  renderMemories();
  try {
    if (approveButton || rejectButton) {
      await api(`/api/memories/${memoryId}/confirmation`, {
        method: "POST",
        body: JSON.stringify({ approved: Boolean(approveButton) }),
      });
    } else if (archiveButton) {
      await api(`/api/memories/${memoryId}`, { method: "DELETE" });
    }
    await loadMemories();
    showToast(
      approveButton
        ? "记忆已确认并生效"
        : rejectButton
          ? "候选记忆已忽略"
          : "长期记忆已归档",
    );
  } catch (error) {
    $("memoryListError").textContent = error.message;
  } finally {
    state.memoryMutatingId = null;
    renderMemories();
  }
});

$("openAgentButton").addEventListener("click", openAgentDialog);
$("closeAgentButton").addEventListener("click", () => closeDialog($("agentDialog")));
$("resetAgentButton").addEventListener("click", resetAgentSession);
$("agentMessage").addEventListener("input", (event) => {
  $("agentCharacterCount").textContent = `${event.target.value.length} / 5000`;
});
$("agentMessage").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    $("agentForm").requestSubmit();
  }
});
$("agentConfirmForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitAgentConfirmation(false);
});
$("approveAgentButton").addEventListener("click", () => {
  submitAgentConfirmation(true);
});
$("agentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.agentSending) return;
  if (isAgentConversationLocked(state.planningState || createPlanningState())) return;

  const message = $("agentMessage").value.trim();
  if (!message) return;
  if (!state.planningState) state.planningState = createPlanningState();
  const previousStateFingerprint = agentStateFingerprint(
    state.planningState,
  );

  $("agentError").textContent = "";
  state.agentSending = true;
  state.agentPendingMessage = message;
  renderAgent();

  try {
    const result = state.agentSessionId
      ? await api(`/api/agent/?session_id=${encodeURIComponent(state.agentSessionId)}`, {
        method: "PATCH",
        body: JSON.stringify({ message }),
      })
      : await api("/api/agent/", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
    applyAgentTurnResult(result);
    refreshPendingMemories().catch(() => {});
    $("agentMessage").value = "";
    $("agentCharacterCount").textContent = "0 / 5000";
  } catch (error) {
    let recoveredSession = null;
    if (
      state.agentSessionId
      && shouldRecoverAgentSession(error)
    ) {
      $("agentError").textContent = "连接中断，正在同步会话状态…";
      recoveredSession = await recoverAgentSession(
        previousStateFingerprint,
      );
    }

    if (recoveredSession) {
      $("agentMessage").value = "";
      $("agentCharacterCount").textContent = "0 / 5000";
      $("agentError").textContent = "";
      refreshPendingMemories().catch(() => {});
      showToast("已同步会话最新状态");
    } else {
      $("agentError").textContent = error.message;
    }
  } finally {
    state.agentPendingMessage = null;
    state.agentSending = false;
    renderAgent();
    if (!$("agentDialog").open) return;
    focusAgentControl();
  }
});

$("showProjectFormButton").addEventListener("click", () => $("projectForm").classList.remove("hidden"));
$("cancelProjectButton").addEventListener("click", () => $("projectForm").classList.add("hidden"));
$("projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const project = await api("/api/plans", {
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
    state.collapsedTaskIds.clear();
    renderProjects(true);
    renderProjectHeader();
    loadTasks().catch((error) => showToast(error.message));
  } else {
    state.selectedProject =
      state.projects.find(isDefaultProject)
      || state.projects[0]
      || null;
    state.collapsedTaskIds.clear();
    renderProjects(false);
    renderProjectHeader();
    loadTasks().catch((error) => showToast(error.message));
  }
});

$("projectStatusSelect").addEventListener("change", async (event) => {
  const project = state.selectedProject;
  if (!project || event.target.value === project.status) return;
  try {
    await api(`/api/plans/${project.plan_id}/status`, {
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

$("editProjectButton").addEventListener("click", openProjectDialog);
$("closeProjectButton").addEventListener("click", () => closeDialog($("projectDialog")));
$("cancelProjectEditButton").addEventListener("click", () => closeDialog($("projectDialog")));
$("projectEditForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const project = state.selectedProject;
  if (!project) return;
  $("projectEditError").textContent = "";
  $("projectEditSubmitButton").disabled = true;
  try {
    state.selectedProject = await api(`/api/plans/${project.plan_id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: $("editProjectTitle").value.trim(),
        goal: $("editProjectGoal").value.trim() || null,
        description: $("editProjectDescription").value.trim() || null,
      }),
    });
    closeDialog($("projectDialog"));
    await loadProjects();
    await loadTasks();
    showToast("项目信息已更新");
  } catch (error) {
    $("projectEditError").textContent = error.message;
  } finally {
    $("projectEditSubmitButton").disabled = false;
  }
});

$("archiveProjectButton").addEventListener("click", async () => {
  if (!state.selectedProject) return;
  try {
    await api(`/api/plans/${state.selectedProject.plan_id}`, { method: "DELETE" });
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
    const project = await api(`/api/plans/${state.selectedProject.plan_id}/restore`, { method: "POST" });
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
  $("taskSubmitButton").disabled = true;
  try {
    const startTime = $("taskStartTime").value;
    const dueTime = $("taskDueTime").value;
    validateTaskDateRange(startTime, dueTime);
    const taskData = {
      title: $("taskTitle").value.trim(),
      description: $("taskDescription").value.trim() || null,
      acceptance_criteria: $("taskCriteria").value.trim() || null,
      priority: $("taskPriority").value,
      start_time: datetimeLocalToApi(startTime),
      due_time: datetimeLocalToApi(dueTime),
    };
    if (state.editingTask) {
      await api(`/api/tasks/${state.editingTask.task_id}`, {
        method: "PATCH",
        body: JSON.stringify(taskData),
      });
    } else {
      await api("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          plan_id: state.selectedProject.plan_id,
          parent_task_id: state.parentTask?.task_id || null,
          ...taskData,
        }),
      });
    }
    const successMessage = state.editingTask ? "任务已更新" : "任务已创建";
    resetTaskForm();
    $("taskForm").classList.add("hidden");
    await loadTasks();
    showToast(successMessage);
  } catch (error) {
    $("taskError").textContent = error.message;
  } finally {
    $("taskSubmitButton").disabled = false;
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
  $("toggleArchivedTasksButton").classList.toggle("active", state.showArchivedTasks);
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
  const toggleButton = event.target.closest("[data-toggle-children]");
  if (toggleButton) {
    const taskId = Number(toggleButton.dataset.toggleChildren);
    if (state.collapsedTaskIds.has(taskId)) {
      state.collapsedTaskIds.delete(taskId);
    } else {
      state.collapsedTaskIds.add(taskId);
    }
    renderTasks();
    return;
  }

  const completeButton = event.target.closest("[data-complete-task]");
  const editButton = event.target.closest("[data-edit-task]");
  const childButton = event.target.closest("[data-child-task]");
  const archiveButton = event.target.closest("[data-archive-task]");
  const restoreButton = event.target.closest("[data-restore-task]");
  try {
    if (completeButton) {
      const task = state.tasks.find((item) => item.task_id === Number(completeButton.dataset.completeTask));
      const targetStatus = ["completed", "cancelled"].includes(task.status) ? "pending" : "completed";
      await changeTaskStatus(task.task_id, targetStatus);
    } else if (editButton) {
      const task = state.tasks.find((item) => item.task_id === Number(editButton.dataset.editTask));
      openTaskForm(null, task);
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

[$("profileDialog"), $("projectDialog"), $("memoryDialog"), $("agentDialog")].forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog(dialog);
  });
});

boot();
