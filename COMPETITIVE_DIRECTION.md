# Competitive direction — read this before the next phase

*Written 17 September 2026 by an outside review, against the working tree at
`D:\projects\KDB Innovations\business-eos`. Every claim below was checked
against the code or against a competitor's live site, not recalled.*

*Audience: the Claude Code session building this product. Kyle asked for an
outside read on whether this is on track to be best-in-class, and the answer
turned up something structural that changes the framing of the whole roadmap.*

---

## 0. The finding that reframes everything else

**"EOS" means two completely different things, and this repo has been building
one of them while the owner has started aiming at the other.**

- **EOS as you've built it** — "operating system for a business," the
  infrastructure sense. Scheduling, stock, ledger, invoicing, bookings. This is
  what the code is.
- **EOS as the market means it** — the **Entrepreneurial Operating System**,
  Gino Wickman's framework from *Traction*. Rocks, Scorecard, Level 10
  meetings, V/TO, Accountability Chart, Issues/IDS, People Analyzer. This is
  what someone typing "EOS software" into Google is looking for, and it is a
  category with an official incumbent.

I grepped the entire backend and frontend for every EOS concept — `rock`,
`scorecard`, `level 10`, `accountability`, `traction`, `people analyzer`, `V/TO`.
**Zero hits. Not one, in either half of the codebase.**

That is not a bug. The product is coherent and good at what it is. But it means
the name on the door promises a category the product does not serve, and anyone
who arrives from an EOS search bounces immediately. It also means that when
Kyle says he wants to build "the masterclass of this EOS area," you and he may
be picturing two different products.

**This must be settled before another phase is built.** Everything below assumes
it gets settled the way I recommend in §3, but say so explicitly in the repo
either way.

---

## 1. What the code actually is

Measured, not recalled:

| | |
|---|---|
| Backend | ~12,000 lines, 24 modules, 474 tests passing |
| Frontend | 5,693 lines, 143 tests passing |
| Styling | 3,183 lines across 12 CSS files |
| Domain | Scheduling · labor compliance · inventory variance · double-entry ledger · invoicing · payroll · public booking |
| Data model | 42 SQLModel tables — `Schedule`, `ScheduleShift`, `CoverageRule`, `LaborProjection`, `InventoryMovement`, `JournalLine`, `Booking` |
| Billing | $29 first module, $10 each after |

The domain language is unambiguous: coverage rules, labor percentage of
forecast, gin running out on Thursday, menu-item food cost, eleven jurisdictions
of break-premium law. **This is a restaurant and small-operator ops platform.**
A strong one.

And the differentiators are genuinely differentiated. Per `STATE_OF_THE_PRODUCT.md`,
verified by tests rather than asserted:

- **Preflight** answers four questions before a rota is published — is it
  legal, is it covered, can we afford it, does it match forecast — and refuses
  to clear a week it cannot price. No competitor answers all four together.
- **The variance engine** computes unexplained loss against sales depletion and
  logged waste. A standalone inventory tool structurally cannot do this,
  because it does not hold the sales.
- **The compliance engine** covers eleven jurisdictions with citations and
  surfaces a $145 premium in NYC *before* publishing rather than after payroll.

These are real. Hold onto them.

---

## 2. On the restaurant angle being "a weakness"

Kyle's instinct is that the restaurant-side functionality is a liability. **He
is half right, and the half he's wrong about is the more important half.**

**Wrong:** the restaurant depth is the single most valuable thing in this
repository. Vertical specificity is what makes the three differentiators above
possible at all. A generic business tool cannot compute unexplained shrinkage,
because it does not know what a pour is. Nory, MarginEdge and Restaurant365 are
all worth real money precisely *because* they are restaurant-shaped. Stripping
that out to become generic would trade a defensible product for an
undifferentiated one — and would delete the only features here that a competitor
cannot copy in a sprint.

**Right:** the *positioning* is the weakness, in three specific ways.

