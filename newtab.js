/* ═══════════════════════════════════════════════════════════
   ox-alpha new tab — runtime
   agent · telemetry · bookmarks · modals · timeline
   ═══════════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";
const DEFAULT_MODEL = "openrouter/free";
const MAX_ROUNDS = 8;
const DAY_MS = 86_400_000;

const MODELS = [
  ["openrouter/free", "Auto — best free for the task"],
  ["z-ai/glm-5.2:free", "GLM 5.2 · 256K"],
  ["openai/gpt-oss-120b:free", "GPT-OSS 120B · coding + tools"],
  ["nvidia/nemotron-3-ultra-550b-a55b:free", "Nemotron 3 Ultra · 1M ctx"],
  ["nvidia/nemotron-3.5-lightning:free", "Nemotron 3.5 Lightning · fast"],
  ["nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 3 Super · 262K"],
  ["thinkingmachines/inkling:free", "Inkling · vision + reasoning"],
  ["google/gemma-4-31b-it:free", "Gemma 4 31B · vision"],
  ["cohere/north-mini-code:free", "North Mini Code · code"],
  ["poolside/laguna-s-2.1:free", "Laguna S 2.1 · coding agent"],
  ["openai/gpt-oss-20b:free", "GPT-OSS 20B · lightweight"],
  ["custom", "Custom model id…"],
];

const ENGINES = {
  google: "https://www.google.com/search?q=",
  ddg: "https://duckduckgo.com/?q=",
  bing: "https://www.bing.com/search?q=",
  brave: "https://search.brave.com/search?q=",
  youtube: "https://www.youtube.com/results?search_query=",
};

const ENGINE_LABELS = {
  google: "Google",
  ddg: "DuckDuckGo",
  bing: "Bing",
  brave: "Brave",
  youtube: "YouTube",
};

const APPS = [
  ["GitHub", "github.com"],
  ["YouTube", "youtube.com"],
  ["Vercel", "vercel.com"],
  ["Netlify", "netlify.com"],
  ["Cloudflare", "dash.cloudflare.com"],
  ["Stack Overflow", "stackoverflow.com"],
];

const AGENT_PROMPT = [
  "You are ox-alpha, an autonomous browser agent living in a developer's new tab.",
  "You control the browser through tools: you can list, open, focus and close tabs, search the web, and read page content.",
  "When a task involves facts, research, links or anything uncertain — use tools instead of guessing.",
  "Chain multiple tools freely until the task is genuinely done, then reply with a short summary of what you did.",
  "For pure explanations or code questions, answer directly without tools.",
  "Keep answers concise. Put code in fenced blocks.",
].join(" ");

const TOOLS = [
  {
    type: "function",
    function: {
      name: "list_tabs",
      description: "List currently open browser tabs with their id, title and url.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "open_tab",
      description: "Open a url in a new browser tab and focus it.",
      parameters: {
        type: "object",
        properties: { url: { type: "string", description: "Full or bare domain url" } },
        required: ["url"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "focus_tab",
      description: "Bring an existing tab to the front.",
      parameters: {
        type: "object",
        properties: { tabId: { type: "integer" } },
        required: ["tabId"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "close_tab",
      description: "Close a tab by its id.",
      parameters: {
        type: "object",
        properties: { tabId: { type: "integer" } },
        required: ["tabId"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "web_search",
      description: "Search the web, returns top results with title, url and snippet.",
      parameters: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "read_page",
      description:
        "Read visible text of a browser tab (defaults to the active tab). Use after opening a search result to extract its content.",
      parameters: {
        type: "object",
        properties: { tabId: { type: "integer", description: "Optional tab id" } },
      },
    },
  },
];

let settings = { apiKey: "", model: DEFAULT_MODEL, engine: "google" };
let chatHistory = [];
let controller = null;
let toastTimer;
let notesTimer;
let exts = [];
let telemetry = { ready: false, visitsToday: 0, visitsWeek: 0 };

/* ═══════════════════════════════════════════════════════════
   BOOT
   ═══════════════════════════════════════════════════════════ */

init();

async function init() {
  settings = await chrome.storage.local.get({
    apiKey: "",
    model: DEFAULT_MODEL,
    engine: "google",
  });
  if (!settings.model) settings.model = DEFAULT_MODEL;
  if (!ENGINES[settings.engine]) settings.engine = "google";
  if (!settings.apiKey && window.NOIR_CONFIG?.apiKey) {
    settings.apiKey = window.NOIR_CONFIG.apiKey;
  }

  injectSvgDefs();
  startClocks();
  setupCursorGlow();
  renderCalendar();
  setupEngines();
  setupCommandBar();
  setupModals();
  setupDock();
  setupBookmarks();
  setupChat();
  setupSettings();
  setupNotes();
  setupExtensions();
  setupRecent();
  loadTelemetry();
  updateAiStatus();
}

/* ═══════════════════════════════════════════════════════════
   SHARED SVG DEFS (amber gradient for donut arcs)
   ═══════════════════════════════════════════════════════════ */

