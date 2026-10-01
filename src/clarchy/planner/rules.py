"""Rule-based planner: requirements text to an architecture spec, without AI.

It reads numbers (users, requests per second, data size, availability, budget), the region,
compliance regimes and about twenty needs (uploads, payments, search over documents,
background jobs, real-time events, ...) from the text, then assembles a design with
standard wiring. Every component keeps the exact sentence that triggered it as evidence,
so the result is explainable, and anything it had to guess is listed as an assumption or
an open question. It is a fast first draft and the fallback when no AI model is set up.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from clarchy.delivery import add_delivery
from clarchy.spec import ArchitectureSpec, Component, Edge, Provenance, Requirements
from clarchy.workflows import generate_workflows

FLAGS = re.IGNORECASE

# --- reading the text ---------------------------------------------------------------

NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|million|thousand|lakh|crore)?\b"
MULTIPLIER = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "lakh": 1e5, "crore": 1e7}

USERS = re.compile(
    NUM + r"\s*\+?\s*(?:[a-z][a-z-]*\s+){0,2}?"
    r"(users|customers|visitors|shoppers|members|students|employees|people|subscribers|"
    r"players|patients|drivers|riders|learners)",
    FLAGS,
)
RATE = re.compile(
    NUM + r"\s*(?:requests|req|calls|transactions|orders|messages|events|uploads)\s*"
    r"(?:per|/|a|an|each)\s*(second|sec|s|minute|min|hour|day)\b",
    FLAGS,
)
RPS = re.compile(NUM + r"\s*(rps|qps|tps)\b", FLAGS)
SIZE = re.compile(NUM + r"\s*(pb|tb|gb|petabytes?|terabytes?|gigabytes?)\b", FLAGS)
GROWTH = re.compile(
    NUM + r"\s*(pb|tb|gb|petabytes?|terabytes?|gigabytes?)\s*(?:of new data\s*)?"
    r"(?:per|a|/|each|every)\s*(day|week|month|year)",
    FLAGS,
)
AVAILABILITY = re.compile(r"(99(?:\.\d{1,3})?)\s*%", FLAGS)
HIGH_AVAILABILITY = re.compile(
    r"\b(high(ly)? availab\w*|mission[- ]critical|no downtime|24/7|always on)\b", FLAGS
)
DEVELOPERS = re.compile(
    NUM + r"\s*(?:software |full[- ]stack |backend |frontend )?"
    r"(developers|engineers|devs|programmers)\b",
    FLAGS,
)
RETENTION_WORDS = re.compile(r"\b(keep|kept|retain\w*|retention|archiv\w*|preserv\w*)\b", FLAGS)
PERIOD = re.compile(r"(\d+(?:\.\d+)?)[- ]*(years?|yrs?|months?)\b", FLAGS)
BUDGET = re.compile(r"\$\s?" + NUM + r"\s*(?:usd)?\s*(?:per|a|/)\s*(month|year)", FLAGS)

COMPLIANCE = {
    "HIPAA": r"\bhipaa\b",
    "PCI DSS": r"\bpci(?:[- ]?dss)?\b",
    "GDPR": r"\bgdpr\b",
    "SOC 2": r"\bsoc ?2\b",
    "ISO 27001": r"\biso ?27001\b",
    "FedRAMP": r"\bfedramp\b",
    "SOX": r"\b(sox|sarbanes[- ]oxley)\b",
}

# Checked in order; the first match wins.
REGIONS = [
    ("india-mumbai", r"\b(india|indian|mumbai|bengaluru|bangalore|delhi|hyderabad|chennai|pune)\b"),
    ("singapore", r"\b(singapore|south[- ]?east asia|malaysia|indonesia)\b"),
    ("sydney", r"\b(australia|australian|sydney|melbourne|new zealand)\b"),
    ("uk", r"\b(uk|united kingdom|britain|british|london|england)\b"),
    ("eu-central", r"\b(germany|german|frankfurt|berlin|munich|central europe|switzerland)\b"),
    ("eu-west", r"\b(ireland|dublin|europe|european|eu|france|paris|netherlands|spain)\b"),
    ("us-west", r"\b(us[- ]west|west coast|california|oregon|seattle|san francisco)\b"),
    ("us-east", r"\b(us|usa|u\.s\.|united states|america|north america|east coast|new york)\b"),
]

NEEDS = {
    "web": r"\b(web ?sites?|web apps?|web portal|front[- ]?end|single[- ]page|landing pages?|"
    r"browsers?|dashboards?)\b",
    "devices": r"\b(devices?|sensors?|iot|vehicles?|vans?|trucks?|machines?|meters?)\b",
    "mobile": r"\b(mobile apps?|ios|android|react native|flutter|smartphones?)\b",
    "api": r"\b(apis?|rest|graphql|backend|endpoints?|webhooks?|partners? integrat\w*)\b",
    "auth": r"\b(log ?ins?|sign[- ]?(?:in|up|on)|accounts?|authenticat\w*|sso|oauth|"
    r"user profiles?|roles? and permissions)\b",
    "files": r"\b(uploads?|uploading|images?|photos?|pictures?|videos?|media|files?|attachments?|"
    r"avatars?|recordings?)\b",
    "relational": r"\b(orders?|payments?|transactions?|invoices?|inventory|bookings?|"
    r"reservations?|relational|sql|postgres\w*|mysql|billing|accounting|catalogu?e?s?|"
    r"appointments?|enrol\w*|checkout|deposits?)\b",
    "keyvalue": r"\b(sessions?|shopping carts?|carts?|leaderboards?|key[- ]value|nosql|"
    r"chat history|conversation history|"
    r"device state|user preferences|high write)\b",
    "cache": r"\b(cach\w+|low latency|sub[- ]second|fast response|hot data|leaderboards?)\b",
    "llm": r"\b(chat ?bots?|ai assistant|assistants?|llms?|gpt|claude|generative|gen ?ai|"
    r"summari[sz]\w*|natural language|language models?|question answering|rag)\b",
    "agents": r"\b(ai agents?|agentic|langgraph|lang ?chain|crewai|autogen|multi[- ]agent|"
    r"tool[- ]calling|agents? that (?:call|use|run) tools|agent workflows?)\b",
    "gateway": r"\b(litellm|llm gateway|ai gateway|model gateway|model router|model routing|"
    r"(?:several|multiple|different) (?:llms|models|model providers)|fallback models?|"
    r"token budgets?|token quotas?|azure openai|openrouter)\b",
    "llmops": r"\b(langfuse|langsmith|llm tracing|llm observability|tracing|traces|"
    r"prompt management|prompt versions?|evals?|evaluations?|token (?:usage|costs?)|"
    r"hallucinat\w*)\b",
    "guardrails": r"\b(guardrails?|content safety|content filter\w*|prompt injection|"
    r"jailbreak\w*|toxic\w*|harmful content|pii|personal data|redact\w*)\b",
    "access": r"\b(iam|access control|least privilege|role[- ]based|rbac|access reviews?|"
    r"cloud architects?|platform team|grants? access|access requests?|privileged access|"
    r"permissions?)\b",
    "audit": r"\b(audit\w*|traceab\w*|who did what|sox|change logs?)\b",
    "encryption": r"\b(encrypt\w*|kms|customer[- ]managed keys|own keys|byok|hsm)\b",
    "backup": r"\b(backups?|disaster recovery|point[- ]in[- ]time|restores?|rpo|rto)\b",
    "archive": r"\b(archiv\w*|glacier|cold storage|retention|retain\w*|"
    r"records? (?:management|keeping))\b",
    "devenv": r"\b(codespaces|dev ?containers?|cloud (?:ide|workstations?)|"
    r"dev(?:elopment)? environments?)\b",
    "coding_ai": r"\b(copilot|claude code|cursor|amazon q developer|gemini code assist|"
    r"ai coding|coding assistants?|ai pair[- ]programm\w*)\b",
    "vector": r"\b(rag|retrieval|semantic search|embeddings?|vectors?|knowledge base|"
    r"(?:our|company|internal|policy) (?:docs|documents|documentation|wiki))\b",
    "jobs": r"\b(background|asynchronous|async|queues?|jobs?|thumbnails?|transcod\w*|"
    r"notifications?|reminders?|sms|batch processing|retries|retry|"
    r"(?:send|sends|sending) (?:an? )?e-?mails?)\b",
    "events": r"\b(event[- ]driven|webhooks?|pub/?sub|publish\w*|subscrib\w*|"
    r"integrations? with|notify other)\b",
    "workflow": r"\b(workflows?(?! management)|multi[- ]step|approval (?:workflows?|steps?|"
    r"chains?|process\w*)|second approver|sign[- ]offs?|orchestrat\w+|state machines?|sagas?)\b",
    "stream": r"\b(stream(?:s|ing)? (?:of )?(?:events|data|telemetry)|real[- ]time "
    r"(?:analytics|events|data|processing|tracking)|telemetry|clickstream|iot|sensors?|"
    r"kafka|kinesis)\b",
    "analytics": r"\b(analytics|business intelligence|bi tools?|bi\b|data warehouse|"
    r"insights|kpis?|reports? in (?:our|the) bi)\b",
    "etl": r"\b(etl|data pipelines?|transform(?:s|ations)? (?:the )?data|nightly|"
    r"data cleaning|aggregat\w+)\b",
    "containers": r"\b(containers?|containeri[sz]\w*|docker|microservices?|long[- ]running|"
    r"websockets?|streaming responses|streams? back|existing (?:app|application|service))\b",
    "kubernetes": r"\b(kubernetes|k8s|helm|keda|gitops|argo ?cd|eks|aks|gke)\b",
    "serverless": r"\b(serverless|lambda|functions?|spiky|bursty|pay[- ]per[- ]use|"
    r"scale to zero|low traffic|occasional)\b",
    "security": r"\b(secur\w+|attacks?|ddos|bots?|owasp|firewall|fraud)\b",
    "global": r"\b(global|worldwide|international|multiple countries|cdn)\b",
    "secrets_hint": r"\b(api keys?|credentials|third[- ]party|payment providers?|stripe)\b",
}

# A sentence or line; a full stop followed by a digit (99.95%) doesn't end a sentence.
SENTENCE = re.compile(r"(?:[^\n.!?]|\.(?=\d))+[.!?]?")


def _number(raw: str, unit: str | None) -> float:
    value = float(raw.replace(",", ""))
    return value * MULTIPLIER.get((unit or "").lower(), 1)


def _sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) offsets of each sentence or line."""
    return [(m.start(), m.end()) for m in SENTENCE.finditer(text) if m.group().strip()]


