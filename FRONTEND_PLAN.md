# The front end, in phases

*Written 16 September 2026, after looking at every screen in a browser rather
than reading the code for them.*

The backend got this treatment and it worked: eighteen real bugs, found by
running things. The front end has never had it. What follows is the same idea
pointed at the half of the product a customer actually touches.

---

## The honest diagnosis

Three sentences, because the plan only makes sense if the problem is stated
plainly.

**The differentiated product is wearing a generic shell.** Preflight, the
variance engine and the compliance check are things Deputy and QuickBooks
cannot do. None of them are visible from the screen a user lands on.

**The dashboard has nothing on it.** Four tiles, three of them reading `$0.00`
or `0`, and a panel that says *"Sell. Deliver. Record. Understand."* — which is
marketing copy sitting inside the product. That panel exists because there was
nothing real to put there. It is the tell.

**The design language stops at the front door.** `theme.css` has ambient light,
warm near-black, amber-for-interaction, hover states that lift. The sign-in
screen uses all of it. The ten screens behind it are flat boxes.

There is one screen that already works: **Ask**. Generous space, one clear job,
starter questions, a quiet usage meter in the corner. It is the reference for
everything below — not because it is decorated, but because it knows what it is
for.

---

## What "masterpiece" means here

Not more decoration. Four specific properties, and every phase below is judged
against them:

| | |
|---|---|
| **It answers before you ask** | A screen opens already knowing what you came for. The dashboard should say "this week's rota is 43% labor" before you go looking. |
| **Nothing is inert** | If a thing can be acted on, it looks like it. Hover lifts, reveals, or lights. No button that is a grey rectangle. |
| **Numbers move** | A figure that changes should *change* — count, morph, slide. A price that jumps from $39 to $49 is a number. A price that counts up is a product. |
| **It is never blank** | Empty states say what is missing and offer the fix. Loading shows the shape of what is coming. Errors say what to do. |

---

## Phase 1 — Billing, restored

**Why first:** it is the page that sells the product, it is nearly right
already, and it is the fastest proof that this effort is real.

What is wrong with it today, from the screenshot:

- **The first three rows cannot be bought.** Overview, Settings and
  Notifications sit at the top of the list marked ALWAYS ON, pushing the ten
  things a customer actually chooses below the fold. They should be a single
  quiet line, not three cards.
- **On and off look nearly the same.** A selected module and an unselected one
  differ by a small amber tick. Selecting should feel like selecting.
- **The price does not move.** It re-fetches and swaps. It should count.
- **`$273/mo` saved is the strongest number on the page** and it is rendered at
  the same weight as everything else.

Work:

1. Non-billable modules out of the list; one line under the summary: *"Home,
   settings and notifications are always included."*
2. Selected state that reads at a glance — lit border, raised surface, the
   amber doing real work.
3. The price counts between values when modules toggle. The "you keep" figure
   counts with it.
4. Hover reveals what a module replaces and what it costs elsewhere — the
   argument for buying it, at the moment of deciding.
5. Module cards in a grid rather than a single column, so ten choices read as a
   menu rather than a list.

**Done when:** the page can be screenshotted and used as the pricing section of
the marketing site without changes.

---

## Phase 2 — The assistant, on every page

**Why second:** it is the best idea in this plan and it fixes a product problem,
not just a visual one.

Right now there are two AI surfaces and both are whole pages. Asking a question
means leaving whatever you were doing, which means nobody asks. The two pages
also duplicate each other: **Ask** reads everything and proposes changes;
**Scheduling AI** does twelve scheduling actions the agent cannot.

The fix is the bubble:

- A single orb, bottom right, on every screen. Always there, never in the way.
- **It changes with the page.** On the rota it is the Scheduling AI, and it can
  regenerate a week or move a shift. Everywhere else it is Ask. Same bubble, the
  right brain.
- **It arrives knowing where you are.** Opened on the rota for week of 14 Sept,
  it already has that week. No "which schedule do you mean."
- It opens as a panel, not a modal — the page stays visible behind it, because
  the whole point is asking *about* what you are looking at.
- It pulses when it has something unprompted to say: a preflight blocker, stock
  about to run out, a payment that failed.

