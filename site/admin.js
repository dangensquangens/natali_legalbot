const base = window.LEGALBOT_API_BASE.replace(/\/+$/, "");
const form = document.querySelector("#stats-form");
const password = document.querySelector("#password");
const status = document.querySelector("#status");
const stats = document.querySelector("#stats");
const submit = form.querySelector("button");

function chart(title, rows) {
  const section = document.createElement("section");
  const heading = document.createElement("h2");
  heading.textContent = title;
  section.append(heading);
  if (rows.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "Пока нет обращений.";
    section.append(empty);
    return section;
  }
  const max = Math.max(1, ...rows.map((row) => row[1]));
  for (const [label, count] of rows) {
    const row = document.createElement("div");
    row.className = "chart-row";
    const name = document.createElement("span");
    name.textContent = label;
    const bar = document.createElement("meter");
    bar.max = max;
    bar.value = count;
    bar.setAttribute("aria-label", label);
    const number = document.createElement("span");
    number.textContent = count;
    row.append(name, bar, number);
    section.append(row);
  }
  return section;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submit.disabled) return;
  stats.hidden = true;
  stats.replaceChildren();
  submit.disabled = true;
  status.textContent = "Загружаем статистику…";
  try {
    const response = await fetch(base + "/api/statistics", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({password: password.value}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    const total = document.createElement("p");
    total.textContent = "Всего запросов: " + data.total;
    stats.append(
      total,
      chart("Результаты поиска", [
        ["Найден ответ", data.answered],
        ["Потребовалось уточнение", data.clarified],
        ["Ответа в базе нет", data.unmatched],
      ]),
      chart("Запросы по темам", data.topics),
      chart("Запросы по дням", data.days),
      chart("Популярные ситуации", data.cases)
    );
    stats.hidden = false;
    status.textContent = "";
  } catch (error) {
    status.textContent = error instanceof TypeError || error instanceof SyntaxError
      ? "Статистика временно недоступна."
      : error.message;
  } finally {
    password.value = "";
    submit.disabled = false;
  }
});
