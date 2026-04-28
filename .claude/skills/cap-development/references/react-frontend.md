# Generate a lean React frontend for a CAP backend

Generate a **single-file React frontend** (`app/index.html`) for the CAP backend. The file is served statically by CAP — no build step, no npm, no node_modules.

## Step 1 — Get the service model

Use the `search_model` tool from the cds-mcp to get access of the service definition.

For each service, collect:

| Item | Source |
|---|---|
| Service name | Definition name where `kind === "service"` |
| OData base path | `@path` annotation or `endpoints[].path` from MCP |
| Entities | Entity names scoped to the service (e.g. `OrderService.Orders`) |
| Key field(s) | Elements with `key: true` |
| Scalar fields + types | Elements with `type` like `cds.String`, `cds.Integer`, `cds.Decimal`, `cds.Boolean`, `cds.Timestamp`, `cds.UUID`, etc. |
| Bound actions | `actions` block on the entity — name, params (name + type) |
| Readonly | `@readonly` annotation on the entity |

## Step 2 — Generate `app/index.html`

Start from the template at [`assets/react-app-template.html`](../assets/react-app-template.html). Replace the placeholders:

- `{ServiceName}` — the service name for the page title
- `{ODataBasePath}` — the resolved OData base path (e.g. `/odata/v4/order`)
- `{EntityComponents}` — one React component per entity (see below)
- `{AppComponent}` — top-level `<App />` with tab navigation across entities

If multiple services exist, ask the user which one to generate the UI for (or generate one page per service).

### Hard rules

- **Single file** — all HTML, CSS, and JS in one `index.html`
- **No build step** — React, ReactDOM, and Babel loaded from `https://unpkg.com` CDN
- **JSX via Babel standalone** — `<script type="text/babel">` blocks only
- **No UI framework** — plain CSS only (the template has a minimal stylesheet)
- **No external assets** — no images, no icon fonts, no external CSS
- **OData v4 only** — use the `odata()` helper from the template

### Per-entity component

Generate a `function {EntityName}View()` component with:

**List view (default)**
- `useEffect` fetches `GET /{EntityName}?$top=100` on mount and on every refresh
- A `<table>` renders all scalar fields as columns (skip Associations/Compositions)
- Key column(s) rendered first
- A "Refresh" button re-triggers the fetch
- Status/boolean fields rendered with a coloured badge (green/red/grey)
- DateTime fields formatted as locale date strings
- Decimal/number fields right-aligned with `className="num"`

**Bound actions** (only for entities that have them)
- One button per action in each table row
- Actions with **no parameters**: click fires POST immediately, then refreshes
- Actions with **parameters**: click opens an inline `<dialog>` with one labelled `<input>` per parameter, "Confirm" and "Cancel" buttons
- On success: brief green banner (auto-dismiss 3s)
- On error: red banner with `error.message` from the OData response

**Readonly entities** — omit create/edit/delete controls.

### CSS guidelines

The template already includes a minimal stylesheet. When generating, follow these conventions:
- Table: full width, bordered cells, alternating row shading (already styled)
- Buttons: use `.btn` + `.btn-neutral` / `.btn-green` / `.btn-red` / `.btn-blue`
- Badges for status values: `.badge-green` (Approved/true), `.badge-red` (Rejected), `.badge-amber` (Pending), `.badge-grey` (false/unknown)
- Modal overlay via native `<dialog>` element (already styled)

## Step 3 — Verify

After writing the file:
1. Confirm `app/index.html` exists at the correct path
2. Print the OData base path and the list of entities/actions wired up
3. Tell the user to run `cds watch` and open `http://localhost:4004` to see the app
