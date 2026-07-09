# LeadRadar AI — Project Memory

## What this project is
Agentic lead-discovery tool. Phase 1 MVP: find restaurants in a Mumbai
neighborhood with no/poor websites, audit them, score them, output JSON.

## Phase 1 MVP status
All 5 checkpoints complete as of 2026-07-10 (branch checkpoint-5-scoring-output,
not yet merged). Full pipeline (discover → audit → verdict → score → JSON)
runs end-to-end via `uv run python scripts/run_discovery.py` in ~70-80s
against real Bandra, Mumbai data. SRS Section 11 Definition of Done:
- [x] Checkpoints 1-5 complete and logged here
- [x] One full run produces a JSON lead list with scores (output/leads_{timestamp}.json)
- [x] Router survived a real (not simulated) provider quota exhaustion —
      witnessed live during both the Checkpoint 4 and Checkpoint 5 runs
      (Groq 429 → OpenRouter fallback)
- [x] No hardcoded API keys in source files (all via .env / core/config.py)
- [x] HOT-bucket leads agree by eye: all 6 HOT leads in the latest run are
      businesses with no website at all — as bad as it gets
Phase 1 MVP is functionally done. Everything past this point (CRM,
outreach, multi-vertical/multi-city, dashboard, db/, features/, workers/,
Docker, CI) is explicitly Phase 2+ per the SRS.

## Architecture decisions log
- 2026-07-09: Checkpoint 1 done — LLM router built and tested with simulated
  429 fallback (mocked httpx.post, no real API calls). Cooldown default
  60min, in-memory dict keyed by (provider_name, key) in llm/cooldown.py.
  Router lives in src/leadradar/llm/router.py, providers in
  src/leadradar/llm/providers/ (groq, gemini, openrouter). Providers raise
  typed RateLimitError/AuthError (defined in providers/base.py) which the
  router catches to trigger cooldown + fallback. Project uses uv for
  dependency/venv management. No real provider API keys available yet —
  .env.example has placeholders only.

- 2026-07-10: Real Groq + OpenRouter keys added to .env; Gemini key skipped
  for now (deferred, not blocking — GEMINI_KEY_1 is optional). Added
  scripts/smoke_test_router.py for manual live testing against real
  provider APIs. Ran it once: Groq answered directly (200 OK), confirming
  live connectivity through the Router end-to-end.

- 2026-07-10: Checkpoint 2 done (branch checkpoint-2-business-discovery) —
  Business Discovery tool built in src/leadradar/tools/places_client.py,
  wired into scripts/run_discovery.py. Deviation from the SRS: the SRS
  assumes the legacy Google Places "Nearby Search" API, but that returned
  REQUEST_DENIED on this project ("legacy API not enabled"). Switched to
  **Places API (New)** `searchNearby` (POST + X-Goog-Api-Key/X-Goog-FieldMask
  headers) instead — confirmed working live. Deduplicates by place_id
  (FR-1.3) defensively, though a single call is already unique. Live run
  against Bandra, Mumbai (radius 3000m, category=restaurant) returned 20
  real businesses, 6 with no website (e.g. Mokai Cafe Chapel Road, Elco Veg
  Restaurant, Miya Kebabs) — confirms the tool finds genuine leads.

- 2026-07-10: Checkpoint 3 done (branch checkpoint-3-website-audit) —
  Website Audit tool built: src/leadradar/tools/web_audit.py
  (audit_website) + src/leadradar/tools/screenshot.py
  (capture_screenshot, filenames under ./screenshots/ as
  {slugified_business_name}_{short_url_hash}.png for easy identification —
  audit_website() and capture_screenshot() both take an optional `name`
  param, passed through from business["name"] in run_discovery.py).
  Launches a fresh Chromium instance per call via Playwright sync API —
  simple over optimal for MVP; revisit browser reuse if a full run gets
  slow. Extended beyond the SRS's literal Checkpoint 3 return shape to
  also include has_mobile_viewport (FR-2.3), decided explicitly since the
  SRS text was inconsistent between FR-2.3 and the Checkpoint 3 prompt.
  Null-website skip logic (FR-2.1) lives in the caller
  (scripts/run_discovery.py), not inside audit_website() itself, keeping
  the tool a pure "given a URL, audit it" function. Wired into
  run_discovery.py: each business now gets a business["audit"] dict.
  Live run against real Checkpoint 2 Bandra data: 20 businesses processed
  in ~44s (well under the 5-minute NFR-3 budget), 14 real screenshots
  saved, 6 no-website businesses correctly skipped without invoking
  Playwright, 0 websites failed to load. Caught a real signal too: "Lucky
  Restaurant" loaded fine but over plain http (has_ssl=False).

