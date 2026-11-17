# Sybil Stage 5: Real Merchants & Web Domain Evaluation

**Objective:** Enable the Sybil engine to evaluate real web domains and e-commerce merchants against the imported 50,000-node Common Crawl graph, displaying real anchor trust paths, `sybil-v2` scores, bottleneck witnesses, and fail-closed policy decisions.

---

## Architecture Overview

1. **Resolver (`server/aegis/sybil_resolver.py`):** Canonicalizes URLs to domain nodes (e.g. `https://www.anker.com/products/123` → `anker.com`). Isolates multi-tenant stores (e.g. `*.myshopify.com`, `*.etsy.com`) so individual seller subdomains do not inherit platform-root authority.
2. **Evaluator (`server/aegis/sybil_real.py`):**
   - Looks up the domain in `dataset.base.index`.
   - If indexed: computes `sybil-v2` robustness ($S, D, L, E, R$), extracts incoming links, runs backward BFS to trace paths back to curated anchors (`wikipedia.org`, `mit.edu`, etc.), and computes min-cut bottleneck capacity.
   - If unindexed: returns fail-closed zero-support evidence ($R = 0.0$, `policy_passed = False`).
3. **API Endpoint (`server/api/main.py`):** `POST /sybil/real/evaluate`.
4. **Console UI (`web/app/(console)/sybil/`):** Real Merchant Inspector card on the `/sybil` playground with quick-test domain chips, score breakdowns, trust breadcrumbs, and policy badges.

---

## Step 1: Pydantic Schemas

**File:** `server/aegis/schemas.py`

Add models at the end of the Sybil section:

```python
class AnchorPath(BaseModel):
    anchor: str
    length: int
    hops: list[str]


class RealMerchantEvidence(BaseModel):
    domain: str
    canonical_url: str
    indexed: bool
    rank_in_dataset: int | None = None
    in_degree: int = 0
    out_degree: int = 0
    top_recommenders: list[str] = Field(default_factory=list)
    anchor_paths: list[AnchorPath] = Field(default_factory=list)
    scores: SybilShopScore
    policy_passed: bool
    policy_reason: str
    disclosure: str = (
        "A heuristic measure of structural support and tested sensitivity based on "
        "Common Crawl link history. Not a probability that this merchant is safe."
    )


class RealMerchantAuditRequest(BaseModel):
    url_or_domain: str
    max_paths: int = Field(default=3, ge=1, le=10)


class RealMerchantAuditResponse(BaseModel):
    evidence: RealMerchantEvidence
    elapsed_ms: float
```

---

## Step 2: Domain Entity Resolver

**File:** `server/aegis/sybil_resolver.py` (Create)

```python
"""URL to domain entity canonicalization for Sybil evaluation."""

from urllib.parse import urlsplit

MULTI_TENANT_SUFFIXES = (
    "myshopify.com",
    "etsy.com",
    "ebay.com",
    "gumroad.com",
    "bigcartel.com",
)


def resolve_merchant_domain(raw: str) -> tuple[str, bool]:
    """Extract canonical domain from URL or domain string.

    Returns (canonical_domain, is_multi_tenant).
    """
    cleaned = raw.strip().lower()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    parsed = urlsplit(cleaned)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]

    for suffix in MULTI_TENANT_SUFFIXES:
        if host.endswith("." + suffix):
            return host, True
        if host == suffix:
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                return f"{path_parts[0]}.{suffix}", True
            return host, True

    return host, False
```

**Unit Test:** `server/tests/test_sybil_resolver.py`

```python
from aegis.sybil_resolver import resolve_merchant_domain


def test_standard_domains():
    assert resolve_merchant_domain("https://www.anker.com/products/1")[0] == "anker.com"
    assert resolve_merchant_domain("ikea.com/in/en")[0] == "ikea.com"
    assert resolve_merchant_domain("store.google.com")[0] == "store.google.com"


def test_multi_tenant_subdomains():
    domain, multi = resolve_merchant_domain("https://gadgets.myshopify.com")
    assert domain == "gadgets.myshopify.com"
    assert multi is True


def test_multi_tenant_paths():
    domain, multi = resolve_merchant_domain("https://etsy.com/shop/handmadetoys")
    assert domain == "handmadetoys.etsy.com"
    assert multi is True
```

---

## Step 3: Real Domain Trust Evaluator

**File:** `server/aegis/sybil_real.py` (Create)

