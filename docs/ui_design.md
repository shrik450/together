# UI / UX Design

This doc captures the UI/UX principles and a lightweight design system for
Together. It exists so new modules can feel cohesive without constraining their
layout.

## Goals

- Mobile-first UI that still feels great on desktop
- Utilitarian aesthetic (clarity > decoration), with delight coming from
  interactions and polish
- A consistent "app shell" across modules (global nav + page chrome), while
  allowing modules to choose their own density and layout in the main pane
- Server-rendered HTML + HTMX interactions with clear, reliable states
- Dark mode as a first-class default (via `prefers-color-scheme`)

## Non-goals

- A "branded" product look (no big accent colors, gradients, or marketing UI)
- A SPA-style client router or modal-heavy interface
- Autosave-driven UX (every mutation is an explicit form submission)

---

## Design Principles

1. **Content-first**: UI should get out of the way when content is present.
   Prefer typography, spacing, and structure over ornamentation.
2. **Utilitarian by default**: Calm, neutral surfaces and predictable patterns.
   Keep visual hierarchy clear and avoid unnecessary novelty.
3. **Mobile-first**: Start with a single-column, touch-friendly baseline. Add
   complexity only at larger viewports.
4. **Consistent shell, flexible modules**: The global navigation and base
   components are shared; modules own the layout of the main content pane.
5. **Purposeful typography**: Typography is a core design tool. Use it to
   communicate hierarchy and make long-form reading/writing comfortable.
6. **Density with intention**: Avoid "airy" whitespace, but never at the cost
   of scannability. Lists and forms should feel compact yet breathable.
7. **State colors only**: Color is primarily semantic (success/warn/danger).
   Avoid a persistent "brand accent" that competes with content.
8. **Micro-interactions over flourish**: Delight comes from responsiveness,
   subtle transitions, and small affordances—not animations or effects.
9. **Fit and finish**: Alignment, rhythm, and spacing matter. Small UI wobbles
   accumulate and make the whole app feel sloppy.

---

## Design Language

Together's visual identity is built on a clear metaphor: **a desktop of printed
media**. The app shell is unambiguously a computer interface; the content within
each module takes cues from physical print media appropriate to its purpose.

### The Metaphor

- **The shell is a desk.** Navigation, chrome, and actions are digital UI—clean,
  functional, and inspired by Apple platform conventions (macOS Sequoia / iOS 18
  era). There is a clear but not distracting separation between the UI and the
  content it holds.
- **The content is printed media.** Each module draws typographic and layout
  inspiration from a physical print format that fits its purpose. The content
  feels like a document sitting on the desk, not like more UI.
- **Not skeuomorphic.** We are not imitating physical objects (no paper textures,
  torn edges, or fake shadows). Instead, we adapt how print media has
  *transitioned to digital*—studying how newspapers, magazines, and journals
  have evolved into digital formats while retaining their typographic character.

### Module Print Inspirations

When designing a module, identify the print medium that best fits its content:

| Module          | Print Inspiration      | Typography / Layout Cues                          |
|-----------------|------------------------|---------------------------------------------------|
| Current Affairs | Newspaper (e.g., NYT)  | Serif headlines, kickers, datelines, linear flow  |
| Eats            | Food magazine          | Multi-column grids, pull quotes, mixed hierarchy  |
| Journal         | Typewritten journal    | Monospace, intimate margins, simple structure     |

The implementer should study how these media have been adapted for digital (e.g.,
nytimes.com, Bon Appétit, personal blogs) rather than copying print layouts
directly.

### Shell vs. Content

The shell and content have distinct responsibilities:

- **Shell (UI chrome)**
  - Always uses system UI font and base framework styling
  - Handles navigation (sidebar, breadcrumb bar)
  - Hosts page-level actions via the `actions` template context variable
  - Styled consistently across all modules

- **Content (module pane)**
  - Uses module-appropriate typography (serif, monospace, etc.)
  - Owns layout and density decisions
  - Contains in-content interactions (e.g., quiz answers, navigation within
    multi-step flows)
  - Styled per-module using the CSS framework's typography utilities

**The boundary rule:** If an interaction mutates state or triggers a workflow
(Save, Publish, Add, Delete), it belongs in the shell. If it's navigation or
interaction *within* content (selecting a quiz answer, expanding a section,
following a link), it lives in content.

### Actions in the Shell

Handlers pass page-level actions to templates via the `actions` context variable.
This keeps the UI/content separation clean:

- The shell provides a consistent action area (in the breadcrumb bar on narrow
  viewports, in the header on wide viewports)
- Handlers declare: action label, href, style (primary, secondary, destructive),
  and method (get, post)
- Users always know where to look for "what can I do on this page"

**Implementation:**

```python
from framework.ui import PageAction

@get("/journal/123")
async def journal_entry() -> Template:
    return Template(
        template_name="journal/entry.html",
        context={
            "actions": [
                PageAction(label="Discard", href="/journal/123/discard", style="secondary", method="post"),
                PageAction(label="Publish", href="/journal/123/publish", style="primary", method="post"),
            ],
        },
    )
```

