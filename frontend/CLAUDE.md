# Frontend rules

## Do not touch the page edges (left and right)

Every signed-in page starts and ends at the same two lines, measured from the window edge:

- **Left edge: 40px** (`--edge-left`). The navbar logo and the page content start here.
- **Right edge: 28px** (`--edge-right`). The navbar's profile button, the profile card that opens
  from it, and the page content all end here. The 10px scrollbar (`--scrollbar-w`) is always
  reserved, and the content's right padding gives that space back.

These are defined once in `src/assets/main.css` and used only by `components/layout/AppShell.vue`
(the `.content` padding) and `components/layout/AppNavbar.vue` (the `.topbar` padding).

**Future implementations must not move either edge.** In particular, do not:

- change, override or re-declare `--edge-left`, `--edge-right` or `--scrollbar-w`, or the horizontal
  padding of `.content` and `.topbar`, or `scrollbar-gutter` on `.content`;
- add horizontal padding, margin or `max-width` to a page's root element, or centre it, so that its
  content starts or ends somewhere other than the two edges (a page's root fills the width of `.content`);
- use negative margins, `100vw`, or absolutely positioned wrappers to push content past an edge;
- add a second scroll container around a page that would put a scrollbar (and its gutter) inside the edges;
- use `--edge-left` / `--edge-right` anywhere except the two layout files above. A page that needs to
  line up with an edge already does, because it sits inside `.content`.

What is fine: padding, margins and widths *inside* a page's own cards, sections and grids, and vertical
spacing anywhere. If a screen genuinely needs a different edge (for example a full-bleed map), stop and
ask first; do not work around it locally.

If an edge has to change for the whole app, change the variable in `main.css` once and re-check the navbar,
the profile card, the notification panel and a dashboard together, because they are meant to line up.

The `/dev/ui` catalogue page mirrors the same edges so components show at their real widths.

## Other conventions

- One font, Inter, via `var(--font)`. One corner radius, `var(--radius)`, for containers, cards, fields
  and hover highlights; chips and pill buttons use `var(--radius-pill)`. Icons are white (`var(--icon)`).
- Reusable pieces live in `src/components/ui`, `src/components/layout` and `src/components/shared`, and
  are shown in the `/dev/ui` catalogue (development builds only). Add a new shared component there too.
- Keep the `data-testid` attributes and the `.nav-item` / `.content` class names: the Playwright specs use them.
