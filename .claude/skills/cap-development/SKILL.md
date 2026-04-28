---
name: cap-development
description: Bootstraps a CAP Node.js application, provides expert guidance for building and extending CAP Node.js applications. Covers project initialization, CDS modeling, declarative annotations, and custom handler best practices. Use when the user wants to create a fullstack application or extend an existing CAP backend.
license: MIT
metadata:
  author: cap-team
  team: cap
---

## What I do

Provide correct, lean, idiomatic, testable guidance for CAP (Cloud Application Programming Model) Node.js
development — from project setup and CDS modeling through declarative annotations and custom
event handlers.

## MCP Server

Always use the CAP MCP server to:
- Search CAP documentation before guessing at APIs or annotations
- Read the effective CDS model of an existing project before adding or changing anything

Never use the CAP MCP server as Fiori/SAPUI5 documentation. It contains useful information about
how CAP integrates with Fiori/SAPUI5 but is not a complete reference for those frameworks.

## Steps

### 1. Project Initialization

When starting a new project, run in the `assets/` directory:

```sh
cds init <name> --nodejs
npm add -D @sap/cds-dk && npm pkg set scripts.build="cds build && cp -R app gen/srv/app && find gen/srv/app -name '*.cds' -delete && mkdir -p gen/srv/db && cp -R db/data gen/srv/db/data"
cds watch # start the dev loop
```

Rules:
- **Never** run `cds add sample` — it scaffolds a full demo app into the project.
- Use `cds add tiny-sample` only if the user explicitly wants a minimal starter model.
- Use `cds add <feature>` (e.g. `hana`, `xsuaa`, `approuter`, `mta`) to add features incrementally and only when needed (e.g. when deployment is requested).

### 2. CDS Modeling

Apply these conventions consistently:

- Reuse built-in aspects: `cuid`, `managed`, `temporal` from `@sap/cds/common`
- Use `Composition of many` for parent-child / document structures; `Association to` for references
- Use `localized String` for user-facing text that needs translation
- Naming: PascalCase for entities and types, camelCase for elements
- Define a `namespace` in `db/schema.cds` to avoid naming collisions between db and service layers
- Always expose db entities via projections in services — never expose db entities directly
- Expose only the elements clients actually need; use `excluding { ... }` to trim
- Don't expose an entity just because it exists — shape the projection for the consumer: trim with `excluding`, add calculated fields or flattened associations (e.g. `author.name as author`), and restrict with `@restrict`; only reach for actions/functions when the shape can't be expressed declaratively
- Entities written to only internally don't belong in the public service; put them in an admin service if needed
- Avoid two projections in the same service pointing to the same underlying entity — CDS can't auto-redirect associations and will error; remove the redundant projection or use `@cds.redirection.target`
- Keep Fiori UI annotations in `app/` annotation files, not in service definitions
- Always use `sap.common.CodeList` entities for status, type, category, or any classifying field — **never** use plain `String enum` types

### 3. Declarative First

Prefer annotations over custom handler code. Only write handlers when declarative options are insufficient.

| Need | Annotation |
|---|---|
| Input validation (format) | `@assert.format: '...'` |
| Input validation (range) | `@assert.range: [min, max]` |
| Cross-field / exists check | `@assert: (case when ... then '...' end)` |
| Required field / parameter | `@mandatory` |
| Read-only entity | `@readonly` |
| Insert-only entity | `@insertonly` |
| Authorization | `@restrict` / `@requires` |
| Audit fields | `: managed` aspect |
| Draft support | `@odata.draft.enabled` |

> Use Draft only when building a Fiori / SAPUI5 application. It is a complex mechanism that
> other UI frameworks cannot handle easily.

### 4. File & Service Conventions

- Match `.cds` and `.js` file names exactly (e.g. `order-service.cds` + `order-service.js`) — CAP auto-discovers implementations by convention; no `@impl` annotation needed
- One service per `.cds` file — splitting services keeps convention-based matching clean
- Use `@restrict` with `where` conditions (e.g. `userID = $user`) for row-level access control; don't rely on application-level filtering

### 5. Custom Handlers

When handlers are necessary:

- Register with `srv.on`, `srv.before`, `srv.after` — use the correct phase
- Reject with `req.reject(code, message)` — never throw raw errors
- Use explicit column lists in SELECT — never `SELECT *`
- Rely on CAP's intrinsic transaction handling — no manual transactions
- Minimize DB round-trips: combine checks into the query itself rather than SELECT + check + UPDATE
- Before writing any validation logic, check if it can be expressed declaratively

  ```js
  // ❌ two DB calls
  const row = await SELECT.one.from(Entity).where({ ID })
  if (row.status === 'locked') return req.reject(400, '...')
  await UPDATE(Entity, ID).with({ status: 'locked' })

  // ✅ one DB call
  const n = await UPDATE(Entity, ID)
    .where({ status: { '!=': 'locked' } })
    .with({ status: 'locked' })
  if (!n) return req.reject(409, 'Not found or already locked')
  ```

### 6. Sample Data

Generate data files with the CLI, never create them manually or invent UUIDs.

1. Generate CSVs for all entities: `cds add data --records <Amount>`
   Use `--filter <Entity>` to scope to specific entities (case-insensitive substring match; use regex like "books$" to exclude .texts compositions).
2. Replace placeholder values (e.g. title-29894036) with realistic domain content. Keep generated IDs and foreign-key references intact.
- **Gotcha**: `cds add data` without `--records` generates header-only CSVs, always pass `--records`.

### 7. Write Tests

*CRITICAL — NEVER skip this step*. immediately after adding any custom logic in event handlers. **Never** write tests for generic functionality the service provider already handles. Use **jest** as the test runner.
Follow these [testing guidelines](./references/write-tests.md)

### 8. Frontend

Always generate a lightweight single-file React app served statically by CAP as frontend for the application. No build step, no npm. Best for simple dashboards or custom UIs. Never generate a Fiori Elements frontend and never generate any other frontend framework.

Follow [react-frontend.md](./references/react-frontend.md)

**Rules (all frontends):**

- Create only **one** webapp under `app/`; use views/tabs for multiple pages
- Implement **all** features from the PRD — never build a reduced UI
- Frontend API calls must use correct URLs matching the backend service paths
- `manifest.json` service URLs must point to the local backend, not SAP cloud systems

## Don't

- Write handlers for things the generic service provider already handles
- Hardcode tenant IDs, system IDs, or credentials anywhere
- Put user-facing strings inline — use `_i18n/` bundles
- Run `cds add sample`
- Use `await` inside a synchronous `cds.on('served', ...)` callback