Examples:

- Journal entry page: "Discard" (secondary), "Publish" (primary)
- Restaurant detail page: "Edit" (secondary), "Add Visit" (primary)
- Settings page: "Cancel" (secondary), "Save Changes" (primary)

In-content interactions (quiz prev/next, accordion expand, link navigation) do
not go through this mechanism—they are part of the content and styled
accordingly.

### Navigation Model

Together uses a unified navigation model based on `NavNode`. Instead of separate
breadcrumb and sidebar nav concepts, handlers provide a single `nav_stack` that
the shell renders appropriately for each viewport.

**Data structure:**

```python
from framework.ui import NavNode

@dataclass
class NavNode:
    label: str
    href: str | None = None   # None = current page
    icon: str | None = None   # Optional, any node can have one
```

**Context variable:**

```python
nav_stack: list[list[NavNode]]
```

Each inner list represents a **level** in the hierarchy. The first node in each
level is the active node at that level; subsequent nodes are siblings available
for quick-switching.

**Rules:**

1. Each inner list is a **level** in the hierarchy
2. First node in each level is the **active node**; remaining nodes are
   **siblings** for quick-switching
3. The **last level** is implicitly the current page
4. Handlers currently provide the levels they want rendered for the current
   page
5. The scaffolded shell always ensures Home appears in breadcrumb rendering
6. Registered top-level module `NavNode`s populate the sidebar when modules
   call `register_nav_node()`

**Example - entry page** (`/current-affairs/2026-01-10`):

```python
@get("/current-affairs/2026-01-10")
async def entry_page() -> Template:
    return Template(
        template_name="current_affairs/entry.html",
        context={
            "nav_stack": [
                [
                    NavNode(label="Jan 10"),
                    NavNode(label="Jan 9", href="/current-affairs/2026-01-09/"),
                    NavNode(label="Jan 8", href="/current-affairs/2026-01-08/"),
                ],
            ],
        },
    )
```

Illustrative full stack once a module registers its top-level nav node:

```
[
    [NavNode("Home", "/")],
    [NavNode("Current Affairs", "/current-affairs/", icon="newspaper")],
    [NavNode("Jan 10"), NavNode("Jan 9", "..."), NavNode("Jan 8", "...")],
]
```

**Example - module index** (`/current-affairs/`):

```python
@get("/current-affairs/")
async def index() -> Template:
    return Template(
        template_name="current_affairs/index.html",
        context={"nav_stack": []},
    )
```

Full stack: `[[Home, /]], [[Current Affairs]]` → Breadcrumb: `Home > Current Affairs`

**Example - deeper hierarchy** (`/eats/123/visit/456`):

```python
context={
    "nav_stack": [
        [
            NavNode(label="Katz's Deli", href="/eats/123/"),
            NavNode(label="Joe's Pizza", href="/eats/456/"),
        ],
        [
            NavNode(label="Visit Jan 5"),
            NavNode(label="Visit Dec 28", href="/eats/123/visit/123/"),
        ],
    ],
}
```

**Shell rendering:**

| Viewport | Behavior |
|----------|----------|
| **Narrow** | Breadcrumb bar shows only the **last two levels** of the rendered stack. Tapping a node with siblings opens a dropdown for quick-switching. |
| **Wide** | Sidebar shows all top-level modules. The active module is expanded, showing the full path with siblings visible at each level. |

---

## UI/UX Principles

> **Note:** This section covers UX rationale and design specifications for the
> app shell. For technical implementation details and code examples, see
> `docs/architecture.md`.

### Global App Shell & Navigation

Together has a consistent app shell that wraps every page. Navigation state is
provided via the `nav_stack` context variable (see "Navigation Model" above).

- **Layout modes**
  - **Wide viewports (`min-width: 900px`)**: Persistent left sidebar navigation,
    with the module content in the right pane.
  - **Narrow viewports**: A top breadcrumb bar instead of the sidebar, with the
    module content below.
- **Sidebar navigation (wide)**
  - Functions like a small file tree / accordion.
  - Top-level items are modules once those modules register via
    `register_nav_node()`.
  - When inside a module, that module expands to show the current path with
    siblings visible at each level (from `nav_stack`).
  - Avoid unbounded lists in the sidebar; use "Recent N" items plus stable entry
    points and let deep browsing happen in the main pane.
- **Breadcrumb bar (narrow)**
  - Shows only the last two levels of the rendered navigation stack.
  - Tapping a node with siblings opens a dropdown for quick-switching.
  - The current scaffold can show `Home` as a crumb when it is one of those last
    two levels.
  - The right side can include the logged-in user avatar/menu.
- **Module ownership**
  - Everything to the right of the sidebar (or below the breadcrumb bar) is the
    module's responsibility.
  - Modules may choose density and layout (reading column vs wide/grid), but
    must use shared tokens/components so the app still feels like one system.

