# LeadRadar AI — Project Memory

## What this project is
Agentic lead-discovery tool. Phase 1 MVP: find restaurants in a Mumbai
neighborhood with no/poor websites, audit them, score them, output JSON.

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

## Known gotchas
- GEMINI_KEY_1 not configured yet — Router currently only has groq +
  openrouter in its provider list until that's added.
- Live smoke test succeeded on the first try (Groq didn't fail), so a
  *real* 429 fallback still hasn't been observed — only the mocked one in
  tests/unit/test_llm_router.py. SRS Definition-of-Done wants at least one
  real quota-exhaustion event witnessed; revisit this once free-tier usage
  climbs in later checkpoints.
- Places API (New) `searchNearby` caps maxResultCount at 20 per call and
  has no next-page-token pagination (unlike the legacy API the SRS
  describes). Fine for MVP scale (~20 businesses/run) but multi-call
  pagination would be needed to scale beyond one `searchNearby` call per
  area in a later phase.
- web_audit.py launches a new browser per audit_website() call rather than
  reusing one browser across a whole run — simplest correct option for
  now; if run_discovery.py ever creeps close to the 5-minute NFR-3 budget
  with a larger batch, switch to one shared browser + per-site pages.