function injectSvgDefs() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "0");
  svg.setAttribute("height", "0");
  svg.style.position = "absolute";
  svg.innerHTML = `
    <defs>
      <linearGradient id="amberGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f4c98a"/>
        <stop offset="1" stop-color="#e8a355"/>
      </linearGradient>
    </defs>`;
  document.body.appendChild(svg);
}

/* ═══════════════════════════════════════════════════════════
   CLOCKS — topbar, hero, timeline
   ═══════════════════════════════════════════════════════════ */

function startClocks() {
  const hm = $("#hm");
  const date = $("#date");
  const tbDate = $("#tbDate");

  const tick = () => {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");

    hm.textContent = `${hh}:${mm}:${ss}`;
    date.textContent = d.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    tbDate.textContent = `${d.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    })} · ${hh}:${mm}`;
  };

  tick();
  setInterval(tick, 1000);
}

/* ═══════════════════════════════════════════════════════════
   TELEMETRY — history → hero stats, donuts, bars, timeline
   ═══════════════════════════════════════════════════════════ */

function loadTelemetry() {
  if (!chrome.history?.search) {
    $("#statVisits").textContent = "—";
    $("#actTotal").textContent = "no permission";
    return;
  }

  chrome.history.search(
    { text: "", maxResults: 1000, startTime: Date.now() - 7 * DAY_MS },
    (items) => {
      const now = Date.now();
      const midnight = new Date().setHours(0, 0, 0, 0);

      let visits24 = 0;
      let visitsToday = 0;
      let visitsWeek = 0;

      for (const item of items) {
        const t = item.lastVisitTime || 0;
        if (!t) continue;
        if (now - t <= DAY_MS) visits24++;
        if (t >= midnight) visitsToday++;
        visitsWeek++;
      }

      const tabsCount = Number($("#statTabs").dataset.value || 0);

      $("#statVisits").textContent = String(visitsToday);
      $("#actTotal").textContent = `${visits24} visits · 24h`;
      $("#recentHint").textContent = `${items.length} sites · 7d`;

      telemetry = { ready: true, visitsToday, visitsWeek };
      renderDonuts({ tabsCount, exts, visitsToday, visitsWeek });
    }
  );
}

function renderDonuts({ tabsCount, exts, visitsToday, visitsWeek }) {
  const on = exts.filter((e) => e.enabled).length;
  const extPct = exts.length ? on / exts.length : 0;
  const tabPct = Math.min(1, tabsCount / 25);
  const avgDay = visitsWeek / 7;
  const focusPct = avgDay > 0 ? Math.min(1, visitsToday / (avgDay * 1.5)) : 0;

  const donuts = [
    { pct: extPct, num: `${on}/${exts.length}`, label: "ext on" },
    { pct: tabPct, num: String(tabsCount), label: "tabs" },
    { pct: focusPct, num: `${Math.round(focusPct * 100)}%`, label: "vs avg" },
  ];

  const host = $("#donuts");
  host.replaceChildren();

  for (const d of donuts) {
    const R = 26;
    const C = 2 * Math.PI * R;
    const wrap = document.createElement("div");
    wrap.className = "donut";
    wrap.innerHTML = `
      <svg viewBox="0 0 64 64">
        <circle class="donut-track" cx="32" cy="32" r="${R}" fill="none" stroke-width="5"/>
        <circle class="donut-arc" cx="32" cy="32" r="${R}" fill="none" stroke-width="5"
          stroke-dasharray="${C}" stroke-dashoffset="${C}"
          transform="rotate(-90 32 32)"/>
        <text class="donut-num" x="32" y="37" text-anchor="middle">${d.num}</text>
      </svg>
      <span class="donut-label">${d.label}</span>`;
    host.appendChild(wrap);

    const arc = wrap.querySelector(".donut-arc");
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        arc.style.strokeDashoffset = String(C * (1 - d.pct));
      })
    );
  }
}

/* ═══════════════════════════════════════════════════════════
   BOOKMARKS PILL BAR
   ═══════════════════════════════════════════════════════════ */