@dataclass
class Reading:
    text: str
    spans: list[tuple[int, int]]

    def quote(self, match: re.Match) -> str:
        """The exact sentence around a match, trimmed to about 160 characters."""
        start, end = match.start(), match.end()
        for s, e in self.spans:
            if s <= start < e:
                start, end = s, e
                break
        if end - start > 180:
            start = max(match.start() - 70, start)
            end = min(match.end() + 70, end)
        return self.text[start:end].strip(" \t,;:-•*")

    def find(self, pattern: str | re.Pattern, limit: int = 2) -> tuple[list[str], list[str]]:
        """Up to `limit` quotes and the matched words. Quotes come from the sentences with
        the most distinct matches (ties in document order); headings are not quoted."""
        regex = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, FLAGS)
        words: list[str] = []
        by_quote: dict[str, set[str]] = {}
        order: list[str] = []
        for m in regex.finditer(self.text):
            word = m.group(0).lower()
            if word not in words:
                words.append(word)
            line_start = self.text.rfind("\n", 0, m.start()) + 1
            if self.text[line_start : m.start()].lstrip().startswith("#"):
                continue
            q = self.quote(m)
            if not q:
                continue
            if q not in by_quote:
                by_quote[q] = set()
                order.append(q)
            by_quote[q].add(word)
        ranked = sorted(order, key=lambda q: (-len(by_quote[q]), order.index(q)))
        return ranked[:limit], words