The two full pages stay for long sessions. The bubble is for the ninety percent
of questions that are one line.

**Done when:** you can be anywhere in the app, ask "how did last month go",
and get an answer without losing your place.

---

## Phase 3 — The dashboard, rebuilt

Delete the marketing panel. Replace the four generic tiles with the four things
this product knows that no competitor does.

Candidate shape:

- **This week's rota** — the preflight verdict, in one line, with the blockers.
  *"2 things to sort. Labor is 43% of forecast. Gin runs out Thursday."*
- **Money** — in, out, and the net, as a shape rather than a number.
- **What runs out** — the stock risks, soonest first, with days of cover.
- **What needs you** — unpaid invoices, failed payments, pending approvals,
  support tickets. The list of things only a human can clear.

Every tile is a door. Every tile says what to do, not just what is true.

**Done when:** the dashboard on a real workspace tells you something you did not
already know.

---

## Phase 4 — Charts

There is not a single visualization in the product. There is a double-entry
ledger, invoices, expenses, a trial balance, fourteen days of stock movement,
and a labor forecast — all of it rendered as tables of numbers.

- Cash in against cash out, thirty days.
- Labor as a share of revenue, by day, against the 33% and 40% lines.
- Food cost by menu item, worst first — the menu-engineering data already
  computed and never shown.
- Stock burn-down with the reorder point drawn on it.

House rules: one accent per series, the palette already defined
(amber = interaction, rose = money leaving, mint = money kept), readable in
both themes, and never a chart where a sentence would do.

**Done when:** a customer can see their month rather than read it.

---

## Phase 5 — The design language, past the front door

The atmosphere exists in `theme.css` and stops at sign-in.

- Ambient light and grain on every page, not just auth.
- The cursor spotlight, toned to the level agreed months ago.
- Cards that lift and reveal on hover; surfaces that imply clickable without
  drawing a button.
- Entrance: content arrives staggered rather than popping.
- Skeletons crossfade into content instead of swapping.
- **The 26 remaining `App.css` selectors** that outrank the theme on
  specificity. Each one is a place the old blue-and-purple design still wins.

**Done when:** no screen in the app looks like it came from a different
product than the sign-in page.

---

## Phase 6 — The Scheduling AI page

The last screen the redesign never reached, and the reason `App.css` cannot yet
be deleted — 222 of its classes exist only for this page.

Restyle it into the language, fold its twelve actions into the bubble from
phase 2, and `App.css` can finally go. That deletion is the end of the whole
class of bug that produced the white topbar, the violet sign-in panel and the
blue glow on amber buttons.

**Done when:** `App.css` is deleted and nothing changes.

> **This was wrong, and phase 6 corrected it.** It assumed only the Scheduling
> AI page needed `App.css`. Twelve pages do — AssistantPage, ManagerPage,
> AvailabilityPage, SettingsPage, NotificationsPage, FinancePage,
> EmployeeHomePage, RequestsPage, PlatformPage, AgentPage, BookingAdminPage,
> AuthPage. Deleting the file means restyling all twelve, which is a phase of
> its own rather than a cleanup at the end of this one.
>
> What phase 6 did instead: removed 97 rules nothing references, renamed the
> file `theme-legacy.css` for what it actually is, stripped the last of its
> colour, and put guards in `theme.test.js` so it can only ever shrink. The
> bug class is retired; the file outlives it.

---

## Order, and why

Phases 1 and 2 are the ones you can feel. They come first because momentum
matters and because they are the two you asked for.

3 and 4 are the ones that make it worth $29 — they take the things the backend
already computes and put them where somebody will see them.

5 and 6 are the finish. They are last because they are the largest and because
doing them before the screens are settled means doing them twice.

Each phase is independently shippable. None of them require the one before it,
except 6 which wants 2 done first.

---

## How each phase gets verified

The same way the backend bugs were found, because it is the only thing that has
worked: **build it, open it in a browser, look at it.** Every phase ends with
screenshots of the real screens, not a description of them.

Frontend tests keep their job — the money, the arithmetic, the states — but
they do not judge whether something is good. That is done by looking.
