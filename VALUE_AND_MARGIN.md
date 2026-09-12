# What each module is worth, and whether a customer can cost you money

Two questions, answered honestly. The second one has real math.

---

# Part 1 — What makes a module worth $10

## The honest frame first

**No single module here is worth $10 on its own merits against a best-in-class
competitor.** Deputy's scheduler will out-feature yours for a while. Zoho's
inventory is more mature. Acuity's booking flow has had a decade of polish. If a
customer is comparing your scheduling module against Deputy feature-for-feature,
you lose that comparison today.

That's not the comparison to invite.

What a customer is buying for $10 isn't the module. It's **the module being in the
same database as everything else they run.** Every competitor listed above is a
sealed box that exports CSVs. Yours is one system where a shift, an invoice, a
stock count and a booking are rows in the same place.

That difference isn't marketing. It creates capabilities that are *structurally
impossible* for a standalone tool, no matter how good its features get. Those
capabilities are what the $10 buys, and they're listed per module below.

---

## Scheduling & shifts — $10

**Standalone equivalent:** Deputy $5–9/user, 7shifts $40/location

**What only works because it shares a database:**

- **Labor cost against real revenue, live.** Not projected from last year's
  averages — computed against today's actual invoices and bookings. A standalone
  scheduler doesn't know what you sold; it can only ever guess at whether you're
  overstaffed.
- **Bookings drive staffing.** Twelve appointments on Thursday means Thursday
  needs the staff to cover them. In a split stack that's a human reading one
  screen and typing into another.
- **Labor flows into the ledger automatically.** Scheduled hours become a labor
  cost line without anybody re-keying it.

**Honest weakness:** OR-Tools constraint solving is genuinely strong — better
math than most rule-based competitors — but Deputy has state-by-state labor law
compliance alerts you don't. Don't claim parity there.

---

## Inventory & stock — $10

**Standalone equivalent:** Zoho $29–249, Sortly $49–79, inFlow $129+

**What only works because it shares a database:**

- **Shrinkage becomes visible.** This is the single most valuable thing in the
  product. Disconnected inventory costs operators ~1.6% of sales — $16k/year at a
  $1M location — precisely because what sold and what's on the shelf live in
  different systems and nobody reconciles them. Same database, and the gap between
  sold and counted surfaces by itself.
- **The assistant can answer "what's running low" in one sentence**, because
  stock levels and reorder points are queryable alongside everything else.
- **Purchases hit the books once.** A restock is a stock movement and a bill at
  the same time, not two entries.

**This module alone can be argued to pay for the entire subscription.** One
prevented over-order or caught discrepancy per month clears $119.

---

## Invoicing & payments — $10

**Standalone equivalent:** ~$30/mo, and usually bundled into accounting anyway

**What only works because it shares a database:**

- **Invoices post to the ledger as they're issued.** No monthly export-import ritual.
- **The assistant knows your AR.** "Who owes me and how late" is one question.
- **Bookings become invoices** without retyping the customer.

**Honest weakness:** this is the most commoditised module in the set. Nearly
everything invoices. It's worth $10 as connective tissue, not as a headline.

---

## Customers & CRM — $10

**Standalone equivalent:** $35+/mo

**What only works because it shares a database:**

- **One customer record, genuinely.** Their bookings, invoices, payment history
  and notes are the same record, not four records that happen to share an email.
- **A booking creates the customer.** Already built — a new email on a booking
  writes a CRM contact automatically.
- **"What's this customer worth" is answerable** because lifetime spend is a query,
  not a spreadsheet exercise.

---

## Books & accounting — $10

**Standalone equivalent:** $70+/mo, or bundled into payroll at $80–180

**What only works because it shares a database:**

- **The ledger is fed by the operation, not typed into.** Invoices, bills,
  payments, inventory movements and labor all post themselves. This is the
  difference between bookkeeping being a weekly chore and being a byproduct.
- **P&L is live, not month-end.** Because it's computed from the same rows the
  business is already writing.

**This is your most under-priced module at $10.** Real double-entry with chart of
accounts, trial balance, P&L and balance sheet is serious infrastructure —
Restaurant365 charges $469/month largely for this. Do not apologise for it.

---

## Bookings & appointments — $10

**Standalone equivalent:** Acuity $20–61, Square Appointments $49/location

**What only works because it shares a database:**

- **Availability comes from the actual schedule.** A standalone booker takes
  appointments for hours nobody is rostered. Yours knows who's on.
- **The booking is already a customer, an invoice and a staffing requirement.**
- **No double-booking across channels**, because there's only one calendar.

---

## Payroll prep — $10

**Standalone equivalent:** Gusto $49 + $6/employee, Roll $39 + $5/employee

**What only works because it shares a database:** hours come from the schedule
that already exists. No timesheet export, no re-keying, no reconciliation.

**Be careful how you sell this one.** Federal withholding is implementable
correctly against IRS Pub 15-T. State and local across 7,000+ jurisdictions is
not something to hand-roll. Sell it as *payroll prep* — hours to gross pay, ready
for a filer — until Symmetry's tax engine is licensed. A wrong withholding number
is a customer's IRS penalty, and being technically not liable won't save the
relationship.

---

## Menus & QR ordering — $10

**Standalone equivalent:** BentoBox stacks $119 + $49 + $19 = $187/mo

**What only works because it shares a database:** menu items are inventory items.
Run out of something and it goes dark on the menu automatically. Selling a dish
draws down its ingredients. BentoBox cannot do this at any price, because it
doesn't know what's in your stockroom.

**Best margin story in the set** — cheap to build, competitor charges $187.

---

## Sales tracking — $10

