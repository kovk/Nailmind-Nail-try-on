const state = {
  token: localStorage.getItem("nailmind_admin_token") || "",
  user: null,
  activeView: "",
  styles: [],
  selectedStyleId: "",
  creatingStyle: false,
  trendCollect: null,
  trendsData: null,
  xhsStatus: null,
};

const authScreen = document.getElementById("auth-screen");
const workspace = document.getElementById("workspace");
const loginForm = document.getElementById("login-form");
const authError = document.getElementById("auth-error");
const tabs = document.getElementById("tabs");
const view = document.getElementById("view");
const sidebarNav = document.getElementById("sidebar-nav");
const refreshViewButton = document.getElementById("refresh-view");
const topbarDetailButton = document.getElementById("topbar-detail");

const roleLayouts = {
  platform_admin: {
    title: "运营工作台",
    subtitle: "面向用户增长、款式转化和门店履约的 ToC 运营后台。",
    note: "首页看运营结论，详情页处理款式、趋势、商家申请和行为明细；不展示技术枚举和测试数据。",
    views: [
      { id: "overview", label: "用户看板", kicker: "运营看板", title: "用户增长与款式转化", description: "用真实曝光、点击、试戴与预约埋点生成运营结论；明细只在下钻页展示。" },
      { id: "quality", label: "试戴质检", kicker: "质检台", title: "AI 试戴质量复核", description: "查看用户手图、款式图和生成图，使用 qwen3.7-plus 初评，运营可人工改分保存。" },
      { id: "styles", label: "款式运营", kicker: "款式库", title: "款式资产与上下架", description: "编辑款式名称、风格、标签、上下架状态和图片资产。" },
      { id: "requests", label: "商家审核", kicker: "审核台", title: "商家申请审批", description: "处理门店提交的上架、下架申请，并同步到真实库存状态。" },
      { id: "trends", label: "趋势洞察", kicker: "趋势", title: "社区趋势与站内热度", description: "结合小红书热帖、站内真实热款和 OpenClaw 建议，判断上新与加推方向。" },
    ],
  },
  merchant_admin: {
    title: "商家工作台",
    subtitle: "只处理门店商品、预约履约、上架申请和营业时间。",
    note: "商家端不展示运营分析或社区趋势，只保留门店经营所需的数据和操作。",
    views: [
      { id: "goods", label: "商品信息", kicker: "Merchant", title: "门店商品与库存", description: "查看当前门店可售款式、库存状态与展示图片，不展示运营侧趋势信息。" },
      { id: "bookings", label: "预约信息", kicker: "Bookings", title: "预约履约", description: "查看真实预约记录、用户姓名、到店时段和当前履约状态。" },
      { id: "requests", label: "商家申请", kicker: "申请", title: "上架与下架申请", description: "向平台运营提交款式上架或下架申请，并保留历史审批记录。" },
      { id: "store", label: "门店设置", kicker: "Store", title: "门店档期与营业状态", description: "调整门店可预约时段和是否接单，前台预约入口会直接读取这里的真实状态。" },
    ],
  },
  merchant_staff: {
    title: "商家工作台",
    subtitle: "只处理门店商品、预约履约、上架申请和营业时间。",
    note: "商家端不展示运营分析或社区趋势，只保留门店经营所需的数据和操作。",
    views: [
      { id: "goods", label: "商品信息", kicker: "Merchant", title: "门店商品与库存", description: "查看当前门店可售款式、库存状态与展示图片，不展示运营侧趋势信息。" },
      { id: "bookings", label: "预约信息", kicker: "Bookings", title: "预约履约", description: "查看真实预约记录、用户姓名、到店时段和当前履约状态。" },
      { id: "requests", label: "商家申请", kicker: "申请", title: "上架与下架申请", description: "向平台运营提交款式上架或下架申请，并保留历史审批记录。" },
      { id: "store", label: "门店设置", kicker: "Store", title: "门店档期与营业状态", description: "调整门店可预约时段和是否接单，前台预约入口会直接读取这里的真实状态。" },
    ],
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDateTime(value) {
  if (!value) return "暂无";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function roleLabel(role) {
  if (role === "platform_admin") return "运营管理员";
  if (role === "merchant_admin") return "商家管理员";
  return "门店成员";
}

function humanizeHealthLabel(value) {
  if (value === "insufficient_distribution") return "曝光不足";
  if (value === "optimize_candidate") return "有兴趣未转化";
  if (value === "delist_candidate") return "低效曝光";
  if (value === "healthy") return "表现稳定";
  if (value === "insufficient_data") return "数据待积累";
  return value || "待观察";
}

function healthActionText(value) {
  if (value === "insufficient_distribution") return "建议先加曝光：放到首页推荐、热门位或活动位测试。";
  if (value === "optimize_candidate") return "建议先优化转化：补试戴图、改标题卖点或强化预约入口。";
  if (value === "delist_candidate") return "建议减少资源：点击率偏低，可降权观察或准备下架。";
  if (value === "healthy") return "建议保持投放：继续曝光，并观察预约承接。";
  return "继续积累真实用户行为后再判断。";
}

function currentLayout() {
  return roleLayouts[state.user?.role] || roleLayouts.merchant_admin;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    let message = text || `Request failed: ${res.status}`;
    try {
      const payload = JSON.parse(text);
      message = payload.detail || payload.message || message;
    } catch {
      // Keep raw response text when the server did not return JSON.
    }
    throw new Error(message);
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}

function setAuthError(message = "") {
  authError.textContent = message;
  authError.classList.toggle("hidden", !message);
}

function showWorkspace(user) {
  state.user = user;
  const layout = currentLayout();
  authScreen.classList.add("hidden");
  workspace.classList.remove("hidden");
  document.getElementById("workspace-title").textContent = layout.title;
  document.getElementById("workspace-subtitle").textContent = layout.subtitle;
  document.getElementById("role-note").textContent = layout.note;
  document.getElementById("user-name").textContent = user.name;
  document.getElementById("user-meta").textContent = user.email;
  document.getElementById("role-chip").textContent = roleLabel(user.role);
  document.getElementById("topbar-user-name").textContent = user.name;
  document.getElementById("topbar-user-role").textContent = roleLabel(user.role);
  renderTabs();
}

function emptyState(title, message) {
  return `
    <article class="surface surface-block empty-state">
      <h3>${escapeHtml(title)}</h3>
      <p class="lead compact">${escapeHtml(message)}</p>
    </article>
  `;
}

function imageOrFallback(url, alt) {
  if (!url) {
    return `<div class="style-thumb"></div>`;
  }
  return `<img class="style-thumb" src="${escapeHtml(url)}" alt="" data-image-label="${escapeHtml(alt)}" loading="lazy" referrerpolicy="no-referrer" />`;
}

function statusPill(label, stateValue) {
  return `<span class="status-pill" data-state="${escapeHtml(stateValue)}">${escapeHtml(label)}</span>`;
}

function renderTrendCollectStatus() {
  const collect = state.trendCollect;
  if (!collect) return "";
  const statusText = {
    crawling: "正在通过账号矩阵爬取小红书高赞帖子，OpenClaw 将在爬取完成后开始分析。",
    analyzing: "帖子已爬取完成，OpenClaw 正在生成运营建议。",
    done: `本轮完成：采集 ${collect.posts?.length || 0} 篇帖子，生成 ${collect.recommendationsCreated || 0} 条建议。`,
    failed: collect.message || "采集失败，请检查账号矩阵登录态或稍后重试。",
  }[collect.status] || "";
  const stateName = collect.status === "failed" ? "rejected" : collect.status === "done" ? "approved" : "pending";
  return `
    <article class="surface surface-block trend-progress-card">
      <div class="style-card-head">
        <div>
          <p class="eyebrow">采集进度</p>
          <h3>${escapeHtml(collect.title || "小红书数据抓取")}</h3>
        </div>
        ${statusPill(collect.status === "done" ? "已完成" : collect.status === "failed" ? "失败" : "进行中", stateName)}
      </div>
      <p class="lead compact">${escapeHtml(statusText)}</p>
      ${
        collect.status !== "done" && collect.status !== "failed"
          ? `<div class="progress-rail"><span></span></div>`
          : ""
      }
    </article>
  `;
}

function renderXhsCollectionHealth() {
  const health = state.xhsStatus;
  if (!health) return "";
  const statusMap = {
    healthy: ["数据源可用", "approved"],
    expired: ["数据源失效", "rejected"],
    missing_cookie: ["数据源待维护", "rejected"],
    missing_spider: ["Spider_XHS 未就绪", "rejected"],
    spider_import_failed: ["Spider_XHS 加载失败", "rejected"],
    unavailable: ["采集服务不可用", "rejected"],
    unhealthy: ["数据源异常", "rejected"],
  };
  const [label, stateName] = statusMap[health.status] || ["待检查", "pending"];
  const checks = [
    ["采集服务", health.accountMatrixReachable ? "已连接" : "不可用", health.accountMatrixReachable],
    ["数据源", health.accountId ? "已配置" : "待维护", Boolean(health.accountId)],
    ["凭证", health.hasCookie ? "已配置" : "待维护", health.hasCookie],
    ["Spider_XHS", health.spiderReady ? "可调用" : "不可用", health.spiderReady],
  ];
  return `
    <article class="surface surface-block xhs-health-card">
      <div class="style-card-head">
        <div>
          <p class="eyebrow">采集状态</p>
          <h3>小红书采集状态</h3>
        </div>
        ${statusPill(label, stateName)}
      </div>
      <p class="lead compact">${escapeHtml(health.message || "等待后台采集源状态检查。")}</p>
      <div class="health-check-grid">
        ${checks
          .map(
            ([name, value, ok]) => `
              <span class="health-check" data-state="${ok ? "ok" : "bad"}">
                <strong>${escapeHtml(name)}</strong>
                ${escapeHtml(value)}
              </span>
            `,
          )
          .join("")}
      </div>
      <a class="action-link secondary-button" href="/xhs-account/platforms/xhs/accounts" target="_blank" rel="noreferrer">
        打开小红书采集控制台
      </a>
    </article>
  `;
}

function renderCollectedPosts(posts = []) {
  if (!posts.length) return "";
  return `
    <section class="surface surface-block">
      <div class="section-head">
        <div>
          <p class="eyebrow">已采集帖子</p>
          <h3>本轮爬取帖子</h3>
        </div>
        <span class="muted">按点赞数从高到低</span>
      </div>
      <div class="collected-post-list">
        ${posts
          .map(
            (post) => `
              <article class="collected-post-row">
                ${imageOrFallback(post.imageUrl, post.title || "小红书帖子")}
                <div>
                  <h4>${escapeHtml(post.title || "未命名帖子")}</h4>
                  <p class="muted">${escapeHtml(post.author || "-")}</p>
                  <a class="action-link" href="${escapeHtml(post.url || "#")}" target="_blank" rel="noreferrer">查看原帖</a>
                </div>
                <div class="stats-row">
                  <span class="stat-chip">赞 ${escapeHtml(post.likeCount || 0)}</span>
                  <span class="stat-chip">藏 ${escapeHtml(post.collectCount || 0)}</span>
                  <span class="stat-chip">评 ${escapeHtml(post.commentCount || 0)}</span>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderTabs() {
  const layout = currentLayout();
  tabs.innerHTML = layout.views
    .map(
      (item) => `
        <button class="tab-button ${state.activeView === item.id ? "is-active" : ""}" data-view="${item.id}" type="button">
          ${escapeHtml(item.label)}
        </button>
      `,
    )
    .join("");
  sidebarNav.innerHTML = layout.views
    .map(
      (item) => `
        <button class="sidebar-link ${state.activeView === item.id ? "is-active" : ""}" data-view="${item.id}" type="button">
          <span class="sidebar-link-mark"></span>
          <span>${escapeHtml(item.label)}</span>
        </button>
      `,
    )
    .join("");
}

function syncPageMeta() {
  const layout = currentLayout();
  const active = layout.views.find((item) => item.id === state.activeView) || layout.views[0];
  document.getElementById("page-kicker").textContent = active.kicker;
  document.getElementById("page-title").textContent = active.title;
  document.getElementById("page-description").textContent = active.description;
  document.getElementById("topbar-range").textContent = state.user?.role === "platform_admin" ? "近 7 天 (06/23 - 06/29)" : "实时工作台";
  topbarDetailButton.classList.toggle("hidden", active.id !== "overview");
  renderTabs();
}

async function login(email, password) {
  const data = await api("/admin/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  state.token = data.token;
  localStorage.setItem("nailmind_admin_token", state.token);
  showWorkspace(data.user);
  await setView(currentLayout().views[0].id);
}

function normalizeCommaList(value) {
  return value
    .split(/[，,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatPercent(value) {
  const numeric = Number(value || 0);
  return `${(numeric * 100).toFixed(1)}%`;
}

function formatDurationMetric(metric) {
  if (!metric || metric.averageMs === null || metric.averageMs === undefined) return "待积累";
  const seconds = metric.averageMs / 1000;
  return `${seconds.toFixed(1)}s`;
}

function formatDurationCi(metric) {
  if (!metric || metric.averageMs === null || metric.averageMs === undefined) return "暂无有效试戴耗时样本";
  const lower = Number(metric.ciLowerMs || metric.averageMs) / 1000;
  const upper = Number(metric.ciUpperMs || metric.averageMs) / 1000;
  return `99% CI ${lower.toFixed(1)}s - ${upper.toFixed(1)}s，样本 ${metric.sampleSize}`;
}

function formatScoreMetric(metric) {
  if (!metric || metric.score === null || metric.score === undefined) return "待评测";
  return `${(Number(metric.score) * 100).toFixed(1)}分`;
}

function eventBusinessMeta(eventName) {
  const map = {
    style_impression: ["款式曝光", "用户在列表、首页或推荐位看到了这款美甲。", "曝光"],
    style_click: ["查看款式详情", "用户点击进入款式详情，说明图片或标题产生了兴趣。", "兴趣"],
    style_favorite: ["收藏款式", "用户把款式加入收藏，后续可能再次试戴或预约。", "留存"],
    search_submit: ["提交搜索", "用户主动搜索款式、风格或门店关键词。", "搜索"],
    tryon_source_select: ["选择试戴入口", "用户选择从热门、收藏、推荐或上传入口开始试戴。", "试戴"],
    tryon_start: ["开始 AI 试戴", "用户已发起试戴请求，进入生成链路。", "试戴"],
    tryon_complete: ["AI 试戴完成", "系统已经生成试戴结果，可用于计算生成耗时和完成率。", "完成"],
    booking_create: ["提交预约", "用户从款式或试戴结果进入预约，形成转化。", "转化"],
    booking_confirm: ["确认到店预约", "门店确认预约，表示预约进入履约阶段。", "履约"],
    tryon_quality_eval: ["试戴质量评测", "人工或模型对试戴结果进行了质量打分。", "质检"],
    tryon_manual_eval: ["人工质量评测", "人工评估款式还原度和手部一致性。", "质检"],
    tryon_model_eval: ["模型质量评测", "模型评估试戴效果是否可用于展示。", "质检"],
  };
  return map[eventName] || [eventName || "未知事件", "系统记录了一条真实业务行为。", "事件"];
}

function eventObjectLabel(item) {
  const parts = [];
  if (item.styleName) parts.push(`款式 ${item.styleName}`);
  else if (item.styleId) parts.push("款式名称待同步");
  if (item.storeId) parts.push(`门店 ${item.storeId}`);
  if (item.userId) parts.push(`用户 #${item.userId}`);
  return parts.length ? parts.join(" · ") : "未绑定具体款式";
}

function sourcePageLabel(value) {
  const map = {
    home: "首页",
    styles: "款式列表",
    style_detail: "款式详情",
    favorites: "收藏页",
    tryon: "AI 试戴页",
    tryon_upload: "上传手图页",
    tryon_async: "后台试戴任务",
    tryon_worker: "后台生成任务",
    booking: "预约页",
    booking_detail: "预约详情",
    styles_search: "搜索结果",
  };
  return map[value] || value || "-";
}

function renderDashboardFunnel(data) {
  const steps = [
    ["曝光", data.funnel.impressions, "用户看到款式"],
    ["点击", data.funnel.clicks, "进入详情"],
    ["试戴", data.funnel.tryonStarts, "发起 AI 试戴"],
    ["预约", data.funnel.bookingCreates, "提交到店预约"],
  ];
  const maxValue = Math.max(...steps.map(([, value]) => Number(value || 0)), 1);
  return steps
    .map(([label, value, hint], index) => {
      const width = Math.round((Number(value || 0) / maxValue) * 100);
      const rate =
        index === 0
          ? data.rates.clickThroughRate
          : index === 1
            ? data.rates.tryonStartRate
            : index === 2
              ? data.rates.bookingConversionRate
              : null;
      return `
        <div class="funnel-step">
          <div class="funnel-meta">
            <strong>${escapeHtml(label)}</strong>
            <span>${escapeHtml(hint)}</span>
          </div>
          <div class="funnel-bar"><span style="width: ${width}%"></span></div>
          <b>${escapeHtml(value)}</b>
          ${rate === null ? "<small>最终转化</small>" : `<small>${formatPercent(rate)}</small>`}
        </div>
      `;
    })
    .join("");
}

function renderStyleHealthDistribution(items = []) {
  const groups = items.reduce((acc, item) => {
    const label = humanizeHealthLabel(item.healthLabel);
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {});
  const entries = Object.entries(groups);
  if (!entries.length) return `<p class="metric-label">暂无款式表现数据。</p>`;
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  return entries
    .map(([label, count]) => `
      <div class="distribution-row">
        <span>${escapeHtml(label)}</span>
        <div class="distribution-bar"><span style="width: ${Math.round((count / total) * 100)}%"></span></div>
        <b>${count}</b>
      </div>
    `)
    .join("");
}

function requestSummary(items = []) {
  const now = new Date();
  const todayKey = now.toISOString().slice(0, 10);
  let pending = 0;
  let today = 0;
  let risk = 0;
  for (const item of items) {
    if (item.status === "pending") pending += 1;
    const createdAt = item.createdAt ? new Date(item.createdAt) : null;
    if (createdAt && !Number.isNaN(createdAt.getTime()) && createdAt.toISOString().slice(0, 10) === todayKey) {
      today += 1;
    }
    if ((item.reason || "").includes("紧急") || (item.reason || "").includes("投诉") || (item.requestedAction || "") === "delist") {
      risk += 1;
    }
  }
  return { pending, today, risk };
}

function overviewActionLabel(item) {
  if (item.healthLabel === "insufficient_distribution") return "提升曝光";
  if (item.healthLabel === "optimize_candidate") return "优化转化";
  if (item.healthLabel === "delist_candidate") return "降权观察";
  if (item.healthLabel === "healthy") return "继续加推";
  return "进入运营";
}

function metricIcon(label) {
  if (label === "曝光") return "◉";
  if (label === "点击") return "↗";
  if (label === "试戴开始") return "✦";
  if (label === "预约转化") return "⌂";
  return "•";
}

function metricScorePercent(metric) {
  if (!metric || metric.score === null || metric.score === undefined) return null;
  return Math.max(0, Math.min(100, Math.round(Number(metric.score) * 100)));
}

function renderTryonExperienceChart(quality) {
  const duration = quality.averageDuration || {};
  const averageSeconds = duration.averageMs === null || duration.averageMs === undefined ? null : Number(duration.averageMs) / 1000;
  const durationTargetSeconds = 10;
  const durationPercent = averageSeconds === null ? 0 : Math.max(6, Math.min(100, Math.round((averageSeconds / durationTargetSeconds) * 100)));
  const durationState = averageSeconds === null ? "待积累" : averageSeconds <= durationTargetSeconds ? "流畅" : "偏慢";
  const styleScore = metricScorePercent(quality.styleFidelity);
  const consistencyScore = metricScorePercent(quality.manualConsistency);
  const scoreRows = [
    ["款式还原度", styleScore, quality.styleFidelity?.sampleSize || 0],
    ["手部一致性", consistencyScore, quality.manualConsistency?.sampleSize || 0],
  ];
  return `
    <div class="tryon-dashboard">
      <div class="tryon-speed-card">
        <div>
          <span>平均生成耗时</span>
          <strong>${formatDurationMetric(duration)}</strong>
          <small>${escapeHtml(formatDurationCi(duration))}</small>
        </div>
        <b data-state="${averageSeconds !== null && averageSeconds <= durationTargetSeconds ? "ok" : "warn"}">${durationState}</b>
      </div>
      <div class="tryon-duration-bar">
        <span style="width: ${durationPercent}%"></span>
      </div>
      <div class="tryon-target-row">
        <span>0s</span>
        <strong>生成耗时参考线</strong>
        <span>偏慢</span>
      </div>
      <div class="tryon-score-list">
        ${scoreRows
          .map(
            ([label, score, sample]) => `
              <div class="tryon-score-row">
                <div class="funnel-meta">
                  <strong>${escapeHtml(label)}</strong>
                  <span>${sample ? `样本 ${sample}` : "待评测"}</span>
                </div>
                <div class="distribution-bar"><span style="width: ${score === null ? 0 : score}%"></span></div>
                <b>${score === null ? "待评测" : `${score}分`}</b>
              </div>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderOverview(data) {
  const quality = data.tryonQuality || {};
  const privacy = quality.privacyPolicy || {};
  const requestMeta = requestSummary(data.pendingRequests || []);
  view.innerHTML = `
    <section class="metrics-grid metrics-grid-dashboard">
      <article class="surface surface-block metric-card">
        <div class="metric-head">
          <span class="metric-icon">${metricIcon("曝光")}</span>
          <div class="metric-title-group">
            <p class="eyebrow">曝光</p>
            <span class="metric-trend">真实流量</span>
          </div>
        </div>
        <div class="metric-value">${data.funnel.impressions}</div>
        <p class="metric-label">点击率 ${formatPercent(data.rates.clickThroughRate)}</p>
        <p class="metric-subtext">用户看到款式</p>
      </article>
      <article class="surface surface-block metric-card">
        <div class="metric-head">
          <span class="metric-icon">${metricIcon("点击")}</span>
          <div class="metric-title-group">
            <p class="eyebrow">点击</p>
            <span class="metric-trend">兴趣触发</span>
          </div>
        </div>
        <div class="metric-value">${data.funnel.clicks}</div>
        <p class="metric-label">最近 ${data.windowDays} 天真实点击事件</p>
        <p class="metric-subtext">进入详情</p>
      </article>
      <article class="surface surface-block metric-card">
        <div class="metric-head">
          <span class="metric-icon">${metricIcon("试戴开始")}</span>
          <div class="metric-title-group">
            <p class="eyebrow">试戴开始</p>
            <span class="metric-trend">进入生成</span>
          </div>
        </div>
        <div class="metric-value">${data.funnel.tryonStarts}</div>
        <p class="metric-label">完成率 ${formatPercent(data.rates.tryonCompleteRate)}</p>
        <p class="metric-subtext">开始 AI 试戴</p>
      </article>
      <article class="surface surface-block metric-card">
        <div class="metric-head">
          <span class="metric-icon">${metricIcon("预约转化")}</span>
          <div class="metric-title-group">
            <p class="eyebrow">预约转化</p>
            <span class="metric-trend">到店意向</span>
          </div>
        </div>
        <div class="metric-value">${data.funnel.bookingCreates}</div>
        <p class="metric-label">预约转化率 ${formatPercent(data.rates.bookingConversionRate)}</p>
        <p class="metric-subtext">提交到店预约</p>
      </article>
    </section>

    <section class="dashboard-grid overview-dashboard-grid">
      <article class="surface surface-block dashboard-panel wide-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow">用户链路</p>
            <h3>用户转化漏斗</h3>
          </div>
          <button class="secondary-button" type="button" data-open-events>查看行为明细</button>
        </div>
        <div class="funnel-chart">${renderDashboardFunnel(data)}</div>
      </article>

      <article class="surface surface-block dashboard-panel tryon-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow">试戴质检</p>
            <h3>AI 试戴质检</h3>
          </div>
          <span class="status-pill" data-state="${metricScorePercent(quality.styleFidelity) >= 85 ? "approved" : "pending"}">${formatDurationMetric(quality.averageDuration) === "待积累" ? "待积累" : Number((quality.averageDuration?.averageMs || 0) / 1000) <= 10 ? "流畅" : "偏慢"}</span>
        </div>
        ${renderTryonExperienceChart(quality)}
        <p class="metric-label">还原度和一致性来自人工评测或模型评估事件，没有样本时不补虚假分数。</p>
      </article>
    </section>

    <section class="overview-lower-grid">
      <article class="surface surface-block overview-table-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow">款式运营</p>
            <h3>款式动作建议</h3>
          </div>
        </div>
        <div class="overview-table">
          <div class="overview-table-head">
            <span>款式名称</span>
            <span>当前问题</span>
            <span>曝光</span>
            <span>点击</span>
            <span>综合分</span>
            <span>建议动作</span>
            <span>操作</span>
          </div>
          ${
            data.styleSnapshots.length
              ? data.styleSnapshots
                  .map(
                    (item) => `
                      <div class="overview-table-row">
                        <div class="overview-cell title-cell">
                          <strong>${escapeHtml(item.styleName)}</strong>
                        </div>
                        <div class="overview-cell">${statusPill(humanizeHealthLabel(item.healthLabel), item.healthLabel)}</div>
                        <div class="overview-cell">${item.impressions}</div>
                        <div class="overview-cell">${item.clicks}</div>
                        <div class="overview-cell">${item.compositeRecommendationScore}</div>
                        <div class="overview-cell cell-note">${escapeHtml(healthActionText(item.healthLabel))}</div>
                        <div class="overview-cell">
                          <button class="primary-button table-action-button" type="button" data-open-style="${escapeHtml(item.styleId)}">${escapeHtml(overviewActionLabel(item))}</button>
                        </div>
                      </div>
                    `,
                  )
                  .join("")
              : emptyState("暂无款式快照", "当款式和埋点数据积累后，这里会自动展示真实表现。")
          }
        </div>
      </article>

      <div class="overview-side-stack">
        <article class="surface surface-block">
          <div class="section-head">
            <div>
              <p class="eyebrow">款式结构</p>
              <h3>款式健康分布</h3>
            </div>
          </div>
          <div class="distribution-list">
            ${renderStyleHealthDistribution(data.styleSnapshots)}
          </div>
          <div class="distribution-footer">
            <strong>共 ${data.styleSnapshots.length} 款式</strong>
            <button class="link-button" type="button" data-open-style-list>查看全部</button>
          </div>
        </article>

        <article class="surface surface-block side-combo-panel">
          <div class="mini-section">
            <div class="section-head compact-head">
              <div>
                <p class="eyebrow">商家审核</p>
                <h3>待处理申请</h3>
              </div>
              <button class="secondary-button compact-button" type="button" data-open-requests>进入审核</button>
            </div>
            <div class="mini-stats-grid">
              <div class="mini-stat">
                <strong>${requestMeta.pending}</strong>
                <span>待审核商家</span>
              </div>
              <div class="mini-stat">
                <strong>${requestMeta.today}</strong>
                <span>今日新增申请</span>
              </div>
              <div class="mini-stat">
                <strong>${requestMeta.risk}</strong>
                <span>风险提示</span>
              </div>
            </div>
          </div>
          <div class="mini-section compliance-section">
            <div class="section-head compact-head">
              <div>
                <p class="eyebrow">数据合规</p>
                <h3>隐私与脱敏展示</h3>
              </div>
            </div>
            <p class="metric-label">${escapeHtml(privacy.resultDisplay || "运营端仅展示聚合指标。")}</p>
            <div class="stats-row compact-stats">
              <span class="stat-chip">${escapeHtml(privacy.heatAnalysis || "款式热度使用埋点聚合。")}</span>
              <span class="stat-chip">${escapeHtml(privacy.frontendRule || "前端不展示用户级原图。")}</span>
            </div>
          </div>
        </article>
      </div>
    </section>
  `;
}

function renderStyleManagement(items) {
  const styles = items;
  if (!styles.length) {
    view.innerHTML = emptyState("暂无真实款式", "请先导入真实款式数据，或由运营新建款式。");
    return;
  }
  if (!state.selectedStyleId || !styles.some((item) => item.id === state.selectedStyleId)) {
    state.selectedStyleId = styles[0].id;
  }
  const selectedStyle = styles.find((item) => item.id === state.selectedStyleId) || styles[0];
  const selectedTags = (selectedStyle.tags || []).join("，");
  const selectedColors = (selectedStyle.colors || []).join("，");

  view.innerHTML = `
    <section class="style-layout">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">款式库</p>
            <h3>真实款式库</h3>
          </div>
          <button id="create-style-trigger" class="secondary-button" type="button">新建款式</button>
        </div>
        <div class="style-collection">
          ${styles
            .map(
              (item) => `
                <button class="style-card ${item.id === state.selectedStyleId ? "is-active" : ""}" data-style-id="${escapeHtml(item.id)}" type="button">
                  ${imageOrFallback(item.imageUrl, item.name)}
                  <div class="style-card-head">
                    <div>
                      <h4>${escapeHtml(item.name)}</h4>
                      <p class="muted">${escapeHtml(item.vibe)}</p>
                    </div>
                    ${statusPill(item.status === "active" ? "已上架" : item.status === "draft" ? "草稿" : "已下架", item.status)}
                  </div>
                  <div class="tag-row">${(item.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
                </button>
              `,
            )
            .join("")}
        </div>
      </article>

      <article class="surface surface-block style-editor">
        <div class="section-head">
          <div>
            <p class="eyebrow">编辑器</p>
            <h3>${state.creatingStyle ? "新建款式" : "编辑款式"}</h3>
          </div>
          ${state.creatingStyle ? '<button id="cancel-create-style" class="ghost-button" type="button">取消</button>' : ""}
        </div>

        <form id="style-form" class="editor-form">
          <div class="image-preview-frame">
            ${selectedStyle.imageUrl ? `<img src="${escapeHtml(selectedStyle.imageUrl)}" alt="${escapeHtml(selectedStyle.name)}" />` : ""}
          </div>
          <div class="editor-grid">
            <label>
              名称
              <input name="name" value="${escapeHtml(selectedStyle.name)}" required />
            </label>
            <label>
              风格描述
              <input name="vibe" value="${escapeHtml(selectedStyle.vibe)}" required />
            </label>
            <label>
              甲型定位
              <input name="nailType" value="${escapeHtml(selectedStyle.nailType || "")}" />
            </label>
            <label>
              肤色适配
              <input name="skinTone" value="${escapeHtml(selectedStyle.skinTone || "")}" />
            </label>
          </div>
          <label>
            标签
            <input name="tags" value="${escapeHtml(selectedTags)}" placeholder="用逗号分隔，例如：法式，显白，通勤" />
          </label>
          <label>
            色系
            <input name="colors" value="${escapeHtml(selectedColors)}" placeholder="用逗号分隔，例如：裸粉，奶油白" />
          </label>
          <label>
            上下架状态
            <select name="status">
              <option value="draft" ${selectedStyle.status === "draft" ? "selected" : ""}>草稿</option>
              <option value="active" ${selectedStyle.status === "active" ? "selected" : ""}>上架中</option>
              <option value="inactive" ${selectedStyle.status === "inactive" ? "selected" : ""}>已下架</option>
            </select>
          </label>
          <label>
            替换图片
            <input name="image" type="file" accept="image/*" />
          </label>
          <div class="button-row">
            <button class="primary-button" type="submit">${state.creatingStyle ? "创建并保存" : "保存更改"}</button>
            ${
              !state.creatingStyle
                ? `<button id="quick-toggle-style" class="ghost-button" type="button">${selectedStyle.status === "active" ? "下架款式" : "上架款式"}</button>`
                : ""
            }
          </div>
        </form>
      </article>
    </section>
  `;
}

function renderRequestList(items, allowReview) {
  if (!items.length) {
    view.innerHTML = emptyState("暂无申请", "这里会保留商家发起的真实上架与下架申请。");
    return;
  }
  view.innerHTML = `
    <section class="request-grid">
      ${items
        .map(
          (item) => `
            <article class="surface request-card">
              <div class="style-card-head">
                <div>
                  <p class="eyebrow">${item.requestedAction === "launch" ? "上架申请" : "下架申请"}</p>
                  <h3>${escapeHtml(item.styleName || "未命名款式")}</h3>
                </div>
                ${statusPill(item.status === "approved" ? "已通过" : item.status === "rejected" ? "已驳回" : "待审核", item.status)}
              </div>
              <div class="stats-row">
                <span class="stat-chip">门店 ${escapeHtml(item.storeName || item.storeId || "-")}</span>
                <span class="stat-chip">提交时间 ${escapeHtml(formatDateTime(item.createdAt))}</span>
              </div>
              <p class="lead compact">${escapeHtml(item.reason || "未填写申请说明。")}</p>
              ${
                allowReview && item.status === "pending"
                  ? `
                    <label>
                      审核备注
                      <textarea data-review-note="${escapeHtml(item.id)}" placeholder="写给商家的审核意见"></textarea>
                    </label>
                    <div class="button-row">
                      <button class="success-button" data-approve-request="${escapeHtml(item.id)}" type="button">通过申请</button>
                      <button class="danger-button" data-reject-request="${escapeHtml(item.id)}" type="button">驳回申请</button>
                    </div>
                  `
                  : item.reviewNote
                    ? `<p class="muted">审核备注：${escapeHtml(item.reviewNote)}</p>`
                    : ""
              }
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderTrendSuggestions(data) {
  const community = data.community || { stats: {}, topics: [], clusters: [], hotPosts: [], aiHighlights: [] };
  const product = data.product || { stats: {}, hotStyles: [], conversionLeaders: [] };
  const items = data.recommendations || [];
  const curatedPosts = community.aiHighlights || [];
  const isCollecting = state.trendCollect?.status === "crawling" || state.trendCollect?.status === "analyzing";
  view.innerHTML = `
    <section class="metrics-grid">
      <article class="surface surface-block">
        <p class="eyebrow">社区趋势</p>
        <div class="metric-value">${community.stats.topics || 0}</div>
        <p class="metric-label">已入库的小红书监控话题</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">高热帖子</p>
        <div class="metric-value">${community.stats.posts || 0}</div>
        <p class="metric-label">最近一轮采到的有效热帖样本</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">站内款式</p>
        <div class="metric-value">${product.stats.styles || 0}</div>
        <p class="metric-label">有真实埋点和图片的在库款式</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">智能建议</p>
        <div class="metric-value">${items.length}</div>
        <p class="metric-label">待运营处理的趋势建议</p>
      </article>
    </section>

    ${renderTrendCollectStatus()}
    ${renderXhsCollectionHealth()}
    ${renderCollectedPosts(state.trendCollect?.posts || [])}

    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">智能建议</p>
            <h3>小红书趋势采集</h3>
          </div>
          <a class="action-link secondary-button" href="/xhs-account/platforms/xhs/discovery" target="_blank" rel="noreferrer">
            采集控制台
          </a>
        </div>
        <p class="lead compact">运营可以在 Nail Mind 直接采集，也可以打开小红书采集控制台管理账号与抓取任务；系统会自动完成控制台授权，不需要输入 operator。</p>
        <form id="trend-collect-form" class="stack-form">
          <label>
            关键词
            <input name="keywords" placeholder="例如：法式美甲, 猫眼美甲, 新中式美甲" />
          </label>
          <div class="editor-grid">
            <label>
              每个关键词采样数
              <input name="maxPostsPerKeyword" type="number" min="1" max="12" value="6" />
            </label>
            <label>
              浏览器模式
              <select name="headless">
                <option value="true" selected>无头模式</option>
                <option value="false">可视模式</option>
              </select>
            </label>
          </div>
          <button class="primary-button" type="submit" ${isCollecting ? "disabled" : ""}>
            ${isCollecting ? "正在爬取并分析..." : "开始采集并生成建议"}
          </button>
        </form>
      </article>
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">站内热度</p>
            <h3>站内热度复核</h3>
          </div>
        </div>
        <p class="lead compact">这里展示真实埋点里升温最快的款式。运营可以先看站内收藏、试戴、预约，再决定是否采纳 OpenClaw 的上新或加推动作。</p>
        <div class="stats-row">
          <span class="stat-chip">曝光 ${product.stats.impressions || 0}</span>
          <span class="stat-chip">收藏 ${product.stats.favorites || 0}</span>
          <span class="stat-chip">试戴 ${product.stats.tryonStarts || 0}</span>
          <span class="stat-chip">预约 ${product.stats.bookingCreates || 0}</span>
        </div>
      </article>
    </section>

    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">社区话题</p>
            <h3>小红书高热话题</h3>
          </div>
        </div>
        <div class="list-stack">
          ${
            community.topics.length
              ? community.topics
                  .map(
                    (topic) => `
                      <article class="overview-card surface">
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(topic.title || topic.clusterLabel || topic.topicKey)}</h4>
                            <p class="muted">${escapeHtml(topic.clusterLabel || "未聚类")}</p>
                          </div>
                          ${statusPill(`热度 ${topic.heatScore}`, "healthy")}
                        </div>
                        <p class="lead compact">${escapeHtml(topic.summary || "该话题已进入监控池。")}</p>
                        <div class="stats-row">
                          <span class="stat-chip">样本 ${topic.evidenceCount || 0}</span>
                          <span class="stat-chip">最近抓取 ${escapeHtml(formatDateTime(topic.lastSeenAt))}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : emptyState("暂无社区话题", "先执行一次采集，系统才会开始积累社区趋势数据。")
          }
        </div>
      </article>

      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">风格聚类</p>
            <h3>社区风格簇</h3>
          </div>
        </div>
        <div class="list-stack">
          ${
            community.clusters.length
              ? community.clusters
                  .map(
                    (cluster) => `
                      <article class="overview-card surface">
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(cluster.label)}</h4>
                            <p class="muted">${escapeHtml((cluster.topicTitles || []).slice(0, 2).join(" / ") || "无代表标题")}</p>
                          </div>
                          ${statusPill(`热度 ${cluster.heatScore}`, "healthy")}
                        </div>
                        <div class="stats-row">
                          <span class="stat-chip">话题 ${cluster.topicCount}</span>
                          <span class="stat-chip">样本帖 ${cluster.postCount}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : emptyState("暂无风格簇", "抓到足够多的社区帖子后，这里会自动归纳当前正在升温的风格簇。")
          }
        </div>
      </article>
    </section>

    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">精选样本</p>
            <h3>OpenClaw 精选样本</h3>
          </div>
        </div>
        <div class="recommendation-grid">
          ${
            curatedPosts.length
              ? curatedPosts
                  .slice(0, 6)
                  .map(
                    (post) => `
                      <article class="request-card surface">
                        ${imageOrFallback(post.imageUrl, post.title || "热帖样本")}
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(post.title || "未命名帖子")}</h4>
                            <p class="muted">${escapeHtml(post.recommendedBy ? `来自建议：${post.recommendedBy}` : (post.author || "-"))}</p>
                          </div>
                          ${statusPill(post.engagementLabel || "OpenClaw 已筛选", "healthy")}
                        </div>
                        <p class="lead compact">这条样本已通过 OpenClaw 初步筛选，用于辅助判断当前风格是否值得上新或加推。</p>
                        ${
                          (post.tags || []).length
                            ? `<div class="tag-row">${post.tags
                                .slice(0, 4)
                                .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
                                .join("")}</div>`
                            : ""
                        }
                      </article>
                    `,
                  )
                  .join("")
              : emptyState("暂无精选样本", "这里优先展示 OpenClaw 已筛过的有效社区样本，不再直接暴露原始爬取噪声。")
          }
        </div>
      </article>

      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">站内款式</p>
            <h3>站内热款与转化领先款</h3>
          </div>
        </div>
        <div class="list-stack">
          ${
            product.hotStyles.length
              ? product.hotStyles
                  .slice(0, 6)
                  .map(
                    (item) => `
                      <article class="overview-card surface">
                        ${imageOrFallback(item.imageUrl, item.styleName)}
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(item.styleName)}</h4>
                            <p class="muted">${escapeHtml(item.signalLabel)}</p>
                          </div>
                          ${statusPill(humanizeHealthLabel(item.healthLabel), item.healthLabel)}
                        </div>
                        <div class="stats-row">
                          <span class="stat-chip">曝光 ${item.impressions}</span>
                          <span class="stat-chip">收藏 ${item.favorites}</span>
                          <span class="stat-chip">试戴 ${item.tryonStarts}</span>
                          <span class="stat-chip">预约 ${item.bookingCreates}</span>
                        </div>
                      </article>
                    `,
                  )
                  .join("")
              : emptyState("暂无站内热款", "有真实埋点后，这里会显示当前用户最感兴趣的款式。")
          }
        </div>
      </article>
    </section>

    ${
      items.length
        ? `
          <section class="section-head">
            <div>
              <p class="eyebrow">运营建议</p>
              <h3>OpenClaw 运营建议</h3>
            </div>
          </section>
          <section class="recommendation-grid">
            ${items
              .map(
                (item) => {
                  const sourcePosts = item.candidatePayload?.sourcePosts || [];
                  const previewImage = item.imageUrl || item.candidatePayload?.imageUrl || sourcePosts[0]?.imageUrl || "";
                  return `
                  <article class="surface request-card">
                    ${imageOrFallback(previewImage, item.candidateName || item.targetStyleId || "趋势建议")}
                    <div class="style-card-head">
                      <div>
                        <p class="eyebrow">${escapeHtml(item.type)}</p>
                        <h3>${escapeHtml(item.candidateName || item.targetStyleId || "未命名建议")}</h3>
                      </div>
                      ${statusPill(item.status === "approved" ? "已采纳" : item.status === "rejected" ? "已驳回" : "待审核", item.status)}
                    </div>
                    <p class="lead compact">${escapeHtml(item.triggerReason)}</p>
                    <div class="stats-row">
                      <span class="stat-chip">置信度 ${escapeHtml(item.confidenceScore)}</span>
                      <span class="stat-chip">目标款式 ${escapeHtml(item.targetStyleId || "-")}</span>
                      <span class="stat-chip">样本数 ${escapeHtml(sourcePosts.length)}</span>
                    </div>
                    ${
                      sourcePosts.length
                        ? `<div class="list-stack">
                            ${sourcePosts
                              .slice(0, 3)
                              .map(
                                (post) => `
                                  <div class="overview-card surface">
                                    <strong>${escapeHtml(post.title || "未命名帖子")}</strong>
                                    <div class="stats-row">
                                      <span class="stat-chip">作者 ${escapeHtml(post.author || "-")}</span>
                                      <span class="stat-chip">赞 ${escapeHtml(post.likeCount || 0)}</span>
                                      <span class="stat-chip">藏 ${escapeHtml(post.collectCount || 0)}</span>
                                    </div>
                                  </div>
                                `,
                              )
                              .join("")}
                          </div>`
                        : ""
                    }
                    ${
                      item.status === "pending"
                        ? `
                          <label>
                            审核备注
                            <textarea data-review-trend="${escapeHtml(item.id)}" placeholder="补充采纳原因或风险提醒"></textarea>
                          </label>
                          <div class="button-row">
                            <button class="success-button" data-approve-trend="${escapeHtml(item.id)}" type="button">采纳建议</button>
                            <button class="danger-button" data-reject-trend="${escapeHtml(item.id)}" type="button">暂不采用</button>
                          </div>
                        `
                        : ""
                    }
                  </article>
                `;
                },
              )
              .join("")}
          </section>
        `
        : emptyState("暂无 OpenClaw 建议", "趋势模块接入真实建议后，这里会自动展示待处理记录。")
    }
  `;
}

function renderEvents(items) {
  view.innerHTML = items.length
    ? `
      <section class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">行为明细</p>
            <h3>用户行为明细</h3>
          </div>
          <button class="secondary-button" type="button" data-back-overview>返回看板</button>
        </div>
        <p class="metric-label">这里展示 App 真实触发的行为流水，用于排查转化链路。事件名已翻译成运营语言，原始技术字段只放在每张卡片底部。</p>
      </section>
      <section class="event-grid">
        ${items
          .map((item) => {
            const [title, description, stage] = eventBusinessMeta(item.eventName);
            return `
              <article class="surface event-card">
                <div class="style-card-head">
                  <div>
                    <p class="eyebrow">${escapeHtml(stage)}</p>
                    <h3>${escapeHtml(title)}</h3>
                  </div>
                  <span class="muted">${escapeHtml(formatDateTime(item.occurredAt))}</span>
                </div>
                <p class="metric-label">${escapeHtml(description)}</p>
                <div class="stats-row">
                  <span class="stat-chip">${escapeHtml(eventObjectLabel(item))}</span>
                  <span class="stat-chip">来源 ${escapeHtml(sourcePageLabel(item.sourcePage))}</span>
                  <span class="stat-chip">设备 ${escapeHtml(item.deviceId || "-")}</span>
                </div>
                <details>
                  <summary>查看原始字段</summary>
                  <pre>${escapeHtml(JSON.stringify({ eventName: item.eventName, sourcePage: item.sourcePage, payload: item.payload || {} }, null, 2))}</pre>
                </details>
              </article>
            `;
          })
          .join("")}
      </section>
    `
    : `
      <section class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">行为明细</p>
            <h3>用户行为明细</h3>
          </div>
          <button class="secondary-button" type="button" data-back-overview>返回看板</button>
        </div>
      </section>
      ${emptyState("暂无真实埋点", "没有事件就显示为空，不会生成测试行为。")}
    `;
}

function qualityScoreValue(record, key) {
  const manual = record.manualEvaluation || {};
  const model = record.modelEvaluation || {};
  return manual[key] ?? model[key] ?? "";
}

function renderHandConsistencyBreakdown(modelEval = {}) {
  const breakdown = modelEval.handConsistencyBreakdown || {};
  const items = [
    ["手指数量", breakdown.fingerCount],
    ["皮肤质感", breakdown.skinTexture],
    ["手型姿态", breakdown.poseConsistency],
    ["背景保持", breakdown.backgroundPreservation],
    ["甲面贴合", breakdown.nailPlacement],
  ];
  if (!items.some(([, value]) => value !== null && value !== undefined)) {
    return `<p class="metric-label">手部一致性子项等待模型自动评分。</p>`;
  }
  return `
    <div class="quality-breakdown">
      ${items
        .map(([label, value]) => `<span class="stat-chip">${escapeHtml(label)} ${value ?? "待评估"}</span>`)
        .join("")}
    </div>
  `;
}

function renderTryonQuality(items, modelName) {
  view.innerHTML = `
    <section class="surface surface-block">
      <div class="section-head">
        <div>
          <p class="eyebrow">质检流程</p>
          <h3>自动模型评分 + 人工复核</h3>
        </div>
        <span class="stat-chip">评估模型 ${escapeHtml(modelName || "qwen3.7-plus")}</span>
      </div>
      <p class="metric-label">用户每次完成试戴后，系统会自动评估款式还原度和手部一致性。手部一致性拆分为手指数量、皮肤质感、手型姿态、背景保持、甲面贴合，运营只需复核并可人工改分。</p>
    </section>
    ${
      items.length
        ? `<section class="quality-grid">
            ${items
              .map((item) => {
                const modelEval = item.modelEvaluation || {};
                const manualEval = item.manualEvaluation || {};
                return `
                  <article class="surface surface-block quality-card" data-quality-record="${escapeHtml(item.id)}">
                    <div class="section-head">
                      <div>
                        <p class="eyebrow">试戴记录</p>
                        <h3>${escapeHtml(item.styleName || "未命名款式")}</h3>
                      </div>
                      <span class="muted">${escapeHtml(formatDateTime(item.createdAt))}</span>
                    </div>
                    <div class="quality-images">
                      <figure>
                        ${item.handImageUrl ? `<img src="${escapeHtml(item.handImageUrl)}" alt="用户手图" />` : `<div class="style-thumb"></div>`}
                        <figcaption>用户手图</figcaption>
                      </figure>
                      <figure>
                        ${item.styleImageUrl ? `<img src="${escapeHtml(item.styleImageUrl)}" alt="款式图" />` : `<div class="style-thumb"></div>`}
                        <figcaption>款式图</figcaption>
                      </figure>
                      <figure>
                        ${item.resultUrl ? `<img src="${escapeHtml(item.resultUrl)}" alt="生成结果" />` : `<div class="style-thumb"></div>`}
                        <figcaption>生成图</figcaption>
                      </figure>
                    </div>
                    <div class="quality-score-panel">
                      <div class="stats-row">
                        <span class="stat-chip">自动还原度 ${modelEval.styleFidelity ?? "评分中"}</span>
                        <span class="stat-chip">自动一致性 ${modelEval.manualConsistency ?? "评分中"}</span>
                        <span class="stat-chip">人工还原度 ${manualEval.styleFidelity ?? "未保存"}</span>
                        <span class="stat-chip">人工一致性 ${manualEval.manualConsistency ?? "未保存"}</span>
                      </div>
                      ${renderHandConsistencyBreakdown(modelEval)}
                      <p class="metric-label">${escapeHtml(manualEval.reviewNote || modelEval.reviewNote || "等待质检。")}</p>
                    </div>
                    <form class="quality-review-form" data-quality-form="${escapeHtml(item.id)}">
                      <div class="editor-grid">
                        <label>
                          款式还原度
                          <input name="styleFidelity" type="number" min="0" max="100" value="${escapeHtml(qualityScoreValue(item, "styleFidelity"))}" placeholder="0-100" required />
                        </label>
                        <label>
                          手部一致性
                          <input name="manualConsistency" type="number" min="0" max="100" value="${escapeHtml(qualityScoreValue(item, "manualConsistency"))}" placeholder="0-100" required />
                        </label>
                      </div>
                      <label>
                        质检备注
                        <textarea name="reviewNote" placeholder="例如：款式细节还原较好，手指数量正常，肤色保持自然。">${escapeHtml(manualEval.reviewNote || "")}</textarea>
                      </label>
                      <div class="button-row">
                        <button class="primary-button" type="submit">保存人工评分</button>
                      </div>
                    </form>
                  </article>
                `;
              })
              .join("")}
          </section>`
        : emptyState("暂无试戴记录", "用户完成 AI 试戴后，这里会出现可质检的真实记录。")
    }
  `;
}

function renderMerchantGoods(items) {
  view.innerHTML = items.length
    ? `
      <section class="cards-grid">
        ${items
          .map((item) => {
            const style = item.style || {};
            return `
              <article class="surface merchant-card">
                ${imageOrFallback(style.imageUrl, style.name || "门店款式")}
                <div class="style-card-head">
                  <div>
                    <h3>${escapeHtml(style.name || "未命名款式")}</h3>
                    <p class="muted">${escapeHtml(style.vibe || "门店在售款式")}</p>
                  </div>
                  ${statusPill(item.status === "active" ? "在售" : "已下架", item.status)}
                </div>
                <div class="stats-row">
                  <span class="stat-chip">库存 ${escapeHtml(item.inventoryCount)}</span>
                  <span class="stat-chip">门店在售</span>
                </div>
              </article>
            `;
          })
          .join("")}
      </section>
    `
    : emptyState("暂无商品信息", "当前商家账号还没有绑定真实在售款式。");
}

function renderMerchantBookings(items) {
  view.innerHTML = items.length
    ? `
      <section class="booking-grid">
        ${items
          .map(
            (item) => `
              <article class="surface booking-card">
                <div class="style-card-head">
                  <div>
                    <p class="eyebrow">${escapeHtml(item.status)}</p>
                    <h3>${escapeHtml(item.styleName)}</h3>
                  </div>
                  <span class="muted">${escapeHtml(item.slot)}</span>
                </div>
                <div class="stats-row">
                  <span class="stat-chip">顾客 ${escapeHtml(item.name)}</span>
                  <span class="stat-chip">电话 ${escapeHtml(item.phone)}</span>
                  <span class="stat-chip">创建于 ${escapeHtml(formatDateTime(item.createdAt))}</span>
                </div>
                <p class="lead compact">${escapeHtml(item.note || "用户未填写备注。")}</p>
              </article>
            `,
          )
          .join("")}
      </section>
    `
    : emptyState("暂无预约", "当前门店还没有真实预约记录。");
}

function renderMerchantRequests(items, listingItems) {
  const listingOptions = listingItems
    .map((item) => `<option value="${escapeHtml(item.styleId)}">${escapeHtml(item.style?.name || "未命名款式")}</option>`)
    .join("");
  view.innerHTML = `
    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">创建申请</p>
            <h3>提交上架或下架申请</h3>
          </div>
        </div>
        <form id="merchant-request-form" class="stack-form">
          <label>
            款式
            <select name="styleId" required>${listingOptions}</select>
          </label>
          <label>
            操作类型
            <select name="requestedAction">
              <option value="launch">申请上架</option>
              <option value="delist">申请下架</option>
            </select>
          </label>
          <label>
            申请说明
            <textarea name="reason" placeholder="例如：预约量上升，需要恢复上架。"></textarea>
          </label>
          <button class="primary-button" type="submit">提交申请</button>
        </form>
      </article>
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">历史记录</p>
            <h3>申请记录</h3>
          </div>
        </div>
        ${
          items.length
            ? `<div class="list-stack">
                ${items
                  .map(
                    (item) => `
                      <div class="request-card surface">
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(item.styleName || "未命名款式")}</h4>
                            <p class="muted">${escapeHtml(item.requestedAction === "launch" ? "上架申请" : "下架申请")}</p>
                          </div>
                          ${statusPill(item.status === "approved" ? "已通过" : item.status === "rejected" ? "已驳回" : "待审核", item.status)}
                        </div>
                        <p class="lead compact">${escapeHtml(item.reason || "未填写申请说明。")}</p>
                        <p class="muted">提交于 ${escapeHtml(formatDateTime(item.createdAt))}</p>
                      </div>
                    `,
                  )
                  .join("")}
              </div>`
            : emptyState("暂无申请记录", "提交后，这里会保留真实审批结果。")
        }
      </article>
    </section>
  `;
}

function renderMerchantStore(data) {
  const store = data.store;
  if (!store) {
    view.innerHTML = emptyState("未绑定门店", "当前商家账号还没有绑定真实门店。");
    return;
  }
  view.innerHTML = `
    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">门店</p>
            <h3>${escapeHtml(store.name)}</h3>
          </div>
          ${statusPill(store.isAcceptingBookings ? "可预约" : "暂停接单", store.isAcceptingBookings ? "active" : "inactive")}
        </div>
        <div class="stats-row">
          <span class="stat-chip">门店编号 ${escapeHtml(store.id)}</span>
          <span class="stat-chip">营业时间 ${escapeHtml(store.openHours)}</span>
          <span class="stat-chip">在售款 ${escapeHtml(data.summary.listingCount)}</span>
        </div>
      </article>
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">档期</p>
            <h3>更新营业状态</h3>
          </div>
        </div>
        <form id="merchant-store-form" class="stack-form">
          <label>
            可预约时段
            <textarea name="slots">${escapeHtml((store.slots || []).join("，"))}</textarea>
          </label>
          <label>
            接单状态
            <select name="isAcceptingBookings">
              <option value="true" ${store.isAcceptingBookings ? "selected" : ""}>正常接单</option>
              <option value="false" ${!store.isAcceptingBookings ? "selected" : ""}>暂停接单</option>
            </select>
          </label>
          <button class="primary-button" type="submit">保存门店设置</button>
        </form>
      </article>
    </section>
  `;
}

async function loadOverview() {
  const [overview, requests] = await Promise.all([
    api("/admin/analytics/overview"),
    api("/admin/requests"),
  ]);
  overview.pendingRequests = requests.items || [];
  renderOverview(overview);
}

async function loadStyles() {
  const data = await api("/admin/styles");
  state.styles = data.items;
  renderStyleManagement(data.items);
}

async function loadRequests() {
  const data = await api("/admin/requests");
  renderRequestList(data.items, true);
}

async function loadTrends() {
  const [data, xhsStatus] = await Promise.all([
    api("/admin/trends/dashboard"),
    api("/admin/trends/xhs-status").catch((error) => ({
      status: "unavailable",
      message: error.message || "小红书采集状态检查失败",
      accountMatrixReachable: false,
      accountId: null,
      hasCookie: false,
      spiderReady: false,
      loginHealthy: false,
    })),
  ]);
  state.trendsData = data;
  state.xhsStatus = xhsStatus;
  renderTrendSuggestions(data);
}

async function loadEvents() {
  document.getElementById("page-kicker").textContent = "行为明细";
  document.getElementById("page-title").textContent = "用户行为明细";
  document.getElementById("page-description").textContent = "从经营总览下钻查看真实埋点流水，用运营语言解释每一步用户行为。";
  document.getElementById("topbar-range").textContent = "最近 60 条";
  topbarDetailButton.classList.add("hidden");
  const data = await api("/admin/analytics/events?limit=60");
  renderEvents(data.items);
}

async function loadTryonQuality() {
  const data = await api("/admin/tryon/quality?limit=20");
  renderTryonQuality(data.items || [], data.model);
}

async function loadMerchantGoods() {
  const data = await api("/admin/merchants/me/listings");
  renderMerchantGoods(data.items);
}

async function loadMerchantBookings() {
  const data = await api("/admin/merchants/me/bookings");
  renderMerchantBookings(data.items);
}

async function loadMerchantRequests() {
  const [requests, listings] = await Promise.all([
    api("/admin/merchants/me/requests"),
    api("/admin/merchants/me/listings"),
  ]);
  renderMerchantRequests(requests.items, listings.items);
}

async function loadMerchantStore() {
  const data = await api("/admin/merchants/me/dashboard");
  renderMerchantStore(data);
}

async function setView(viewId) {
  state.activeView = viewId;
  syncPageMeta();
  if (state.user.role === "platform_admin") {
    if (viewId === "overview") return loadOverview();
    if (viewId === "styles") return loadStyles();
    if (viewId === "requests") return loadRequests();
    if (viewId === "trends") return loadTrends();
    if (viewId === "quality") return loadTryonQuality();
    if (viewId === "events") return loadEvents();
    return;
  }
  if (viewId === "goods") return loadMerchantGoods();
  if (viewId === "bookings") return loadMerchantBookings();
  if (viewId === "requests") return loadMerchantRequests();
  if (viewId === "store") return loadMerchantStore();
}

async function saveStyleForm(form) {
  const formData = new FormData(form);
  const payload = {
    name: formData.get("name"),
    vibe: formData.get("vibe"),
    nailType: formData.get("nailType"),
    skinTone: formData.get("skinTone"),
    tags: normalizeCommaList(String(formData.get("tags") || "")),
    colors: normalizeCommaList(String(formData.get("colors") || "")),
    status: formData.get("status"),
  };
  let styleId = state.selectedStyleId;
  if (state.creatingStyle) {
    const created = await api("/admin/styles", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        price: "",
        code: "",
      }),
    });
    styleId = created.style.id;
    state.selectedStyleId = styleId;
  } else {
    await api(`/admin/styles/${encodeURIComponent(styleId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }
  const image = formData.get("image");
  if (image instanceof File && image.size > 0) {
    const uploadData = new FormData();
    uploadData.append("image", image);
    await api(`/admin/styles/${encodeURIComponent(styleId)}/image`, {
      method: "POST",
      body: uploadData,
    });
  }
  state.creatingStyle = false;
  await loadStyles();
}

async function quickToggleStyle() {
  const style = state.styles.find((item) => item.id === state.selectedStyleId);
  if (!style) return;
  const nextStatus = style.status === "active" ? "inactive" : "active";
  await api(`/admin/styles/${encodeURIComponent(style.id)}/status`, {
    method: "POST",
    body: JSON.stringify({ status: nextStatus }),
  });
  await loadStyles();
}

function createDraftStyle() {
  state.creatingStyle = true;
  const draft = {
    id: "__draft__",
    name: "",
    vibe: "",
    nailType: "",
    skinTone: "",
    tags: [],
    colors: [],
    status: "draft",
    imageUrl: "",
  };
  state.styles = [draft, ...state.styles.filter((item) => item.id !== "__draft__")];
  state.selectedStyleId = "__draft__";
  renderStyleManagement(state.styles);
}

async function submitReview(path, note) {
  await api(path, {
    method: "POST",
    body: JSON.stringify({ reviewNote: note || "" }),
  });
  if (state.activeView === "requests") {
    await loadRequests();
  } else if (state.activeView === "trends") {
    await loadTrends();
  }
}

async function submitMerchantRequest(form) {
  const formData = new FormData(form);
  await api("/admin/merchants/me/requests", {
    method: "POST",
    body: JSON.stringify({
      styleId: formData.get("styleId"),
      requestedAction: formData.get("requestedAction"),
      reason: formData.get("reason"),
    }),
  });
  await loadMerchantRequests();
}

async function saveMerchantStore(form) {
  const formData = new FormData(form);
  await api("/admin/merchants/me/store", {
    method: "PATCH",
    body: JSON.stringify({
      slots: normalizeCommaList(String(formData.get("slots") || "")),
      isAcceptingBookings: formData.get("isAcceptingBookings") === "true",
    }),
  });
  await loadMerchantStore();
}

async function collectTrendSuggestions(form) {
  const formData = new FormData(form);
  const keywords = normalizeCommaList(String(formData.get("keywords") || ""));
  if (!keywords.length) {
    throw new Error("请至少输入一个趋势关键词");
  }
  const payload = {
      keywords,
      maxPostsPerKeyword: Number(formData.get("maxPostsPerKeyword") || 6),
      headless: formData.get("headless") === "true",
  };
  state.trendCollect = {
    status: "crawling",
    title: `正在爬取：${keywords.join(" / ")}`,
    posts: [],
    recommendationsCreated: 0,
  };
  renderTrendSuggestions(state.trendsData || {});
  let crawlResult;
  try {
    crawlResult = await api("/admin/trends/crawl", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch (error) {
    const message = error.message || "";
    state.trendCollect = {
      status: "failed",
      title: "小红书数据抓取失败",
      posts: [],
      message: message.includes("登录") || message.includes("Cookie") || message.includes("PC 账号")
        ? "后台小红书采集源需要维护，请联系技术同学更新采集凭证后再试。"
        : message,
      recommendationsCreated: 0,
    };
    renderTrendSuggestions(state.trendsData || {});
    return;
  }
  const collectedPosts = (crawlResult.collectedPosts || []).sort((a, b) => Number(b.likeCount || 0) - Number(a.likeCount || 0));
  if (!collectedPosts.length) {
    state.trendCollect = {
      status: "failed",
      title: "本轮没有抓到可用帖子",
      posts: [],
      message: "账号矩阵已完成请求，但小红书本次返回为空。请稍后重试，或更换关键词、放宽时间范围后再采集。",
      recommendationsCreated: 0,
    };
    renderTrendSuggestions(state.trendsData || {});
    return;
  }
  state.trendCollect = {
    status: "analyzing",
    title: "OpenClaw 正在生成建议",
    posts: collectedPosts,
    recommendationsCreated: 0,
  };
  renderTrendSuggestions(state.trendsData || {});
  let analysisResult;
  try {
    analysisResult = await api("/admin/trends/analyze", {
      method: "POST",
      body: JSON.stringify({
        topicIds: (crawlResult.collectedTopics || []).map((topic) => topic.id),
      }),
    });
  } catch (error) {
    state.trendCollect = {
      status: "failed",
      title: "OpenClaw 分析失败",
      posts: collectedPosts,
      message: error.message,
      recommendationsCreated: 0,
    };
    renderTrendSuggestions(state.trendsData || {});
    throw error;
  }
  state.trendCollect = {
    ...state.trendCollect,
    status: "done",
    title: "采集与 OpenClaw 分析完成",
    recommendationsCreated: analysisResult.recommendationsCreated || 0,
  };
  renderTrendSuggestions({ ...(state.trendsData || {}), recommendations: analysisResult.items || [] });
  await loadTrends();
  if (state.trendsData) renderTrendSuggestions(state.trendsData);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setAuthError("");
  try {
    await login(document.getElementById("email").value, document.getElementById("password").value);
  } catch (error) {
    setAuthError(error.message);
  }
});

document.getElementById("logout").addEventListener("click", () => {
  localStorage.removeItem("nailmind_admin_token");
  state.token = "";
  state.user = null;
  location.reload();
});

tabs.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement) || !target.dataset.view) return;
  try {
    await setView(target.dataset.view);
  } catch (error) {
    alert(error.message);
  }
});

sidebarNav.addEventListener("click", async (event) => {
  const target = event.target;
  const button = target instanceof HTMLElement ? target.closest("[data-view]") : null;
  if (!(button instanceof HTMLButtonElement) || !button.dataset.view) return;
  try {
    await setView(button.dataset.view);
  } catch (error) {
    alert(error.message);
  }
});

refreshViewButton.addEventListener("click", async () => {
  try {
    await setView(state.activeView || currentLayout().views[0].id);
  } catch (error) {
    alert(error.message);
  }
});

topbarDetailButton.addEventListener("click", async () => {
  try {
    await loadEvents();
  } catch (error) {
    alert(error.message);
  }
});

view.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const styleCard = target.closest("[data-style-id]");
  if (styleCard && styleCard instanceof HTMLButtonElement) {
    state.creatingStyle = styleCard.dataset.styleId === "__draft__";
    state.selectedStyleId = styleCard.dataset.styleId;
    renderStyleManagement(state.styles);
    return;
  }

  if (target.id === "create-style-trigger") {
    createDraftStyle();
    return;
  }

  if (target.id === "cancel-create-style") {
    state.creatingStyle = false;
    state.styles = state.styles.filter((item) => item.id !== "__draft__");
    state.selectedStyleId = state.styles[0]?.id || "";
    renderStyleManagement(state.styles);
    return;
  }

  if (target.id === "quick-toggle-style") {
    try {
      await quickToggleStyle();
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  if (target.hasAttribute("data-open-events")) {
    try {
      await loadEvents();
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  const openStyleId = target.getAttribute("data-open-style");
  if (openStyleId) {
    try {
      state.selectedStyleId = openStyleId;
      await setView("styles");
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  if (target.hasAttribute("data-open-requests")) {
    try {
      await setView("requests");
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  if (target.hasAttribute("data-open-style-list")) {
    try {
      await setView("styles");
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  if (target.hasAttribute("data-back-overview")) {
    try {
      await setView("overview");
    } catch (error) {
      alert(error.message);
    }
    return;
  }

  const approveRequestId = target.getAttribute("data-approve-request");
  const rejectRequestId = target.getAttribute("data-reject-request");
  const approveTrendId = target.getAttribute("data-approve-trend");
  const rejectTrendId = target.getAttribute("data-reject-trend");

  try {
    if (approveRequestId) {
      const note = document.querySelector(`[data-review-note="${approveRequestId}"]`)?.value || "";
      await submitReview(`/admin/requests/${encodeURIComponent(approveRequestId)}/approve`, note);
      return;
    }
    if (rejectRequestId) {
      const note = document.querySelector(`[data-review-note="${rejectRequestId}"]`)?.value || "";
      await submitReview(`/admin/requests/${encodeURIComponent(rejectRequestId)}/reject`, note);
      return;
    }
    if (approveTrendId) {
      const note = document.querySelector(`[data-review-trend="${approveTrendId}"]`)?.value || "";
      await submitReview(`/admin/trends/recommendations/${encodeURIComponent(approveTrendId)}/approve`, note);
      return;
    }
    if (rejectTrendId) {
      const note = document.querySelector(`[data-review-trend="${rejectTrendId}"]`)?.value || "";
      await submitReview(`/admin/trends/recommendations/${encodeURIComponent(rejectTrendId)}/reject`, note);
    }
  } catch (error) {
    alert(error.message);
  }
});

view.addEventListener(
  "error",
  (event) => {
    const target = event.target;
    if (!(target instanceof HTMLImageElement) || !target.classList.contains("style-thumb")) return;
    const fallback = document.createElement("div");
    fallback.className = "style-thumb";
    target.replaceWith(fallback);
  },
  true,
);

view.addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = event.target;
  if (!(target instanceof HTMLFormElement)) return;
  try {
    if (target.classList.contains("quality-review-form")) {
      const recordId = target.getAttribute("data-quality-form");
      const formData = new FormData(target);
      await api(`/admin/tryon/quality/${encodeURIComponent(recordId)}/manual-review`, {
        method: "POST",
        body: JSON.stringify({
          styleFidelity: Number(formData.get("styleFidelity")),
          manualConsistency: Number(formData.get("manualConsistency")),
          reviewNote: String(formData.get("reviewNote") || ""),
          evaluator: "manual",
        }),
      });
      await loadTryonQuality();
      return;
    }
    if (target.id === "style-form") {
      await saveStyleForm(target);
      return;
    }
    if (target.id === "merchant-request-form") {
      await submitMerchantRequest(target);
      return;
    }
    if (target.id === "merchant-store-form") {
      await saveMerchantStore(target);
      return;
    }
    if (target.id === "trend-collect-form") {
      await collectTrendSuggestions(target);
    }
  } catch (error) {
    alert(error.message);
  }
});

async function bootstrap() {
  if (!state.token) return;
  try {
    const data = await api("/admin/auth/me");
    showWorkspace(data.user);
    await setView(currentLayout().views[0].id);
  } catch {
    localStorage.removeItem("nailmind_admin_token");
  }
}

bootstrap();
