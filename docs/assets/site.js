const filters = document.querySelector("#filters");
const taskQuery = document.querySelector("#task-query");
const scoreFilter = document.querySelector("#score-filter");
const count = document.querySelector("#result-count");
const table = document.querySelector("#table-wrap");
const taskRows = document.querySelector("#task-rows");

function cell(row, value, className = "") {
  const element = row.insertCell();
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

function showResults(results) {
  const query = taskQuery.value.trim().toLowerCase();
  const score = scoreFilter.value;
  const shown = results.filter(result =>
    result.task.toLowerCase().includes(query) && (score === "" || String(result.score) === score)
  );
  const fragment = document.createDocumentFragment();

  for (const result of shown) {
    const row = document.createElement("tr");
    cell(row, result.task);
    cell(row, result.verdict, result.score === 1 ? "passed" : "failed");
    const details = Number.isInteger(result.passed) && Number.isInteger(result.total);
    cell(row, details ? `${result.passed} / ${result.total}` : "—");
    fragment.append(row);
  }

  if (shown.length === 0) {
    const row = document.createElement("tr");
    cell(row, "没有符合条件的题目。").colSpan = 3;
    fragment.append(row);
  }

  taskRows.replaceChildren(fragment);
  count.textContent = `显示 ${shown.length} / ${results.length} 题`;
}

async function loadResults() {
  filters.hidden = false;
  count.textContent = "正在加载逐题成绩…";
  try {
    const response = await fetch("benchmark/results.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const results = await response.json();
    showResults(results);
    taskQuery.addEventListener("input", () => showResults(results));
    scoreFilter.addEventListener("change", () => showResults(results));
    table.hidden = false;
  } catch {
    count.textContent = "逐题成绩加载失败，可以下载 CSV 或 Excel。";
    taskQuery.disabled = true;
    scoreFilter.disabled = true;
  }
}

loadResults();