function setupBookmarks() {
  const bar = $("#bmBar");
  const scroll = $("#bmScroll");

  if (!chrome.bookmarks?.getRecent) {
    bar.hidden = true;
    return;
  }

  chrome.bookmarks.getRecent(40, (items) => {
    const marks = (items || []).filter((b) => /^https?:\/\//i.test(b.url || ""));
    if (!marks.length) {
      bar.hidden = true;
      return;
    }
    for (const b of marks) {
      let host = "";
      try {
        host = new URL(b.url).hostname.replace(/^www\./, "");
      } catch {}
      const a = document.createElement("a");
      a.className = "bm-pill";
      a.href = b.url;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.title = `${b.title || host} — ${host}`;
      const img = document.createElement("img");
      img.src = `https://www.google.com/s2/favicons?domain=${host}&sz=32`;
      img.alt = "";
      img.loading = "lazy";
      const label = document.createElement("span");
      label.textContent = shorten(b.title || host, 26);
      a.append(img, label);
      scroll.appendChild(a);
    }
  });

  $("#bmLeft").addEventListener("click", () => scrollByAmount(scroll, -320));
  $("#bmRight").addEventListener("click", () => scrollByAmount(scroll, 320));

  $("#tgBookmarks").addEventListener("click", () => {
    chrome.tabs.create({ url: "chrome://bookmarks" });
  });
}

function scrollByAmount(el, dx) {
  el.scrollBy({ left: dx, behavior: "smooth" });
}

function shorten(text, max) {
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

/* ═══════════════════════════════════════════════════════════
   MODALS
   ═══════════════════════════════════════════════════════════ */

function setupModals() {
  $("#tgAi").addEventListener("click", () =>
    setModal("ai", $("#aiModal").classList.contains("closed"))
  );
  $("#tgExt").addEventListener("click", () =>
    setModal("ext", $("#extModal").classList.contains("closed"))
  );

  for (const close of $$(".modal-close")) {
    close.addEventListener("click", () => setModal(close.dataset.modal, false));
  }

  for (const id of ["aiModal", "extModal"]) {
    const overlay = $("#" + id);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) setModal(id === "aiModal" ? "ai" : "ext", false);
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!$("#aiModal").classList.contains("closed")) {
      if (!$("#settings").hidden) {
        $("#settings").hidden = true;
        return;
      }
      if (controller) {
        stopStream();
        return;
      }
      setModal("ai", false);
    } else if (!$("#extModal").classList.contains("closed")) {
      setModal("ext", false);
    } else {
      document.activeElement?.blur();
    }
  });
}

function setModal(name, open) {
  const overlay = $(name === "ai" ? "#aiModal" : "#extModal");
  const toggle = $(name === "ai" ? "#tgAi" : "#tgExt");
  overlay.classList.toggle("closed", !open);
  toggle.classList.toggle("active", open);
  if (open && name === "ai") {
    setTimeout(() => $("#prompt").focus(), 60);
  }
}

/* ═══════════════════════════════════════════════════════════
   APP DOCK
   ═══════════════════════════════════════════════════════════ */

const APP_ICONS = {
  github:
    '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>',
  youtube:
    '<svg viewBox="0 0 16 16"><rect x="1.25" y="3.4" width="13.5" height="9.2" rx="2.4" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M6.9 5.95v4.1L10.5 8 6.9 5.95Z" fill="currentColor"/></svg>',
  vercel:
    '<svg viewBox="0 0 16 16"><path d="M8 2.7 14 13.1H2L8 2.7Z" fill="currentColor"/></svg>',
  netlify:
    '<svg viewBox="0 0 16 16"><path d="M8 1.9 13.8 5.1v5.8L8 14.1 2.2 10.9V5.1L8 1.9Z" fill="none" stroke="currentColor" stroke-width="1.15" stroke-linejoin="round"/><path d="M5.9 10.3V6l4.2 3.4V5.7" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cloudflare:
    '<svg viewBox="0 0 16 16"><path d="M4.4 11.5h6.9a2.05 2.05 0 0 0 .4-4.06 3.3 3.3 0 0 0-6.25-1.32 2.5 2.5 0 0 0-1.05 5.38Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M9.1 9.3l1.15 2.2" stroke="currentColor" stroke-width="1.05" stroke-linecap="round"/></svg>',
  stackoverflow:
    '<svg viewBox="0 0 16 16"><path d="M3.9 13.6h8.2" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"/><path d="M5.3 11.1V8.8M7.5 11.1V6.9M9.7 11.1V7.6" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"/><path d="M4.6 5.9 10.9 3.4" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"/></svg>',
};

function setupDock() {
  const dock = $("#dock");
  for (const [name, host] of APPS) {
    const icon = host.split(".")[0] === "dash" ? "cloudflare" : host.split(".")[0];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tile";
    btn.title = host;
    const glyph = document.createElement("span");
    glyph.className = "tile-icon";
    glyph.innerHTML = APP_ICONS[icon] || APP_ICONS.github;
    const span = document.createElement("span");
    span.className = "tile-name";
    span.textContent = name;
    btn.append(glyph, span);
    btn.addEventListener("click", () => chrome.tabs.create({ url: `https://${host}` }));
    dock.appendChild(btn);
  }
}

/* ═══════════════════════════════════════════════════════════
   SEARCH ENGINES
   ═══════════════════════════════════════════════════════════ */

function setupEngines() {
  const wrap = $("#engines");

  const setActive = () => {
    for (const b of wrap.querySelectorAll("button")) {
      b.classList.toggle("active", b.dataset.engine === settings.engine);
    }
    $("#tbEngine").textContent = ENGINE_LABELS[settings.engine];
  };
  setActive();

  wrap.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-engine]");
    if (!btn) return;
    settings.engine = btn.dataset.engine;
    chrome.storage.local.set({ engine: settings.engine });
    setActive();
    setMode("web");
    $("#cmd").focus();
  });
}

/* ═══════════════════════════════════════════════════════════
   COMMAND BAR
   ═══════════════════════════════════════════════════════════ */

