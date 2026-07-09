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

## Known gotchas
- GEMINI_KEY_1 not configured yet — Router currently only has groq +
  openrouter in its provider list until that's added.
- Live smoke test succeeded on the first try (Groq didn't fail), so a
  *real* 429 fallback still hasn't been observed — only the mocked one in
  tests/unit/test_llm_router.py. SRS Definition-of-Done wants at least one
  real quota-exhaustion event witnessed; revisit this once free-tier usage
  climbs in later checkpoints.
