# Sybil Stage 4 (Advanced Analysis) Implementation Plan

> **Execution:** Follow this plan task-by-task within the user-authorized scope.

**Goal:** Implement Stage 4 of Aegis Sybil Defense: Bounded Max-Flow / Min-Cut Bottleneck Witness, Automated Adversarial Attack Search, and the 210-Scenario Structural Benchmark Matrix with interactive frontend analysis.

**Architecture:** 
- A sparse graph max-flow solver (`server/aegis/sybil_maxflow.py`) extracts a 2,500-node explanation subgraph around anchors and shop supporters, solves unit-capacity flow with `scipy.sparse.csgraph.maximum_flow`, and outputs the exact minimum cut edges isolating the cluster.
- An adversarial attack search optimizer (`server/aegis/sybil_search.py`) explores candidate attack topologies within the 25-credit Challenge budget (capped at 500 proposals / 60s) to discover worst-case attacks.
- A structural benchmark engine (`server/aegis/sybil_benchmark.py`) runs the 210-scenario matrix comparing naive counts, PageRank, and Aegis `sybil-v2`.
- REST endpoints and interactive canvas overlays in `/sybil` render the bottleneck witness, trigger attack searches, and display matrix results.

**Tech Stack:** Python 3.12, FastAPI, NumPy, SciPy (csgraph maximum_flow), Pydantic v2, Next.js 16, TypeScript, d3-force canvas.

---

### Task 1: Stage 4 Schemas & Contract Definition

**Files:**
- Modify: `server/aegis/schemas.py`
- Modify: `web/lib/api-types.ts` (regenerate via openapi-typescript)

**Step 1: Add Stage 4 schemas in `server/aegis/schemas.py`**
- `SybilCutEdge`: source, target, capacity
- `SybilBottleneckWitness`: revision_id, shop, subgraph_nodes, subgraph_edges, max_flow, cut_size, cut_edges, bottleneck_nodes, elapsed_ms, disclosure
- `SybilAttackSearchProposal`: iteration, pattern, count, credits, score, support, withdrawal, connection
- `SybilAttackSearchRequest`: target, seed, max_proposals, max_seconds
- `SybilAttackSearchResult`: dataset_id, target_shop, proposals_evaluated, elapsed_s, stopped_reason, best_score, best_proposal, best_scenario, best_revision_id, history
- `SybilBenchmarkRow`: family, size, credits, seed, raw_count, raw_rank, support, withdrawal, connection, total_robustness, passed_policy
- `SybilBenchmarkSummary`: total_scenarios, attacks_tested, controls_tested, naive_pass_rate, pagerank_pass_rate, aegis_pass_rate, clean_pass_rate, rows, elapsed_s

---

### Task 2: Max-Flow Bottleneck Witness (`server/aegis/sybil_maxflow.py`)

**Files:**
- Create: `server/aegis/sybil_maxflow.py`
- Test: `server/tests/test_sybil_maxflow.py`

**Steps:**
1. Extract k-hop neighborhood from anchors and shop recommenders up to 2,500 nodes.
2. Build unit node-capacitated flow network (vertex splitting $u_{in} \to u_{out}$ with capacity 1, supersource to anchors, shop supporters to supersink).
3. Compute maximum flow using `scipy.sparse.csgraph.maximum_flow`.
4. Traverse residual graph from source to identify reachable cut partition $(S, T)$ and return exact cut edges and bottleneck nodes.
5. Unit tests with known topologies (single bottleneck bridge, disconnected cluster, multi-anchor graph).

---

### Task 3: Adversarial Attack Search (`server/aegis/sybil_search.py`)

**Files:**
- Create: `server/aegis/sybil_search.py`
- Test: `server/tests/test_sybil_search.py`

**Steps:**
1. Implement heuristic local search exploring patterns (chain, dense, clusters, hub, star), sizes (10 to 300), bridges (0 to 12), and takeovers within 25 credits.
2. Enforce limits: max 500 proposals, 60s timeout, deterministic seed, no LLM.
3. Track score progression and return best proposal + scenario revision.
4. Unit tests verifying proposal limit, timeout adherence, budget validity, and score tracking.

---

### Task 4: Structural Benchmark Matrix (`server/aegis/sybil_benchmark.py`)

**Files:**
- Create: `server/aegis/sybil_benchmark.py`
- Test: `server/tests/test_sybil_benchmark.py`

**Steps:**
1. Generate the 6 families $\times$ 3 sizes $\times$ 2 credit levels $\times$ 5 seeds = 180 attacks + 30 controls = 210 scenarios.
2. Evaluate each against naive recommendation count, unweighted PageRank, and Aegis `sybil-v2`.
3. Aggregate pass rates: show 100% naive failure vs 0% Aegis attack pass rate.
4. Unit test verifying matrix generation and metric aggregation.

---

### Task 5: Server API Endpoints in `server/api/main.py`

**Files:**
- Modify: `server/api/main.py`
- Test: `server/tests/test_sybil_api.py`

**Steps:**
1. `POST /sybil/scenarios/{revision_id}/bottleneck`
2. `POST /sybil/datasets/{dataset_id}/search`
3. `GET /sybil/benchmark`
4. Regenerate `web/lib/api-types.ts` from FastAPI OpenAPI spec.

---

### Task 6: Frontend UI in `/sybil` (`web/app/(console)/sybil/`)

**Files:**
- Modify: `web/app/(console)/sybil/readiness.tsx`
- Modify: `web/app/(console)/sybil/graph.tsx`
- Modify: `web/app/(console)/sybil/sybil.module.css`

**Steps:**
1. Add Stage 4 Analysis section:
   - "Bottleneck Witness" button: triggers max-flow, renders cut size, max-flow value, and highlights cut edges in gold/amber dashed lines on canvas.
   - "Red-Team Attack Search" button: runs search, displays best attack discovered and button to load directly into the playground.
   - "Benchmark Matrix" expandable view showing the 210-case empirical evaluation table.
2. Update canvas in `graph.tsx` to render highlighted bottleneck witness edges.

---

### Task 7: Verification, Documentation & Push

**Steps:**
1. Run full backend pytest suite (all tests passing).
2. Run web unit tests, Next.js typegen, TypeScript typecheck, ESLint.
3. Update `session_notes.md` with Stage 4 completion notes.
4. Commit directly to `main` and `git push origin main`.
