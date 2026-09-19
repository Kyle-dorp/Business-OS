# Visual direction

*Standalone visual spec for `business-eos`. Companion to
`COMPETITIVE_DIRECTION.md` (the audit) and `OWNER_INTENT_AND_EOS_PRIMER.md`
(the reasoning). This file is visuals only — everything here is about what the
product looks like and how that gets enforced in code.*

*Written 18 September 2026 against the working tree. Contrast figures below were
computed from the actual token values, not estimated.*

---

## The verdict, up front

**The design language is not the problem. The enforcement of it is.**

There is a real, deliberate visual identity in this repo — a warm near-black
room, amber for interaction, one job per colour, ambient light and grain. It is
better than most funded SaaS products. The palette passes accessibility checks
that most shipped products fail. The charting is better-reasoned than commercial
charting libraries.

And it is currently held together by **CSS import order**, with a **second,
contradicting design system sitting dead in the tree**, and **three component
primitives that no page imports**. The identity exists as an intention. It is
not yet a system that a new screen automatically inherits.

Everything below is about closing that gap. The work is mostly deletion and
consolidation, not new design.

---

## Part 1 — What already exists and should not be touched

Establish this first so nothing good gets "improved" away.

### `frontend/src/theme.css` — the real design language

490 lines, and it opens with a statement of intent worth keeping verbatim:

> *The world: a warm room at night. Deep brown-black ground, light pooling from
> a few soft sources, fine grain over everything. Interface elements are barely
> there until you approach them, then they warm up.*
>
> *Colour has one job each: amber — interaction, focus, anything you can touch.
> rose — money leaving, warnings, variance. mint — money kept, confirmations,
> healthy states. Nothing else gets a colour.*

That last discipline is the single most valuable line in the stylesheet. It is
what stops a glow-heavy interface turning into a fairground. **Any new colour
added to this product must either take one of those three jobs or justify a
fourth in writing.**

### `frontend/src/components/Charts.jsx` — exemplary, leave alone

Colours run through a palette validator against the real surface. CVD ΔE
documented per series (12.5 deutan, 25.5 normal). A deliberate, *explained*
decision to sit outside the dark-mode lightness band, with the reasoning given.
Magnitude treated as sequential rather than categorical — the file correctly
notes that colouring bars by their own value "spends the identity channel
re-encoding what length already says." Every chart ships with a hover read-out
**and** a table view.

This is the quality bar for the rest of the product. Do not rewrite it; copy its
thinking.

### `frontend/src/components/States.jsx` — right rules, wrong reach

The rules it states are exactly correct:

> *Empty says what is missing and offers the action that fixes it. "No data"
> makes a reader wonder whether the page is broken.*
> *Loading shows the shape of what is coming rather than a spinner, so the
> layout does not jump when it arrives.*
> *Error says what failed and what to do. A stack trace is for us; a person
> mid-shift needs a sentence and a retry button.*

The problem is adoption, covered in Part 3.

### `landing/index.html` — the best-executed surface in the project

Fraunces display + Figtree UI, numbered section rails, a convergence animation
that *argues the product thesis* rather than decorating, cited statistics with
named sources, and disciplined copy ("Six logins. Six bills. One business.").

**The app should be pulled up to this page's standard, not the other way round.**

---

## Part 2 — The palette passes. Here is the proof.

Every token in `theme.css`, measured against the two real background values.
WCAG AA needs 4.5:1 for body text, 3.0:1 for large text and UI components.

| Token | Hex | on `--void` `#0E0B0C` | on `--void-lift` `#15100F` | Verdict |
|---|---|---|---|---|
| `--ink` | `#F6F0EA` | **17.33:1** | 16.69:1 | Body text ✓ |
| `--ink-2` | `#C6B9B1` | **10.24:1** | 9.86:1 | Body text ✓ |
| `--muted` | `#8C7F79` | **5.06:1** | 4.88:1 | Body text ✓ |
| `--faint` | `#6A5F5A` | **3.17:1** | 3.05:1 | Large text / UI only |
| `--amber` | `#F5A65B` | **9.78:1** | 9.42:1 | Body text ✓ |
| `--amber-hot` | `#FFC98F` | **13.06:1** | 12.58:1 | Body text ✓ |
| `--amber-deep` | `#C97A3A` | **5.90:1** | 5.69:1 | Body text ✓ |
| `--rose` | `#D9788D` | **6.55:1** | 6.31:1 | Body text ✓ |
| `--mint` | `#77D8C2` | **11.56:1** | 11.13:1 | Body text ✓ |

