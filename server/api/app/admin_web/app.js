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
const XHS_ACCOUNT_MATRIX_URL = "/xhs-account/platforms/xhs/accounts";

const roleLayouts = {
  platform_admin: {
    title: "运营工作台",
    subtitle: "围绕真实埋点、款式资产和门店申请做统一运营决策。",
    note: "运营端可以直接调整款式资料、上下架状态、图片资产，并审核商家申请和 OpenClaw 建议。",
    views: [
      { id: "overview", label: "经营总览", kicker: "Operations", title: "真实埋点总览", description: "只展示数据库里的真实曝光、点击、试戴与预约事件，不写入任何测试埋点。" },
      { id: "styles", label: "款式管理", kicker: "Catalog", title: "款式资产与数据库编辑", description: "可直接编辑款式名称、风格、标签、上下架状态，并替换图片资产。" },
      { id: "requests", label: "商家申请", kicker: "Requests", title: "商家申请审批", description: "保留门店提交的上架、下架申请，运营审核后同步到真实库存状态。" },
      { id: "trends", label: "趋势中枢", kicker: "Trends", title: "社区趋势与站内热度联动", description: "同一页查看小红书高热话题、站内真实热款和 OpenClaw 建议，让运营同时判断外部风向与内部承接能力。" },
      { id: "events", label: "埋点明细", kicker: "Events", title: "真实事件流", description: "按时间查看真实用户行为事件，支持复盘款式曝光、试戴与预约链路。" },
    ],
  },
  merchant_admin: {
    title: "商家工作台",
    subtitle: "只处理门店商品、预约履约、上架申请和营业时间。",
    note: "商家端不展示运营分析或社区趋势，只保留门店经营所需的数据和操作。",
    views: [
      { id: "goods", label: "商品信息", kicker: "Merchant", title: "门店商品与库存", description: "查看当前门店可售款式、库存状态与展示图片，不展示运营侧趋势信息。" },
      { id: "bookings", label: "预约信息", kicker: "Bookings", title: "预约履约", description: "查看真实预约记录、用户姓名、到店时段和当前履约状态。" },
      { id: "requests", label: "商家申请", kicker: "Requests", title: "上架与下架申请", description: "向平台运营提交款式上架或下架申请，并保留历史审批记录。" },
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
      { id: "requests", label: "商家申请", kicker: "Requests", title: "上架与下架申请", description: "向平台运营提交款式上架或下架申请，并保留历史审批记录。" },
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
  if (value === "insufficient_distribution") return "分发不足";
  if (value === "optimize_candidate") return "待优化";
  if (value === "delist_candidate") return "下架观察";
  if (value === "healthy") return "表现稳定";
  if (value === "insufficient_data") return "数据不足";
  return value || "待观察";
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
          <p class="eyebrow">Collection Status</p>
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
    healthy: ["登录态有效", "approved"],
    expired: ["登录已过期", "rejected"],
    missing_cookie: ["缺少登录态", "rejected"],
    missing_spider: ["Spider_XHS 未就绪", "rejected"],
    spider_import_failed: ["Spider_XHS 加载失败", "rejected"],
    unavailable: ["账号矩阵不可用", "rejected"],
    unhealthy: ["登录态异常", "rejected"],
  };
  const [label, stateName] = statusMap[health.status] || ["待检查", "pending"];
  const checks = [
    ["账号矩阵", health.accountMatrixReachable ? "已连接" : "不可用", health.accountMatrixReachable],
    ["PC 账号", health.accountId ? `#${health.accountId}` : "未绑定", Boolean(health.accountId)],
    ["Cookie", health.hasCookie ? "已读取" : "缺失", health.hasCookie],
    ["Spider_XHS", health.spiderReady ? "可调用" : "不可用", health.spiderReady],
  ];
  return `
    <article class="surface surface-block xhs-health-card">
      <div class="style-card-head">
        <div>
          <p class="eyebrow">Spider_XHS Status</p>
          <h3>小红书采集状态</h3>
        </div>
        ${statusPill(label, stateName)}
      </div>
      <p class="lead compact">${escapeHtml(health.message || "等待账号矩阵状态检查。")}</p>
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
      ${
        health.loginHealthy
          ? ""
          : `<a class="action-link secondary-button" href="${XHS_ACCOUNT_MATRIX_URL}" target="_blank" rel="noreferrer">去账号矩阵重新登录</a>`
      }
    </article>
  `;
}

function renderCollectedPosts(posts = []) {
  if (!posts.length) return "";
  return `
    <section class="surface surface-block">
      <div class="section-head">
        <div>
          <p class="eyebrow">Crawled Posts</p>
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
}

function syncPageMeta() {
  const layout = currentLayout();
  const active = layout.views.find((item) => item.id === state.activeView) || layout.views[0];
  document.getElementById("page-kicker").textContent = active.kicker;
  document.getElementById("page-title").textContent = active.title;
  document.getElementById("page-description").textContent = active.description;
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

function renderOverview(data, events) {
  view.innerHTML = `
    <section class="metrics-grid">
      <article class="surface surface-block">
        <p class="eyebrow">曝光</p>
        <div class="metric-value">${data.funnel.impressions}</div>
        <p class="metric-label">最近 ${data.windowDays} 天真实曝光事件</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">试戴</p>
        <div class="metric-value">${data.funnel.tryonStarts}</div>
        <p class="metric-label">完成率 ${data.rates.tryonCompleteRate}</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">收藏</p>
        <div class="metric-value">${data.funnel.favorites}</div>
        <p class="metric-label">收藏率 ${data.rates.favoriteRate}</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">预约</p>
        <div class="metric-value">${data.funnel.bookingCreates}</div>
        <p class="metric-label">成交率 ${data.rates.dealConversionRate}</p>
      </article>
    </section>

    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">Style Health</p>
            <h3>款式表现快照</h3>
          </div>
        </div>
        <div class="list-stack">
          ${
            data.styleSnapshots.length
              ? data.styleSnapshots
                  .map(
                    (item) => `
                      <div class="overview-card surface">
                        <div class="style-card-head">
                          <div>
                            <h4>${escapeHtml(item.styleName)}</h4>
                            <p class="muted">${escapeHtml(item.styleId)}</p>
                          </div>
                          ${statusPill(item.healthLabel, item.healthLabel)}
                        </div>
                        <div class="stats-row">
                          <span class="stat-chip">曝光 ${item.impressions}</span>
                          <span class="stat-chip">点击 ${item.clicks}</span>
                          <span class="stat-chip">综合分 ${item.compositeRecommendationScore}</span>
                        </div>
                      </div>
                    `,
                  )
                  .join("")
              : emptyState("暂无款式快照", "当款式和埋点数据积累后，这里会自动展示真实表现。")
          }
        </div>
      </article>

      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">Events</p>
            <h3>最新真实事件</h3>
          </div>
        </div>
        <div class="list-stack">
          ${
            events.items.length
              ? events.items
                  .slice(0, 8)
                  .map(
                    (item) => `
                      <div class="event-card surface">
                        <div class="style-card-head">
                          <strong>${escapeHtml(item.eventName)}</strong>
                          <span class="muted">${escapeHtml(formatDateTime(item.occurredAt))}</span>
                        </div>
                        <div class="stats-row">
                          <span class="stat-chip">款式 ${escapeHtml(item.styleId || "-")}</span>
                          <span class="stat-chip">门店 ${escapeHtml(item.storeId || "-")}</span>
                          <span class="stat-chip">页面 ${escapeHtml(item.sourcePage || "-")}</span>
                        </div>
                      </div>
                    `,
                  )
                  .join("")
              : emptyState("暂无真实事件", "这里不会填充任何虚拟埋点。")
          }
        </div>
      </article>
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
            <p class="eyebrow">Catalog</p>
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
            <p class="eyebrow">Editor</p>
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
                  <h3>${escapeHtml(item.styleName || item.styleId)}</h3>
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
        <p class="eyebrow">Community</p>
        <div class="metric-value">${community.stats.topics || 0}</div>
        <p class="metric-label">已入库的小红书监控话题</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">Hot Posts</p>
        <div class="metric-value">${community.stats.posts || 0}</div>
        <p class="metric-label">最近一轮采到的有效热帖样本</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">In-App Styles</p>
        <div class="metric-value">${product.stats.styles || 0}</div>
        <p class="metric-label">有真实埋点和图片的在库款式</p>
      </article>
      <article class="surface surface-block">
        <p class="eyebrow">OpenClaw</p>
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
            <p class="eyebrow">OpenClaw</p>
            <h3>小红书趋势采集</h3>
          </div>
          <a class="action-link secondary-button" href="${XHS_ACCOUNT_MATRIX_URL}" target="_blank" rel="noreferrer">
            登录小红书账号矩阵
          </a>
        </div>
        <p class="lead compact">先在账号矩阵完成扫码、手机号验证码或 Cookie 导入，系统才会使用真实登录态采集小红书热帖，再交给 OpenClaw 生成运营建议。</p>
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
            <p class="eyebrow">In-App Trend</p>
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
            <p class="eyebrow">Community Topics</p>
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
            <p class="eyebrow">Style Clusters</p>
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
            <p class="eyebrow">OpenClaw Picks</p>
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
            <p class="eyebrow">In-App Styles</p>
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
              <p class="eyebrow">Recommendations</p>
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
      <section class="event-grid">
        ${items
          .map(
            (item) => `
              <article class="surface event-card">
                <div class="style-card-head">
                  <div>
                    <p class="eyebrow">${escapeHtml(item.eventName)}</p>
                    <h3>${escapeHtml(item.styleId || item.storeId || "无业务对象")}</h3>
                  </div>
                  <span class="muted">${escapeHtml(formatDateTime(item.occurredAt))}</span>
                </div>
                <div class="stats-row">
                  <span class="stat-chip">页面 ${escapeHtml(item.sourcePage || "-")}</span>
                  <span class="stat-chip">用户 ${escapeHtml(item.userId || "-")}</span>
                  <span class="stat-chip">设备 ${escapeHtml(item.deviceId || "-")}</span>
                </div>
                <pre>${escapeHtml(JSON.stringify(item.payload || {}, null, 2))}</pre>
              </article>
            `,
          )
          .join("")}
      </section>
    `
    : emptyState("暂无真实埋点", "没有事件就显示为空，不会生成测试行为。");
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
                ${imageOrFallback(style.imageUrl, style.name || item.styleId)}
                <div class="style-card-head">
                  <div>
                    <h3>${escapeHtml(style.name || item.styleId)}</h3>
                    <p class="muted">${escapeHtml(style.vibe || "门店在售款式")}</p>
                  </div>
                  ${statusPill(item.status === "active" ? "在售" : "已下架", item.status)}
                </div>
                <div class="stats-row">
                  <span class="stat-chip">库存 ${escapeHtml(item.inventoryCount)}</span>
                  <span class="stat-chip">款式编号 ${escapeHtml(item.styleId)}</span>
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
    .map((item) => `<option value="${escapeHtml(item.styleId)}">${escapeHtml(item.style?.name || item.styleId)}</option>`)
    .join("");
  view.innerHTML = `
    <section class="split">
      <article class="surface surface-block">
        <div class="section-head">
          <div>
            <p class="eyebrow">Create Request</p>
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
            <p class="eyebrow">History</p>
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
                            <h4>${escapeHtml(item.styleName || item.styleId)}</h4>
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
            <p class="eyebrow">Store</p>
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
            <p class="eyebrow">Schedule</p>
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
  const [overview, events] = await Promise.all([
    api("/admin/analytics/overview"),
    api("/admin/analytics/events?limit=12"),
  ]);
  renderOverview(overview, events);
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
  const data = await api("/admin/analytics/events?limit=60");
  renderEvents(data.items);
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
    const isLoginExpired = message.includes("登录已过期") || message.includes("登录态") || message.includes("PC 账号登录");
    state.trendCollect = {
      status: "failed",
      title: isLoginExpired ? "小红书账号登录已过期" : "小红书数据抓取失败",
      posts: [],
      message: isLoginExpired
        ? "请点击“登录小红书账号矩阵”，重新完成 PC 账号扫码、手机号验证码或 Cookie 导入；登录成功后再回来采集。"
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