let cmdMode = "ask";

function setupCommandBar() {
  const cmd = $("#cmd");

  for (const btn of $$(".mode-seg button")) {
    btn.addEventListener("click", () => setMode(btn.dataset.mode));
  }

  const run = () => {
    const q = cmd.value.trim();
    if (!q) return;
    if (cmdMode === "web") {
      location.href = ENGINES[settings.engine] + encodeURIComponent(q);
    } else {
      cmd.value = "";
      setModal("ai", true);
      runAgent(q);
    }
  };

  cmd.addEventListener("keydown", (e) => {
    if (e.key === "Enter") run();
  });

  window.addEventListener("keydown", (e) => {
    if (
      e.key === "/" &&
      !["TEXTAREA", "INPUT"].includes(document.activeElement.tagName) &&
      $("#aiModal").classList.contains("closed")
    ) {
      e.preventDefault();
      $("#cmd").focus();
    }
  });
}

function setMode(mode) {
  cmdMode = mode;
  for (const b of $$(".mode-seg button")) {
    b.setAttribute("aria-selected", String(b.dataset.mode === mode));
  }
  const cmd = $("#cmd");
  cmd.placeholder =
    mode === "ask"
      ? "Give ox-alpha a task…"
      : `Search with ${ENGINE_LABELS[settings.engine]}…`;
  cmd.focus();
}

/* ═══════════════════════════════════════════════════════════
   CHAT UI
   ═══════════════════════════════════════════════════════════ */

function setupChat() {
  const form = $("#askForm");
  const prompt = $("#prompt");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = prompt.value.trim();
    if (!text || controller) return;
    prompt.value = "";
    resizePrompt();
    runAgent(text);
  });

  prompt.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  prompt.addEventListener("input", resizePrompt);

  $("#stopBtn").addEventListener("click", stopStream);

  $("#clearChat").addEventListener("click", () => {
    if (controller) stopStream();
    chatHistory = [];
    resetThread();
    toast("Conversation cleared");
  });

  bindChips($("#thread"));
}

function bindChips(root) {
  for (const chip of root.querySelectorAll(".chip")) {
    chip.addEventListener("click", () => {
      const p = $("#prompt");
      p.value = chip.dataset.fill;
      resizePrompt();
      p.focus();
    });
  }
}

function resizePrompt() {
  const p = $("#prompt");
  p.style.height = "auto";
  p.style.height = Math.min(p.scrollHeight, 120) + "px";
}

function resetThread() {
  const thread = $("#thread");
  thread.innerHTML = `
    <div class="thread-empty">
      <p>ox-alpha is an agent — it opens tabs, searches the web and reads pages to finish tasks.</p>
      <div class="chips">
        <button type="button" class="chip" data-fill="Search for the top 3 articles on JavaScript event loop and open the best one.">research + read</button>
        <button type="button" class="chip" data-fill="Find my tab with documentation and close all other duplicate tabs.">tidy tabs</button>
        <button type="button" class="chip" data-fill="Explain git rebase vs merge with a clear example.">plain question</button>
      </div>
    </div>`;
  bindChips(thread);
}

function ensureThreadStarted() {
  $(".thread-empty")?.remove();
}

function addUserMsg(text) {
  ensureThreadStarted();
  const el = document.createElement("div");
  el.className = "msg user";
  el.textContent = text;
  $("#thread").appendChild(el);
  scrollThread(true);
}

function addAiMsg() {
  ensureThreadStarted();
  const el = document.createElement("div");
  el.className = "msg ai";

  const steps = document.createElement("div");
  steps.className = "steps";
  el.appendChild(steps);

  const body = document.createElement("div");
  body.className = "msg-body";
  el.appendChild(body);

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "iconbtn msg-copy";
  copy.title = "Copy";
  copy.hidden = true;
  copy.innerHTML =
    '<svg viewBox="0 0 16 16"><rect x="5.5" y="5.5" width="8" height="8" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M10.5 5.5v-2a1.6 1.6 0 0 0-1.6-1.6H4.1a1.6 1.6 0 0 0-1.6 1.6v4.8a1.6 1.6 0 0 0 1.6 1.6h1.4" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>';
  copy.addEventListener("click", () => {
    navigator.clipboard.writeText(copy.dataset.raw || "");
    toast("Copied");
  });
  el.appendChild(copy);

  $("#thread").appendChild(el);
  scrollThread(true);
  return { el, steps, body, copy };
}

const STEP_ICONS = {
  run: '<svg viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
  done: '<svg viewBox="0 0 12 12"><path d="M2.6 6.3 4.9 8.6 9.4 3.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  fail: '<svg viewBox="0 0 12 12"><path d="M3.2 3.2l5.6 5.6M8.8 3.2 3.2 8.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
};

function addStep(ai, tool) {
  const step = document.createElement("div");
  step.className = "step running";
  let summary = "";
  try {
    summary = Object.values(JSON.parse(tool.args || "{}")).join(" ");
  } catch {}
  step.innerHTML = `<span class="si">${STEP_ICONS.run}</span><b>${escapeHtml(tool.name)}</b><span>${escapeHtml(shorten(summary, 64))}</span>`;
  ai.steps.appendChild(step);
  scrollThread(true);
  return step;
}

