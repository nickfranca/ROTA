const state = {
  year: "",
  years: [],
  summary: null,
};

const number = new Intl.NumberFormat("pt-BR");
const compact = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const monthFormatter = new Intl.DateTimeFormat("pt-BR", { month: "short" });

const $ = (selector) => document.querySelector(selector);

async function api(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== "" && value != null),
  );
  const response = await fetch(`${path}${query.size ? `?${query}` : ""}`);
  if (!response.ok) throw new Error(`API respondeu ${response.status}`);
  return response.json();
}

function setServiceLinks() {
  const host = window.location.hostname || "localhost";
  document.querySelectorAll(".service-link").forEach((link) => {
    const port = link.dataset.port;
    const path = link.dataset.path || "";
    link.href = `${window.location.protocol}//${host}:${port}${path}`;
    link.target = "_blank";
    link.rel = "noopener";
  });
}

function initPresentation() {
  const slides = [...document.querySelectorAll(".presentation-slide")];
  const counter = $("#slide-counter");
  const title = $("#slide-title");
  const previous = $("#previous-slide");
  const next = $("#next-slide");
  let activeIndex = 0;

  function updateControls(index) {
    activeIndex = Math.max(0, Math.min(index, slides.length - 1));
    counter.textContent = `${String(activeIndex + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;
    title.textContent = slides[activeIndex].dataset.title || "Apresentação";
    previous.disabled = activeIndex === 0;
    next.disabled = activeIndex === slides.length - 1;
  }

  function goTo(index) {
    const target = Math.max(0, Math.min(index, slides.length - 1));
    slides[target].scrollIntoView({ behavior: "smooth", block: "start" });
    updateControls(target);
  }

  previous.addEventListener("click", () => goTo(activeIndex - 1));
  next.addEventListener("click", () => goTo(activeIndex + 1));

  document.addEventListener("keydown", (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (["ArrowDown", "ArrowRight", "PageDown"].includes(event.key)) {
      event.preventDefault();
      goTo(activeIndex + 1);
    }
    if (["ArrowUp", "ArrowLeft", "PageUp"].includes(event.key)) {
      event.preventDefault();
      goTo(activeIndex - 1);
    }
    if (event.key === "Home") goTo(0);
    if (event.key === "End") goTo(slides.length - 1);
  });

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      updateControls(slides.indexOf(visible.target));
    },
    { threshold: [0.25, 0.5, 0.7] },
  );

  slides.forEach((slide) => observer.observe(slide));
  updateControls(0);
}

function daysBetween(start, end) {
  if (!start || !end) return 1;
  const first = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  return Math.max(1, Math.round((last - first) / 86400000) + 1);
}

function updateSummary(summary) {
  state.summary = summary;
  const accidents = Number(summary.acidentes || 0);
  const people = Number(summary.pessoas || 0);
  const injured = Number(summary.feridos || 0);
  const deaths = Number(summary.mortos || 0);
  const days = daysBetween(summary.primeira_data, summary.ultima_data);

  $("#metric-accidents").textContent = number.format(accidents);
  $("#metric-people").textContent = number.format(people);
  $("#metric-injured").textContent = number.format(injured);
  $("#metric-deaths").textContent = number.format(deaths);
  $("#metric-daily").textContent = `${number.format(Math.round(accidents / days))} por dia`;
  $("#injured-rate").textContent = people
    ? `${((injured / people) * 100).toFixed(1).replace(".", ",")}% das pessoas envolvidas.`
    : "Sem registros no período.";
  $("#death-rate").textContent = accidents
    ? `${((deaths / accidents) * 100).toFixed(1).replace(".", ",")} mortes a cada 100 acidentes.`
    : "Sem registros no período.";
  $("#map-total").textContent = compact.format(accidents);

  const lastDate = summary.ultima_data
    ? new Date(`${summary.ultima_data}T00:00:00`)
    : null;
  $("#map-update").textContent = lastDate
    ? `${monthFormatter.format(lastDate)} ${lastDate.getFullYear()}`
    : "—";
  $("#period-label").textContent =
    summary.primeira_data && summary.ultima_data
      ? `${summary.primeira_data.slice(0, 4)} — ${summary.ultima_data.slice(0, 4)}`
      : "Período indisponível";
}

function renderYears(years) {
  state.years = years.map((item) => item.ano);
  const container = $("#year-options");
  container.innerHTML = `
    <button class="active" data-year="">Todos os anos</button>
    ${state.years.map((year) => `<button data-year="${year}">${year}</button>`).join("")}
  `;
  container.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button || button.classList.contains("active")) return;
    container.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.year = button.dataset.year;
    await refreshAnalysis();
  });
}

function linePath(points) {
  return points.map(([x, y], index) => `${index ? "L" : "M"} ${x} ${y}`).join(" ");
}

function renderMonthly(data) {
  const container = $("#monthly-chart");
  if (!data.length) {
    container.innerHTML = '<div class="error-state">Nenhum registro neste período.</div>';
    return;
  }

  const width = 820;
  const height = 300;
  const padding = { top: 20, right: 20, bottom: 36, left: 48 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const maxAccidents = Math.max(...data.map((item) => Number(item.acidentes)), 1);
  const maxDeaths = Math.max(...data.map((item) => Number(item.mortos)), 1);
  const step = data.length > 1 ? innerWidth / (data.length - 1) : innerWidth;

  const accidentPoints = data.map((item, index) => [
    padding.left + index * step,
    padding.top + innerHeight - (Number(item.acidentes) / maxAccidents) * innerHeight,
  ]);
  const deathPoints = data.map((item, index) => [
    padding.left + index * step,
    padding.top + innerHeight - (Number(item.mortos) / maxDeaths) * innerHeight,
  ]);
  const area = `${linePath(accidentPoints)} L ${padding.left + innerWidth} ${padding.top + innerHeight} L ${padding.left} ${padding.top + innerHeight} Z`;

  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const y = padding.top + innerHeight * ratio;
      const label = number.format(Math.round(maxAccidents * (1 - ratio)));
      return `
        <line class="grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" />
        <text class="axis-label" x="0" y="${y + 4}">${label}</text>
      `;
    })
    .join("");

  const labels = data
    .map((item, index) => {
      const date = new Date(`${item.mes}T00:00:00`);
      const label = data.length > 14
        ? `${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getFullYear()).slice(2)}`
        : monthFormatter.format(date).replace(".", "");
      return `<text class="axis-label" text-anchor="middle" x="${padding.left + index * step}" y="${height - 8}">${label}</text>`;
    })
    .join("");

  const points = accidentPoints
    .map(([x, y], index) => `
      <circle
        class="chart-point"
        cx="${x}" cy="${y}" r="4"
        data-month="${data[index].mes}"
        data-accidents="${data[index].acidentes}"
        data-deaths="${data[index].mortos}"
      />
    `)
    .join("");

  container.innerHTML = `
    <svg class="line-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#8b7cff" stop-opacity=".2" />
          <stop offset="1" stop-color="#8b7cff" stop-opacity="0" />
        </linearGradient>
      </defs>
      ${grid}
      <path class="area-path" d="${area}" />
      <path class="accident-path" d="${linePath(accidentPoints)}" />
      <path class="death-path" d="${linePath(deathPoints)}" />
      ${points}
      ${labels}
    </svg>
  `;

  const tooltip = $("#chart-tooltip");
  container.querySelectorAll(".chart-point").forEach((point) => {
    point.addEventListener("mouseenter", (event) => {
      const date = new Date(`${point.dataset.month}T00:00:00`);
      tooltip.innerHTML = `
        <strong>${monthFormatter.format(date)} ${date.getFullYear()}</strong><br>
        ${number.format(point.dataset.accidents)} acidentes<br>
        ${number.format(point.dataset.deaths)} mortes
      `;
      tooltip.classList.add("visible");
      moveTooltip(event);
    });
    point.addEventListener("mousemove", moveTooltip);
    point.addEventListener("mouseleave", () => tooltip.classList.remove("visible"));
  });
}

function moveTooltip(event) {
  const tooltip = $("#chart-tooltip");
  tooltip.style.left = `${event.clientX}px`;
  tooltip.style.top = `${event.clientY}px`;
}

function renderCauses(data) {
  const container = $("#causes-chart");
  const top = data.slice(0, 6);
  const max = Math.max(...top.map((item) => Number(item.acidentes)), 1);
  container.innerHTML = top
    .map((item) => `
      <div class="bar-row" title="${item.causa}">
        <div class="bar-copy">
          <span>${item.causa || "Não informado"}</span>
          <strong>${number.format(item.acidentes)}</strong>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${(Number(item.acidentes) / max) * 100}%"></div>
        </div>
      </div>
    `)
    .join("");
}

function renderStates(data) {
  const container = $("#states-list");
  container.innerHTML = data
    .slice(0, 5)
    .map((item, index) => `
      <div class="state-row">
        <span class="state-rank">${String(index + 1).padStart(2, "0")}</span>
        <div class="state-name">
          <strong>${item.uf || "N/I"}</strong>
          <span>${number.format(item.mortos || 0)} mortes registradas</span>
        </div>
        <div class="state-value">
          <strong>${number.format(item.acidentes)}</strong>
          <span>acidentes</span>
        </div>
      </div>
    `)
    .join("");
}

function renderLoads(data) {
  const container = $("#load-table");
  container.innerHTML = data
    .slice(0, 6)
    .map((item) => `
      <div class="load-row">
        <strong>${item.ano_fonte}</strong>
        <span>${item.arquivo.replace(".csv", "")}</span>
        <span class="load-speed">${number.format(Math.round(item.linhas_por_segundo))} lin/s</span>
        <span class="load-time">${String(item.duracao_segundos).replace(".", ",")} s</span>
      </div>
    `)
    .join("");
}

function showAnalysisError() {
  ["#monthly-chart", "#causes-chart", "#states-list"].forEach((selector) => {
    $(selector).innerHTML = '<div class="error-state">Não foi possível consultar a API.</div>';
  });
  $("#data-status").innerHTML = "<i style='background:#ff6f68'></i> API indisponível";
}

async function refreshAnalysis() {
  $("#data-status").innerHTML = "<i></i> Atualizando";
  const params = state.year ? { ano: state.year } : {};
  try {
    const [summary, monthly, causes, states] = await Promise.all([
      api("/api/resumo", params),
      api("/api/serie-mensal", params),
      api("/api/top-causas", { ...params, limite: 6 }),
      api("/api/por-uf", params),
    ]);
    updateSummary(summary);
    renderMonthly(monthly);
    renderCauses(causes);
    renderStates(states);
    $("#data-status").innerHTML = "<i></i> Base conectada";
  } catch (error) {
    console.error(error);
    showAnalysisError();
  }
}

async function start() {
  setServiceLinks();
  initPresentation();
  try {
    const [years, loads] = await Promise.all([
      api("/api/por-ano"),
      api("/api/cargas"),
    ]);
    renderYears(years);
    renderLoads(loads);
    await refreshAnalysis();
  } catch (error) {
    console.error(error);
    showAnalysisError();
    $("#load-table").innerHTML = '<div class="error-state">Histórico indisponível.</div>';
  }
}

start();
