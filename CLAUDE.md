# CLAUDE.md

Guidance for coding agents working in this repository.
Sections 1–4 adapt the Karpathy-inspired guidelines from
[multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills);
the rest is specific to this project.

**Tradeoff:** these rules favour caution over speed. For trivial changes, use judgment.

## 1. Think before coding

- State assumptions explicitly. If a request has more than one reading, say so and ask; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- Never invent Home Assistant APIs (methods, selectors, translation keys, MDI icons). If unsure an API exists in the target version, check the installed `homeassistant` package first (`tests/test_ha_api.py` is the place to pin it).

## 2. Simplicity first

- Minimum code that solves the request. No speculative features, options or abstractions.
- No error handling for impossible cases; real failure modes (network, bad XML, missing channel) are handled and tested.
- If it could be half the length, rewrite it.

## 3. Surgical changes

- Touch only what the request needs. Don't reformat or "improve" adjacent code; match the existing style.
- Remove only what your own change made unused. Mention unrelated dead code, don't delete it.
- Every changed line should trace back to the request.

## 4. Goal-driven execution

- Turn the task into checks: "fix X" → a test that reproduces X, then make it pass.
- Write the test first, run it and watch it fail, then implement. For timer or fallback logic, also break the code on purpose once and confirm a test catches it.
- Report what was verified (tests run, real HA) separately from what was only read. Never say "works" for something not run.

## Project

Home Assistant custom integration `on_air`: what is on Italian TV now and tonight, from free XMLTV guides (open-epg.com, iptv-epg.org), one sensor per selected channel. A separate repo holds the Lovelace card (`ha-on-air-card`). Personal use, not published; the structure stays Marketplace-compatible.

### Architecture

- Pure modules, no `homeassistant` imports, time passed in as a parameter: `channels.py` (channel keys, presets, groups), `xmltv.py` (streaming parser), `merge.py` (source merge), `guide.py` (now/next/tonight, timer instants), `contract.py` (state and attributes), `models.py`.
- Home Assistant modules: `coordinator.py` (download every 12 h, parse in the executor, keep the last good data per source), `sensor.py` (no polling; one timer per sensor at the next programme boundary or the 06:00 rollover), `config_flow.py`, `__init__.py`.
- The integration computes, the card only presents. Every value a card shows is an attribute documented in `docs/attributes-contract.md`. Bump `contract_version` only for breaking changes (rename, removal, change of meaning).

### Rules

- `manifest.json`: `domain` and `name` first, the other keys sorted; no external requirements. Version consistent across manifest, card and git tag.
- Translations: `strings.json` == `translations/it.json`; `translations/en.json` has the same keys. UI text is Italian; code, comments, docstrings, README and docs are English.
- Options flows return the complete options (HA replaces `entry.options`, it does not merge).
- Use `dt_util.now()` / the HA time zone, never `datetime.now()` or `date.today()`.
- Keep big attributes out of the recorder (`_unrecorded_attributes`); attributes must stay far below 16 KB.
- No personal data in attributes or logs.

### Tests

- Python 3.14 with `pytest-homeassistant-custom-component` (`pip install -r requirements_test.txt`), then `pytest` from the repo root.
- No network in tests: XMLTV fixtures in `tests/fixtures/`, HTTP via `aioclient_mock`, time via `freezer`. Import `custom_components.on_air` at module level in test files (inside a test function HA's test package shadows it).
- The guide hosts may be unreachable from sandboxes; real downloads are checked on a real Home Assistant.

### Commits

Conventional title only, in English (`feat:`, `fix:`, `test:`, `docs:`, `chore:`): no body, no trailers. The maintainer commits and pushes.