# --- the plan -----------------------------------------------------------------------


@dataclass
class RulesPlan:
    name: str
    summary: str
    requirements: Requirements
    found: list[str] = field(default_factory=list)  # human-readable facts we read
    needs: dict[str, list[str]] = field(default_factory=dict)  # need -> evidence quotes
    words: dict[str, list[str]] = field(default_factory=dict)  # need -> matched words
    decisions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


# "a photo sharing app", "an internal policy assistant": a name for untitled requirements.
PRODUCT = re.compile(
    r"\b(?:a|an|the|our|my)\s+((?:[\w'-]+\s+){1,4}?(?:app|application|platform|service|site|"
    r"website|portal|system|tool|marketplace|dashboard|assistant|chatbot|bot|api|store|shop|"
    r"tracker|game|network|product))\b",
    FLAGS,
)
FILLER = re.compile(r"^(?:(?:simple|new|small|basic|modern|very|fully|easy)\s+)+", FLAGS)


def _title_and_summary(text: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = ""
    rest = lines
    if lines:
        first = lines[0].lstrip("#").strip()
        first = re.sub(
            r"^(requirements?|prd|spec(ification)?|brief)\s*(for|:|-)\s*", "", first, flags=FLAGS
        )
        if 3 <= len(first) <= 70 and not first.endswith("."):
            name = first.strip(" :-")
            rest = lines[1:]
    body = " ".join(rest)
    match = re.search(r"[^.!?]{20,}[.!?]", body)
    summary = (match.group(0).strip() if match else body[:160]).strip()
    if not name:
        product = PRODUCT.search(summary or body[:300])
        words = FILLER.sub("", product.group(1)) if product else ""
        name = words[:1].upper() + words[1:] if words else "Your application"
    if len(summary) > 200:
        summary = summary[:197].rsplit(" ", 1)[0] + "…"
    return name, summary


def _read_requirements(r: Reading, plan: RulesPlan) -> Requirements:
    text = r.text
    req: dict = {}

    users = [m for m in USERS.finditer(text)]
    if users:
        best = max(users, key=lambda m: _number(m.group(1), m.group(2)))
        req["users"] = int(_number(best.group(1), best.group(2)))
        plan.found.append(f"{req['users']:,} users")
    rates = []
    for m in RATE.finditer(text):
        per = m.group(3).lower()
        divisor = {"second": 1, "sec": 1, "s": 1, "minute": 60, "min": 60, "hour": 3600}.get(per)
        value = _number(m.group(1), m.group(2))
        # A daily figure says nothing about peaks: assume peaks at 3x the average.
        rates.append(value / divisor if divisor else value / 86400 * 3)
    rates += [_number(m.group(1), m.group(2)) for m in RPS.finditer(text)]
    if rates:
        req["peak_rps"] = round(max(rates), 2)
        plan.found.append(f"{req['peak_rps']:g} requests/second at peak")

    to_gb = {"p": 1024 * 1024, "t": 1024, "g": 1}
    growth = GROWTH.search(text)
    if growth:
        gb = _number(growth.group(1), growth.group(2)) * to_gb[growth.group(3)[0].lower()]
        per = growth.group(4).lower()
        req["data_growth_gb_per_month"] = round(
            gb * {"day": 30, "week": 4.3, "month": 1, "year": 1 / 12}[per], 1
        )
        plan.found.append(f"{req['data_growth_gb_per_month']:g} GB of new data a month")
    sizes = [
        m
        for m in SIZE.finditer(text)
        if not (growth and growth.start() <= m.start() < growth.end())
    ]
    if sizes:
        m = sizes[0]
        req["data_gb"] = round(_number(m.group(1), m.group(2)) * to_gb[m.group(3)[0].lower()], 1)
        plan.found.append(f"{req['data_gb']:g} GB of data")

    avail = AVAILABILITY.search(text)
    if avail:
        req["availability_target"] = avail.group(1)
        plan.found.append(f"{avail.group(1)}% availability")
    elif HIGH_AVAILABILITY.search(text):
        req["availability_target"] = "99.95"
        plan.assumptions.append(
            "You asked for high availability without a number; the design targets 99.95%."
        )
    else:
        plan.assumptions.append("No availability target was given; the design assumes 99.9%.")

    budget = BUDGET.search(text)
    if budget:
        amount = _number(budget.group(1), budget.group(2))
        req["monthly_budget_usd"] = round(
            amount / 12 if budget.group(3).lower() == "year" else amount
        )
        plan.found.append(f"${req['monthly_budget_usd']:,} a month budget")

    devs = DEVELOPERS.search(text)
    if devs:
        req["developers"] = int(_number(devs.group(1), devs.group(2)))
        plan.found.append(f"{req['developers']:,} developers")
    # The longest period mentioned decides how long records are kept.
    periods = [
        float(m.group(1)) if m.group(2).lower().startswith("y") else float(m.group(1)) / 12
        for sentence in SENTENCE.findall(text)
        if RETENTION_WORDS.search(sentence)
        for m in PERIOD.finditer(sentence)
    ]
    if periods:
        req["retention_years"] = round(max(periods), 2)
        plan.found.append(f"records kept {req['retention_years']:g} years")

    compliance = [name for name, pattern in COMPLIANCE.items() if re.search(pattern, text, FLAGS)]
    if compliance:
        req["compliance"] = compliance
        plan.found.append("compliance: " + ", ".join(compliance))

    for key, pattern in REGIONS:
        m = re.search(pattern, text, FLAGS)
        if m:
            req["region"] = key
            plan.found.append(f"region near {m.group(0)}")
            break
    else:
        plan.assumptions.append("No region was mentioned, so the design uses US East.")
        plan.open_questions.append(
            "Where are most users, and must data stay in a particular country?"
        )

    if "users" not in req:
        plan.assumptions.append(
            "No user numbers were given, so the design is sized for about 10,000 monthly users."
        )
        plan.open_questions.append(
            "How many people will use it each month, and what does peak traffic look like?"
        )
    if "monthly_budget_usd" not in req:
        plan.open_questions.append("Is there a monthly budget the design must fit?")
    lowered = text.lower()
    if re.search(r"\b(payments?|card|checkout)\b", lowered) and "PCI DSS" not in compliance:
        plan.open_questions.append(
            "Will you take card payments directly (PCI DSS) or through a payment provider?"
        )
    if re.search(r"\b(patients?|medical|health records?|clinic\w*)\b", lowered) and (
        "HIPAA" not in compliance
    ):
        plan.open_questions.append(
            "Does the app store health information covered by HIPAA or similar rules?"
        )
    if re.search(r"\b(personal data|eu users|european users|privacy)\b", lowered) and (
        "GDPR" not in compliance
    ):
        plan.open_questions.append("Do GDPR or other privacy laws apply to your users?")
    return Requirements(**req)


def analyse(text: str) -> RulesPlan:
    reading = Reading(text, _sentences(text))
    name, summary = _title_and_summary(text)
    plan = RulesPlan(name=name, summary=summary, requirements=Requirements())
    plan.requirements = _read_requirements(reading, plan)
    for need, pattern in NEEDS.items():
        quotes, words = reading.find(pattern)
        if quotes:
            plan.needs[need] = quotes
            plan.words[need] = words
    if "agents" in plan.needs and "llm" not in plan.needs:
        plan.needs["llm"] = plan.needs["agents"][:1]
        plan.words["llm"] = []
    _assemble(plan)
    return plan


# --- assembling the design ------------------------------------------------------------


def _list(words: list[str], limit: int = 3) -> str:
    words = words[:limit]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# How matched words read inside a sentence. None drops a word that adds nothing there
# ("queue" in "while queue and jobs run"); words not listed are used as written.
PHRASES: dict[str, list[tuple[str, str | None]]] = {
    "agents": [
        (r"agentic|agent workflows?", None),
        (r"langgraph", "LangGraph agents"),
        (r"lang ?chain", "LangChain agents"),
        (r"crewai", "CrewAI agents"),
        (r"autogen", "AutoGen agents"),
        (r"multi[- ]agent", "multi-agent workflows"),
        (r"tool[- ]calling|agents? that \w+ tools", "tool-calling agents"),
        (r"ai agents?", "the AI agents"),
    ],
    "files": [
        (r"upload\w*", None),
        (r"(photo|image|picture|video|file|attachment|avatar|recording)s?", r"\1s"),
    ],
    "relational": [
        (r"relational|sql|postgres\w*|mysql", None),
        (r"(order|payment|transaction|invoice|booking|reservation|appointment|deposit)s?", r"\1s"),
        (r"catalogu?e?s?", "the catalogue"),
        (r"enrol\w*", "enrolments"),
    ],
    "keyvalue": [
        (r"key[- ]value|nosql|high write", None),
        (r"(?:shopping )?carts?", "shopping carts"),
        (r"(session|leaderboard)s?", r"\1s"),
        (r"(?:chat|conversation) history", "chat history"),
    ],
    "llm": [
        (r"llms?|gpt|claude|generative|gen ?ai", None),
        (r"(?:ai )?assistants?|copilot", "the assistant"),
        (r"chat ?bots?", "the chatbot"),
        (r"summari[sz]\w*", "summaries"),
        (r"natural language", "natural-language questions"),
        (r"rag", "answers grounded in your documents"),
    ],
    "jobs": [
        (r"background|asynchronous|async|queues?|jobs?|retries|retry|batch processing", None),
        (r"(thumbnail|notification|reminder)s?", r"\1s"),
        (r"transcod\w*", "video transcoding"),
        (r"sms", "SMS messages"),
        (r".*e-?mails?", "emails"),
    ],
    "workflow": [
        (r"workflows?|orchestrat\w+", None),
        (r"multi[- ]step", "multi-step processes"),
        (r"(approval|state machine|saga)s?", r"\1s"),
    ],
    "stream": [
        (r"kafka|kinesis", None),
        (r"stream\w* (?:of )?(events|data|telemetry)", r"streaming \1"),
        (r"iot|sensors?", "sensor data"),
        (r"clickstream", "clickstreams"),
    ],
    "analytics": [
        (r"data warehouse", None),
        (r"reports? in (?:our|the) bi", "BI reports"),
        (r"bi tools?|bi", "BI tools"),
        (r"kpis?", "KPIs"),
    ],
    "containers": [
        (r"docker", "Docker"),
        (r"containers?|containeri[sz]\w*", "containers"),
        (r"microservices?", "microservices"),
        (r"long[- ]running", "long-running work"),
        (r"websockets?", "WebSockets"),
        (r"existing (?:app|application|service)", "an existing app"),
    ],
    "serverless": [
        (r"serverless|lambda|functions?", None),
        (r"spiky|bursty", "spiky traffic"),
        (r"pay[- ]per[- ]use", "pay-per-use billing"),
        (r"scale to zero", "scaling to zero"),
        (r"occasional", "occasional use"),
    ],
}


def _records(examples: str) -> str:
    return f"Records such as {examples}" if examples else "Your records"


def _phrases(need: str, words: list[str]) -> list[str]:
    out: list[str] = []
    for word in words:
        phrase: str | None = word
        for pattern, replacement in PHRASES.get(need, []):
            m = re.fullmatch(pattern, word, FLAGS)
            if m:
                phrase = m.expand(replacement) if replacement else None
                break
        if phrase and phrase not in out:
            out.append(phrase)
    return out


def _assemble(plan: RulesPlan) -> None:
    need, req = plan.needs, plan.requirements

    def say(key: str, default: str, limit: int = 2) -> str:
        phrases = _phrases(key, plan.words.get(key, []))
        return _list(phrases, limit) if phrases else default

    users = req.users or 10_000
    peak = req.peak_rps
    requests_month = int(peak * 86400 * 30 * 0.3) if peak else users * 600
    ha = float(req.availability_target) >= 99.9
    comps: list[Component] = []
    edges: list[Edge] = []

    def add(**kwargs) -> Component:
        comp = Component(**kwargs)
        comps.append(comp)
        return comp

    def link(a: str, b: str, label: str | None = None) -> None:
        edges.append(Edge(source=a, target=b, label=label))

    # Compute model.
    if "kubernetes" in need:
        compute = "kubernetes"
        plan.decisions.append("Kubernetes, because you asked for it")
        why = "Runs the services on Kubernetes, as requested, with rolling updates and autoscaling."
    elif "containers" in need:
        compute = "container-service"
        plan.decisions.append(
            f"containers, because you mention {say('containers', 'containers', 1)}"
        )
        why = (
            "Runs the API as containers on a managed service, with no servers to patch; "
            f"chosen because you mention {say('containers', 'containers')}."
        )
    elif "serverless" in need or users < 50_000:
        compute = "serverless-function"
        reason = (
            say("serverless", "a serverless setup") if "serverless" in need else "modest traffic"
        )
        plan.decisions.append(f"serverless functions, because of {reason}")
        why = "Runs the API as functions that scale to zero and bill per request, which suits " + (
            reason + "."
        )
    else:
        compute = "container-service"
        plan.decisions.append(f"containers, because {users:,} users means steady traffic")
        why = "Steady, high traffic is cheaper on always-on containers than per-request functions."

    # Who uses it.
    if "devices" in need:
        client_label = "Devices and dashboard users" if "web" in need else "Devices"
    elif "web" in need and "mobile" in need:
        client_label = "Web and mobile users"
    elif "mobile" in need:
        client_label = "Mobile app users"
    elif "web" in need or "api" not in need:
        client_label = "Users (browser)"
    else:
        client_label = "API clients"
    add(id="users", capability="client", label=client_label)

    public_web = any(n in need for n in ("web", "mobile", "api", "auth", "devices"))
    if public_web:
        add(
            id="dns",
            capability="dns",
            label="Domain",
            rationale="Points your domain at the app and routes around unhealthy endpoints.",
        )
        link("users", "dns")
    front = "users"
    if "web" in need or ("files" in need and "global" in need):
        add(
            id="cdn",
            capability="cdn",
            label="Site and media edge",
            rationale="Serves the front end and media from locations close to users, which is "
            "faster and lowers data-transfer cost.",
            evidence=need.get("web", need.get("global", []))[:1],
            sizing={"egress_gb_per_month": max(20, users // 200)},
        )
        link("users", "cdn", "HTTPS")
        front = "cdn"
        if "web" in need:
            add(
                id="site",
                capability="object-storage",
                label="Front-end assets",
                rationale="Static front-end files need no servers; the CDN reads them privately.",
                sizing={"storage_gb": 2},
            )
            link("cdn", "site")
    if "security" in need or req.compliance or users >= 100_000 or "relational" in need:
        reason = ", ".join(req.compliance) if req.compliance else None
        add(
            id="firewall",
            capability="waf",
            label="Web firewall",
            rationale="Filters bots and common web attacks before they reach the app"
            + (f"; part of protecting data covered by {reason}." if reason else "."),
            evidence=need.get("security", [])[:1],
            sizing={"requests_per_month": requests_month},
        )
        link(front, "firewall", "HTTPS" if front == "users" else "/api/*")
        front = "firewall"

    if compute == "serverless-function":
        add(
            id="api",
            capability="api-gateway",
            label="API",
            rationale="Front door for the API: authentication, throttling and routing without "
            "servers.",
            evidence=need.get("api", [])[:1],
            sizing={"requests_per_month": requests_month},
        )
    else:
        add(
            id="api",
            capability="load-balancer",
            label="Cluster ingress" if compute == "kubernetes" else "HTTPS load balancer",
            rationale="Spreads HTTPS traffic across instances in several availability zones and "
            "terminates TLS.",
            evidence=need.get("api", [])[:1],
        )
    link(front, "api", "/api/*" if front == "cdn" else None)

    app_label = {
        "serverless-function": "API functions",
        "container-service": "API service",
        "kubernetes": "API services",
    }[compute]
    if compute == "serverless-function":
        sizing = {"invocations_per_month": requests_month, "avg_duration_ms": 150, "memory_mb": 512}
    else:
        tasks = max(2, min(20, math.ceil((peak or users / 20_000) / 100) + 1))
        sizing = {"vcpu": 1, "memory_gb": 2, "tasks": tasks}
    add(
        id="app",
        capability=compute,
        label=app_label,
        rationale=why,
        evidence=(need.get("kubernetes") or need.get("containers") or need.get("serverless") or [])[
            :1
        ],
        sizing=sizing,
    )
    link("api", "app")

    if "auth" in need:
        add(
            id="auth",
            capability="identity",
            label="Sign-up and sign-in",
            rationale="Managed accounts, sign-in and tokens instead of storing passwords yourself.",
            evidence=need["auth"][:1],
            sizing={"monthly_active_users": users},
        )
        link("app", "auth", "verify token")

    stores: list[str] = []
    if "relational" in need:
        add(
            id="db",
            capability="relational-db",
            label="Main database",
            rationale=f"{_records(say('relational', '', 3))} need transactions and joins, so "
            "they belong in a relational database"
            + (", replicated across zones for the availability target." if ha else "."),
            evidence=need["relational"][:2],
            sizing={"storage_gb": max(20, req.data_gb or 20), "multi_az": ha},
        )
        stores.append("db")
    if "keyvalue" in need or ("relational" not in need and compute == "serverless-function"):
        add(
            id="kv",
            capability="key-value-db",
            label="App data" if "relational" not in need else "Sessions and fast lookups",
            rationale=(
                f"Simple lookups such as {say('keyvalue', 'sessions')} suit a serverless "
                "key-value store with no idle cost."
                if _phrases("keyvalue", plan.words.get("keyvalue", []))
                else "Simple key lookups suit a serverless key-value store that scales with "
                "the functions and costs nothing when idle."
            ),
            evidence=need.get("keyvalue", [])[:1],
            sizing={"storage_gb": max(5, (req.data_gb or 20) // 4)},
        )
        stores.append("kv")
    if "cache" in need or (users >= 100_000 and compute != "serverless-function"):
        add(
            id="cache",
            capability="cache",
            label="Cache",
            rationale="Keeps hot data in memory to cut response times and database load.",
            evidence=need.get("cache", [])[:1],
            sizing={"node_memory_gb": 2, "nodes": 2 if ha else 1},
        )
        stores.append("cache")
    media_words = {
        "image",
        "images",
        "photo",
        "picture",
        "pictures",
        "photos",
        "video",
        "videos",
        "media",
        "avatar",
        "avatars",
        "recording",
        "recordings",
    }
    documents_only = (
        "vector" in need and "llm" in need and not media_words & set(plan.words.get("files", []))
    )
    if "files" in need and not documents_only:
        add(
            id="files",
            capability="object-storage",
            label="Uploaded files",
            rationale=f"Durable, low-cost storage for {say('files', 'uploaded files')}.",
            evidence=need["files"][:1],
            sizing={"storage_gb": max(50, req.data_gb or 100)},
        )
        stores.append("files")
    for store in stores:
        link("app", store)

    if "llm" in need:
        add(
            id="llm",
            capability="llm-inference",
            label="Language models",
            rationale=f"Managed models for {say('llm', 'the AI features')}; you pay per token "
            "instead of hosting GPUs.",
            evidence=need["llm"][:1],
        )
        # Who talks to the models: the app, or an agent runtime working for it, through a
        # gateway when there are several models, providers or budgets to manage.
        caller = "app"
        if "agents" in need:
            add(
                id="agent",
                capability="agent-orchestration",
                label="AI agent",
                rationale=f"Runs {say('agents', 'the agents', 1)}: multi-step reasoning that calls "
                "tools, keeps state between steps and can be resumed after a failure.",
                evidence=need["agents"][:1],
            )
            link("app", "agent", "run")
            caller = "agent"
            plan.decisions.append(
                f"an agent runtime, because you mention {say('agents', 'agents', 1)}"
            )
        if "gateway" in need:
            add(
                id="gateway",
                capability="llm-gateway",
                label="LLM gateway",
                rationale="One API for every model, with per-team keys, budgets, rate limits, "
                "fallbacks to another model and caching.",
                evidence=need["gateway"][:1],
            )
            link(caller, "gateway", "prompt")
            link("gateway", "llm", "route")
        else:
            link(caller, "llm", "generate")
        if "agents" in need or "gateway" in need or "llmops" in need:
            add(
                id="llm-traces",
                capability="llm-observability",
                label="LLM tracing",
                rationale="Records every prompt, tool call, token count and cost, so answers can "
                "be debugged, evaluated and kept within budget.",
                evidence=need.get("llmops", [])[:1],
            )
            if "llmops" not in need:
                plan.assumptions.append(
                    "Added LLM tracing because agents and model gateways are hard to debug and "
                    "cost-control without it."
                )
        if "vector" in need:
            add(
                id="knowledge",
                capability="vector-search",
                label="Knowledge index",
                rationale="Finds the passages most relevant to each question, so answers are "
                "grounded in your own documents.",
                evidence=need["vector"][:1],
            )
            add(
                id="docs",
                capability="object-storage",
                label="Source documents",
                rationale="Holds the documents the assistant answers from.",
            )
            add(
                id="indexer",
                capability="serverless-function",
                label="Document indexing",
                rationale="Splits new documents into chunks and indexes their embeddings when "
                "they change.",
            )
            link(caller, "knowledge", "retrieve")
            link("docs", "indexer", "on upload")
            link("indexer", "llm", "embed")
            link("indexer", "knowledge", "index")

    has_workers = "jobs" in need or "workflow" in need
    if "jobs" in need:
        add(
            id="queue",
            capability="message-queue",
            label="Job queue",
            rationale=f"Lets the API answer straight away while {say('jobs', 'slow tasks')} run "
            "in the background, with automatic retries.",
            evidence=need["jobs"][:2],
            sizing={"requests_per_month": max(100_000, requests_month // 10)},
        )
        link("app", "queue", "enqueue")
    if "workflow" in need:
        add(
            id="workflow",
            capability="workflow",
            label="Multi-step workflow",
            rationale=f"Coordinates {say('workflow', 'multi-step processes')} with retries and "
            "visible state.",
            evidence=need["workflow"][:1],
        )
        link("queue" if "jobs" in need else "app", "workflow")
    if has_workers:
        worker_cap = "serverless-function" if compute == "serverless-function" else compute
        add(
            id="workers",
            capability=worker_cap,
            label="Background workers",
            rationale="Processes queued work separately from the API, so heavy tasks never slow "
            "users down.",
        )
        link("workflow" if "workflow" in need else "queue", "workers")
        for store in [s for s in stores if s != "cache"][:2]:
            link("workers", store)
    if "events" in need:
        add(
            id="events",
            capability="event-bus",
            label="Domain events",
            rationale="Publishes events so other services and integrations can react without "
            "being wired into the API.",
            evidence=need["events"][:1],
        )
        link("workers" if has_workers else "app", "events", "publish")

    if "stream" in need or "analytics" in need:
        if "stream" in need:
            add(
                id="stream",
                capability="stream",
                label="Event stream",
                rationale=f"Ingests {say('stream', 'incoming events')} in order and lets several "
                "consumers read the same data.",
                evidence=need["stream"][:1],
            )
            link("app", "stream", "events")
        add(
            id="lake",
            capability="object-storage",
            label="Data lake",
            rationale="Cheap, durable storage for raw and curated data.",
            sizing={"storage_gb": max(100, (req.data_gb or 100) * 2)},
        )
        link("stream" if "stream" in need else "app", "lake", "raw")
        if "analytics" in need or "etl" in need:
            add(
                id="etl",
                capability="batch-etl",
                label="Data transforms",
                rationale="Cleans and reshapes the data on a schedule without running a cluster.",
                evidence=need.get("etl", [])[:1],
            )
            link("etl", "lake", "read + write")
        if "analytics" in need:
            add(
                id="warehouse",
                capability="data-warehouse",
                label="Analytics warehouse",
                rationale=f"Fast SQL for {say('analytics', 'reporting')}.",
                evidence=need["analytics"][:1],
            )
            link("lake", "warehouse", "load")

    if "relational" in need or "secrets_hint" in need:
        add(
            id="secrets",
            capability="secrets",
            label="Credentials",
            rationale="Keeps database passwords and API keys out of code and rotates them.",
            evidence=need.get("secrets_hint", [])[:1],
        )
        link("app", "secrets")
    # Security and records: what regulated, AI or company-wide systems need around them.
    regulated = bool(req.compliance)
    ai = "llm" in need
    if "llm" in need and ("guardrails" in need or "agents" in need or regulated):
        add(
            id="guardrails",
            capability="ai-guardrails",
            label="AI guardrails",
            rationale="Screens prompts and answers for prompt injection, harmful content and "
            "personal data before they reach the model or the user.",
            evidence=need.get("guardrails", [])[:1],
        )
        link("agent" if "agents" in need else "app", "guardrails", "screen")
        if "guardrails" not in need:
            plan.assumptions.append(
                "Added AI guardrails: agents and regulated data need prompts and answers "
                "screened for injection and personal data."
            )
    if "access" in need or regulated or ai:
        add(
            id="access",
            capability="access-governance",
            label="Cloud access governance",
            rationale="Staff sign in to the cloud with the company directory; the cloud "
            "architects approve roles with least privilege, and access is reviewed regularly.",
            evidence=need.get("access", [])[:1],
        )
    if "audit" in need or regulated or ai:
        add(
            id="audit",
            capability="audit-logging",
            label="Audit trail",
            rationale="Records who did what - every console change, data access and model "
            "call - in a log nobody can edit"
            + (f", kept {req.retention_years:g} years." if req.retention_years else "."),
            evidence=need.get("audit", [])[:1],
        )
    if "encryption" in need or set(req.compliance) & {"HIPAA", "PCI DSS", "GDPR", "FedRAMP"}:
        add(
            id="keys",
            capability="key-management",
            label="Encryption keys",
            rationale="Customer-managed keys encrypt the databases, files and backups, with "
            "rotation and a log of every use.",
            evidence=need.get("encryption", [])[:1],
        )
    data_stores = [c.id for c in comps if c.capability in ("relational-db", "key-value-db")]
    if data_stores and ("backup" in need or req.retention_years or regulated or ha):
        add(
            id="backup",
            capability="backup",
            label="Backups",
            rationale="Daily backups with point-in-time restore, copied to a separate account "
            "so a mistake or an attack cannot delete both.",
            evidence=need.get("backup", [])[:1],
        )
    if req.retention_years or "archive" in need:
        add(
            id="archive",
            capability="archive-storage",
            label="Records archive",
            rationale="Lifecycle rules move records out of the hot stores as they age, into "
            "archive storage that costs a fraction"
            + (
                f", until they can be deleted after {req.retention_years:g} years."
                if req.retention_years
                else "."
            ),
            evidence=need.get("archive", [])[:1],
        )
        records = [c.id for c in comps if c.capability == "object-storage" and c.id != "site"]
        for store in [*data_stores, *records][:2]:
            link(store, "archive", "age out")
    # Assistant first, so the build lane reads assistant → environment → repository.
    if "coding_ai" in need:
        add(
            id="assistant",
            capability="ai-coding-assistant",
            label="AI coding assistant",
            rationale="AI suggestions in the editor and in code review, licensed per developer.",
            evidence=need["coding_ai"][:1],
        )

    if "devenv" in need:
        add(
            id="devenv",
            capability="dev-environment",
            label="Dev environments",
            rationale="Ready-to-code environments, so a new developer starts in minutes with "
            "the same tools as everyone else.",
            evidence=need["devenv"][:1],
        )
    add(
        id="logs",
        capability="monitoring",
        label="Logs, metrics and alarms",
        rationale="Central logs, metrics and alarms so problems show up before users report them.",
        sizing={"log_ingest_gb_per_month": max(5, users // 5_000)},
    )
    plan.components, plan.edges = comps, edges


def build_spec(plan: RulesPlan, source: str | None = None) -> ArchitectureSpec:
    """Runtime design only: no toolchain, no workflows."""
    return ArchitectureSpec(
        name=plan.name,
        summary=plan.summary,
        requirements=plan.requirements,
        assumptions=plan.assumptions,
        open_questions=plan.open_questions,
        components=plan.components,
        edges=plan.edges,
        provenance=Provenance(mode="rules", source=source),
    )


def plan_with_rules(text: str, source: str | None = None) -> ArchitectureSpec:
    """The complete rule-based design: runtime, toolchain and workflows."""
    spec = add_delivery(build_spec(analyse(text), source))
    return spec.model_copy(update={"workflows": generate_workflows(spec)})