function endStep(step, ok) {
  step.classList.remove("running");
  step.classList.add(ok ? "done" : "fail");
  step.querySelector(".si").innerHTML = ok ? STEP_ICONS.done : STEP_ICONS.fail;
}

function paint(body, raw, streaming, copyBtn) {
  body.innerHTML = mdLite(raw) + (streaming ? '<span class="caret"></span>' : "");
  if (copyBtn && !streaming && raw) {
    copyBtn.hidden = false;
    copyBtn.dataset.raw = raw;
  }
}

function scrollThread(force) {
  const t = $("#thread");
  const nearBottom = t.scrollHeight - t.scrollTop - t.clientHeight < 90;
  if (force || nearBottom) t.scrollTop = t.scrollHeight;
}

function busy(on) {
  $("#sendBtn").hidden = on;
  $("#stopBtn").hidden = !on;
  const dot = $("#aiDot");
  dot.classList.toggle("busy", on);
  dot.classList.toggle("ok", !on && Boolean(settings.apiKey));
}

function stopStream() {
  controller?.abort();
}

/* ═══════════════════════════════════════════════════════════
   AGENT LOOP
   ═══════════════════════════════════════════════════════════ */

async function runAgent(text) {
  const key = settings.apiKey.trim();
  if (!key) {
    openSettings();
    toast("Add your OpenRouter API key first");
    return;
  }

  addUserMsg(text);
  const ai = addAiMsg();
  controller = new AbortController();
  busy(true);

  const messages = [
    { role: "system", content: AGENT_PROMPT },
    ...chatHistory,
    { role: "user", content: text },
  ];

  try {
    let finalRaw = "";

    for (let round = 0; round < MAX_ROUNDS; round++) {
      const { raw, toolCalls } = await streamTurn(messages, ai);

      if (!toolCalls.length) {
        finalRaw = raw;
        break;
      }

      if (round === MAX_ROUNDS - 1) break;

      messages.push({
        role: "assistant",
        content: raw || null,
        tool_calls: toolCalls.map((t) => ({
          id: t.id,
          type: "function",
          function: { name: t.name, arguments: t.args || "{}" },
        })),
      });

      for (const t of toolCalls) {
        const step = addStep(ai, t);
        let args = {};
        try {
          args = JSON.parse(t.args || "{}");
        } catch {}
        const result = await execTool(t.name, args);
        endStep(step, !/"error"/.test(result.slice(0, 120)));
        messages.push({
          role: "tool",
          tool_call_id: t.id,
          content: String(result).slice(0, 6000),
        });
      }
    }

    if (!finalRaw) finalRaw = "(stopped before finishing)";

    chatHistory.push({ role: "user", content: text });
    chatHistory.push({ role: "assistant", content: finalRaw });
    paint(ai.body, finalRaw, false, ai.copy);
  } catch (err) {
    if (err.name !== "AbortError") {
      ai.el.classList.add("err");
      paint(ai.body, err.message, false);
    }
  } finally {
    controller = null;
    busy(false);
    updateAiStatus();
    scrollThread(false);
  }
}

async function streamTurn(messages, ai) {
  const res = await fetch(OPENROUTER_URL, {
    method: "POST",
    signal: controller.signal,
    headers: {
      Authorization: `Bearer ${settings.apiKey.trim()}`,
      "Content-Type": "application/json",
      "X-Title": "ox-alpha",
    },
    body: JSON.stringify({
      model: settings.model,
      stream: true,
      messages,
      tools: TOOLS,
    }),
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j.error?.message || msg;
    } catch {}
    throw new Error(msg);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let raw = "";
  const tools = {};

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (payload === "[DONE]") continue;
      try {
        const json = JSON.parse(payload);
        const delta = json.choices?.[0]?.delta;
        if (!delta) continue;
        if (delta.content) {
          raw += delta.content;
          paint(ai.body, raw, true);
          scrollThread(false);
        }
        for (const tc of delta.tool_calls || []) {
          const slot = (tools[tc.index] ??= { id: "", name: "", args: "" });
          if (tc.id) slot.id = tc.id;
          if (tc.function?.name) slot.name += tc.function.name;
          if (tc.function?.arguments) slot.args += tc.function.arguments;
        }
      } catch {}
    }
  }

  return { raw, toolCalls: Object.values(tools) };
}

/* ═══════════════════════════════════════════════════════════
   TOOL EXECUTION
   ═══════════════════════════════════════════════════════════ */

