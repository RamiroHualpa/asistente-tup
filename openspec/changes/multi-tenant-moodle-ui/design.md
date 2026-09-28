## Context

`backend/config.py` currently exposes `MOODLE_SKILL_DIR`, `SALIDAS_CAMPUS`, and `MIS_DATOS` as module-level constants computed once at import time (`HOME / ".moodle-skill"` etc.). The sibling `Skill-Moodle-dev` repo (contract already fixed, read from its `design.md`/`spec.md`, not modified here) is adding an active-tenant pointer at `~/.moodle-skill/estado.json` and per-tenant directories at `~/.moodle-skill/<tenant_id>/`, with `aulas.json`/`comisiones.json` falling back to the curated `tup` files, and a migration that only copies old flat files into `tup/` (never deletes them). See proposal.md - Why for the motivation.

This repo does not call moodle-tutor MCP tools directly from Python; it only builds natural-language prompts (`recetas.py` → `armar_pedido`) that a live `claude-agent-sdk` session sends to a Claude Code session, which in turn drives the MCP server. That pattern is preserved: campus selection is expressed as an instruction in the prompt, never as a direct tool call from this codebase.

## Goals / Non-Goals

**Goals:**
- Read the active tenant and resolve tenant-scoped paths dynamically (per call), so the active tenant can change between calls within the same running backend process without restarting it.
- Surface the list of registered campuses and the active one to the frontend.
- Let any of the 8 `campus`-category recetas optionally target a specific campus via the prompt, without adding per-receta logic.
- Preserve exact current behavior for installs that have never touched multi-tenant features.

**Non-Goals:**
- Implementing `agregar_campus`/`usar_campus` MCP tools (owned by `Skill-Moodle-dev`).
- Encrypting tenant data or credentials.
- Changing the prompt-only architecture (no direct MCP calls added to this repo).
- Persisting the frontend's campus selection anywhere beyond the single prompt being built.

## Decisions

- **Constants become functions.** `MOODLE_SKILL_DIR`, `SALIDAS_CAMPUS`, `MIS_DATOS` move from module-level `Path` constants to `moodle_skill_dir()`, `salidas_campus()`, `mis_datos_path()` functions that re-read `tenant_activo()` on every call. Alternative considered: keep them as constants and only add a separate tenant-path helper used in the (rare) call sites that need it — rejected because it would let some code paths silently keep using the stale `tup` root after a tenant switch, and the number of call sites to update (4 in `app.py`) is small enough that consistency is cheap.
- **`tenant_activo()` mirrors `leer()`'s tolerant-read pattern**: try to read and parse `~/.moodle-skill/estado.json`, catch `OSError`/`json.JSONDecodeError`, default to `"tup"` on any failure or missing `tenant_activo` key. This matches the sibling repo's own default and keeps a single fallback story across both repos.
- **`listar_campus()` reads `tenants.json` directly**, same direct-read pattern already used by `app.py`'s `_mis_datos()` for `mis_datos.json` — no new abstraction layer, tolerant of a missing file (returns `[]`).
- **`GET /api/campus` echoes the active tenant** (`{"campus": [...], "activo": "..."}`) rather than just the list, so the frontend can always show which campus is currently active — mirroring the sibling design's own "always show which is active" mitigation for tenant-switch confusion.
- **`campus` is a plain optional field for prompt substitution purposes**, not a new kind of validated input. `armar_pedido`/`faltantes` in `recetas.py` need no logic change; only the receta prompt templates gain an additional `[[...]]` optional block (e.g. `[[Trabajá contra el campus {campus} (usá usar_campus si hace falta).]]`) plus a `campos` entry of `tipo: "campus"`. Alternative considered: give `campus` special-cased handling in `armar_pedido` (e.g. always injecting a tenant-switch instruction) — rejected as unnecessary complexity; the existing optional-block mechanism already covers "only include this text if the field has a value."
- **Frontend selector mirrors the existing `curso` branch** in `web/app.js`'s `campo()` dispatcher: a plain `<select>` populated from `E.campus.campus`, with the entry matching `E.campus.activo` pre-selected. No `bus` dependency is needed (unlike `curso`→`comision`/`tarea`, there's no downstream field that depends on the chosen campus).

## Risks / Trade-offs

- [Risk] Converting constants to functions is a breaking change to any other code (in this repo only — sibling repo untouched) that imported `config.MOODLE_SKILL_DIR` etc. as values. → Mitigation: grep confirms `app.py` is the only other consumer; all 4 call sites are updated in this change's tasks.
- [Risk] Re-reading `estado.json` on every call adds a small amount of filesystem I/O per request. → Mitigation: the file is tiny and local; this matches the existing `leer()` pattern already used per-request for `config.json`, so it's consistent with current performance characteristics.
- [Risk] If the sibling repo's `tenants.json`/`estado.json` shapes end up different from what's assumed here (field names, structure). → Mitigation: this design was written after reading the sibling's fixed `design.md`/`spec.md`; if those files change before this ships, `tenant_activo()`/`listar_campus()` are the only two functions that would need adjusting.

## Migration Plan

No data migration in this repo (the sibling repo owns migrating old flat `~/.moodle-skill/` files into `tup/`, and does so non-destructively). This change is purely additive to `asistente-tup-dev`'s own code: existing installs with no `estado.json`/`tenants.json` keep working unchanged. No rollback concerns beyond standard git revert.
