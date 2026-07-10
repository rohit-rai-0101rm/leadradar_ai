# LeadRadar AI — Project Memory

## What this project is
Agentic lead-discovery tool. Phase 1 MVP: find restaurants in a Mumbai
neighborhood with no/poor websites, audit them, score them, output JSON.

## Phase 1 MVP status
All 5 checkpoints complete and merged into main as of 2026-07-10. Full
pipeline (discover → audit → verdict → score → JSON)
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

- 2026-07-10: Phase 2 — Outreach Generation done (branch
  phase2-outreach-generation). This is NOT one of the SRS's original 5
  checkpoints — the SRS has no FRs and no build prompt for outreach, only
  a name in the architecture sketch (agents/outreach_agent.py,
  agents/prompts/outreach_email.md). User picked this as the Phase 2
  priority per the SRS's own "decide on Phase 2 priorities" closing note.
  Scope decision: only HOT/WARM-bucket leads get an outreach draft
  (COLD leads have fine websites, pitching them wastes LLM calls).
  Refactored shared logic out of verdict.py into agents/providers.py
  (build_providers()) and agents/json_utils.py (parse_json_object()) so
  the new agents/outreach_agent.py doesn't duplicate it — verdict.py's
  existing tests passed unchanged after the refactor, confirming it was
  behavior-preserving. New agents/prompts/outreach_email.md is a versioned
  prompt template (double-brace {{placeholders}} replaced via str.replace,
  not .format(), since the prompt itself needs literal JSON-instruction
  braces) generating a 120-180 word email with subject+body, signed
  "[Your Name]" as a placeholder (not an invented persona — the real user
  signs it). get_outreach_email() sends text-only (no screenshot resend —
  the verdict's reasoning already distilled the visual issue into text).
  Found and fixed two real JSON-parsing bugs surfaced by live runs (not
  hypothetical): (1) models often emit literal newlines inside JSON string
  values instead of escaping them as \n, which strict json.loads rejects
  — fixed via json.loads(text, strict=False); (2) models sometimes append
  a stray trailing "}" after the valid object closes, which json.loads
  rejects as "Extra data" — fixed by replacing the old regex-based
  extraction with json.JSONDecoder().raw_decode(), which parses the first
  valid JSON value and ignores trailing garbage. Both fixes live in the
  shared agents/json_utils.py, benefiting verdict.py too. Live full
  pipeline run: 20 businesses, 8 HOT/WARM leads, 7/8 outreach drafts
  parsed successfully on first or second attempt, 1/8 fell back safely
  after both attempts failed (confirmed via isolated re-testing that this
  is normal LLM response variance, not a parsing bug — the same business
  succeeded 4/4 times when retried separately). Manually read 2 full
  drafts: genuinely specific and grounded (one referenced the business's
  actual measured load time and missing SSL from the real audit data,
  not generic filler).

- 2026-07-11: Multi-vertical support. User wants to target multiple
  business categories (restaurants converted well in early live testing;
  hospitals were tried and rejected — see gotchas) instead of just
  restaurants in Bandra. Considered a separate YouTube/influencer
  discovery vertical first, decided against it (different platform,
  different audit signals, would double scope before the first vertical
  is even validated) — staying restaurant-shaped businesses only, just
  swappable category + location. scripts/run_discovery.py's hardcoded
  BANDRA_LAT/BANDRA_LNG/RADIUS_M/CATEGORY constants replaced with argparse
  flags (--category, --lat, --lng, --radius, --location-name), all
  optional and defaulting to the original restaurant/Bandra values so the
  zero-arg invocation is unchanged. Output filename now
  leads_{category}_{location}_{timestamp}.json (slugified) so different
  category/location runs never collide. Added config/target_categories.json:
  a plain reference list of Google Places categories judged likely to
  convert (owner-operated, single decision-maker, personal-mobile-as-
  contact — same profile that made restaurants work) plus an explicit
  "avoid" list with the hospital finding below. Live-tested with
  `--category beauty_salon --lat 19.1358 --lng 72.8262 --location-name
  "Andheri West, Mumbai" --radius 2000`: 20 salons found, pipeline
  completed end-to-end with real outreach drafts, confirming the flags
  actually thread through discovery → audit → verdict → scoring →
  outreach → output correctly.

- 2026-07-11: Fixed a real crash surfaced by the beauty_salon live test —
  OpenRouter free-tier models occasionally return HTTP 200 with an error
  body instead of the expected `choices` key (not a 429, so the existing
  RateLimitError/AuthError handling didn't catch it). This raised an
  unhandled KeyError that crashed the entire run instead of falling back
  to the next provider, violating the NFR-2 "never crash on single
  failure" pattern the rest of the codebase follows. Fixed by adding
  `ProviderError` (llm/providers/base.py) for malformed/missing-completion
  responses, checked explicitly in all three providers (openrouter, groq,
  gemini — same latent gap existed in all, fixed for consistency even
  though only openrouter had triggered it live) before indexing into the
  response, and wired into Router.complete()'s except clause alongside
  RateLimitError/AuthError so it triggers the same cooldown+fallback path.
  Confirmed via full 32-test unit suite (unaffected) and a second live run
  of the same beauty_salon/Andheri test: the same provider_error condition
  recurred but was now caught and logged (`llm_router_fallback
  provider=openrouter reason=provider_error`) instead of crashing the
  process, and the run completed end-to-end.

## Known gotchas
- Category choice matters a lot for conversion odds, confirmed via a live
  `--category hospital` test in Bandra (2026-07-10): 6/7 HOT/WARM leads had
  only a front-desk landline on file (not WhatsApp-able), and the single
  HOT lead with a real mobile number aside, the rest included a municipal
  government hospital with no single decision-maker — institutional
  categories don't fit this tool's outreach model even when the website
  signals score them as strong leads. Restaurants and (per the live
  beauty_salon test) salons/clinics fit better: owner-operated, personal
  mobile as the listed contact. See config/target_categories.json for the
  running recommended/avoid list.
- RESOLVED (2026-07-11): 3 real Gemini keys added (GEMINI_KEY_1/2/3),
  config.py and agents/providers.py extended to pick up all three (same
  multi-key pattern as groq_key_1/2), giving the router a third full
  fallback provider. Live-tested directly against the real API before
  wiring in: `gemini-2.0-flash` (the model already hardcoded in
  providers.py) returned 429 RESOURCE_EXHAUSTED with `limit: 0` on all
  three keys — not a real rate limit, that model simply isn't available
  on this account's free tier. `gemini-1.5-flash` 404'd (deprecated).
  `gemini-2.5-flash` worked cleanly on both a text-only call and a real
  vision call against an actual screenshot (assure_clinic screenshot from
  the beauty_salon test run) — description was genuinely grounded in the
  image content, not generic. Switched providers.py to `gemini-2.5-flash`.
  Also fixed scripts/smoke_test_router.py, which had its own stale
  duplicate `build_providers()` predating the agents/providers.py
  extraction (Phase 2) — still on gemini_key_1-only and the broken
  gemini-2.0-flash model name. Now imports the real build_providers()
  instead of duplicating it, so it can't drift out of sync again.
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
