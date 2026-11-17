# Sybil Stage 5: Real websites in the Common Crawl sample

**Status:** implemented 2026-11-17 (revised from the first draft of this plan; see "Changes from the draft").

**Goal:** a judge types any real URL or domain on `/sybil` and sees where that site stands in the
imported 50,000-site Common Crawl graph: the same sybil-v2 score as the playground shops, the link
paths that connect it to the anchors, the sites that send it the most trust, and whether the agent
would go ahead or ask first.

## How it works

1. **Resolver** (`server/aegis/sybil_resolver.py`). Parses a URL or bare domain into a lower-case
   ASCII host (IDN → punycode). Rejects IP addresses, single-label hosts and malformed labels
   (→ 422). Nothing is fetched. Matching tries the host, then each parent with at least two labels,
   and keeps the longest one in the sample (`store.cnet.com` → `cnet.com`; the graph holds
   registrable domains such as `amazon.com.au` and `www.gov.ie`).
2. **Shared platforms.** One seller on a shared platform never inherits the platform's trust:
   subdomain platforms (`*.myshopify.com`, `*.github.io`, `*.blogspot.com`, …) unless the seller's
   own subdomain is a node, and path sellers (`etsy.com/shop/x`, `ebay.com/str/x`). These return
   `shared_platform`, no score, ASK.
3. **Score** (`server/aegis/sybil_real.py`). The matched site is passed to the unchanged `assess()`
   as the only supporter of a one-off target, so its mass is exactly its own anchor trust. That is
   the quantity τ was frozen on (clean 95th percentile of node trust), so S, D, L and E mean the
   same here as for the shops. E cuts the top 12 outside sites linking into it.
4. **Evidence.** In-sample in-links, original outdegree, extraction depth, top 8 linkers by trust
   sent per link, and up to `max_paths` shortest anchor → site link chains (backward BFS, ≤ 6
   links, each chain ends at its first anchor, higher-trust linkers preferred).
5. **Policy.** Same as the agent's graph policy (`SybilGraphEvidence.passes`: R ≥ 60, S ≥ 0.5,
   L ≥ 0.5, converged). Status values:
   - `scored`: pass or ASK by the policy.
   - `anchor`: one of the eight declared anchors; passes by assumption.
   - `not_in_sample`: no evidence either way; no score (never shown as 0); ASK.
   - `shared_platform`: see 2; ASK.
   - `unavailable`: propagation did not converge; ASK.
6. **API:** `POST /sybil/real/evaluate` with `{query, max_paths=1..8}` → `SybilRealDomainEvidence`.
   Runs off the event loop; the domain index (domain → node, reverse adjacency) is warmed at
   startup. ~0.13–0.45 s per lookup on the PC.
7. **UI:** `web/app/(console)/sybil/real-site.tsx`, "Check a real website" under "Deeper analysis".
   Example chips: `techcrunch.com` (passes, R 63), `ebay.com` (R 44, asks), `anotherbikeshop.com`
   (R 1.5), `ikea.com` (not in sample), `gadgets.myshopify.com` (platform seller). Anything that
   doesn't pass is amber "asks you first", never red: a real site is never labelled bad.

## Limits (say these in Q&A)

- The sample is 50k sites around eight mostly academic anchors, so many big shops (`amazon.com`,
  `ikea.com`, `etsy.com`) are not in it. Only 12 of the 400 best-supported sites pass the policy.
- Links are not endorsements; asset/CDN links count too. Missing incoming links are possible.
- The score describes the imported graph, not the whole web or the merchant's behaviour.

## Adding real shops (amazon.com, flipkart.com, …)

The anchor sample does not contain most big shops. `eval/sybil_shops.txt` lists 47 shopping
sites, fixed before any of them was scored. `sybil_prepare.py --include` adds them on top of
the sample:

- **The anchor sample does not change.** It has the same 50k sites and the same 1M hash-selected
  links (tested in `eval/test_sybil_extract.py`).
- **Each listed shop joins only if a sampled site links to it.** It keeps every link between it
  and the sample, outside the edge limit, plus its true outdegree. Its depth is one past its
  shallowest linker.
- **The manifest records them** as `extraction.included`. The loader checks the base limits
  without them and allows depth + 1 only for these sites.
- **Some values change as a result.** τ, the baseline Shop A/B recommenders and the dataset hash
  are recomputed. Old playground revisions stop applying, as with any new artifact.

**Run on the machine that has the 9 GB source** (same environment as the first extraction):

```bash
cd server && uv run python ../eval/sybil_prepare.py \
  --source ../.sybil-data/source \
  --output ../.sybil-data/artifact-shops \
  --jar <path to the cc-webgraph jar used before> \
  --webgraph-commit 8a3a34e2f3bc16b865ee234eab83a4917086b814 \
  --include ../eval/sybil_shops.txt
```

It prints which shops were added, which were already sampled and which nothing in the sample
links to. Send the four output files (`manifest.json`, `nodes.json`, `adjacency.npz`,
`reverse.npz`, ~12 MB).

**Deploy:**
1. Copy the four files to a new folder on the PC, e.g. `server/data/sybil-shops/`.
2. Point `SYBIL_DATA_DIR` at that folder and restart `aegis.service`.
3. Keep `server/data/sybil/` as the fallback: switching back is a one-line `.env` change.

## Changes from the draft

- **Score:** the draft summed every in-linker's full trust as separate "recommendations". τ is
  calibrated on a node's own trust, so that pushed almost every site to S≈1. Now the site's own
  trust is scored.
- **Missing sites:** the draft scored them R = 0. Now they have no score (`not_in_sample`), which
  matches "unavailable, never zero".
- **Policy:** the draft dropped S ≥ 0.5. Now the shared policy object is used.
- **Resolver:**
  - It no longer invents hosts (`etsy.com/shop/x` → `x.etsy.com`).
  - A bare platform host is no longer flagged as a seller.
  - The platform flag is now used, not thrown away.
  - Subdomains map to the registrable domain.
- **Code:** the draft's code used names that don't exist (`base.nodes`, `graph.n`, `SybilScenario`,
  the `assess` signature, `ShopScore` fields) and a one-anchor test fixture that `assess` rejects.

## Verification

- `server/tests/test_sybil_real.py`: resolver, scoring equals node trust, subdomain match,
  missing/platform/anchor statuses, paths never pass through a second anchor, API 200/422.
- Full server suite, ruff, `pnpm typecheck`, `pnpm lint`; `web/lib/api-types.ts` regenerated.
