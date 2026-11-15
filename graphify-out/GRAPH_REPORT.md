# Graph Report - Aegis  (2026-11-15)

## Corpus Check
- 222 files · ~214,292 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 78 file(s) not represented in the graph (top: .jsonl 21, .csv 20, .css 16)
- WARNING: 78 of 300 files seen (26%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 2198 nodes · 5401 edges · 129 communities (104 shown, 25 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 432 edges (avg confidence: 0.9)
- Token cost: 423,356 input · 0 output

## Community Hubs (Navigation)
- Agent View and Trials
- Schema Contracts
- Run Loop Orchestration
- FastAPI Routes
- Neuform Shader Sources
- URL Security and Scan
- Console Preset Launcher
- Pre-commit Checkout Audit
- Sybil Scenario Edits
- LLM Router Tests
- Sybil Runtime Queue
- Console Evidence UI
- Math Scramble Component
- Coordinate Click Executor
- Disguised Ad Fixtures
- Sybil Sparse Scoring
- Visibility and Hit-test
- shadcn Config
- Landing Verification Script
- Eval Harness Runner
- CI Workflow
- Web Dev Dependencies
- Console Shell Layout
- StarBorder Effect
- LLM Settings and Cache Modes
- Run Evidence JS Tests
- Landing Entrance Design
- Run API Tests
- Run Event Bus
- Landing Tunnel and Dithering
- Shield Audit Feedback
- Sybil Dataset Artifacts
- Run View Panes
- browser-use Wrapper Tests
- Recovery Tests
- Ask Gate and R1 Tests
- Postgres Event Store
- Sybil Graph Extraction
- Sybil Import Tests
- Fail-closed Guard
- R2 Disposable Trials
- Docker Compose Deploy
- A4 Link Truth
- Scan Tests
- TechText Effect
- Arena Contract Verification
- TS Config
- Scripted Agent Tests
- Shielded Loop Tests
- Counter Component
- HF Deploy Script
- Dev Plan Contracts
- Permission Pair UI
- Sybil Related Research
- Spotlight and Scheduler
- Sybil Data Download
- Deferred Extensions
- DecryptedText Effect
- Memory Event Store
- Landing Artwork and Phases
- ClickSpark Effect
- ElectricBorder Effect
- Verdict Engine
- Test Arena Server
- Decision Cache
- LLM Completion Calls
- Ledger and Schema Plan
- Product Positioning and Features
- Contract Tests
- Arena Verify Harness
- Product Design Context
- Console UX and Demo
- Web Runtime Dependencies
- Lab API Tests
- Eval Case Manifest
- Ask Endpoint Tests
- Detector Design Principles
- Sybil Page UI
- WebGraph Java Bridge
- Snapshot and Trap Research
- Eval Results Notes
- Landing Asset Pipeline
- B5 Instruction Quarantine
- Intent Ledger Parsing
- Galaxy Effect
- Brief and Benchmarks
- Button Component
- C1 Persuasion Stripper
- Lab Page
- Outcome Cards
- Server Hosting Setup
- Architecture Decisions
- Sybil Extension Spec
- Provider Failure and Own Keys
- Neuform Effect Runtime
- browser-use Demo
- Eval Protocol
- AnimatedContent Effect
- A3 Faint Text
- Run Replay Page
- Web Scripts
- Agent Pointer Docs
- Trap Arena Concept
- A5 Context Binding
- Rate Limit Bucket
- Wrapper Ask Flow
- Eval Presets Plan
- Dev Roles and Preambles
- Event Persistence
- DotGrid Effect
- Minor Cluster 110
- Minor Cluster 111
- Minor Cluster 112
- Minor Cluster 113
- Minor Cluster 114
- Minor Cluster 115
- Minor Cluster 116
- Minor Cluster 117
- Minor Cluster 118
- Minor Cluster 120
- Minor Cluster 121

## God Nodes (most connected - your core abstractions)
1. `run_side()` - 85 edges
2. `Action` - 76 edges
3. `Ledger` - 57 edges
4. `take_snapshot()` - 52 edges
5. `PageSnapshot` - 49 edges
6. `AskGate` - 44 edges
7. `Finding` - 41 edges
8. `react` - 40 edges
9. `click_text()` - 38 edges
10. `snap_at()` - 35 edges

## Surprising Connections (you probably didn't know these)
- `A-D3-01 B1 intent ledger` --references--> `parse_ledger()`  [EXTRACTED]
  DEV_PLAN.md → server/aegis/intent.py
- `Scroll-scrub inspection frame transition` --semantically_similar_to--> `Volumetric glowing square tunnel`  [INFERRED] [semantically similar]
  .impeccable/surfaces/web-app-landing-landing-experience-tsx.md → web/LANDING_IMPLEMENTATION_PLAN.md
- `auto_approve()` --uses--> `AskPayload`  [INFERRED]
  eval/browser_use_demo.py → server/aegis/schemas.py
- `A-D1-05 Minimal snapshot and agent view` --references--> `build_agent_view()`  [EXTRACTED]
  DEV_PLAN.md → server/aegis/agent.py
- `A-D1-06 Executor, agent, unshielded loop` --references--> `run_side()`  [EXTRACTED]
  DEV_PLAN.md → server/aegis/loop.py

## Import Cycles
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/a1_visibility.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/c1_persuasion.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/a5_context.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/a4_link_truth.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/b5_quarantine.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/a2_hit_test.py -> server/aegis/detectors/__init__.py`
- 2-file cycle: `server/aegis/detectors/__init__.py -> server/aegis/detectors/a3_faint_text.py -> server/aegis/detectors/__init__.py`

## Hyperedges (group relationships)
- **Shielded action pipeline: snapshot, verdict, audit, recovery, human gate** — server_aegis_snapshot_py_server_aegis_snapshot, server_aegis_verdict, server_aegis_audit, server_aegis_loop, server_aegis_events [INFERRED 0.85]
- **Contract codegen: schemas.py to OpenAPI to api-types.ts** — server_aegis_schemas, server_api_main, dev_plan_gen_command, web_lib_api_types [EXTRACTED 1.00]
- **Evaluation pipeline: run, analyze, publish, stats** — eval_run, eval_analyze, eval_publish, dev_plan_scripted_approval_policy, dev_plan_quota_rule [EXTRACTED 1.00]
- **Shielded per-action pipeline** — server_aegis_snapshot_py_server_aegis_snapshot, server_aegis_agent, server_aegis_verdict, server_aegis_executor, server_aegis_events, server_aegis_audit [EXTRACTED 1.00]
- **Permission ledger to audit to human approval** — project_brief_ledger, project_brief_b2, project_brief_d2, project_brief_r1_permission_pairs [INFERRED 0.85]
- **Sybil trust scoring** — project_brief_sybil_common_crawl, project_brief_sybil_anchors, project_brief_sybil_ppr, project_brief_sybil_score [EXTRACTED 1.00]
- **Seed-based link trust propagation lineage** — sybil_consensus_context_personalized_pagerank, sybil_consensus_context_trustrank, sybil_consensus_context_sybilrank, sybil_consensus_context_majestic_trust_flow [INFERRED 0.75]
- **Final evaluation block design** — eval_readme_final_protocol, eval_readme_configs_u_f_i, eval_readme_i_minus_audit, eval_readme_scripted_approval_policy, eval_readme_cache_off, eval_readme_eval_freeze [EXTRACTED 1.00]
- **Landing artwork render pipeline** — web_lib_landing_prepare_assets, web_public_landing_artwork_aegis_master, web_lib_landing_pixels, web_lib_landing_renderer, web_app_landing_aegis_artwork [INFERRED 0.75]
- **Aurora Home purchase flow product → cart → checkout → confirmation** — web_public_arena_product_product_page, web_public_arena_cart_cart_page, web_public_arena_checkout_checkout_page, web_public_arena_confirmation_confirmation_page [INFERRED 0.95]
- **T09 disguised ad trap and clean twin** — server_tests_fixtures_disguised_ad_disguised_ad_fixture, server_tests_fixtures_disguised_clean_disguised_clean_fixture, server_tests_fixtures_disguised_ad_t09_disguised_ad, server_tests_fixtures_disguised_clean_clean_twin [INFERRED 0.85]
- **Mini Shop bundled traps** — server_tests_fixtures_mini_shop_mini_shop_fixture, server_tests_fixtures_mini_shop_t05_hidden_injection, server_tests_fixtures_mini_shop_t03_preselected_plan, server_tests_fixtures_mini_shop_t01_fake_close, server_tests_fixtures_mini_shop_t02_clickjacking_overlay [EXTRACTED 1.00]

## Communities (129 total, 25 thin omitted)

### Community 0 - "Agent View and Trials"
Cohesion: 0.05
Nodes (50): _agent_element(), AgentElement, AgentView, build_agent_view(), build_messages(), _cap(), is_interactive(), render_agent_view() (+42 more)

### Community 1 - "Schema Contracts"
Cohesion: 0.07
Nodes (43): A-D3-04 D2 human gate, Action schema, Element schema, Event schema, Finding schema, Trap taxonomy, _checks(), _observed() (+35 more)

### Community 2 - "Run Loop Orchestration"
Cohesion: 0.07
Nodes (29): A-D3-03 Verified recovery (configuration I), A-D3-05 D4 fail-closed and latency, Agent, _Builder, _unshielded(), neutralize(), _ambiguous(), _ask_id() (+21 more)

### Community 3 - "FastAPI Routes"
Cohesion: 0.07
Nodes (37): make_store(), sample_run(), AskDecision, HealthArena, HealthLLM, Preset, RunCreate, RunCreated (+29 more)

### Community 4 - "Neuform Shader Sources"
Cohesion: 0.04
Nodes (29): AmberHalftone, BakeKnobs, ConnectivityGraph, ConstellationField, DefenseLines, DIAGNOSTICS_PANEL_DEFAULTS, DIAGNOSTICS_PANEL_VARIANTS, DiagnosticsPanelVariant (+21 more)

### Community 5 - "URL Security and Scan"
Cohesion: 0.07
Nodes (26): A-D1-02 Contract PR #1, C3 REST routes, sample_run_events(), LabRequest, ScanRequest, arena_origin(), install_guard(), handle() (+18 more)

### Community 6 - "Console Preset Launcher"
Cohesion: 0.09
Nodes (36): ConsolePage(), escapeXml(), extras(), groupPresets(), HEADLINE, MODEL_HINTS, OwnKeyPanel(), PIPELINE (+28 more)

### Community 7 - "Pre-commit Checkout Audit"
Cohesion: 0.15
Nodes (32): A-D3-02 Checkout extractor and pre-commit audit, AuditReport / CheckoutState, audit(), add(), correction_hint(), extract_checkout_state(), _fmt(), is_irreversible() (+24 more)

### Community 8 - "Sybil Scenario Edits"
Cohesion: 0.14
Nodes (25): SybilBudget, SybilGenerate, SybilLink, SybilRecommendation, SybilScenarioCreate, SybilWeights, apply(), assess_scenario() (+17 more)

### Community 9 - "LLM Router Tests"
Cohesion: 0.12
Nodes (21): FakeClient, Out, _rate_limit(), _router(), test_all_fail_raises_with_reasons(), no_sleep(), test_cache_hit_skips_network_and_is_labelled(), test_empty_failed_generation_is_resent_like_a_tool_call() (+13 more)

### Community 10 - "Sybil Runtime Queue"
Cohesion: 0.12
Nodes (13): SybilAssessmentRecord, SybilGraphEdge, SybilGraphNode, SybilGraphView, SybilShopScore, Dataset, assessment_identity(), calculate_assessment() (+5 more)

### Community 11 - "Console Evidence UI"
Cohesion: 0.11
Nodes (22): react, OutcomeCell(), permitted(), RunsPage(), ARENA_EXAMPLES, inView(), REAL_EXAMPLES, Report (+14 more)

### Community 12 - "Math Scramble Component"
Cohesion: 0.10
Nodes (28): MathScrambleDemo(), buildLayout(), Cell, colorCache, DEFAULT_COLORS, DEFAULT_LINES, findHighlights(), ghostAt() (+20 more)

### Community 13 - "Coordinate Click Executor"
Cohesion: 0.11
Nodes (9): _center(), ExecResult, execute(), hit_test_veto(), _NavWatch, test_click_on_covered_button_hits_overlay(), test_slow_navigation_is_waited_for(), test_type_and_tick() (+1 more)

### Community 14 - "Disguised Ad Fixtures"
Cohesion: 0.13
Nodes (28): Disguised ad test fixture, Off-domain ad link ads.example.net/offer, T09 disguised ad (Sponsored label outside box), Clean twin (no Sponsored label) for false-positive test, Disguised ad clean twin fixture, Prefilled email field, Faint fine print (T07-style), Mini Shop dev fixture (+20 more)

### Community 15 - "Sybil Sparse Scoring"
Cohesion: 0.19
Nodes (17): assess(), Assessment, Config, Graph, propagate(), Propagation, reference_scale(), ShopScore (+9 more)

### Community 16 - "Visibility and Hit-test"
Cohesion: 0.19
Nodes (13): detect(), detect(), has_box(), by_text(), click(), snap_at(), test_clean_twin_silent(), test_click_on_invisible_target_is_high() (+5 more)

### Community 17 - "shadcn Config"
Cohesion: 0.07
Nodes (26): aliases, components, hooks, lib, ui, utils, Authorization, iconLibrary (+18 more)

### Community 19 - "Eval Harness Runner"
Cohesion: 0.15
Nodes (13): A-D1-07 Eval skeleton and baseline pilot, GroundTruth, main(), _norm(), rescore(), Row, run_one(), on_start() (+5 more)

### Community 20 - "CI Workflow"
Cohesion: 0.08
Nodes (25): run, jobs, server, web, name, on, pull_request, push (+17 more)

### Community 21 - "Web Dev Dependencies"
Cohesion: 0.11
Nodes (24): eslint, eslint-config-next, openapi-typescript, tailwindcss, @tailwindcss/turbopack, @types/node, @types/react, @types/react-dom (+16 more)

### Community 22 - "Console Shell Layout"
Cohesion: 0.13
Nodes (20): ConsoleLayout(), ReloadRedirect(), BrowserHealth, Home(), also, AppShell(), CurrentMenu(), Cursor() (+12 more)

### Community 23 - "StarBorder Effect"
Cohesion: 0.12
Nodes (25): clamp(), ease(), HOVERS, mix(), Mote, outline(), Palette, Point (+17 more)

### Community 24 - "LLM Settings and Cache Modes"
Cohesion: 0.12
Nodes (10): A-D5-02 Cache modes (off/fallback/on), Current state audit (11 Nov, 09dd465), main(), JSON repair path in router, Settings, LLMRouter, parse_chain(), _slot() (+2 more)

### Community 25 - "Run Evidence JS Tests"
Cohesion: 0.12
Nodes (9): typescript, action, check(), helpers, verdict(), checkSampleStream(), main(), typescript@^5 (+1 more)

### Community 26 - "Landing Entrance Design"
Cohesion: 0.14
Nodes (19): Entrance surface spec (impeccable), React Bits Galaxy star field, Scroll-scrub inspection frame transition, React Bits TechText drafting vocabulary, boldFont, clamp01(), ease(), GLASS (+11 more)

### Community 27 - "Run API Tests"
Cohesion: 0.16
Nodes (17): LLMAgent, _cli(), _clean_purchase(), client(), _frames(), _ledger(), _run_own(), test_own_key_run_uses_its_router_and_never_leaks() (+9 more)

### Community 28 - "Run Event Bus"
Cohesion: 0.19
Nodes (10): _Run, RunBus, _done(), _snap(), _summary(), test_bus_persists_events_and_summary(), test_persist_failure_reported_once_and_run_continues(), test_postgres_copy_never_holds_the_jpeg() (+2 more)

### Community 29 - "Landing Tunnel and Dithering"
Cohesion: 0.17
Nodes (16): Props, SquareTunnel(), Landing acceptance checklist, Ordered 4x4 Bayer dithering, Landing implementation plan, Routes and entry rules, Dither and pixel renderer (WebGL2 instanced), Volumetric glowing square tunnel (+8 more)

### Community 30 - "Shield Audit Feedback"
Cohesion: 0.16
Nodes (13): _audit(), _audit_feedback(), _commit_decision(), _el(), _keys(), PageSnapshot, _script(), _cs_id() (+5 more)

### Community 31 - "Sybil Dataset Artifacts"
Cohesion: 0.23
Nodes (13): file_hash(), load_dataset(), artifact(), sign(), test_anchor_identity_is_checked(), test_artifact_hash_mismatch_is_rejected(), test_manifest_identity_is_checked(), test_missing_manifest_is_not_a_ready_dataset() (+5 more)

### Community 32 - "Run View Panes"
Cohesion: 0.16
Nodes (20): ApprovalDialog(), EvidenceCards(), TwoView(), AgentPane, describe(), EventRow, Ledger(), PaneProps (+12 more)

### Community 33 - "browser-use Wrapper Tests"
Cohesion: 0.22
Nodes (9): AegisTools, _approver(), Driver, session(), test_bypass_actions_removed(), test_clean_checkout_denied_pays_nothing(), test_no_approver_fails_closed(), test_t01_fake_close_blocked() (+1 more)

### Community 34 - "Recovery Tests"
Cohesion: 0.16
Nodes (10): _ChangingGate, _kinds(), _RepricingGate, _run(), test_i_minus_audit_pays_with_plan_still_ticked(), test_in_budget_change_during_approval_is_not_executed(), test_page_change_during_approval_is_reaudited(), keep() (+2 more)

### Community 35 - "Ask Gate and R1 Tests"
Cohesion: 0.18
Nodes (13): AskGate, _checks(), _hash(), _run(), test_authorized_plan_permitted_and_kept(), test_benign_gift_wrap_permitted(), test_budget_conflict_asks_and_nothing_is_bought(), test_forbidden_plan_removed_by_agent() (+5 more)

### Community 37 - "Sybil Graph Extraction"
Cohesion: 0.16
Nodes (5): extract(), Extraction, Adjacency, labels(), prepare()

### Community 38 - "Sybil Import Tests"
Cohesion: 0.12
Nodes (6): test_bounded_range_requests(), test_confirmed_resume_and_completed_hash(), test_short_confirmed_range_resumes_at_actual_server_end(), test_unconfirmed_resume_preserves_file(), _files(), test_no_ground_truth_hooks_in_aegis()

### Community 39 - "Fail-closed Guard"
Cohesion: 0.19
Nodes (10): Finding, check_fast(), guard_finding(), run_guarded(), boom(), fine(), slow(), test_fail_open_logs_but_allows() (+2 more)

### Community 40 - "R2 Disposable Trials"
Cohesion: 0.14
Nodes (12): A-D4-03a/b R2 spike, A-D4-04 R2 go/no-go record, commitment_from_text(), outcome_from_page(), Commitment, TrialReport, apply_trial(), diff_states() (+4 more)

### Community 41 - "Docker Compose Deploy"
Cohesion: 0.11
Nodes (18): depends_on, image, ports, restart, volumes, SYBIL_DATA_DIR, build, env_file (+10 more)

### Community 42 - "A4 Link Truth"
Cohesion: 0.23
Nodes (11): detect(), _dist(), _domain_ok(), _host(), _lie(), Element, Ledger, test_clean_twin_silent() (+3 more)

### Community 43 - "Scan Tests"
Cohesion: 0.16
Nodes (7): arena_port(), client(), local_is_public(), scan(), test_rebinding_is_refused(), test_refuses_non_public(), test_trap_page_and_clean_twin()

### Community 44 - "TechText Effect"
Cohesion: 0.15
Nodes (18): approach(), Art, Band, Box, Cell, clamp01(), Glyph, Kick (+10 more)

### Community 46 - "TS Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 47 - "Scripted Agent Tests"
Cohesion: 0.16
Nodes (10): click_text(), test_order_confirmation_ends_the_side(), test_scripted_clean_purchase_on_arena(), test_start_url(), test_unshielded_loop_on_fixture(), _box(), _loop(), test_loop_r2_reroutes_then_verifies_untick() (+2 more)

### Community 48 - "Shielded Loop Tests"
Cohesion: 0.27
Nodes (12): start_url(), ScriptedAgent, _run(), test_clean_flow_has_no_stops(), test_commitment_lines(), test_t01_fake_close_rerouted_then_second_choice_runs(), test_t02_overlay_neutralized_but_unshielded_subscribes(), test_t05_injection_stripped_and_logged() (+4 more)

### Community 49 - "Counter Component"
Cohesion: 0.20
Nodes (17): clamp(), Counter(), CounterProps, createFormatter(), digitsFor(), DIRECTIONS, Engine, Item (+9 more)

### Community 50 - "HF Deploy Script"
Cohesion: 0.15
Nodes (11): load_env(), main(), web/app/app-theme.css, Day 3 console: ASK dialog, evidence and outcome cards, Web README (Shield Console + arena), Gift wrap benign add-on (R1), Human-only release checks, Console routes (/console, /runs, /stats, /health, /arena) (+3 more)

### Community 51 - "Dev Plan Contracts"
Cohesion: 0.13
Nodes (16): DEV_PLAN.md (Aegis 7-day plan), Commit and push protocol (no branches), C2 SSE wire format, C6 Screenshots and replay, C7 Eval freeze (Mon 16 11:00), Critical path, Daily sync protocol, Day-by-day schedule (+8 more)

### Community 52 - "Permission Pair UI"
Cohesion: 0.14
Nodes (9): next, PairSummary(), permissionLabel(), PermissionPair(), shieldedOutcome(), azeretMono, coolvetica, metadata (+1 more)

### Community 53 - "Sybil Related Research"
Cohesion: 0.16
Nodes (15): Anduin (2026), BrightID, De-anonymizing Social Networks, Sybil Consensus Context (discussion reference), Epistemic Sybil Resistance (2026), Majestic Trust Flow, Manufactured consensus attack, Occlusion saliency experiment (+7 more)

### Community 54 - "Spotlight and Scheduler"
Cohesion: 0.18
Nodes (15): clamp(), falloff(), Palette, Settings, SHAPES, SpotlightCard(), SpotlightCardProps, SpotlightShape (+7 more)

### Community 55 - "Sybil Data Download"
Cohesion: 0.18
Nodes (6): download(), main(), fetch(), open_with_retry(), sha256(), storage_check()

### Community 56 - "Deferred Extensions"
Cohesion: 0.17
Nodes (14): ALEX behavioral model learning, AttriGuard, ConsentChk, Cordon semantic transactions, Stage 1 core verification gates, Deep check / Pro checking (two-control, four configurations), Deferred Extensions (partner reference), Independent ecommerce platform test deployment (Stage 4) (+6 more)

### Community 57 - "DecryptedText Effect"
Cohesion: 0.17
Nodes (15): motion, DecryptedText, advance(), DecryptedText(), DecryptedTextProps, EngineRef, flipFrames(), FrameState (+7 more)

### Community 59 - "Landing Artwork and Phases"
Cohesion: 0.18
Nodes (11): AegisArtwork(), Props, SliderControlProps, Landing phase state machine, animate(), Phase, SEEN_KEY, signalConsoleEntry() (+3 more)

### Community 60 - "ClickSpark Effect"
Cohesion: 0.17
Nodes (15): Burst, channels(), clamp(), ClickSpark, ClickSparkEasing, ClickSparkHandle, ClickSparkProps, ClickSparkShape (+7 more)

### Community 61 - "ElectricBorder Effect"
Cohesion: 0.22
Nodes (15): BorderPath, clamp(), compile(), ElectricBorder(), ElectricBorderProps, link(), nearestOn(), parseColor() (+7 more)

### Community 62 - "Verdict Engine"
Cohesion: 0.20
Nodes (12): A-D1-06 Executor, agent, unshielded loop, A-D2-06 Verdict engine and shielded loop (F), VerdictPayload.neutralized (T02 click-through), fast_detectors(), run_fast(), _a(), Action, combine() (+4 more)

### Community 63 - "Test Arena Server"
Cohesion: 0.18
Nodes (6): serve(), arena_url(), fixture_url(), page(), _QuietHandler, _serve()

### Community 64 - "Decision Cache"
Cohesion: 0.17
Nodes (4): PgCache, DecisionCache, LLMResult, MemoryCache

### Community 65 - "LLM Completion Calls"
Cohesion: 0.16
Nodes (4): cache_key(), _failed_generation(), _LoggedErrors, _retry_after()

### Community 66 - "Ledger and Schema Plan"
Cohesion: 0.14
Nodes (9): A-D3-01 B1 intent ledger, B-D4-06 Metrics and analysis handoff, C1 Pydantic schema contract, C8 R2 trial payloads, Cut list, Open questions Q1-Q14, Outcome / commitments model, Veer prospective rollout (+1 more)

### Community 67 - "Product Positioning and Features"
Cohesion: 0.15
Nodes (6): Agent Browser Shield, PayBench, T03 preselection, T04 hidden fee, T06 urgency + social proof, T08 trick wording

### Community 68 - "Contract Tests"
Cohesion: 0.18
Nodes (4): client(), test_rest_sample_and_presets(), test_routes_declared(), test_sample_stream_framing()

### Community 70 - "Product Design Context"
Cohesion: 0.17
Nodes (6): Accessibility commitments, Brand commitments (AEGIS wordmark, dark ground, orange accent, React Bits), Primary user: hackathon judge on 1280x720 projector, Product design context (PRODUCT.md), eval-freeze tag and final eval blocks, Model groq:openai/gpt-oss-20b (eval/dev/demo)

### Community 71 - "Console UX and Demo"
Cohesion: 0.17
Nodes (6): Console routes (/, /console, /runs, /lab, /scan, /stats, /health, /arena), Veer, Approval binds exact checkout shown, Animated landing entrance (/), React Bits console revamp, Flat UI overhaul (app-theme.css, --sN tokens)

### Community 72 - "Web Runtime Dependencies"
Cohesion: 0.15
Nodes (13): lucide-react, react-dom, shadcn, three, tw-animate-css, dependencies, lucide-react@^1.71.0, next@16.4.6 (+5 more)

### Community 73 - "Lab API Tests"
Cohesion: 0.31
Nodes (8): client(), lab(), test_bad_requests_are_rejected(), test_box_without_effect_is_not_called_a_violation(), test_forbidden_plan_recommends_unticked(), test_label_is_text_not_markup_or_instructions(), test_permission_flips_the_answer(), test_reversed_sharing_box_recommends_ticked()

### Community 74 - "Eval Case Manifest"
Cohesion: 0.17
Nodes (11): cases, default_authorized, addons, budget, data_sharing, lines, shipping, default_task (+3 more)

### Community 75 - "Ask Endpoint Tests"
Cohesion: 0.30
Nodes (6): _decide(), _pending(), test_approve_deny_timeout(), test_auto_approve_is_labelled_demo(), test_resolve_twice_or_unknown_fails(), test_route_resolves_and_404s()

### Community 76 - "Detector Design Principles"
Cohesion: 0.17
Nodes (3): CaMeL, T05 hidden injection, T07 faint-text injection

### Community 77 - "Sybil Page UI"
Cohesion: 0.23
Nodes (8): SybilPage(), Assessment, Dataset, GraphPreview(), GraphView, Revision, Score(), SybilReadiness()

### Community 79 - "Snapshot and Trap Research"
Cohesion: 0.20
Nodes (6): A-D1-05 Minimal snapshot and agent view, C4 Arena contract, DECEPTICON (arXiv 2512.22894), EIA (arXiv 2409.11295), Pop-up attack paper (arXiv 2411.02391), SusBench (arXiv 2510.11035)

### Community 80 - "Eval Results Notes"
Cohesion: 0.20
Nodes (9): Known base-agent noise (early done), Baseline pilot U N=1, Divergence count (6 traps, gpt-oss-20b), Aegis evaluation README, E6 browser-use drop-in (AegisTools), Groq TPM / tokens-per-day limits, T11 cloaked checkout limit, Variant b pilot U and I (+1 more)

### Community 81 - "Landing Asset Pipeline"
Cohesion: 0.24
Nodes (9): Dithered Medusa Aegis shield artwork, require, sharp, aegis-dithered.png (three-color poster), aegis-master.png (3072x3072 master), Aegis artwork provenance, Imagegen generation prompt, Roboto Slab self-hosted font (Apache 2.0) (+1 more)

### Community 82 - "B5 Instruction Quarantine"
Cohesion: 0.38
Nodes (7): detect(), test_clean_twin_silent(), test_harmless_assistant_copy_silent(), test_ordinary_your_order_copy_silent(), test_output_directed_injections_flagged(), test_t05_injection_flagged(), test_t07_faint_injection_quarantined()

### Community 83 - "Intent Ledger Parsing"
Cohesion: 0.42
Nodes (10): parse_ledger(), _parse(), _parse(), _reply(), test_ambiguous_task_is_unresolved(), test_authorized_plan_is_named(), test_default_task(), test_flag_without_named_extra_is_refused() (+2 more)

### Community 84 - "Galaxy Effect"
Cohesion: 0.25
Nodes (10): clamp(), finish(), Galaxy(), GalaxyDirection, GalaxyProps, keyOf(), Program, Settings (+2 more)

### Community 85 - "Brief and Benchmarks"
Cohesion: 0.20
Nodes (7): Aegis (project brief), AgentSpec, DECEPTICON benchmark, SusBench benchmark, Track 03: AI Bodyguard, Verdict schema, Confirmed divergences T01b,T02,T03b,T04b,T05b,T08

### Community 86 - "Button Component"
Cohesion: 0.22
Nodes (8): @base-ui/react, class-variance-authority, cn, Button(), buttonVariants, @base-ui/react@^1.9.0, class-variance-authority@^0.7.1, cn@^0.5.2

### Community 87 - "C1 Persuasion Stripper"
Cohesion: 0.31
Nodes (5): detect(), _kind(), quote(), test_clean_twin_silent(), test_t06_pressure_flagged()

### Community 88 - "Lab Page"
Cohesion: 0.29
Nodes (9): Branch, EXAMPLES, headline(), Lab, LabPage(), money(), plain(), Receipt() (+1 more)

### Community 89 - "Outcome Cards"
Cohesion: 0.40
Nodes (9): Commitment, difference(), DoneEvent, OutcomeCards(), PERIOD_SHORT, recurringLabel(), recurringOf(), rupees() (+1 more)

### Community 90 - "Server Hosting Setup"
Cohesion: 0.33
Nodes (8): Oracle Always Free server setup, Oracle Ampere A1 VM, sslip.io hostname + docker compose, Tailscale Funnel backend hosting, fail(), json(), pass(), smoke.sh script

### Community 91 - "Architecture Decisions"
Cohesion: 0.22
Nodes (3): Architecture (web + server + Supabase), Tech stack, Backend on home PC via Tailscale Funnel + aegis.service

### Community 92 - "Sybil Extension Spec"
Cohesion: 0.31
Nodes (5): Eight declared trust anchors, Common Crawl domain graph cc-main-2026-aug-sep-oct, SYBIL_ENABLED feature flag, Sybil engine and Common Crawl import progress, Sybil scenario/assessment APIs

### Community 93 - "Provider Failure and Own Keys"
Cohesion: 0.28
Nodes (3): AllProvidersFailed, OwnLLM, OwnKeyRouter

### Community 94 - "Neuform Effect Runtime"
Cohesion: 0.25
Nodes (9): buildFocusedDocument(), clamp(), createEffectComponent(), DiagnosticsPanel(), NeuformBatchEffect(), readAutomaticMode(), resolveBackground(), resolveMode() (+1 more)

### Community 95 - "browser-use Demo"
Cohesion: 0.25
Nodes (3): ask_terminal(), auto_approve(), _Quiet

### Community 96 - "Eval Protocol"
Cohesion: 0.25
Nodes (6): Configurations U / F / I, eval-freeze code freeze tag, groq:openai/gpt-oss-20b eval/demo model, Final evaluation protocol (N=2, 50-run blocks), I-minus-audit matched ablation, project_brief.md

### Community 97 - "AnimatedContent Effect"
Cohesion: 0.25
Nodes (6): gsap, AnimatedContentProps, AnimatedContentStaggerFrom, AnimatedContentWipe, WIPES, gsap@^3.15.1

### Community 98 - "A3 Faint Text"
Cohesion: 0.43
Nodes (4): detect(), test_clean_twin_silent(), test_faint_text_flagged(), test_t07_faint_injection_flagged()

### Community 99 - "Run Replay Page"
Cohesion: 0.43
Nodes (6): Props, RunPage(), Session(), Live(), Replay(), RunSession()

### Community 100 - "Web Scripts"
Cohesion: 0.25
Nodes (8): scripts, build, dev, gen:types, lint, start, typecheck, verify:day1

### Community 101 - "Agent Pointer Docs"
Cohesion: 0.33
Nodes (3): AGENTS.md (Codex pointer), CLAUDE.md (Claude Code pointer), Session notes log

### Community 102 - "Trap Arena Concept"
Cohesion: 0.29
Nodes (4): Aurora Home mock shop, Default task text change, T11 cloaked checkout trap, Variant-b realistic traps

### Community 103 - "A5 Context Binding"
Cohesion: 0.43
Nodes (3): detect(), test_clean_twin_silent(), test_sponsored_checkout_flagged()

### Community 106 - "Eval Presets Plan"
Cohesion: 0.33
Nodes (3): A-D4-02 Full eval harness, C5 Presets, R1 permission pair presets

### Community 107 - "Dev Roles and Preambles"
Cohesion: 0.33
Nodes (6): Dev A (Claude Code user), Dev B (Codex user), GEN command (OpenAPI to api-types.ts), Preamble A (Claude Code), Preamble B (Codex), Task cards

### Community 109 - "DotGrid Effect"
Cohesion: 0.60
Nodes (5): backOut(), compile(), DotGrid(), smootherstep(), toRgb()

### Community 110 - "Minor Cluster 110"
Cohesion: 0.50
Nodes (5): Cloudflare Insights beacon script, Flow Field with Particle Trails page, Flow field particle renderer, postMessage param listener (SPEED, NOISE_SCALE), SimplexNoise (Gustavson)

### Community 111 - "Minor Cluster 111"
Cohesion: 0.40
Nodes (5): Attack Playground (judge experience), Automated attack search, Connection explanation (edge-removal counterfactual), Trusted-source compromise test, SYBIL_ENABLED feature flag

### Community 115 - "Minor Cluster 115"
Cohesion: 0.50
Nodes (3): allowBuilds, sharp, unrs-resolver

## Ambiguous Edges - Review These
- `Partner page` → `T08 partner offers / data sharing destination`  [AMBIGUOUS]
  web/public/arena/partner.html · relation: conceptually_related_to

## Knowledge Gaps
- **95 isolated node(s):** `sh`, `aegis`, `Critical path`, `Outcome / commitments model`, `R1 permission pair presets` (+90 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 743 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `Console Evidence UI` to `Neuform Shader Sources`, `Console Preset Launcher`, `Math Scramble Component`, `Web Dev Dependencies`, `Console Shell Layout`, `StarBorder Effect`, `Landing Entrance Design`, `Landing Tunnel and Dithering`, `Run View Panes`, `TechText Effect`, `Counter Component`, `Permission Pair UI`, `Spotlight and Scheduler`, `DecryptedText Effect`, `Landing Artwork and Phases`, `ClickSpark Effect`, `ElectricBorder Effect`, `Web Runtime Dependencies`, `Sybil Page UI`, `Galaxy Effect`, `Lab Page`, `AnimatedContent Effect`, `Run Replay Page`, `DotGrid Effect`?**
  _High betweenness centrality (0.238) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `run_side()` (e.g. with `Agent` and `.decide()`) actually correct?**
  _`run_side()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `sh`, `aegis`, `Critical path` to the rest of the system?**
  _95 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agent View and Trials` be split into smaller, more focused modules?**
  _Cohesion score 0.0546218487394958 - nodes in this community are weakly interconnected._
- **Why does `Web README (Shield Console + arena)` connect `HF Deploy Script` to `Eval Protocol`, `Arena Verify Harness`, `Console Evidence UI`, `Minor Cluster 111`, `Eval Results Notes`, `Landing Asset Pipeline`, `Console Shell Layout`, `Sybil Data Download`, `Run Evidence JS Tests`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `Action` (e.g. with `Agent` and `LLMAgent`) actually correct?**
  _`Action` has 29 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Partner page` and `T08 partner offers / data sharing destination`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._