### Navigation & HTMX

- Prefer boosted navigation and partial swaps for in-app navigation once feature
  modules need them.
- Every view should still have a canonical URL (no client-only state).
- Avoid modals as a primary interaction pattern; prefer:
  - inline expansion/collapsing sections
  - dedicated pages
  - multi-step forms rendered as pages/sections

### Interaction States (Loading, Success, Error)

- Never leave users guessing: every async interaction shows feedback.
- Loading states should be subtle but obvious:
  - disable the triggering control to prevent double-submit
  - show "Saving…" / "Loading…" text or a small inline spinner
  - use `aria-busy="true"` on the updating region
- Errors should be:
  - inline (near the relevant control/content)
  - written in plain language
  - non-destructive (do not clear user input)
  - recoverable (provide a retry path)

### Forms & Mutations (No Autosave)

- No autosave anywhere.
- Every mutation is an explicit form submit (Save / Submit / Mark done).
- After submit:
  - confirm the result (inline status or redirect with a visible confirmation)
  - preserve scroll position / context when staying on the same page
- For long inputs:
  - prefer smaller sections with explicit submits
  - if multi-step, each step is explicit and revisitable

### Layout & Density (Module-Specific)

- The shell is consistent; module content is not required to share one global
  density. Each module chooses layout and density informed by its print
  inspiration:
  - **Newspaper (Current Affairs)**: Dense, linear, strong vertical rhythm
  - **Magazine (Eats)**: Multi-column on wide, varied prominence, pull quotes
  - **Journal**: Intimate, generous margins, focused on reading/writing comfort
- Keep a predictable internal structure even when density differs:
  - page title + optional subtitle/metadata
  - primary actions near the top
  - consistent spacing scale and component styling

---

## Visual System

### Typography

**Shell typography:**

- Use system UI font (`system-ui, -apple-system, sans-serif`) for all shell
  elements (navigation, buttons, labels, metadata).

**Content typography:**

- Modules may use alternate font stacks appropriate to their print inspiration:
  - Serif: `Georgia, 'Times New Roman', serif` (newspaper, magazine)
  - Monospace: `'SF Mono', 'Fira Code', Consolas, monospace` (journal)
- The CSS framework provides utility classes for these stacks.
- Body text, headlines, and decorative type in content areas follow the module's
  print inspiration.

**Shared defaults:**

- Base font size: `16px`.
- Body line-height: `1.5–1.65` depending on density.
- Prefer consistent hierarchy over many variants:
  - `h1`: 1.5–1.75rem
  - `h2`: 1.25–1.4rem
  - `h3`: 1.1–1.25rem
  - Avoid more than 3 headline levels in a single view.
- Reading comfort:
  - aim for ~60–80 characters per line in reading layouts
  - avoid full-bleed body text on very wide screens

### Spacing & Sizing

Use a small set of spacing tokens everywhere; do not invent one-off gaps.

- Suggested scale: `4, 8, 12, 16, 24, 32, 48` (px)
- Minimum touch target: `44px` height for primary controls on mobile
- Borders are preferred over drop shadows; radius is subtle and consistent

### Color & Theming (State Colors Only)

- Use semantic CSS variables (roles), not hardcoded colors.
- Implement dark mode via `@media (prefers-color-scheme: dark)`.
- Keep the UI mostly grayscale; reserve color for meaning.

Suggested roles:

- `--bg`, `--surface`, `--text`, `--muted`, `--border`
- `--state-success`, `--state-warning`, `--state-danger`

Interactive affordances (links, focus rings) should not depend on a brand
accent; rely on underline, weight, borders, and `outline` for clarity.

### Icons

- Use a very small set of inline SVG icons for clarity and speed.
- Icons should be purely functional (navigation affordances, add/edit, status),
  not decorative.
- Match a restrained "SF Symbols-like" feel: simple, consistent stroke weight,
  no noisy detail.

### Motion

- Default to subtle transitions (100–200ms) for hover/press/reveal.
- Respect `prefers-reduced-motion` and avoid essential meaning conveyed only by
  animation.

---

## Component Principles (Shared)

These components should be provided by the base stylesheet so modules do not
recreate them with slightly different styles:

- Navigation shell (sidebar + breadcrumb bar)
- Page header (title + actions)
- Buttons (primary/secondary/destructive)
- Inputs (text, textarea, select), labels, help text, validation messages
- Lists/tables (dense + comfortable variants)
- Badges/chips for statuses
- Empty states (what this is + how to create the first item)
- Inline alerts (success/warn/error)

Modules may add module-specific components, but should build them out of the
shared primitives (spacing, typography, border treatments).

---

## HTML and CSS guidelines

- Use semantic HTML5 elements (`<header>`, `<nav>`, `<main>`, `<section>`,
`<article>`, `<footer>`) to structure pages; avoid `<div>` soup.