**Eight of nine tokens clear AA for body text with room to spare.** `--faint`
at 3.17:1 is the only one that doesn't, which is correct — it is a de-emphasis
token and should never carry body copy.

**Two rules that follow from this table:**

1. `--faint` is for rules, disabled states, timestamps and decorative marks.
   Never for a sentence a user needs to read. Add a comment saying so in
   `theme.css` next to the token.
2. **The palette does not need changing.** Any contrast failure in this product
   is a *usage* failure — something painting a colour the theme didn't choose.
   Which is exactly what Part 3 is about.

One thing the table does not cover: `body` is set to `font-weight: 300`.
Thin weights at small sizes erode effective contrast regardless of ratio. Body
copy below 16px should step up to 400.

---

## Part 3 — What is structurally broken

Four problems. All four are enforcement failures, not taste failures.

### 3.1 There are two design systems, and the dead one is loaded and armed

| | `src/theme.css` | `src/styles/design-tokens.css` |
|---|---|---|
| Accent | `--amber: #F5A65B` | `--accent: #00d9ff` (cyan) |
| Ground | `--void: #0E0B0C` (warm near-black) | `--bg: #fafafa` (light) |
| Type | Figtree / Fraunces | `-apple-system` system stack |
| Radius | contextual | `--radius-sm/md/lg/xl` 4/6/8/12px |
| Shadows | one `--shadow` | six-step `--shadow-xs` → `--shadow-xl` |
| Lines | 490 | 128 |

They are unrelated products. **And they both define `--surface`, `--text` and
`--bg`** — so whichever loads last silently wins.

`design-tokens.css` is imported by `src/styles/base.css` (279 lines), and
**nothing imports `base.css`** — not `main.tsx`, not `App.jsx`. So 407 lines of
a competing design system sit in the tree, dead, one stray import away from
repainting the entire application cyan-on-white.

This exact failure has already happened once. The comment in `main.tsx` records
it:

> *`index.css` is deliberately not imported. It was the pre-redesign Tailwind
> stylesheet, and because it loaded after App.jsx's theme files it won every tie
> — painting `body` #F9FAFB with #111827 text and a system font stack, directly
> over a design system built for a warm near-black. The sign-in card rendered
> cream-on-white and read as unstyled.*

That is a good comment. The lesson just wasn't applied to its siblings.

**Do this:**
- Delete `src/styles/` entirely (`design-tokens.css` + `base.css`).
- Remove `tailwindcss` from devDependencies, and delete `tailwind.config.js`
  and `postcss.config.js`. Grep confirms **zero** Tailwind utility classes
  anywhere in `src/`. Dead config that can win a specificity fight is not
  neutral.
- If any reset rules from `base.css` are genuinely wanted, move them into
  `theme.css` explicitly rather than keeping the file alive.

### 3.2 Twelve stylesheets, ordered by hand

`App.jsx` imports `App.css`, then eleven theme files, with this comment:

> *Loaded after App.css on purpose: App.css owns layout and structure, these own
> the look, and later import wins on equal specificity.*

The design language is currently a load-order agreement. The repo's own
`FRONTEND_PLAN.md` admits **26 `App.css` selectors still outrank the theme**,
and **222 classes exist solely for the Scheduling AI page**.

`App.css` is 998 lines — roughly a third of all styling in the product — and
every line of it is a place the old blue-and-purple design can still win.

**Finishing the `App.css` deletion is worth more than any new visual feature,**
because it retires an entire category of bug permanently rather than patching
instances of it. This is Phase 6 in `FRONTEND_PLAN.md`; it should move up.

Target end state: `theme.css` plus per-surface files that are *additive only* —
no file redefines a token another file owns.

### 3.3 The primitives exist and nothing uses them

| Component | Imported by |
|---|---|
| `components/Button.tsx` | **0 of 20 pages** |
| `components/Card.tsx` | **0 of 20 pages** |
| `components/Input.tsx` | **0 of 20 pages** |
| `components/States.jsx` | **5 of 20 pages** — Agent, Billing, Compliance, Preflight, Today |
| `hooks/useCountUp.js` | **2 of 20 pages** — Billing, Today |