```python
"""Evaluates structural trust and anchor provenance for real domains."""

from collections import deque
from time import perf_counter

from aegis.schemas import AnchorPath, RealMerchantEvidence, SybilShopScore
from aegis.sybil import assess
from aegis.sybil_resolver import resolve_merchant_domain
from aegis.sybil_scenario import BaseGraph


def find_anchor_paths(base: BaseGraph, target_idx: int, max_paths: int = 3) -> list[AnchorPath]:
    """Backward BFS to find shortest paths from curated anchors to target node."""
    anchor_indices = {base.index[a] for a in base.anchors if a in base.index}
    if target_idx in anchor_indices:
        anchor_name = base.nodes[target_idx]
        return [AnchorPath(anchor=anchor_name, length=1, hops=[anchor_name])]

    # Build incoming adjacency for BFS
    incoming: list[list[int]] = [[] for _ in range(base.graph.n)]
    for u, v in base.graph.edges:
        incoming[v].append(u)

    queue: deque[list[int]] = deque([[target_idx]])
    visited = {target_idx}
    found: list[AnchorPath] = []

    while queue and len(found) < max_paths:
        path = queue.popleft()
        curr = path[-1]

        for prev in incoming[curr]:
            if prev in anchor_indices:
                full_path = [base.nodes[idx] for idx in reversed(path + [prev])]
                found.append(
                    AnchorPath(anchor=base.nodes[prev], length=len(full_path), hops=full_path)
                )
                if len(found) >= max_paths:
                    break
            elif prev not in visited and len(path) < 5:
                visited.add(prev)
                queue.append(path + [prev])

    return found


def evaluate_real_merchant(
    base: BaseGraph,
    url_or_domain: str,
    max_paths: int = 3,
) -> RealMerchantEvidence:
    domain, _ = resolve_merchant_domain(url_or_domain)

    if domain not in base.index:
        unindexed_score = SybilShopScore(
            recommendation_count=0,
            trust_weighted_support=0.0,
            structural_support=0.0,
            effective_anchors=0.0,
            anchor_breadth=0.0,
            anchor_withdrawal_resilience=0.0,
            tested_connection_resilience=0.0,
            total_robustness=0.0,
            cut_sources=(),
        )
        return RealMerchantEvidence(
            domain=domain,
            canonical_url=f"https://{domain}",
            indexed=False,
            scores=unindexed_score,
            policy_passed=False,
            policy_reason=(
                f"Domain '{domain}' is not in the Common Crawl anchor-neighborhood index "
                "(~50,000 domains). Classified as unindexed trust."
            ),
        )

    idx = base.index[domain]
    # Incoming recommenders from graph edges
    recommenders = [base.nodes[u] for u, v in base.graph.edges if v == idx]

    # Temporary scenario mapping domain recommendations to Shop A
    # to evaluate sybil-v2 robustness with identical formula
    from aegis.sybil_scenario import SybilScenario

    recs = tuple((r, "A") for r in recommenders)
    scenario = SybilScenario(base=base, graph=base.graph, recommendations=recs, edits=None)
    assessment = assess(
        base,
        scenario.graph,
        scenario.recommendations,
        base.anchors,
        base.support_scale,
    )
    score = assessment.scores.get("A")

    if score is None:
        raw_score = SybilShopScore(
            recommendation_count=len(recommenders),
            trust_weighted_support=0.0,
            structural_support=0.0,
            effective_anchors=0.0,
            anchor_breadth=0.0,
            anchor_withdrawal_resilience=0.0,
            tested_connection_resilience=0.0,
            total_robustness=0.0,
            cut_sources=(),
        )
    else:
        raw_score = SybilShopScore(
            recommendation_count=len(recommenders),
            trust_weighted_support=round(score.structural_support, 6),
            structural_support=round(score.support, 4),
            effective_anchors=round(score.effective_anchors, 2),
            anchor_breadth=round(score.breadth, 4),
            anchor_withdrawal_resilience=round(score.withdrawal, 4),
            tested_connection_resilience=round(score.connection, 4),
            total_robustness=round(score.total, 2),
            cut_sources=tuple(score.cut_sources),
        )

    paths = find_anchor_paths(base, idx, max_paths=max_paths)
    policy_passed = raw_score.total_robustness >= 60.0 and raw_score.anchor_withdrawal_resilience >= 0.5
    policy_reason = (
        "Meets structural robustness threshold (R >= 60.0, L >= 0.5)."
        if policy_passed
        else f"Fails structural threshold: R={raw_score.total_robustness:.1f} (req 60.0), L={raw_score.anchor_withdrawal_resilience:.2f} (req 0.50)."
    )

    out_degree = sum(1 for u, _ in base.graph.edges if u == idx)

    return RealMerchantEvidence(
        domain=domain,
        canonical_url=f"https://{domain}",
        indexed=True,
        in_degree=len(recommenders),
        out_degree=out_degree,
        top_recommenders=recommenders[:10],
        anchor_paths=paths,
        scores=raw_score,
        policy_passed=policy_passed,
        policy_reason=policy_reason,
    )
```