1. **The name fights the product.** "Business-EOS" reads as either a Traction
   tool (which it isn't) or as generic enterprise software (which undersells it).
2. **The landing page hedges.** It says "small operator" and "the whole shop"
   while every example underneath is a restaurant — house red, oat milk,
   takeaway lids, a bar missing 1.5L of gin. The copy is aiming wide while the
   evidence aims narrow, and the narrow evidence is the persuasive part.
3. **Nothing in the app is named for the buyer.** The nav says "Stock
   intelligence" and "Preflight." A restaurant operator's vocabulary is prep,
   covers, pour cost, rota, close.

So: keep the restaurant engine. **Fix the name and the framing, not the
functionality.**

---

## 3. The play that would actually make this a masterclass

This is the part worth sitting with.

Look at what the EOS (Traction) tools are, structurally. Ninety.io has 18,695+
companies and hosts 138,000+ Level 10 meetings a month at $8.40–$11.20 per user.
EOS One is the official EOS Worldwide product at roughly $10 per additional user.
Bloom Growth starts at $149/mo for ten users. They are mature, well-designed,
and well-distributed.

**And every one of them has the same structural hole: the Scorecard is typed in
by hand.** Somebody sits down on Monday morning and manually enters last week's
numbers into a grid. The entire framework — the thing that's supposed to tell
you the truth about your business — runs on manual data entry, which means it
runs on somebody's memory and somebody's honesty and somebody's Monday.

This gap is real and the market knows it. A newer entrant, ICOS, leads its
entire pitch with "Scorecard pulled from your systems automatically" — they
market directly against manual entry. But they pull from *other people's*
systems through integrations, which is brittle, permission-gated, and breaks
when a vendor changes an API.

**This repo owns the data layer outright.** The ledger, the rota, the stock
counts, the invoices, the labor percentage — all of it is already in one
database that this product controls. Which means:

> **Business-EOS could ship the only Scorecard in the EOS category that fills
> itself in, with no integrations, because it already owns the numbers.**

That is not a feature. That is a category-level argument, and it is only
available to a company that built the ops layer first — which is the "weakness"
Kyle wanted to cut.

The frame to hold: **ops is the engine, EOS is the dashboard.** Ops is the
day-to-day — who's working, what's in stock, what got paid. EOS/Traction is the
strategy layer — where are we going, are we on track. Every EOS tool on the
market is a dashboard with no engine underneath it. This repo is an engine with
no dashboard on top. **They are two halves of the same product, and almost
nobody is positioned to build both.**

So the answer to "is it a good idea to keep both" is yes — but not as two
products. As one product where the second layer is only credible *because* of
the first.

**With one hard caveat, in §7.**

---

## 4. Functionality: where this stands against best-in-class

### Against restaurant ops platforms (the category the code is actually in)

Leaders: Toast, Restaurant365, Nory, 7shifts, MarginEdge, MarketMan, Apicbase,
Tenzo.

| | Business-EOS | Best-in-class |
|---|---|---|
| Scheduling + solver | **Real OR-Tools constraint solve, deterministic** | 7shifts is strong but rules-based |
| Pre-publish validation | **Preflight — four checks, refuses to guess** | Nobody does this |
| Labor compliance | **11 jurisdictions with citations** | Usually an add-on or absent |
| Inventory variance | **Sales-depletion-aware** | MarginEdge/MarketMan, but siloed from labor |
| Bookkeeping | **Real double-entry ledger** | R365 has it; most don't |
| **POS integration** | **None** | **Table stakes. This is the gap.** |
| **Sales forecasting** | Labor projection only | Nory claims 97% forecast accuracy |
| **Mobile / employee app** | Web only | 7shifts' shift-swap app is why staff adopt it |
| **Onboarding** | **None — empty dashboard** | Guided setup universal |
| **Payments processed** | **Zero. No card has ever been charged.** | — |

The first four rows are a genuinely better product than anything on that list
sells as a bundle. The last five are why nobody has bought it yet.

**The most important missing piece is POS integration.** Without sales data
flowing in automatically, the operator hand-enters revenue, and the variance
engine — the crown jewel — runs on numbers somebody typed. Square and Toast both
have accessible APIs. This is the single highest-leverage integration in the
repo's future and it should outrank every remaining visual phase.

### Against EOS/Traction platforms (the category the name implies)

Every one of these is missing entirely, and each is table stakes in that market:
Rocks (quarterly priorities with milestones), Scorecard (weekly measurables with
owners), Level 10 meeting runner (segmented agenda on a timer), V/TO,
Accountability Chart, Issues list with IDS, People Analyzer, Headlines,
meeting-generated To-Dos.

If the EOS layer gets built, build it in this order — it is roughly the order
that produces a demo somebody gasps at:

1. **Scorecard, auto-populated.** The whole argument, and it needs almost no new
   data — labor %, sales, covers, food cost, cash position are already computed.
   A competitor's demo shows an empty grid. Yours shows last week already filled
   in, sourced, with a link through to the journal entry behind each number.
2. **Rocks** tied to those measurables, so progress updates itself.
3. **L10 meeting runner** that opens with the Scorecard already current and no
   "who has last week's numbers?"
4. Issues/IDS, with issues auto-raised from Preflight blockers and variance
   spikes.
5. Accountability Chart, mapped onto the `Membership` roles already in the
   model.
6. V/TO last — it's a document, and it's the least differentiated.

---

## 5. Visual: the honest assessment

Kyle rates visual craft at a third of the whole thing. On that scale, here is
where it actually sits.

### What is already genuinely good — do not touch it

- **`landing/index.html` is strong work.** Fraunces display + Figtree UI, a warm
  near-black palette, ambient light, a convergence animation that *argues* the
  product's thesis rather than decorating it, and cited statistics with sources
  named. The copy is disciplined — "Six logins. Six bills. One business." The
  masthead, the numbered section rails, the module-cost comparison. This page is
  better than most funded SaaS landing pages and better than the app behind it.
- **`theme.css` is a real design language,** not a palette. One job per colour —
  amber for interaction, rose for money leaving, mint for money kept — with a
  comment explaining why that discipline exists. Ambient light, grain, warm
  near-black ground.
- **`Charts.jsx` is exemplary.** Colours run through a validator, CVD ΔE
  documented, a deliberate and *explained* decision to sit outside the dark-mode
  lightness band, magnitude treated as sequential rather than categorical, and
  every chart shipping with both hover read-out and table view. This is
  better-reasoned than the charting in most commercial products.

### What is structurally broken

**1. There are two entire design systems in this repo, and they contradict each
other.**

`src/styles/design-tokens.css` (128 lines) defines a *cyan* accent — `--accent:
#00d9ff` — on a light `#fafafa` ground with a system font stack. `src/theme.css`
(490 lines) defines an *amber* accent — `--amber: #F5A65B` — on a warm near-black
`#0E0B0C` with Figtree/Fraunces. They both define `--surface`, `--text` and
`--bg`. They are visually unrelated products.

`design-tokens.css` is pulled in by `src/styles/base.css`, and **nothing imports
`base.css`** — not `main.tsx`, not `App.jsx`. So 407 lines of a competing design
system sit in the tree, dead, waiting for somebody to import them and repaint
the app cyan. This is the exact class of failure that already happened once with
`index.css` (documented in the comment in `main.tsx`, which is a good comment —
that lesson just wasn't applied to its siblings).

**Delete `src/styles/` entirely.** Also remove `tailwindcss`, `tailwind.config.js`
and `postcss.config.js` — grep confirms zero Tailwind utility classes are used
anywhere in `src/`. Dead config that can silently win a specificity fight is not
neutral.

**2. Twelve stylesheets, load-order-dependent, `App.css` at 998 lines.**

`App.jsx` imports `App.css` then eleven theme files, and the comment says the
quiet part: *"later import wins on equal specificity."* The design language is
currently held together by import order. The repo's own plan admits 26 `App.css`
selectors still outrank the theme and 222 classes exist solely for the
Scheduling AI page. Every one of those is a place the old blue-and-purple
design still wins.

Finishing Phase 6 and deleting `App.css` is worth more than any new visual
feature, because it retires a whole category of bug permanently.

**3. Twenty-one navigation tabs.**

`MANAGER_TABS` has 21 entries in a flat list. Ninety.io — the incumbent, with
comparable surface area — groups everything into **six** categories: Vision,
Data, Process, Traction, Issues, People. Twenty-one flat items is not a
navigation, it's an inventory. It also means a new user's first impression is
twenty-one things they haven't set up.

Group them. Something like: **Today · Money** (sales, purchasing, bookkeeping,
finance, reports) **· People** (availability, scheduling, preflight, labor
rules) **· Stock** (inventory, stock intelligence) **· Guests** (bookings,
contacts) **· Ask · Settings** (billing, security, notifications, settings).
Six doors instead of twenty-one.

**4. No onboarding — and this is now the most expensive visual problem.**

The repo's own audit says a new workspace lands on an empty dashboard with no
guidance. Combined with 21 tabs and empty tiles reading `$0.00`, the first
ninety seconds of this product are its worst ninety seconds — and they're the
only ninety seconds most trials get. The landing page sells beautifully and
hands off to a blank room.

**5. No accessibility pass.** Keyboard access was added ad hoc and never
audited. Focus states exist in `theme.css` (`:focus-visible` with
`--amber-hot`), which is a good start, but nothing verifies tab order, contrast
ratios across the eleven theme files, or screen-reader labelling on the icon-only
buttons — and there are many, since the nav uses `⌂ ◎ $ ↓ ≡ ↗ ✓ □ ◉ ◷ ▦ ◈ ⚖ ◑ ✦ ◇ ● ⛨ ⚙`
as its entire icon language. Those glyphs are typographically consistent, which
is why they look good, but several are unreadable as meaning and some are
announced as punctuation.

---

## 6. What the top of this market does that this product does not

Pulled from Ninety.io's live homepage, as the best-executed example in the
category:

- **Quantified social proof above the fold** — "18,695+ companies,"
  "138,000+ L10 meetings monthly," "8.95/10 average meeting rating," G2 Leader
  badge, Capterra 4.8, named customer logos. Business-EOS's landing page has
  *cited industry statistics*, which is more intellectually honest, but zero
  evidence anyone uses it.
- **Product screenshots in the hero** — laptop showing the dashboard, phone
  showing Rocks. Business-EOS shows an abstract convergence animation. The
  animation is more beautiful and less convincing; buyers want to see the thing.
- **A before/after comparison table** — six rows of disconnected vs. connected.
  Business-EOS has the superior version of this argument already (the $392 vs
  $79 module stack) but buries the emotional payoff under arithmetic.
- **Integrations shown as logos.** Business-EOS has none to show, which is the
  POS problem in §4 wearing a different hat.
- **Support as a selling point** — "under 5 minutes average response, 7 days a
  week."
- **Multiple CTA paths** — free trial, talk to an expert, start free.
  Business-EOS has "Start with one location" and "Talk to us first," which is
  good, plus a booking link that's booked through its own booking module — a
  genuinely excellent detail that should be louder.

---

## 7. The caveat, and what to actually do next

Everything in §3 is the right *strategy*. It is emphatically not the right
*next sprint*, and this is the thing most likely to go wrong after this report
is read.

Per this repo's own audit: **no card has ever been charged, there is no
onboarding, there is no end-to-end test, and there is no second tenant in
production.** The gap between here and a business is not more product. Building
an entire EOS layer right now would be the most sophisticated way available of
avoiding the thing that's actually hard, which is getting one person to pay.

So, in order:

**Now — make it sellable (nothing new gets built)**
1. **Settle the naming question with Kyle.** It gates the landing page, the
   nav, and everything after.
2. **Delete `src/styles/`, Tailwind, and the dead config.** An hour, and it
   retires a live repaint risk.
3. **Onboarding.** Guided first-run that seeds a demo workspace with real-shaped
   data so the dashboard is never empty. Highest-leverage single screen in the
   product.
4. **Collapse 21 tabs into ~6 groups.**
5. **Run one real card through Stripe Checkout** per `STRIPE_TEST_RUNBOOK.md`.
6. **Finish Phase 6, delete `App.css`.**

**Next — make it win its actual category**
7. **POS integration (Square first, then Toast).** Turns the variance engine
   from a good idea into an unanswerable one.
8. First paying customer. One. Real money.

**Then — make it a masterclass**
9. **The auto-populated Scorecard.** Ship it as the headline feature, with the
   claim stated plainly: *the only Scorecard in the EOS category that fills
   itself in.*
10. Rocks tied to those measurables. Then the L10 runner. Then Issues/IDS.

---

## 8. One sentence for the top of the next planning doc

> This is not an EOS tool and it should not pretend to be one yet — it is the
> best-instrumented small-operator ops engine I've seen at this stage, and the
> reason to build the EOS layer later is that owning the ops data is the only
> way anyone will ever ship a Scorecard that fills itself in.

---

### Sources

- [EOS Software Compared: Ninety, Bloom Growth, EOS One, ICOS (2026)](https://www.icos.ai/eos-software/index.html)
- [Ninety.io homepage](https://www.ninety.io/)
- [10 Best EOS Software for Businesses (2026 Guide) — Stackby](https://stackby.com/blog/eos-software-for-businesses/)
- [Buyer's Guide to Restaurant Tech 2026 — Nory](https://www.nory.ai/blog/buyers-guide-to-restaurant-tech-2026)
- [EOS Software Comparison: EOS One vs Ninety.io vs Bloom Growth](https://www.eightfoldadvantage.com/eos-software-comparison-eos-one-vs-ninety-io-vs-bloom-growth)
- Repo files audited: `STATE_OF_THE_PRODUCT.md`, `FRONTEND_PLAN.md`, `BUSINESS_EOS_README.md`, `backend/app/models.py`, `backend/app/modules_registry.py`, `frontend/src/App.jsx`, `frontend/src/theme.css`, `frontend/src/styles/design-tokens.css`, `frontend/src/styles/base.css`, `frontend/src/main.tsx`, `frontend/src/components/Charts.jsx`, `frontend/package.json`, `landing/index.html`
