const topics = [
  "全部",
  "工业界",
  "学术论文",
  "学术新闻",
  "LLM",
  "VLM",
  "AI Agent",
  "Skills / MCP",
  "RL",
  "AI4Health",
  "GNN",
  "SSL",
  "Saved"
];

const state = {
  digest: null,
  topic: "全部",
  query: "",
  mode: "today",
  feedback: JSON.parse(localStorage.getItem("aiBriefingFeedback") || "{}")
};

function saveFeedback() {
  localStorage.setItem("aiBriefingFeedback", JSON.stringify(state.feedback));
}

function normalizeTopic(topic) {
  const map = {
    "Agent Skills / MCP / Tool Use": "Skills / MCP",
    "Graph Neural Network": "GNN",
    "Self-Supervised Learning": "SSL",
    "AI for Health": "AI4Health",
    "Medical AI": "AI4Health"
  };
  return map[topic] || topic;
}

async function loadDigest() {
  const response = await fetch("../data/digests/daily.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Digest not found. Run pipeline/ai_briefing.py first.");
  state.digest = await response.json();
  render();
}

function renderTopics() {
  const nav = document.getElementById("topicNav");
  nav.innerHTML = topics
    .map((topic) => `<button class="${state.topic === topic ? "active" : ""}" data-topic="${topic}">${topic}</button>`)
    .join("");
  nav.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.topic = button.dataset.topic;
      render();
    });
  });
}

function itemMatches(item) {
  const tags = (item.topics || []).map(normalizeTopic);
  const haystack = [
    item.title,
    item.title_zh,
    item.source,
    item.category,
    item.why_it_matters,
    ...(item.topics || [])
  ].join(" ").toLowerCase();

  if (state.topic === "Saved") {
    return state.feedback[item.id]?.saved;
  }
  if (state.topic !== "全部" && !tags.includes(state.topic) && item.category !== state.topic) {
    return false;
  }
  return !state.query || haystack.includes(state.query.toLowerCase());
}

function filtered(items) {
  let result = items.filter(itemMatches);
  if (state.mode === "papers") result = result.filter((item) => item.category === "学术论文");
  if (state.mode === "hot") result = result.slice().sort((a, b) => (b.signals?.hotness || 0) - (a.signals?.hotness || 0));
  if (state.mode === "latest") result = result.slice().sort((a, b) => (b.published || "").localeCompare(a.published || ""));
  if (state.mode === "mine") result = result.filter((item) => state.feedback[item.id]?.saved || state.feedback[item.id]?.read);
  return result;
}

function renderItem(item, index) {
  const fb = state.feedback[item.id] || {};
  const summary = (item.summary_zh || []).map((line) => `<li>${line}</li>`).join("");
  const tags = (item.topics || []).map((topic) => `<span class="chip">${normalizeTopic(topic)}</span>`).join("");
  const citations = item.citations || {};
  const gs = `https://scholar.google.com/scholar?q=${encodeURIComponent(item.title)}`;
  const sourceUrl = item.url || gs;

  return `
    <article class="item-card" data-id="${item.id}">
      <div class="item-topline">
        <span class="rank">#${index + 1}</span>
        <span class="source">${item.source || "Unknown"} · ${item.published || "--"} · S2 ${citations.semantic_scholar ?? "?"} · OA ${citations.openalex ?? "?"}</span>
      </div>
      <h3>${item.title}</h3>
      <div class="zh-title">${item.title_zh || item.title}</div>
      <ul class="summary">${summary}</ul>
      <div class="chips">${tags}</div>
      <p class="why"><strong>为什么值得看：</strong>${item.why_it_matters || "与当前 AI 研究前沿相关。"}</p>
      <p class="action"><strong>Action：</strong>${item.action || "收藏周末精读"}</p>
      <div class="card-actions">
        <a href="${sourceUrl}" target="_blank" rel="noreferrer">原文</a>
        <a href="${gs}" target="_blank" rel="noreferrer">Google Scholar</a>
        <button class="${fb.saved ? "active" : ""}" data-feedback="saved">${fb.saved ? "已收藏" : "收藏"}</button>
        <button class="${fb.read ? "active" : ""}" data-feedback="read">${fb.read ? "已读" : "标记已读"}</button>
        <button class="${fb.hidden ? "active" : ""}" data-feedback="hidden">${fb.hidden ? "已隐藏" : "不感兴趣"}</button>
      </div>
    </article>
  `;
}

function attachFeedbackHandlers() {
  document.querySelectorAll("[data-feedback]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".item-card");
      const id = card.dataset.id;
      const key = button.dataset.feedback;
      state.feedback[id] = state.feedback[id] || {};
      state.feedback[id][key] = !state.feedback[id][key];
      saveFeedback();
      render();
    });
  });
}

function render() {
  if (!state.digest) return;
  renderTopics();

  const topItems = filtered(state.digest.top_10 || []).filter((item) => !state.feedback[item.id]?.hidden);
  const moreItems = filtered(state.digest.more_20 || []).filter((item) => !state.feedback[item.id]?.hidden);
  const allItems = [...(state.digest.top_10 || []), ...(state.digest.more_20 || [])];
  const primarySources = new Set(allItems.filter((item) => item.source_tier === 1).map((item) => item.source));

  document.getElementById("digestTitle").textContent = state.digest.title || "Daily Briefing";
  document.getElementById("topCount").textContent = topItems.length;
  document.getElementById("moreCount").textContent = moreItems.length;
  document.getElementById("sourceCount").textContent = primarySources.size;
  document.getElementById("updatedAt").textContent = (state.digest.generated_at || "").slice(0, 10);

  document.getElementById("topList").innerHTML = topItems.map(renderItem).join("") || `<p class="muted">No matching must-read items.</p>`;
  document.getElementById("moreList").innerHTML = moreItems.map(renderItem).join("") || `<p class="muted">No matching scan-list items.</p>`;
  attachFeedbackHandlers();
}

document.getElementById("searchInput").addEventListener("input", (event) => {
  state.query = event.target.value.trim();
  render();
});

document.querySelectorAll(".bottom-nav button").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll(".bottom-nav button").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    render();
  });
});

loadDigest().catch((error) => {
  document.getElementById("topList").innerHTML = `<p class="muted">${error.message}</p>`;
});
