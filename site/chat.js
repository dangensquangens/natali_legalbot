const base = window.LEGALBOT_API_BASE.replace(/\/+$/, "");
const conversation = document.querySelector("#conversation");
const form = document.querySelector("#question-form");
const question = document.querySelector("#question");
const send = document.querySelector("#send");
const topics = document.querySelector("#topics");
let busy = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function appendMessage(text, role) {
  const message = element("article", "", "message " + role);
  message.append(element("p", text));
  conversation.append(message);
  return message;
}

function addLinks(container, title, entries) {
  if (!entries.length) return;
  container.append(element("h3", title));
  const list = element("ul", "", "sources");
  for (const entry of entries) {
    const row = element("li");
    const link = element("a", entry.title);
    link.href = entry.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    row.append(link);
    if (entry.explanation) row.append(element("p", entry.explanation));
    list.append(row);
  }
  container.append(list);
}

function addLegalNorms(container, norms) {
  const section = element("section", "", "legal-norms");
  section.append(element("h3", "Правовая норма"));
  for (const norm of norms) {
    const disclosure = element("details");
    const summary = element("summary", norm.title);
    const quote = element("blockquote", norm.text);
    quote.setAttribute("cite", norm.url);
    const link = element("a", "Открыть статью в источнике");
    link.href = norm.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    disclosure.append(summary, link, quote);
    section.append(disclosure);
  }
  container.append(section);
}

function choiceButton(choice, useTitle = false) {
  const button = element("button", useTitle ? choice.title : choice.example, "choice");
  button.type = "button";
  button.addEventListener("click", async () => {
    if (busy) return;
    question.focus({preventScroll: true});
    await ask(choice.example, {card_id: choice.id});
  });
  return button;
}

async function loadCatalog() {
  try {
    const catalog = window.LEGALBOT_LOCAL
      ? await window.LEGALBOT_LOCAL.catalog()
      : await request("/api/catalog");
    topics.replaceChildren();
    for (const topic of catalog.topics) {
      const group = element("details", "", "topic");
      group.append(element("summary", topic.name));
      for (const choice of topic.examples) group.append(choiceButton(choice));
      topics.append(group);
    }
  } catch {
    topics.textContent = "Не удалось загрузить темы. Обновите страницу, чтобы повторить попытку.";
  } finally {
    topics.setAttribute("aria-busy", "false");
  }
}

async function request(path, payload) {
  const options = payload ? {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  } : undefined;
  const response = await fetch(base + path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Сервис временно недоступен.");
  return result;
}

async function ask(text, payload) {
  if (busy) return;
  busy = true;
  send.disabled = true;
  appendMessage(text, "user");
  const reply = appendMessage("Ищу в базе…", "bot");
  let failed = false;
  try {
    const result = window.LEGALBOT_LOCAL
      ? await window.LEGALBOT_LOCAL.ask(payload)
      : await request("/api/ask", payload);
    if (result.status === "answer") {
      const card = result.card;
      reply.replaceChildren(
        element("p", card.topic, "category"),
        element("h2", card.title),
        ...card.answer.split("\n\n").map((paragraph) => element("p", paragraph, "answer"))
      );
      addLegalNorms(reply, card.sources);
      addLinks(reply, "Пояснения ведомств", card.explanations);
    } else {
      reply.replaceChildren(element("p", result.message));
      for (const choice of result.choices || []) reply.append(choiceButton(choice, true));
    }
  } catch (error) {
    failed = true;
    const message = error instanceof TypeError || error instanceof SyntaxError
      ? "Не удалось загрузить данные. Попробуйте отправить вопрос ещё раз."
      : error.message;
    reply.replaceChildren(element("p", message));
  } finally {
    busy = false;
    send.disabled = false;
    const replyTop = reply.getBoundingClientRect().top;
    const visibleBottom = Math.min(innerHeight, form.getBoundingClientRect().top);
    if (replyTop < 0 || replyTop > visibleBottom - 80) {
      reply.scrollIntoView({block: "start"});
    }
  }
  return !failed;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const text = question.value.trim();
  if (text.length < 3) {
    question.setCustomValidity("Введите хотя бы три символа.");
    question.reportValidity();
    return;
  }
  question.value = "";
  const answered = await ask(text, {question: text});
  if (!answered && !question.value) question.value = text;
});

question.addEventListener("input", () => question.setCustomValidity(""));
question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

loadCatalog();
