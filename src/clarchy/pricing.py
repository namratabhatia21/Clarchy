"""Cost estimates: what a design costs a month, and over 1 month, 6 months, 1 year and
3 years, on demand and with commitments (Savings Plans, reservations, committed use).

Three parts, kept apart so each can be checked on its own:
- usage (here): provider-neutral quantities per component, from the design's sizing and
  requirements, each with a sentence saying where it came from;
- price books (data/prices/<provider>.yaml): unit prices. AWS comes from the AWS Price
  List API with SKUs (see aws_prices.py); Azure and Google Cloud are compiled by hand
  and marked approximate;
- billing models (data/prices/models.yaml): which priced items each capability has on
  each provider.

Monthly figures use 730 hours. Storage grows with the stated data growth, so longer
periods cost more than a multiple of the first month.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from clarchy import catalog
from clarchy.mapping import ProviderArchitecture

HOURS = 730
SECONDS = HOURS * 3600
TERMS = ((1, "1 month"), (6, "6 months"), (12, "1 year"), (36, "3 years"))


# --- price books -------------------------------------------------------------------------


def _override_dirs() -> list[Path]:
    """Refreshed price books win over the bundled ones (clarchy prices update)."""
    env = os.environ.get("CLARCHY_PRICES_DIR")
    if env is not None:
        return [Path(env)] if env else []
    return [Path.home() / ".cache" / "clarchy" / "prices"]


_LOADED: dict[str, dict[str, Any]] = {}


def _load_yaml(source) -> dict[str, Any]:
    key = str(source)
    if key not in _LOADED:
        _LOADED[key] = yaml.safe_load(source.read_text(encoding="utf-8"))
    return _LOADED[key]


def price_book(provider: str) -> dict[str, Any] | None:
    for folder in _override_dirs():
        candidate = folder / f"{provider}.yaml"
        if candidate.is_file():
            return _load_yaml(candidate)
    bundled = catalog.data_path("prices", f"{provider}.yaml")
    return _load_yaml(bundled) if bundled.is_file() else None


def billing_models() -> dict[str, Any]:
    return _load_yaml(catalog.data_path("prices", "models.yaml"))


# --- usage ----------------------------------------------------------------------------------


@dataclass
class Q:
    """A usage quantity: value per month, how much it grows each month, and why."""

    value: float
    basis: str
    grows: float = 0.0


@dataclass
class Context:
    users: int
    requests_month: float
    data_gb: float
    growth_gb: float
    availability: float
    grower: str | None  # the component whose storage carries the data growth
    first_cluster: str | None
    has_vector: bool
    developers: int = 10
    retention_years: float | None = None
    has_relational: bool = False
    llm_calls: float = 0.0


def _n(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}"
    return f"{value:,.1f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _context(arch: ProviderArchitecture) -> Context:
    spec = arch.spec
    req = spec.requirements
    users = req.users or 10_000
    # Average load: 30% of the stated peak, or 600 requests per user a month.
    requests_month = req.peak_rps * 0.3 * SECONDS if req.peak_rps else users * 600
    stores = [
        c
        for c in spec.components
        if c.capability in ("object-storage", "relational-db", "data-warehouse")
    ]
    grower = None
    if stores:
        grower = max(stores, key=lambda c: (c.sizing or {}).get("storage_gb", 0)).id
    clusters = [c.id for c in spec.components if c.capability == "kubernetes"]
    return Context(
        users=users,
        requests_month=requests_month,
        data_gb=float(req.data_gb or 20),
        growth_gb=float(req.data_growth_gb_per_month or 0),
        availability=float(req.availability_target),
        grower=grower,
        first_cluster=clusters[0] if clusters else None,
        has_vector=any(c.capability == "vector-search" for c in spec.components),
        developers=req.developers or 10,
        retention_years=req.retention_years,
        has_relational=any(c.capability == "relational-db" for c in spec.components),
        llm_calls=next(
            (
                float((c.sizing or {}).get("requests_per_month") or users * 20)
                for c in spec.components
                if c.capability == "llm-inference"
            ),
            users * 20.0,
        ),
    )


def usage(comp, ctx: Context) -> dict[str, Q | str]:
    """Neutral monthly quantities for one component."""
    s = comp.sizing or {}
    cap = comp.capability
    req_m = s.get("requests_per_month") or ctx.requests_month
    out: dict[str, Q | str] = {
        "months": Q(1, "one per month"),
        "hours": Q(HOURS, "always on"),
    }

    def storage(default: float) -> Q:
        gb = float(s.get("storage_gb") or default)
        grows = ctx.growth_gb if comp.id == ctx.grower else 0.0
        basis = f"{_n(gb)} GB" + (f", growing {_n(grows)} GB a month" if grows else "")
        return Q(gb, basis, grows)

    if cap == "dns":
        out |= {
            "zones": Q(1, "one hosted zone"),
            "dns_queries_m": Q(max(0.1, ctx.users * 30 / 1e6), "about 30 lookups per user a month"),
        }
    elif cap == "cdn":
        egress = float(s.get("egress_gb_per_month") or max(20, ctx.users / 200))
        out |= {
            "egress_gb": Q(egress, f"{_n(egress)} GB served a month"),
            # Page views and assets come from people, not from device or API traffic.
            "cdn_requests_10k": Q(
                float(s.get("requests_per_month") or ctx.users * 300) / 1e4,
                "about 300 page and asset requests per user a month",
            ),
        }
    elif cap == "waf":
        out |= {
            "waf_acls": Q(1, "one policy"),
            "waf_rules": Q(5, "five rules or managed rule groups"),
            "waf_requests_m": Q(req_m / 1e6, f"{_n(req_m / 1e6)}M requests a month"),
        }
    elif cap == "load-balancer":
        avg_rps = req_m / SECONDS
        units = max(1, math.ceil(avg_rps / 50))
        out |= {
            "lb_hours": Q(HOURS, "one load balancer, always on"),
            "lcu_hours": Q(
                units * HOURS, f"{units} capacity unit(s) for about {_n(avg_rps)} requests a second"
            ),
            "lb_data_gb": Q(req_m * 20 / 1e6, "about 20 KB per request"),
        }
    elif cap == "api-gateway":
        out["api_requests_m"] = Q(req_m / 1e6, f"{_n(req_m / 1e6)}M calls a month")
    elif cap in ("container-service", "kubernetes"):
        vcpu = float(s.get("vcpu") or 1)
        mem = float(s.get("memory_gb") or 2)
        tasks = int(s.get("tasks") or 2)
        out |= {
            "vcpu_hours": Q(vcpu * tasks * HOURS, f"{tasks} × {_n(vcpu)} vCPU, always on"),
            "gb_hours": Q(mem * tasks * HOURS, f"{tasks} × {_n(mem)} GB, always on"),
        }
        if cap == "kubernetes":
            nodes = max(2, math.ceil(tasks * vcpu / 1.6), math.ceil(tasks * mem / 6.4))
            first = comp.id == ctx.first_cluster
            out |= {
                "node_hours": Q(nodes * HOURS, f"{nodes} nodes (2 vCPU, 8 GB) for {tasks} pods"),
                "cluster_hours": Q(
                    HOURS if first else 0, "one cluster" if first else "shares the first cluster"
                ),
            }
    elif cap == "serverless-function":
        calls = float(s.get("invocations_per_month") or req_m)
        ms = float(s.get("avg_duration_ms") or 200)
        mb = float(s.get("memory_mb") or 512)
        gb_s = calls * ms / 1000 * mb / 1024
        vcpu_s = calls * ms / 1000 * max(0.083, mb / 2048)
        out |= {
            "requests_m": Q(calls / 1e6, f"{_n(calls / 1e6)}M invocations a month"),
            "gb_seconds": Q(gb_s, f"{_n(ms)} ms at {_n(mb)} MB each"),
            "vcpu_seconds": Q(vcpu_s, f"{_n(ms)} ms each"),
        }
    elif cap == "ai-guardrails":
        calls = float(s.get("requests_per_month") or ctx.llm_calls)
        out |= {
            "guard_units_k": Q(
                calls * 3 / 1000, f"{_n(calls)} model calls × 3 text units (prompt and answer)"
            ),
            "guard_records_k": Q(calls * 3 / 1000, f"{_n(calls)} model calls × 3 text records"),
            "guard_tokens_m": Q(calls * 1900 / 1e6, f"{_n(calls)} model calls × 1,900 tokens"),
        }
    elif cap == "archive-storage":
        years = ctx.retention_years
        kept = f", kept {_n(years)} years" if years else ""
        gb = float(s.get("storage_gb") or max(50.0, ctx.data_gb))
        grows = ctx.growth_gb
        basis = f"{_n(gb)} GB of older records" + (
            f", growing {_n(grows)} GB a month" if grows else ""
        )
        out["archive_gb"] = Q(gb, basis + kept, grows)
    elif cap == "backup":
        gb = float(s.get("storage_gb") or max(20.0, ctx.data_gb))
        out |= {
            "backup_gb": Q(
                gb, f"{_n(gb)} GB: daily incremental backups kept 35 days", ctx.growth_gb
            ),
            "backup_kind": "rds_gb" if ctx.has_relational else "s3_gb",
            "backup_instances": Q(
                float(s.get("instances") or 2), "databases and file stores protected"
            ),
        }
    elif cap == "key-management":
        keys = float(s.get("keys") or 5)
        out |= {
            "kms_keys": Q(keys, f"{_n(keys)} customer-managed keys"),
            "kms_requests_10k": Q(
                ctx.requests_month * 0.2 / 1e4, "about one key request per five app requests"
            ),
        }
    elif cap == "audit-logging":
        events = ctx.requests_month * 0.2  # data events on the sensitive stores
        out |= {
            "audit_events_m": Q(events / 1e6, f"{_n(events / 1e6)}M data events on sensitive data"),
            "audit_gb": Q(max(1.0, events * 1.5 / 1e6), "about 1.5 KB per audit event"),
        }
    elif cap == "access-governance":
        admins = float(s.get("admins") or 5)
        out["admins"] = Q(admins, f"{_n(admins)} cloud administrators with just-in-time access")
    elif cap in ("dev-environment", "ai-coding-assistant"):
        devs = float(s.get("developers") or ctx.developers)
        out |= {
            "seats": Q(devs, f"{_n(devs)} developers"),
            "dev_hours": Q(devs * 60, f"{_n(devs)} developers × 60 hours a month"),
            "dev_core_hours": Q(devs * 60 * 4, f"{_n(devs)} developers × 60 hours × 4 cores"),
            "dev_storage_gb": Q(devs * 32, f"{_n(devs)} developers × 32 GB"),
        }
    elif cap == "llm-gateway":
        vcpu = float(s.get("vcpu") or 0.5)
        mem = float(s.get("memory_gb") or 1)
        tasks = int(s.get("tasks") or 2)
        out |= {
            "vcpu_hours": Q(vcpu * tasks * HOURS, f"{tasks} × {_n(vcpu)} vCPU proxies, always on"),
            "gb_hours": Q(mem * tasks * HOURS, f"{tasks} × {_n(mem)} GB, always on"),
            "gateway_hours": Q(HOURS, "one gateway unit, always on"),
        }
    elif cap in ("agent-orchestration", "llm-observability"):
        runs = float(s.get("requests_per_month") or ctx.users * 20)
        if cap == "agent-orchestration":
            out |= {
                "agent_vcpu_hours": Q(
                    runs * 4 / 3600, f"{_n(runs)} agent runs × 4 s of active CPU (1 vCPU)"
                ),
                "agent_gb_hours": Q(
                    runs * 2 * 20 / 3600, f"{_n(runs)} runs × 2 GB for about 20 s each"
                ),
            }
        else:
            out |= {
                "trace_gb": Q(runs * 25 / 1e6, f"{_n(runs)} traced runs × about 25 KB each"),
                "spans_m": Q(runs * 10 / 1e6, f"{_n(runs)} runs × about 10 spans each"),
            }
    elif cap == "llm-inference":
        questions = float(s.get("requests_per_month") or ctx.users * 20)
        embed = questions * 30 / 1e6 + (5 if ctx.has_vector else 0)
        out |= {
            "input_tokens_m": Q(
                questions * 1500 / 1e6,
                f"{_n(questions)} requests × 1,500 tokens (prompt and context)",
            ),
            "output_tokens_m": Q(questions * 400 / 1e6, f"{_n(questions)} answers × 400 tokens"),
            "embedding_tokens_m": Q(
                embed if ctx.has_vector else 0, "questions plus about 5M tokens of new documents"
            ),
        }
    elif cap == "message-queue":
        messages = float(s.get("requests_per_month") or req_m / 10)
        out |= {
            "queue_requests_m": Q(
                messages * 3 / 1e6,
                f"{_n(messages / 1e6)}M messages × 3 calls (send, receive, delete)",
            ),
            "queue_tib": Q(
                messages * 2 * 1024 / 1024**4,
                f"{_n(messages / 1e6)}M messages, published and delivered",
            ),
        }
    elif cap == "event-bus":
        events = float(s.get("requests_per_month") or req_m / 20)
        out["events_m"] = Q(events / 1e6, f"{_n(events / 1e6)}M events a month")
    elif cap == "stream":
        records = float(s.get("requests_per_month") or req_m)
        rps = records / SECONDS
        shards = max(1, math.ceil(rps / 1000))
        out |= {
            "shard_hours": Q(
                shards * HOURS, f"{shards} shard(s) for about {_n(rps)} records a second"
            ),
            "put_units_m": Q(records / 1e6, f"{_n(records / 1e6)}M records a month"),
            "stream_tib": Q(
                records * 2 * 1024 / 1024**4, "records of about 1 KB, written and read"
            ),
        }
    elif cap == "workflow":
        runs = float(s.get("requests_per_month") or req_m / 50)
        out["transitions_k"] = Q(runs * 12 / 1e3, f"{_n(runs)} runs × 12 steps")
    elif cap == "batch-etl":
        out |= {
            "etl_hours": Q(30, "a one-hour job every night"),
            "etl_runs_k": Q(0.03, "30 runs a month"),
        }
    elif cap == "object-storage":
        stored = storage(ctx.data_gb)
        # Objects of about 1 MB: new data a month sets the writes, reads are ten times that.
        new_gb = stored.grows or stored.value * 0.1
        writes = float(s.get("writes_per_month") or max(1000, new_gb * 1000))
        reads = float(s.get("reads_per_month") or writes * 10)
        out |= {
            "storage_gb": stored,
            "writes_k": Q(writes / 1e3, f"{_n(writes)} objects written a month (about 1 MB each)"),
            "reads_k": Q(reads / 1e3, f"{_n(reads)} reads a month"),
        }
    elif cap == "relational-db":
        big = ctx.users >= 300_000 or ctx.requests_month >= 600 * SECONDS * 0.3
        small = ctx.users < 30_000 and ctx.requests_month < 50 * SECONDS * 0.3
        size = "large" if big else "small" if small else "medium"
        multi = s.get("multi_az", ctx.availability >= 99.9)
        out |= {
            "db_size": size,
            "db_az": "multi" if multi else "single",
            "db_hours": Q(
                HOURS, f"one {size} instance" + (" with a standby in another zone" if multi else "")
            ),
            "storage_gb": storage(max(20, ctx.data_gb)),
        }
    elif cap == "key-value-db":
        writes = float(s.get("writes_per_month") or req_m * 0.2)
        reads = float(s.get("reads_per_month") or req_m)
        out |= {
            "write_units_m": Q(writes / 1e6, f"{_n(writes / 1e6)}M writes of up to 1 KB"),
            "read_units_m": Q(reads / 1e6, f"{_n(reads / 1e6)}M reads"),
            "request_units_m": Q((writes * 5 + reads) / 1e6, "5 RU per write, 1 RU per read"),
            "storage_gb": storage(max(5, ctx.data_gb / 4)),
        }
    elif cap == "cache":
        memory = float(s.get("node_memory_gb") or 2)
        nodes = int(s.get("nodes") or (2 if ctx.availability >= 99.9 else 1))
        size = "small" if memory <= 3 else "large"
        out |= {
            "cache_size": size,
            "cache_node_hours": Q(nodes * HOURS, f"{nodes} node(s) with about {_n(memory)} GB"),
            "cache_hours": Q(HOURS, f"one cache with about {_n(memory)} GB"),
            "cache_gb_hours": Q(max(1, memory) * HOURS, f"{_n(max(1, memory))} GB of capacity"),
        }
    elif cap == "vector-search":
        out["vector_hours"] = Q(HOURS, "always on")
    elif cap == "data-warehouse":
        stored = storage(max(100, ctx.data_gb))
        out |= {
            "query_hours": Q(60, "about 2 hours of queries a day"),
            "storage_gb": stored,
            "tib_scanned": Q(
                max(0.5, stored.value * 30 / 1024), "data scanned about 30 times a month"
            ),
        }
    elif cap == "identity":
        mau = float(s.get("monthly_active_users") or ctx.users)
        out["mau"] = Q(mau, f"{_n(mau)} monthly active users")
    elif cap == "secrets":
        out |= {
            "secrets": Q(5, "five secrets"),
            "secret_calls_10k": Q(req_m * 0.01 / 1e4, "cached; about 1 call per 100 requests"),
        }
    elif cap == "monitoring":
        logs = float(s.get("log_ingest_gb_per_month") or max(5, ctx.users / 5000))
        out |= {
            "logs_gb": Q(logs, f"{_n(logs)} GB of logs a month"),
            "alarms": Q(10, "ten alarms"),
        }
    elif cap == "container-registry":
        out["registry_gb"] = Q(5, "about 5 GB of images")
    elif cap == "ci-build":
        out |= {
            "build_minutes": Q(300, "60 builds of 5 minutes a month"),
            "extra_parallel_jobs": Q(0, "fits in the free parallel job"),
        }
    elif cap == "cd-deploy":
        out |= {
            "pipeline_minutes": Q(600, "60 releases of about 10 minutes"),
            "pipelines": Q(1, "one delivery pipeline"),
        }
    return out


# --- estimate -------------------------------------------------------------------------------


@dataclass
class Item:
    name: str
    quantity: float
    unit: str
    unit_price: float
    basis: str
    grows: float
    free: float
    scale: float
    commit: dict[int, float] = field(default_factory=dict)
    approximate: bool = False

    def billable(self, month: int) -> float:
        return max(0.0, (self.quantity + self.grows * self.scale * month) - self.free)

    def cost(self, month: int, years: int | None = None) -> float:
        price = self.unit_price
        if years:
            price = self.commit.get(years) or self.commit.get(1) or price
        return self.billable(month) * price


def _items(comp, model: dict[str, Any], book: dict[str, Any], ctx: Context) -> list[Item]:
    quantities = usage(comp, ctx)
    choices = {k: v for k, v in quantities.items() if isinstance(v, str)}
    items = []
    for spec in model.get("items", []):
        q = quantities.get(spec["quantity"])
        if not isinstance(q, Q):
            raise KeyError(f"{comp.capability}: no usage quantity {spec['quantity']!r}")
        key = spec["price"].format(**choices)
        entry = book["prices"].get(key)
        # Lines priced from the third-party book are flagged; a provider's own book is
        # labelled as a whole (verified or approximate).
        approximate = False
        if entry is None:
            entry = price_book("thirdparty")["prices"][key]
            approximate = True
        scale = float(spec.get("scale", 1))
        free = float(spec.get("free", 0))
        quantity = q.value * scale
        if quantity <= 0:
            continue
        basis = q.basis + (f"; first {_n(free)} free" if free else "")
        commit = {
            years: entry[f"commit_{years}yr"] for years in (1, 3) if f"commit_{years}yr" in entry
        }
        items.append(
            Item(
                spec["name"],
                quantity,
                entry["unit"],
                float(entry["price"]),
                basis,
                q.grows,
                free,
                scale,
                commit,
                approximate,
            )
        )
    return items


def estimate(arch: ProviderArchitecture) -> dict[str, Any]:
    """The cost payload for one design on one provider."""
    provider = arch.provider
    book = price_book(provider)
    models = billing_models().get(provider)
    if not book or not models:
        return {
            "available": False,
            "message": (
                "Open-source software has no licence fee: you pay for the machines it runs on "
                "and the people who operate it, which depends on where you host it. Open a "
                "cloud tab to see a managed-service estimate."
                if provider == "oss"
                else f"No price data for {arch.provider_name} yet."
            ),
        }
    ctx = _context(arch)
    lines, included, not_priced = [], [], []
    for m in arch.components:
        comp = m.component
        if comp.tier == "external" or not m.choice:
            continue
        model = models["capabilities"].get(comp.capability)
        if model is None:
            note = models.get("included", {}).get(comp.capability)
            (included if note else not_priced).append(
                {
                    "component": comp.id,
                    "service": m.choice.service,
                    "note": note or "Not priced yet.",
                }
            )
            continue
        items = _items(comp, model, book, ctx)
        commitment = model.get("commitment") if any(i.commit for i in items) else None
        lines.append((comp, m.choice.service, model, items, commitment))

    def total(month: int, years: int | None = None) -> float:
        return sum(i.cost(month, years) for _, _, _, items, _ in lines for i in items)

    terms = []
    for months, label in TERMS:
        years = {12: 1, 36: 3}.get(months)
        on_demand = sum(total(m) for m in range(months))
        committed = sum(total(m, years) for m in range(months)) if years else None
        has_commit = committed is not None and committed < on_demand - 0.005
        terms.append(
            {
                "months": months,
                "label": label,
                "on_demand": round(on_demand, 2),
                "committed": round(committed, 2) if has_commit else None,
                "commitment": f"{years}-year" if has_commit else None,
            }
        )
    first = total(0)
    # A 1-year commitment pays off once the months you run exceed 12 × (committed rate /
    # on-demand rate), over the spend it covers.
    covered = [i for *_, items, _ in lines for i in items if i.commit]
    covered_od = sum(i.cost(0) for i in covered)
    covered_1yr = sum(i.cost(0, 1) for i in covered)
    break_even = math.ceil(12 * covered_1yr / covered_od) if covered_od > 0.005 else None

    used = {c for *_, c in lines if c}
    payload_lines = []
    for comp, service, model, items, commitment in lines:
        payload_lines.append(
            {
                "component": comp.id,
                "capability": comp.capability,
                "service": service,
                "label": comp.display_label,
                "stage": comp.stage,
                "monthly": round(sum(i.cost(0) for i in items), 2),
                "commitment": commitment,
                "pricing_url": model.get("pricing_url"),
                "approximate": any(i.approximate for i in items),
                "items": [
                    {
                        "name": i.name,
                        "quantity": round(i.billable(0), 4),
                        "unit": i.unit,
                        "unit_price": i.unit_price,
                        "monthly": round(i.cost(0), 4),
                        "basis": i.basis,
                    }
                    for i in items
                ],
            }
        )
    return {
        "available": True,
        "currency": book["currency"],
        "price_region": book["price_region"],
        "as_of": str(book["as_of"]),
        "source": book["source"],
        "verified": bool(book.get("verified")),
        "calculator": book.get("calculator"),
        "monthly": round(first, 2),
        "lines": payload_lines,
        "terms": terms,
        "break_even_months": break_even if break_even and break_even < 12 else None,
        "commitment_notes": [
            f"{name}: {text}"
            for name, text in models.get("commitments", {}).items()
            if name in used
        ],
        "included": included,
        "not_priced": not_priced,
        "assumptions": [
            "Usage comes from each component's sizing and the requirements; edit it in the Spec "
            "tab.",
            "730 hours a month. Always-free allowances are deducted where shown; trials are not.",
            "Excludes tax, support plans, and data transfer not listed.",
        ]
        + (
            [f"Prices are for {book['price_region']}; your region ({arch.region_text}) may differ."]
            if book.get("region_code") != arch.region_code
            else []
        ),
    }


def summary_markdown(cost: dict[str, Any]) -> list[str]:
    """Cost section of the explanation."""
    if not cost.get("available"):
        return ["## Estimated cost", "", cost.get("message", ""), ""]
    money = lambda v: f"${v:,.2f}" if v < 100 else f"${v:,.0f}"  # noqa: E731
    out = [
        "## Estimated cost",
        "",
        f"About **{money(cost['monthly'])} a month** on demand "
        f"({cost['price_region']} list prices as of {cost['as_of']}; {cost['source']}"
        + ("" if cost["verified"] else ", approximate")
        + ").",
        "",
        "| Period | On demand | With commitments |",
        "|---|---:|---:|",
    ]
    for t in cost["terms"]:
        committed = money(t["committed"]) if t["committed"] is not None else "–"
        out.append(f"| {t['label']} | {money(t['on_demand'])} | {committed} |")
    out += ["", "| Service | Per month |", "|---|---:|"]
    for line in sorted(cost["lines"], key=lambda line: -line["monthly"]):
        out.append(f"| {line['service']} ({line['label']}) | {money(line['monthly'])} |")
    out.append("")
    for note in cost["commitment_notes"]:
        out.append(f"- {note}")
    for note in cost["assumptions"]:
        out.append(f"- {note}")
    out.append("")
    return out