This is the root cause of "the design language stops at the front door." Pages
are hand-writing `className="primary-btn"` and their own markup instead of
composing shared components, so a fix to a button fixes one button.

The five pages that *do* use `States` are — not coincidentally — the five that
read as finished.

**Do this, in this order:**

1. Make `Button`, `Card` and `Input` the only sanctioned way to render those
   things. One `Button` with variants (`primary` / `quiet` / `danger`), one
   `Card`, one `Input` with label, hint and error built in.
2. Convert pages to them. Start with the highest-traffic: Today, Manager,
   Platform, Finance, Inventory Intel.
3. **`States` on all 20 pages.** No page ships its own empty, loading or error
   markup. This single change closes most of the "flat boxes" gap.
4. Extend `useCountUp` to every figure that changes — money, percentages,
   counts. The plan's own rule: *"A price that jumps from $39 to $49 is a
   number. A price that counts up is a product."*
5. Add a lint rule or a test that fails when a page imports neither `States` nor
   a sanctioned primitive. The system has to be cheaper to follow than to
   bypass, or it won't be followed.

### 3.4 Twenty-one tabs and a glyph alphabet

`MANAGER_TABS` is a flat list of 21 entries. For comparison, Ninety.io covers
comparable surface area in **six** groups (Vision, Data, Process, Traction,
Issues, People). Twenty-one flat items is not a navigation, it is an inventory —
and for a new user it is twenty-one things they haven't set up.

The icon set is the full nav alphabet:

```
⌂ ◎ $ ↓ ≡ ↗ ✓ □ ◉ ◷ ▦ ◈ ⚖ ◑ ✦ ◇ ● ⛨ ⚙
```

These are typographically consistent, which is why the sidebar looks good. But
several carry no meaning (`◈` for Preflight, `◑` for Bookings, `◇` vs `◉` vs `◎`
are near-indistinguishable at 16px), and screen readers announce some as
punctuation or skip them.

**Do this:**
- Group into roughly six doors:
  **Today · Money** (sales, purchasing, bookkeeping, finance, reports)
  **· People** (availability, scheduling, preflight, labor rules)
  **· Stock** (inventory, stock intelligence)
  **· Guests** (bookings, contacts)
  **· Ask · Settings** (billing, security, notifications, settings)
- Replace the glyphs with `lucide-react` — **it is already a dependency** and
  currently unused. Real icons at a consistent 1.5px stroke, sized 18px, tinted
  `--muted` at rest and `--amber` when active.
- Every icon-only control gets an `aria-label`. Every decorative glyph that
  survives gets `aria-hidden="true"` (as `States.jsx` already does correctly).

---

## Part 4 — The standard every screen is held to

Four properties, from `FRONTEND_PLAN.md`. These are the right bar; restated here
so this file stands alone.

**1. It answers before you ask.** A screen opens already knowing why you came.
The dashboard should say *"this week's rota is 43% labor"* before you go looking
for it.

**2. Nothing is inert.** If a thing can be acted on, it looks like it. Hover
lifts, reveals, or lights. No button that is a grey rectangle.

**3. Numbers move.** A figure that changes should change — count, morph, slide.

**4. It is never blank.** Empty states say what is missing and offer the fix.
Loading shows the shape of what is coming. Errors say what to do.

**The current worst offender against all four is the first-run experience.** A
new workspace lands on an empty dashboard — four tiles, three reading `$0.00` —
behind twenty-one tabs, with no onboarding. The landing page sells beautifully
and hands off to a blank room. **This is the highest-leverage visual work in the
product**, because it is the only ninety seconds most trials will ever get.

---

## Part 5 — The specification

### Type

| | |
|---|---|
| Display (headings, landing) | **Fraunces**, weight 400, `letter-spacing: -.018em`, `line-height: 1.07` |
| UI / body | **Figtree** |
| Body size | **16px floor.** Never smaller for copy a user must read |
| Body weight | **400 at body sizes.** `body { font-weight: 300 }` is too thin below 18px |
| Line height | **1.4–1.6×** for body. Landing uses 1.75 for prose — good |
| Measure | **50–75 characters.** `.lead` caps at `36ch`, `.prose` at `56ch` — both correct, apply the same discipline in-app |
| Families | **Two. That is the ceiling.** |

