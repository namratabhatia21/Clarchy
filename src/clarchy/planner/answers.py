"""Answers to a plan's open questions, and corrections to its assumptions.

People answer in their own words ("50k", "yes", "Frankfurt"). Each answer becomes a plain
statement the planners read like the rest of the brief ("About 50k users use it each
month."), appended under "Answers to earlier questions". Questions that were answered are
not asked again.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

from clarchy.ingest import Document
from clarchy.planner.rules import BUDGET, NUM, USERS
from clarchy.spec import ArchitectureSpec

MAX_ANSWERS = 30
MAX_LENGTH = 500
HEADING = "Answers to earlier questions:"

# What a question or assumption is about, from the wording the planners use.
TOPICS = [
    (r"where are most users|no region was mentioned|region", "region"),
    (r"how many people|user numbers|how many users", "users"),
    (r"budget", "budget"),
    (r"card payments|pci", "pci"),
    (r"hipaa|health information", "hipaa"),
    (r"gdpr|privacy", "gdpr"),
    (r"availability", "availability"),
]
YES = re.compile(r"^\s*(yes|y|yeah|yep|true|correct|it does|they do|we do|applies)\b", re.I)
NO = re.compile(r"^\s*(no|n|nope|false|none|not|it does not|they do not|we do not)\b", re.I)
FIRST_NUMBER = re.compile(NUM, re.I)

# Statements for yes and no that don't repeat the question's keywords on a "no", so a
# "No" to "Does HIPAA apply?" cannot read as a mention of HIPAA.
YES_NO = {
    "pci": (
        "We take card payments directly, so PCI DSS applies.",
        "Card payments go through a payment provider; we never handle card numbers.",
    ),
    "hipaa": (
        "The app stores health information, so HIPAA applies.",
        "The app stores no regulated health information.",
    ),
    "gdpr": ("GDPR applies to our users.", "No special data-protection regulations apply."),
}


@dataclass(frozen=True)
class Answer:
    question: str
    answer: str


class AnswerError(ValueError):
    pass


def parse_answers(raw: Any) -> list[Answer]:
    """From the request: a JSON string or a list of {question, answer} objects."""
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AnswerError("answers must be a JSON list") from exc
    if not isinstance(raw, list) or len(raw) > MAX_ANSWERS:
        raise AnswerError(f"answers must be a list of at most {MAX_ANSWERS} items")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            raise AnswerError("each answer needs a question and an answer")
        question = str(item.get("question") or "").strip()[:MAX_LENGTH]
        answer = str(item.get("answer") or "").strip()[:MAX_LENGTH]
        if answer:
            out.append(Answer(question, answer))
    return out


def topic(text: str) -> str | None:
    lowered = text.lower()
    return next((name for pattern, name in TOPICS if re.search(pattern, lowered)), None)


def statement(item: Answer) -> str:
    """One requirement sentence for an answer."""
    answer = item.answer.strip().rstrip(".")
    answer = answer[:1].upper() + answer[1:]
    about = topic(item.question) if item.question else None
    number = FIRST_NUMBER.search(answer)
    if about in YES_NO:
        yes, no = YES_NO[about]
        if YES.match(answer):
            return yes
        if NO.match(answer):
            return no
        return f"{answer}."
    if about == "users" and not USERS.search(answer) and number:
        return f"About {number.group(0).strip()} users use it each month. {answer}."
    if about == "budget" and not BUDGET.search(answer) and number:
        per = "year" if re.search(r"\b(year|annual|yearly)\b", answer, re.I) else "month"
        return f"The budget is ${number.group(0).strip()} a {per}."
    if about == "region":
        return f"Most users are in {answer}."
    if about == "availability" and number and number.group(0).startswith("99"):
        return f"It needs {number.group(0).strip()}% availability."
    if not item.question:
        return f"{answer}."
    return f"{item.question.rstrip('?. ')}: {answer}."


def with_answers(doc: Document, answers: list[Answer]) -> Document:
    """The document with the answers appended, so quotes from them count as evidence."""
    if not answers:
        return doc
    block = "\n".join(f"- {statement(a)}" for a in answers)
    noun = "answer" if len(answers) == 1 else "answers"
    return replace(
        doc,
        text=f"{doc.text.rstrip()}\n\n{HEADING}\n{block}\n",
        details=[*doc.details, f"{len(answers)} {noun}"],
    )


def _key(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def drop_answered(spec: ArchitectureSpec, answers: list[Answer]) -> ArchitectureSpec:
    """Removes questions that were answered and assumptions that were corrected."""
    asked = {_key(a.question) for a in answers if a.question}
    if not asked:
        return spec
    return spec.model_copy(
        update={
            "open_questions": [q for q in spec.open_questions if _key(q) not in asked],
            "assumptions": [a for a in spec.assumptions if _key(a) not in asked],
        }
    )
