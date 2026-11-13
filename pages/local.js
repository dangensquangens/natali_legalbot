(() => {
  const database = fetch("./knowledge.json").then((response) => {
    if (!response.ok) throw new Error("Не удалось загрузить правовую базу.");
    return response.json();
  });

  function words(text) {
    return text.toLowerCase().replaceAll("ё", "е").match(/[а-яa-z0-9]+\*?/g) || [];
  }

  function matches(question, expression) {
    const terms = words(expression);
    if (!terms.length) return false;
    for (let start = 0; start <= question.length - terms.length; start++) {
      const matched = terms.every((term, offset) => {
        const word = question[start + offset];
        return term.endsWith("*") ? word.startsWith(term.slice(0, -1)) : word === term;
      });
      if (matched) return true;
    }
    return false;
  }

  function findCards(text, cards) {
    const question = words(text).map((word) => word.replace(/\*$/, ""));
    let best = [];
    let bestScore = 0;
    for (const card of cards) {
      let score = 0;
      for (const rule of card.rules) {
        if (rule.every((group) => group.some((term) => matches(question, term)))) {
          score = Math.max(score, rule.length);
        }
      }
      if (score > bestScore) {
        bestScore = score;
        best = [card];
      } else if (score && score === bestScore) {
        best.push(card);
      }
    }
    return best;
  }

  function choice({id, title, example}) {
    return {id, title, example};
  }

  window.LEGALBOT_LOCAL = {
    async catalog() {
      const {topics, cards} = await database;
      return {
        topics: topics.map((name) => ({
          name,
          examples: cards.filter((card) => card.topic === name).map(choice),
        })),
      };
    },
    async ask({question, card_id}) {
      const {cards} = await database;
      const found = card_id
        ? cards.filter((card) => card.id === card_id)
        : findCards(question, cards);
      if (found.length === 1) return {status: "answer", card: found[0]};
      if (found.length > 1) {
        return {
          status: "clarify",
          message: "Подходит несколько ситуаций. Уточните, о какой из них ваш вопрос.",
          choices: found.map(choice),
        };
      }
      return {
        status: "unmatched",
        message: "В базе пока нет точного ответа. Уточните, что произошло, или выберите пример по своей теме.",
      };
    },
  };
})();
