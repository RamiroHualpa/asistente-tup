## Purpose

Lets the tutor see which Moodle campus (tenant) is currently active and pick a campus when building a receta prompt, while keeping a single-tenant install working exactly as before with no configuration.

## ADDED Requirements

### Requirement: Tenant-aware paths with safe default
The system SHALL resolve the active tenant id from `~/.moodle-skill/estado.json` (`tenant_activo` field) on every call that needs a tenant-scoped path, and SHALL default to `"tup"` when that file is absent, unreadable, or missing the field.

#### Scenario: No estado.json present
- **WHEN** `~/.moodle-skill/estado.json` does not exist
- **THEN** the resolved active tenant is `"tup"` and all tenant-scoped paths resolve exactly as they did before multi-tenant support existed

#### Scenario: estado.json present with a tenant set
- **WHEN** `~/.moodle-skill/estado.json` exists and contains `"tenant_activo": "otra-facu"`
- **THEN** the resolved active tenant is `"otra-facu"` and tenant-scoped paths resolve under that tenant's directory

### Requirement: Campus listing endpoint
The system SHALL expose `GET /api/campus` returning the list of registered tenants from `~/.moodle-skill/tenants.json` (each with at least `id`, `nombre`, `url`) together with the currently active tenant id.

#### Scenario: tenants.json does not exist yet
- **WHEN** a client calls `GET /api/campus` and `~/.moodle-skill/tenants.json` is absent
- **THEN** the response contains an empty campus list and the active tenant id (defaulting to `"tup"` per the tenant-aware paths requirement)

#### Scenario: tenants.json has registered campuses
- **WHEN** a client calls `GET /api/campus` and `~/.moodle-skill/tenants.json` lists one or more tenants
- **THEN** the response contains every listed tenant and the id of whichever one is currently active

### Requirement: Campus selector in a receta
A receta's `campos` list MAY declare a field of type `campus`. When present, the frontend SHALL render a selector populated from `GET /api/campus`, and the prompt built for the Claude session SHALL include an instruction to use the `usar_campus` tool for the selected campus, without this system calling any Moodle-tenant MCP tool directly.

#### Scenario: User selects a non-default campus for a receta
- **WHEN** the tutor picks a campus other than the currently active one in a receta that declares a `campus` field, and submits the form
- **THEN** the prompt sent to the Claude session includes an instruction referencing `usar_campus` for the selected campus id

#### Scenario: User leaves the campus field at its default
- **WHEN** the tutor submits a receta with a `campus` field left at the pre-selected active tenant
- **THEN** the prompt sent to the Claude session behaves the same as before this change (no forced tenant switch beyond what is already active)

### Requirement: Backward compatibility for recetas and data reads
Existing recetas and `campos` entries that do not declare a `campus` field SHALL continue to work unchanged, and catalogue/`mis_datos` reads SHALL continue to work when no per-tenant directory exists yet.

#### Scenario: Receta without a campus field
- **WHEN** a receta's `campos` list has no entry of type `campus`
- **THEN** the receta's prompt-building behavior is identical to before this change

#### Scenario: Catalogue read before any tenant directory exists
- **WHEN** `GET /api/catalogo` is called and no `~/.moodle-skill/<tenant_id>/` directory has been created yet
- **THEN** the catalogue read falls back to the pre-existing flat file locations exactly as it did before this change
