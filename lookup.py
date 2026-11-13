"""Подбор правовых карточек по словам и фразам из вопроса."""

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    explanation: str = ""


@dataclass(frozen=True)
class Card:
    id: str
    topic: str
    title: str
    example: str
    answer: str
    sources: tuple[Source, ...]
    # Правило срабатывает, если совпало хотя бы одно выражение в каждой группе.
    rules: tuple[tuple[tuple[str, ...], ...], ...]
    explanations: tuple[Source, ...] = ()
    cases: tuple[Source, ...] = ()


def _words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[а-яa-z0-9]+\*?", text.casefold().replace("ё", "е")))


def _matches(question: tuple[str, ...], expression: str) -> bool:
    terms = _words(expression)
    if not terms:
        return False

    for start in range(len(question) - len(terms) + 1):
        fragment = question[start:start + len(terms)]
        if all(
            word.startswith(term[:-1]) if term.endswith("*") else word == term
            for word, term in zip(fragment, terms)
        ):
            return True
    return False


def find_cards(question: str, cards: Sequence[Card]) -> tuple[Card, ...]:
    """Возвращает самые подходящие карточки. При равенстве нужен выбор пользователя."""
    words = tuple(word.rstrip("*") for word in _words(question))
    best_score = 0
    matches = []

    for card in cards:
        score = max(
            (
                len(rule)
                for rule in card.rules
                if all(any(_matches(words, expression) for expression in group) for group in rule)
            ),
            default=0,
        )
        if score > best_score:
            best_score = score
            matches = [card]
        elif score and score == best_score:
            matches.append(card)

    return tuple(matches)