**Standalone equivalent:** Toast $69, Square $49–60, Clover $135

**What only works because it shares a database:** sales draw down inventory and
post to the ledger in the same motion.

**Strategic note:** deliberately *not* payment processing. The POS players make
their money on the 2.3–2.99% transaction fee, not the software — you cannot win
a price war there and you don't want PCI scope. Let them keep their processor and
be the system that finally makes sense of the data coming out of it.

---

## Team communication — $10

**Standalone equivalent:** ~$25/mo

**What only works because it shares a database:** messages attach to shifts,
tasks and customers. "About tonight's private party" is linked to the booking.

**Honest weakness:** weakest module in the set. Everyone has Slack or a group
chat already. Bundle it, don't lead with it.

---

## The assistant — the thing with no standalone equivalent

This is the one where there's no row in a competitor's pricing table to point at,
because **nobody in this price tier has it.**

- Ask questions in plain language, get answers computed from real records
- Propose changes and approve them from a phone, mid-shift
- It works *because* everything shares a database — an assistant bolted onto a
  siloed tool can only ever answer questions about that silo

And the safety boundary is a feature worth stating out loud: **it proposes, you
approve.** Notes, invoice memos and supplier emails are text other people wrote,
and text other people wrote should never move your stock levels on its own.

---

## The number that actually closes the sale

Stitching these together from separate vendors: **$260–885/month**, across six or
seven logins that don't talk to each other.

All ten modules here: **$119/month.**

You are not asking anyone to believe your scheduler beats Deputy. You're asking
them to notice they're paying six bills for software that can't answer a single
question about their business as a whole.

---

# Part 2 — Can a paying customer cost you money?

Short answer: **no, and there are three stacked safeguards.** Here's the actual math.

## Where the money goes

Infrastructure is nearly fixed. A $79/month Railway tier supports roughly 250
workspaces, so the marginal infra cost of one more customer is about **$0.32/month**.
Irrelevant.

**The Claude API is the only variable cost that matters.**

## What one assistant conversation actually costs

Tool use inflates input tokens — each round re-sends the conversation plus tool
results. A realistic three-round question:

| | Input | Output |
|---|---|---|
| Round 1 (system + tools + question) | ~1,400 | ~150 |
| Round 2 (+ tool result) | ~2,100 | ~250 |
| Round 3 (final answer) | ~2,900 | ~300 |
| **Total** | **~6,400** | **~700** |

At Sonnet rates ($3/M in, $15/M out): **about $0.03 per question.**

## Safeguard 1 — the included allowance

500,000 input + 150,000 output tokens per **workspace** per month.

- That's roughly **100 assistant questions per month**
- Maximum cost to you if fully consumed: **~$3.75**
- Minimum revenue from any paying workspace: **$29**

**Worst case inside the allowance: $29 revenue − $3.75 AI − $0.32 infra = $24.93 kept. 86% margin.**

The allowance is per *workspace*, not per user — deliberately. Plans include
unlimited users, so a 30-person restaurant and a 5-person café share the same
ceiling. Per-user budgets would make the big customer six times more expensive
for the same subscription.

## Safeguard 2 — metered overage

Past the allowance, usage bills at **$0.02 per 1,000 tokens** rather than cutting
someone off mid-thought.

Your blended cost is about **$6 per million tokens** (input-heavy, because tool
use skews that way). You charge **$20 per million**.

**Roughly a 3.3× markup. Overage is more profitable than the base plan.**

Worst realistic case — output-only usage at $15/M cost against $20/M charged —
still clears 1.33×. Thin, but never negative.

## Safeguard 3 — the hard ceiling

At 5× the included allowance (3.25M tokens), the assistant stops regardless of
willingness to pay, until someone deliberately raises it.

This exists for one scenario: **overage is billed in arrears.** A customer whose
card later fails, or who disputes, has already consumed the tokens. The ceiling
caps your total exposure per workspace per month at roughly **$19 of unrecovered
API cost** — the absolute worst case, only reachable by someone actively abusing it.

## The gap worth knowing about

The per-user burst limit (40 messages/hour) would **not** save you on its own. A
30-person team could theoretically issue 1,200 messages an hour — about $36/hour
of API spend.

**The monthly workspace budget is the real backstop, not the burst limit.** It
catches that scenario in under 20 hours of sustained abuse, after which everything
is either metered or stopped. The burst limit is there to stop one person hammering
it, and that's all it should be credited with.

## One adjustment I'd make

The hard ceiling is a flat 5× regardless of plan. On a $29 single-module customer
that's $19 of exposure — 65% of their monthly revenue.

Scale it to the plan instead:

```
AI_HARD_CEILING_MULTIPLIER=3     # for $29 tier
```

Or make it proportional to module count in code. A ten-module customer at $119 can
justify far more headroom than a one-module customer at $29.

## Bottom line

| Scenario | Revenue | Your cost | Kept |
|---|---|---|---|
| 1 module, no AI use | $29 | $0.32 | **$28.68** |
| 1 module, allowance maxed | $29 | $4.07 | **$24.93** |
| 4 modules, allowance maxed | $59 | $4.07 | **$54.93** |
| 10 modules, allowance maxed | $119 | $4.07 | **$114.93** |
| 10 modules, 3× allowance (metered) | $119 + $26 overage | $12 | **$133** |
| Abuse, hard ceiling hit, never pays overage | $29 | $19 | **$10** |

**Every row is positive.** The floor case — deliberate abuse plus non-payment —
still clears $10, and requires someone to work at it.

The thing that will actually threaten your margins is not API usage. It's support
time. One customer who needs an hour of your attention every month costs more than
every token they will ever consume.
