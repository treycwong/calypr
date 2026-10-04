# Calypr design system

One palette and one set of primitives across the website, auth, dashboard and canvas. Tokens
live in `app/globals.css` (the app `:root` block) and `app/spectra.css` (raw ramps). There is no
per-page brand scope any more; if a page looks different, it's using a literal it shouldn't.

## Colour

**Colour is spent on state, not chrome.** The UI itself is graphite and white.

| Meaning | Token / utility | Use for |
|---|---|---|
| Primary action | `--primary` (white) · `bg-primary` | the one main button per view |
| Live / running / success | `--state-running`, `--brand` (`#5cc99b`) · `text-brand`, `bg-brand` | run glow, active wire, "connected" dots, usage meters, success ticks |
| Finished | `--state-done` (white 45%) | completed nodes/wires — never green, or a finished graph looks live |
| Warning | `--state-warning` · `text-state-warning`, `border-state-warning/30`, `bg-state-warning/[0.06]` | locked/read-only, out of credits, limits |
| Destructive | `--destructive` | delete, errors |

Never use raw Tailwind palette colours (`amber-*`, `emerald-*`, `cyan-*`) in product UI. Canvas
wire tints (`components/canvas/node-style.ts`) are the one exception, and none may be green.

The marketing CTA (`spectra/Button` `primary`) is the only green *button*; it's a website
device and is not used inside the product.

## Surfaces (elevation ladder)

| Step | Token | Hex | Where |
|---|---|---|---|
| 0 | `bg-surface-0` / `--background` | `#07090c` | page ground, canvas |
| 1 | `bg-surface-1` / `--sidebar` | `#0b0e12` | panels: sidebar, dashboard main, canvas chrome |
| 2 | `bg-surface-2` / `--card` | `#0f1216` | cards, node cards, palette tiles, dialogs |
| 3 | `bg-surface-3` / `--popover` | `#161a20` | hover on cards, menus, tooltips |
| 4 | `bg-surface-4` / `--accent` | `#1e242c` | selected/active items, menu hover |

Borders are hairlines: `border-border` (white 7%), `white/[0.08]` on cards, `white/[0.12–0.14]`
on hover. Hover washes on chrome are `white/[0.04–0.06]`, not a different grey.

## Radius

Fixed steps, spelled out: **6px** badges · **10px** menus, icon buttons, rail items, card art ·
**12px** inputs, buttons (`rounded-lg`), node cards, tiles · **16px** cards, panels, dialogs ·
**full** nav pills, primary buttons in the shell, tabs. `--radius` is 12px so shadcn's
`rounded-lg` lands on the right step.

## Type

- Figtree everywhere; JetBrains Mono for metadata labels.
- **Product headings:** `PageHeader` (Figtree 500, 24px). Section titles inside a page: 14–16px, 500.
- **Website headings:** `spectra/SectionHeading` (light 300–400, large). Don't use these in the app.
- **Labels:** `font-mono text-[10px]–[11px] uppercase tracking-[0.14em] text-muted-foreground`
  (panel titles, sidebar section labels, `Badge variant="label"`).

## Which primitive

| Need | Use |
|---|---|
| Button in the product | `ui/button` — `default` (white) once per view, `outline` / `ghost` otherwise |
| Button on the website | `spectra/Button` |
| Page title + actions | `dashboard/PageHeader` |
| Segmented switch | `ui/tabs` (pill) |
| Menu | `ui/dropdown-menu` |
| Icon-only control | `ui/tooltip` (or `RailTip` in the sidebar for links) |
| Metadata chip | `ui/badge` `variant="label"` |

## Shell

Dashboard: panels on a ground — `bg-surface-0 p-2 gap-2`, with the sidebar and main as two
16px-radius `surface-1` panels. The sidebar collapses to a 60px rail (`calypr-sidebar` cookie,
read server-side so there's no flash). Canvas: full-bleed (a tool, like Figma), chrome on
`surface-1`, canvas on `surface-0` with `--canvas-dot` dots.