async function execTool(name, args) {
  try {
    switch (name) {
      case "list_tabs": {
        const tabs = await chrome.tabs.query({});
        return JSON.stringify(
          tabs.slice(0, 25).map((t) => ({ tabId: t.id, title: t.title, url: t.url }))
        );
      }
      case "open_tab": {
        const tab = await chrome.tabs.create({ url: normUrl(args.url), active: true });
        return JSON.stringify({ ok: true, tabId: tab.id, url: tab.url });
      }
      case "focus_tab": {
        await chrome.tabs.update(Number(args.tabId), { active: true });
        return JSON.stringify({ ok: true });
      }
      case "close_tab": {
        await chrome.tabs.remove(Number(args.tabId));
        return JSON.stringify({ ok: true });
      }
      case "web_search":
        return await webSearch(String(args.query || ""));
      case "read_page":
        return await readPage(args.tabId);
      default:
        return JSON.stringify({ error: `unknown tool "${name}"` });
    }
  } catch (e) {
    return JSON.stringify({ error: e.message || String(e) });
  }
}

function normUrl(url) {
  const u = String(url || "").trim();
  if (/^https?:\/\//i.test(u)) return u;
  if (/^[\w-]+(\.[\w-]+)+/.test(u)) return "https://" + u;
  return "https://www.google.com/search?q=" + encodeURIComponent(u);
}

async function webSearch(query) {
  const res = await fetch(
    "https://html.duckduckgo.com/html/?q=" + encodeURIComponent(query)
  );
  if (!res.ok) throw new Error(`search failed (HTTP ${res.status})`);

  const doc = new DOMParser().parseFromString(await res.text(), "text/html");
  const results = [];

  for (const a of doc.querySelectorAll("a.result__a")) {
    let href = a.getAttribute("href") || "";
    const m = href.match(/uddg=([^&]+)/);
    if (m) href = decodeURIComponent(m[1]);
    const title = (a.textContent || "").trim();
    if (!title || !/^https?:/i.test(href)) continue;
    const snippet =
      a.closest(".result")?.querySelector(".result__snippet")?.textContent.trim() || "";
    results.push({ title, url: href, snippet: snippet.slice(0, 220) });
    if (results.length >= 6) break;
  }

  if (!results.length) throw new Error("no results parsed");
  return JSON.stringify(results);
}

async function readPage(tabIdArg) {
  let id = Number(tabIdArg);
  if (!Number.isFinite(id) || id <= 0) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    id = tab.id;
  }
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: id },
    func: () =>
      (document.body?.innerText || "")
        .replace(/\s{3,}/g, "\n\n")
        .slice(0, 6000),
  });
  return typeof result === "string" && result.trim()
    ? result
    : "(page had no readable text)";
}

/* ═══════════════════════════════════════════════════════════
   MARKDOWN-LITE
   ═══════════════════════════════════════════════════════════ */

function mdLite(raw) {
  return raw
    .split("```")
    .map((part, i) => {
      if (i % 2 === 1) {
        const nl = part.indexOf("\n");
        const code = nl > -1 ? part.slice(nl + 1) : part;
        return `<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`;
      }
      let html = escapeHtml(part);
      html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
      html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
      return html;
    })
    .join("");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ═══════════════════════════════════════════════════════════
   SETTINGS
   ═══════════════════════════════════════════════════════════ */

function setupSettings() {
  const panel = $("#settings");
  const select = $("#modelSelect");
  const custom = $("#modelCustom");

  for (const [id, label] of MODELS) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id === "custom" ? label : `${label} — ${id}`;
    select.appendChild(opt);
  }

  select.addEventListener("change", () => {
    custom.hidden = select.value !== "custom";
    if (!custom.hidden) custom.focus();
  });

  const syncModel = () => {
    const known = MODELS.some(([id]) => id === settings.model);
    select.value = known ? settings.model : "custom";
    custom.hidden = known;
    if (!known) custom.value = settings.model;
  };

  $("#openSettings").addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      $("#keyInput").value = settings.apiKey;
      syncModel();
      $("#keyInput").focus();
    }
  });

  $("#aiStatus").addEventListener("click", () => {
    setModal("ai", true);
    setTimeout(() => $("#openSettings").click(), 60);
  });

  $("#saveSettings").addEventListener("click", () => {
    settings.apiKey = $("#keyInput").value.trim();
    settings.model =
      select.value === "custom"
        ? custom.value.trim() || DEFAULT_MODEL
        : select.value;
    chrome.storage.local.set(
      { apiKey: settings.apiKey, model: settings.model },
      () => {
        panel.hidden = true;
        updateAiStatus();
        toast(settings.apiKey ? "Saved — ox-alpha ready" : "Saved — no key set");
      }
    );
  });

  document.addEventListener("mousedown", (e) => {
    if (
      !panel.hidden &&
      !panel.contains(e.target) &&
      !e.target.closest("#openSettings") &&
      !e.target.closest("#aiStatus")
    ) {
      panel.hidden = true;
    }
  });
}

function openSettings() {
  setModal("ai", true);
  if ($("#settings").hidden) $("#openSettings").click();
}

function updateAiStatus() {
  const has = Boolean(settings.apiKey);
  $("#aiDot").className = `dot ${has ? "ok" : "warn"}`;
  $("#aiStatusText").textContent = has ? shortModel(settings.model) : "set key";
}

