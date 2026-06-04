const state = {
  token: localStorage.getItem("nailmind_admin_token") || "",
  role: "",
};

const nav = document.getElementById("nav");
const view = document.getElementById("view");
const whoami = document.getElementById("whoami");
const loginForm = document.getElementById("login-form");

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

function card(title, body, extra = "") {
  return `<article class="card"><p class="eyebrow">${title}</p><div>${body}</div>${extra}</article>`;
}

function renderWhoAmI(user) {
  state.role = user.role;
  whoami.textContent = `${user.name} / ${user.email} / ${user.role}`;
  nav.classList.remove("hidden");
}

async function login(email, password) {
  const data = await api("/admin/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  state.token = data.token;
  localStorage.setItem("nailmind_admin_token", state.token);
  renderWhoAmI(data.user);
  await loadView("overview");
}

async function loadOverview() {
  const data = await api("/admin/analytics/overview");
  view.innerHTML = `
    ${card("曝光", `<div class="metric">${data.funnel.impressions}</div>`, `<p class="meta">点击率 ${data.rates.clickThroughRate}</p>`)}
    ${card("收藏", `<div class="metric">${data.funnel.favorites}</div>`, `<p class="meta">收藏率 ${data.rates.favoriteRate}</p>`)}
    ${card("试戴", `<div class="metric">${data.funnel.tryonStarts}</div>`, `<p class="meta">完成率 ${data.rates.tryonCompleteRate}</p>`)}
    ${card("预约", `<div class="metric">${data.funnel.bookingCreates}</div>`, `<p class="meta">成交率 ${data.rates.dealConversionRate}</p>`)}
    ${card("款式快照", `<div class="list">${data.styleSnapshots.map(item => `<div class="list-item"><strong>${item.styleName}</strong><div class="meta">${item.styleId} / ${item.healthLabel}</div><div class="meta">曝光 ${item.impressions} 点击 ${item.clicks}</div></div>`).join("")}</div>`)}
  `;
}

async function loadStyles() {
  const data = await api("/admin/styles");
  view.innerHTML = data.items.map(item => card(
    item.name,
    `<div class="metric">${item.price}</div><p>${item.vibe}</p>`,
    `<p class="meta">${item.id} / ${item.status} / ${item.tags.join("、")}</p>`
  )).join("");
}

async function loadTrends() {
  const data = await api("/admin/trends/recommendations");
  view.innerHTML = data.items.map(item => card(
    item.type,
    `<strong>${item.candidateName || item.targetStyleId || "未命名"}</strong><p>${item.triggerReason}</p>`,
    `<p class="meta">状态 ${item.status} / 置信度 ${item.confidenceScore}</p>`
  )).join("");
}

async function loadRequests() {
  const data = await api("/admin/requests");
  view.innerHTML = data.items.length
    ? data.items.map(item => card(
        item.requestedAction,
        `<strong>${item.styleId}</strong><p>${item.reason || "无备注"}</p>`,
        `<p class="meta">${item.storeId || "-"} / ${item.status}</p>`
      )).join("")
    : card("商家申请", "<p>暂无申请</p>");
}

async function loadMerchant() {
  const data = await api("/admin/merchants/me/dashboard");
  view.innerHTML = `
    ${card("商家门店", `<strong>${data.store.name}</strong><p>${data.store.id}</p>`, `<p class="meta">可预约 ${data.store.isAcceptingBookings}</p>`)}
    ${card("商家概览", `<div class="metric">${data.summary.bookingCount}</div>`, `<p class="meta">待处理申请 ${data.summary.pendingRequestCount} / 可售款 ${data.summary.listingCount}</p>`)}
  `;
}

async function loadView(name) {
  if (name === "overview") return loadOverview();
  if (name === "styles") return loadStyles();
  if (name === "trends") return loadTrends();
  if (name === "requests") return loadRequests();
  if (name === "merchant") return loadMerchant();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await login(document.getElementById("email").value, document.getElementById("password").value);
  } catch (error) {
    alert(error.message);
  }
});

nav.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  if (target.id === "logout") {
    localStorage.removeItem("nailmind_admin_token");
    state.token = "";
    location.reload();
    return;
  }
  if (target.dataset.view) {
    try {
      await loadView(target.dataset.view);
    } catch (error) {
      alert(error.message);
    }
  }
});

async function bootstrap() {
  if (!state.token) return;
  try {
    const data = await api("/admin/auth/me");
    renderWhoAmI(data.user);
    await loadView("overview");
  } catch {
    localStorage.removeItem("nailmind_admin_token");
  }
}

bootstrap();