### Colour

- One job per colour: **amber** = interaction/focus/touchable, **rose** = money
  leaving/warning/variance, **mint** = money kept/confirmation/healthy.
- Roughly **60 / 30 / 10** — dominant neutral, secondary surface, accent. Amber
  used everywhere stops signalling anything.
- `--faint` never carries body copy (3.17:1).
- No fourth accent without written justification.

### Space

- **8px scale**: 4 / 8 / 16 / 24 / 32 / 48 / 64. Never ad-hoc gaps.
- Side gutter on any customer-facing page: `clamp(1.25rem, 5vw, 4.5rem)` —
  the landing page's `--gutter`, which is the right call. Reuse it.
- Generous margins. A page that fills every inch reads as effort before the
  first word is processed.

### Motion

- One easing token: `--ease: cubic-bezier(.22,.72,.2,1)`. Already defined in
  both `theme.css` and the landing page. Use it everywhere; do not introduce a
  second curve.
- Entrance staggered, not popping. Skeletons **crossfade** into content rather
  than swapping.
- Numbers count (`useCountUp`).
- Respect `prefers-reduced-motion` — currently unhandled anywhere in the repo.
  The ambient gradients, the count-ups and the cursor spotlight all need a
  reduced variant.

### Hierarchy and scan path

- The eye scans in a rough Z or F. The one thing that matters most sits where
  the scan starts, clearly heavier than everything else.
- If five things are all bold and coloured, hierarchy collapses and nothing
  stands out. Pick one.
- On any customer-facing page: **one unmistakable action**, repeated, not hidden
  in a nav.

---

## Part 6 — Accessibility: untested, and a short list to fix it

The repo's own audit says it plainly: *"No accessibility pass. Keyboard access
was added to clickable cards ad hoc, never audited."*

What's already right: `:focus-visible` is defined in `theme.css` with a 2px
`--amber-hot` outline at 3px offset — a real focus style, not `outline: none`.
`States.jsx` marks decorative icons `aria-hidden`. The palette clears AA (Part 2).

What needs doing:

- [ ] `aria-label` on every icon-only button — the hamburger, topbar
      notification, drawer close, logout, the workspace `+`.
- [ ] Tab order audited on the drawer + topbar + page content, and a visible
      focus ring confirmed on every interactive element across all 12
      stylesheets.
- [ ] The drawer traps focus when open on mobile, and Escape closes it.
- [ ] `prefers-reduced-motion` variants for ambient gradients, count-ups,
      spotlight, entrance stagger.
- [ ] Touch targets ≥ 44×44px. The topbar and nav glyph buttons are currently
      well under this.
- [ ] Charts: confirm the table view is reachable by keyboard, since it is the
      accessible path to the data.
- [ ] Contrast re-checked on any surface that sits on `--glass` /
      `--glass-2` rather than `--void` directly — translucent surfaces shift
      the effective background and Part 2's figures don't cover them.

---

## Part 7 — Ordered work

Cheapest and most dangerous first.

**Now — deletion, roughly a day**
1. Delete `src/styles/` (407 lines, dead, conflicting).
2. Remove Tailwind dependency + `tailwind.config.js` + `postcss.config.js`.
3. Comment `--faint` in `theme.css` as non-body-text.
4. Step body weight to 400 at body sizes.

**Next — make the system self-enforcing**
5. `States` on all 20 pages.
6. `Button` / `Card` / `Input` adopted, starting with Today, Manager, Platform,
   Finance, Inventory Intel.
7. A test that fails a page shipping its own empty/loading/error markup.

**Then — the two that change what users see**
8. **Onboarding / first-run.** Guided setup that seeds a demo workspace with
   real-shaped data so the dashboard is never empty.
9. **21 tabs → ~6 groups**, glyphs → `lucide-react`.

**Then — retire the old design permanently**
10. Finish Phase 6: restyle the Scheduling AI page, delete `App.css` (998 lines,
    222 of its classes exist only for that page). When `App.css` is gone and
    nothing changes visually, the design system is real.

**Ongoing**
11. Accessibility checklist in Part 6.
12. `useCountUp` on every changing figure.

---

## The one sentence

> The identity is already designed and already passes the tests most products
> fail — what is missing is that a new screen does not inherit it automatically,
> and every item above is about making the good decision the cheap one.