**Unit Test:** `server/tests/test_sybil_real.py`

```python
from types import SimpleNamespace
from aegis.sybil import Graph
from aegis.sybil_real import evaluate_real_merchant
from aegis.sybil_scenario import BaseGraph


def test_evaluate_indexed_and_unindexed():
    nodes = ("wikipedia.org", "techcrunch.com", "anker.com", "other.org")
    base = BaseGraph(
        dataset_id="test",
        revision="a" * 64,
        nodes=nodes,
        graph=Graph(4, ((0, 1), (1, 2)), (1, 1, 0, 0)),
        anchors=("wikipedia.org",),
        support_scale=0.1,
    )

    # 1. Unindexed domain
    unindexed = evaluate_real_merchant(base, "https://nonexistent-store.xyz")
    assert unindexed.indexed is False
    assert unindexed.policy_passed is False
    assert unindexed.scores.total_robustness == 0.0

    # 2. Indexed domain with anchor path
    indexed = evaluate_real_merchant(base, "https://anker.com")
    assert indexed.indexed is True
    assert indexed.domain == "anker.com"
    assert len(indexed.anchor_paths) > 0
    assert indexed.anchor_paths[0].hops == ["wikipedia.org", "techcrunch.com", "anker.com"]
```

---

## Step 4: Server API Endpoint & Contract Regeneration

**File:** `server/api/main.py`

Add import:
```python
from aegis.sybil_real import evaluate_real_merchant
from aegis.schemas import RealMerchantAuditRequest, RealMerchantAuditResponse
```

Add route:
```python
@app.post("/sybil/real/evaluate", response_model=RealMerchantAuditResponse)
async def evaluate_real_domain(body: RealMerchantAuditRequest) -> RealMerchantAuditResponse:
    dataset = _sybil_dataset()
    t0 = time.perf_counter()
    evidence = await asyncio.to_thread(
        evaluate_real_merchant, dataset.base, body.url_or_domain, body.max_paths
    )
    return RealMerchantAuditResponse(
        evidence=evidence,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
```

**Run Contract Sync:**
```bash
cd web
npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts
```
*(Or export openapi.json directly from python if server is offline).*

**Update `web/lib/api.ts`:**
```ts
sybilRealEvaluate: (body: Schema["RealMerchantAuditRequest"], signal?: AbortSignal) =>
  request<Schema["RealMerchantAuditResponse"]>("/sybil/real/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  }),
```

---

## Step 5: Frontend UI — Real Merchant Inspector

**File:** `web/app/(console)/sybil/real-merchant.tsx` (Create)

Create a dedicated inspector component:
- Search input for live URL/domain.
- Quick chips for sample testing (`wikipedia.org`, `anker.com`, `shady-gadgets.biz`).
- Results view showing:
  - Domain Badge: `Indexed (X recommenders)` vs `Unindexed (Fail-Closed)`.
  - Robustness gauge: $R$, $S$, $L$, $E$.
  - Anchor Trust Path breadcrumbs: `Anchor → Recommender → Target`.
  - Policy Status: `Approved for Autonomous Agent` (Green) or `Requires Human Consent (R < 60 or unindexed)` (Amber).
  - Standard disclosure text.

**File:** `web/app/(console)/sybil/readiness.tsx`
- Mount `<RealMerchantInspector />` under the Stage 4 section.

---

## Step 6: Verification Checklist

Execute each command and ensure zero failures:

1. **Python Unit Tests:**
   ```bash
   cd server
   .venv/Scripts/pytest tests/test_sybil_resolver.py tests/test_sybil_real.py tests/test_sybil_api.py
   ```
2. **Ruff Linter & Formatter:**
   ```bash
   cd server
   .venv/Scripts/ruff check aegis/ api/ tests/
   .venv/Scripts/ruff format --check aegis/ api/ tests/
   ```
3. **Web Types & Build:**
   ```bash
   cd web
   npx next typegen
   npx tsc --noEmit
   ```
4. **Web Unit Tests:**
   ```bash
   node --test web/lib/*.test.mjs
   ```
5. **Git Commit & Push (Direct to `main`):**
   ```bash
   git add .
   git commit -m "feat(sybil): implement Stage 5 real merchant and domain evaluation"
   git pull --rebase origin main
   git push origin main
   ```