function shortModel(m) {
  const tail = m.split("/").pop() || m;
  return tail.length > 22 ? tail.slice(0, 20) + "…" : tail;
}

/* ═══════════════════════════════════════════════════════════
   SCRATCHPAD
   ═══════════════════════════════════════════════════════════ */

async function setupNotes() {
  const notes = $("#notes");
  const hint = $("#savedHint");
  const saved = await chrome.storage.local.get({ notes: "" });
  notes.value = saved.notes;

  notes.addEventListener("input", () => {
    clearTimeout(notesTimer);
    notesTimer = setTimeout(() => {
      chrome.storage.local.set({ notes: notes.value }, () => {
        hint.textContent = "saved";
        hint.classList.add("show");
        setTimeout(() => hint.classList.remove("show"), 1200);
      });
    }, 500);
  });
}

/* ═══════════════════════════════════════════════════════════
   CURSOR GLOW
   ═══════════════════════════════════════════════════════════ */

function setupCursorGlow() {
  const glow = $(".glow-a");
  if (!glow || matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  let tx = innerWidth * 0.5;
  let ty = innerHeight * 0.25;
  let cx = tx;
  let cy = ty;

  window.addEventListener(
    "pointermove",
    (e) => {
      tx = e.clientX;
      ty = e.clientY;
    },
    { passive: true }
  );

  const loop = () => {
    cx += (tx - cx) * 0.055;
    cy += (ty - cy) * 0.055;
    glow.style.transform = `translate(${Math.round(cx - 360)}px, ${Math.round(
      cy - 210
    )}px)`;
    requestAnimationFrame(loop);
  };

  loop();
}

/* ═══════════════════════════════════════════════════════════
   CALENDAR
   ═══════════════════════════════════════════════════════════ */

function renderCalendar() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();

  $("#calTitle").textContent = now.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  const cal = $("#cal");
  cal.className = "cal";
  const grid = document.createElement("div");
  grid.className = "cal-grid";

  for (const dow of ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]) {
    const c = document.createElement("span");
    c.className = "cal-dow";
    c.textContent = dow;
    grid.appendChild(c);
  }

  const offset = (new Date(y, m, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const daysPrev = new Date(y, m, 0).getDate();
  const total = Math.ceil((offset + daysInMonth) / 7) * 7;

  const addCell = (label, cls) => {
    const c = document.createElement("span");
    c.className = `cal-day${cls ? " " + cls : ""}`;
    c.textContent = label;
    grid.appendChild(c);
  };

  for (let i = offset - 1; i >= 0; i--) addCell(daysPrev - i, "out");
  for (let d = 1; d <= daysInMonth; d++) addCell(d, d === now.getDate() ? "today" : "");
  for (let d = 1; grid.children.length - 7 < total && d <= 14; d++) addCell(d, "out");

  cal.appendChild(grid);
}

/* ═══════════════════════════════════════════════════════════
   EXTENSIONS
   ═══════════════════════════════════════════════════════════ */

function setupExtensions() {
  const SELF_ID = chrome.runtime.id;
  chrome.management.getAll((items) => {
    exts = items.filter((e) => e.type !== "theme" && e.id !== SELF_ID);
    renderExts();
  });
}

function byState(a, b) {
  if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
  return a.name.localeCompare(b.name);
}

function renderExts() {
  const grid = $("#extGrid");
  grid.replaceChildren();
  const items = exts.slice().sort(byState);
  items.forEach((ext, i) => grid.appendChild(buildExtRow(ext, i)));
  $("#extCount").textContent = items.length
    ? `· ${items.filter((e) => e.enabled).length}/${items.length} on`
    : "";

  if (!items.length) {
    const p = document.createElement("li");
    p.className = "empty";
    p.textContent = "No extensions found";
    grid.appendChild(p);
  }

  chrome.tabs.query({}, (tabs) => {
    $("#statTabs").textContent = String(tabs.length);
    $("#statTabs").dataset.value = String(tabs.length);
    $("#tbTabs").textContent = String(tabs.length);
  });

  const on = items.filter((e) => e.enabled).length;
  $("#statExts").textContent = String(on);

  if (telemetry.ready) {
    renderDonuts({
      tabsCount: Number($("#statTabs").dataset.value || 0),
      exts,
      visitsToday: telemetry.visitsToday,
      visitsWeek: telemetry.visitsWeek,
    });
  }
}

function buildExtRow(ext, index) {
  const row = $("#ext-template").content.firstElementChild.cloneNode(true);
  row.style.setProperty("--i", Math.min(index, 14));
  row.dataset.id = ext.id;
  row.toggleAttribute("data-off", !ext.enabled);

  const iconHost = row.querySelector(".row-icon");
  let best = null;
  for (const icon of ext.icons || []) {
    if (!best || Math.abs(icon.size - 32) < Math.abs(best.size - 32)) best = icon;
  }
  if (best) {
    iconHost.src = best.url;
  } else {
    const tile = document.createElement("span");
    tile.className = "row-icon tile";
    tile.textContent = ext.name.trim().charAt(0).toUpperCase() || "?";
    iconHost.replaceWith(tile);
  }

  row.querySelector(".row-name").textContent = ext.name;
  row.querySelector(".row-version").textContent = `v${ext.version}`;

  const meta = row.querySelector(".row-meta");
  const tag = document.createElement("span");
  if (!ext.mayDisable) {
    tag.className = "row-tag";
    tag.textContent = "locked";
  } else if (ext.installType === "development") {
    tag.className = "row-tag dev";
    tag.textContent = "dev";
  } else if (!ext.enabled) {
    tag.className = "row-tag state-off";
    tag.textContent = "off";
  }
  if (tag.className) meta.appendChild(tag);

  const optionsBtn = row.querySelector(".row-options");
  optionsBtn.hidden = !ext.optionsUrl;
  optionsBtn.addEventListener("click", () =>
    chrome.tabs.create({ url: ext.optionsUrl })
  );

  const uninstallBtn = row.querySelector(".row-uninstall");
  uninstallBtn.hidden = !ext.mayDisable;
  uninstallBtn.addEventListener("click", () => uninstallExt(row, ext, uninstallBtn));

  const toggle = row.querySelector(".switch");
  toggle.disabled = !ext.mayDisable;
  toggle.setAttribute("aria-checked", String(ext.enabled));
  toggle.addEventListener("click", () => toggleExt(toggle, ext));

  return row;
}

function toggleExt(toggle, ext) {
  const next = toggle.getAttribute("aria-checked") !== "true";
  const row = toggle.closest(".row");
  toggle.setAttribute("aria-checked", String(next));
  row.toggleAttribute("data-off", !next);

  chrome.management.setEnabled(ext.id, next, () => {
    if (chrome.runtime.lastError) {
      toggle.setAttribute("aria-checked", String(!next));
      row.toggleAttribute("data-off", next);
      toast(chrome.runtime.lastError.message);
      return;
    }
    ext.enabled = next;
    renderExts();
    toast(`${ext.name} ${next ? "enabled" : "disabled"}`);
  });
}

function uninstallExt(row, ext, btn) {
  if (btn.dataset.armed) {
    chrome.management.uninstall(
      ext.id,
      { showConfirmDialog: true },
      () => {
        if (chrome.runtime.lastError) toast(chrome.runtime.lastError.message);
        else {
          exts = exts.filter((e) => e.id !== ext.id);
          renderExts();
          toast(`${ext.name} removed`);
        }
      }
    );
    return;
  }
  btn.dataset.armed = "1";
  btn.title = "Click again to confirm";
  row.classList.add("armed");
  setTimeout(() => {
    delete btn.dataset.armed;
    btn.title = "Uninstall";
    row.classList.remove("armed");
  }, 2200);
}

/* ═══════════════════════════════════════════════════════════
   RECENT ACTIVITY
   ═══════════════════════════════════════════════════════════ */

function setupRecent() {
  const list = $("#recent");

  if (!chrome.history?.search) {
    const empty = document.createElement("li");
    empty.className = "recent-empty";
    empty.textContent = "History unavailable — reload the extension to grant permission";
    list.appendChild(empty);
    return;
  }

  chrome.history.search(
    { text: "", maxResults: 60, startTime: Date.now() - 48 * 3600 * 1000 },
    (items) => {
      const seenHosts = new Set();
      let shown = 0;

      for (const item of items) {
        if (!/^https?:\/\//i.test(item.url || "")) continue;
        let host;
        try {
          host = new URL(item.url).hostname.replace(/^www\./, "");
        } catch {
          continue;
        }
        if (seenHosts.has(host)) continue;
        seenHosts.add(host);

        const li = document.createElement("li");
        const a = document.createElement("a");
        a.className = "recent-item";
        a.href = item.url;
        a.target = "_blank";
        a.rel = "noreferrer";
        a.title = item.title || item.url;

        const img = document.createElement("img");
        img.src = `https://www.google.com/s2/favicons?domain=${host}&sz=32`;
        img.alt = "";
        img.loading = "lazy";

        const title = document.createElement("span");
        title.className = "recent-title";
        title.textContent = item.title || host;

        const hostEl = document.createElement("span");
        hostEl.className = "recent-host";
        hostEl.textContent = host;

        const time = document.createElement("span");
        time.className = "recent-time";
        time.textContent = ago(item.lastVisitTime);

        a.append(img, title, hostEl, time);
        li.appendChild(a);
        list.appendChild(li);

        if (++shown >= 10) break;
      }

      if (!shown) {
        const empty = document.createElement("li");
        empty.className = "recent-empty";
        empty.textContent = "No recent activity yet";
        list.appendChild(empty);
      }
    }
  );

  function ago(ts) {
    if (!ts) return "";
    const mins = Math.max(1, Math.round((Date.now() - ts) / 60000));
    if (mins < 60) return `${mins}m`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.round(hours / 24)}d`;
  }
}

/* ═══════════════════════════════════════════════════════════
   TOAST
   ═══════════════════════════════════════════════════════════ */

function toast(msg) {
  let el = $(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 1800);
}