- 2026-07-10: Checkpoint 4 done (branch checkpoint-4-llm-verdict) — LLM
  Verdict on screenshots. Extended Provider.complete()/Router.complete()
  with an optional image_base64 param (base.py, groq/openrouter build
  OpenAI-style multimodal content via new openai_style_content() helper;
  gemini builds an inline_data part — Gemini path still untested, no key).
  New src/leadradar/agents/verdict.py: get_verdict(business, audit_result)
  always calls the LLM (text signals always sent per FR-2.4's literal
  wording), attaching the screenshot as an image only when
  audit_result["screenshot_path"] is set. Vision models validated live
  before building: Groq meta-llama/llama-4-scout-17b-16e-instruct (worked
  instantly, even on a 6.4MB screenshot) and OpenRouter
  nvidia/nemotron-nano-12b-v2-vl:free (several other "free" vision model
  IDs guessed from memory 404'd — OpenRouter's free lineup shifts often,
  had to query GET /api/v1/models live to find what's actually available).
  JSON parsing strips markdown code fences and falls back to regex-
  extracting the first {...} block; retries once on parse failure per the
  SRS, then returns a safe fallback verdict (needs_redesign=True,
  error="verdict_parse_failed") rather than crashing the run — same
  NFR-2 philosophy as the Router and web_audit.py. Wired into
  run_discovery.py; full live pipeline (discover→audit→verdict) on real
  Bandra data: 20 businesses in ~78s (well under NFR-3's 5-minute budget),
  8/20 flagged needing redesign. Spot-checked verdicts show genuine visual
  grounding, not boilerplate (e.g. correctly identified "Coming Soon"
  placeholder content on one real site, and an Instagram loading spinner
  on another).

- 2026-07-10: Checkpoint 5 done (branch checkpoint-5-scoring-output) —
  Scoring + Final JSON Output, the last Phase 1 checkpoint.
  src/leadradar/tools/scoring_rules.py: score_lead(business, audit_result,
  verdict) implements FR-4.1's additive scoring (no-website +40,
  needs_redesign +30, low rating +10, no SSL +10, slow load +10) and
  FR-4.2's bucketing (70+=HOT, 40-69=WARM, <40=COLD). SRS didn't define
  numeric thresholds for "low rating" / "slow load", so picked and
  documented defaults: rating < 4.0, load_time_ms > 3000 (3s, standard
  page-abandonment cutoff) — revisit if these feel off in practice.
  run_discovery.py now sorts businesses by score descending, writes the
  full pipeline output (discovery + audit + verdict + scoring fields per
  business) to output/leads_{timestamp}.json, and prints a final
  NAME/BUCKET/SCORE/NEEDS_REDESIGN summary table. Live full-pipeline run:
  20 businesses, JSON validated well-formed, 6 HOT leads (all no-website
  businesses, scores 80-90) — genuinely bad by eye. Another real Groq 429
  fallback fired during this run too (second time now, after Checkpoint 4).

## Known gotchas
- GEMINI_KEY_1 not configured yet — Router currently only has groq +
  openrouter in its provider list until that's added. Gemini's image
  support (inline_data) in gemini_provider.py is implemented but untested.
- RESOLVED (2026-07-10): a real 429 fallback has now been observed live —
  during the Checkpoint 4 full-pipeline run, Groq genuinely rate-limited
  mid-run and the Router fell back to OpenRouter successfully, satisfying
  the SRS's Definition-of-Done requirement for a real (not simulated)
  quota-exhaustion event.
- Places API (New) `searchNearby` caps maxResultCount at 20 per call and
  has no next-page-token pagination (unlike the legacy API the SRS
  describes). Fine for MVP scale (~20 businesses/run) but multi-call
  pagination would be needed to scale beyond one `searchNearby` call per
  area in a later phase.
- web_audit.py launches a new browser per audit_website() call rather than
  reusing one browser across a whole run — simplest correct option for
  now; if run_discovery.py ever creeps close to the 5-minute NFR-3 budget
  with a larger batch, switch to one shared browser + per-site pages.
- scoring_rules.py's needs_redesign contribution is a flat +30 regardless
  of severity — a site that's merely dated and a site that's a broken
  "Coming Soon" placeholder score identically on that axis. FR-4 is
  explicitly "MVP-simplified"; full multi-factor scoring is Phase 2.
- NFR-5 (resumable runs — a crash mid-run shouldn't reprocess already-done
  businesses) is NOT implemented. None of the 5 checkpoints' literal build
  prompts asked for it, and it's not in the Section 11 Definition-of-Done
  checklist, so it was left out of Phase 1 scope. Worth revisiting before
  running larger batches, since a crash partway through currently means
  starting over (and re-spending LLM/API quota on already-processed
  businesses).
