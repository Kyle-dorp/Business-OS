# Feature Map, Real All-in-One Comparables, and How to Actually Find Customers

*Researched August 2026*

---

## PART 1: Is the "$400-1,200/mo all-in-one" gap real?

Yes — and here's the actual evidence, not a vibe.

### Real, named all-in-one platforms and what they cost

| Platform | Price | What it actually covers |
|---|---|---|
| **MarginEdge** | $350/mo/location flat ($500/mo w/ smart scale hardware) | Invoice processing, bill pay, inventory. **Note: if you also use Toast POS, add another $50/mo API fee** — even the "all-in-one" isn't fully one thing |
| **Restaurant365 Essential** | ~$469/mo/location | Accounting + inventory basics |
| **Restaurant365 Professional** | ~$689/mo/location | + advanced inventory/workforce. Payroll/scheduling are still add-ons on top |
| **Restaurant365, 3-location group** | $1,800-$2,400/mo total (~$600-800/location) | Confirms cost scales roughly linearly per location, not down |
| **Rezku POS** | $49/mo/terminal | POS + labor/time cards + inventory + KDS bundled — cheaper, but locked to their payment processing and terminal-count pricing |
| **Lightspeed Retail** | $69-89+/mo | Retail-focused, inventory + POS, add-ons for the rest |

[Sources: MarginEdge/Restaurant365 pricing comparison](https://restauranttools.ai/tools/marginedge), [Restaurant365 pricing breakdown](https://restaurantvelocity.com/blog/restaurant-accounting-software/)

**So the $400-1,200/mo figure wasn't invented — it's real, and it's specifically the tier occupied by Restaurant365 and MarginEdge.** But here's the more useful finding: **that tier is built for multi-location, accounting-grade operators.** A single small restaurant or shop gets quoted $469-689/mo for a product genuinely built for chains. There's a real gap **below** that tier and **above** bare point-solutions like Rezku ($49/terminal, POS-locked) — a single-location or small multi-location business that wants real integration without chain-level pricing or getting handcuffed to one payment processor. That gap is where you sit.

### Is tool-stitching pain actually real and measured, or just theory?

It's measured, and it's worse than either of us guessed:

- **74% of restaurant operators say technology integration directly impacts their profitability** (National Restaurant Association, cited via [PointB's disconnected systems analysis](https://www.pointb.com/Insights/Articles/2025/08/The-Hidden-Costs-of-Disconnected-Systems))
- **Shrinkage from spoilage/theft/miscounts caused by disconnected inventory drains 1.6% of sales** — over **$16,000/year lost at a $1M-revenue location**, from bad data alone, not fraud
- **5-10 hours/week** of staff time burned on manual reconciliation between systems that don't talk to each other
- **When businesses try to fix this by integrating existing tools**, it costs **$5,000 for simple API integrations up to $50,000+ for enterprise multi-location setups** — meaning the "just connect what you have" fix is often more expensive than switching to something unified in the first place

[Source: Point B — Hidden Costs of Disconnected Restaurant Systems](https://www.pointb.com/Insights/Articles/2025/08/The-Hidden-Costs-of-Disconnected-Systems), [Crunchtime — disconnected systems cost analysis](https://www.crunchtime.com/blog/why-disconnected-restaurant-systems-are-costing-you-more-than-you-think)

**This is your actual pitch, backed by numbers, not adjectives:** *"Disconnected systems are quietly costing you ~1.6% of revenue in inventory losses alone, plus 5-10 hours a week of someone's time, plus whatever you're paying across 4-6 subscriptions. Reconnecting what you already own costs $5k-50k. One platform costs less than that in year one."*

---

## PART 2: Feature Map — What You Have, What You Could Add, What the Market Leader Does Best

| Module | You Have (built) | You Could Add | Best-in-class does |
|---|---|---|---|
| **Scheduling** | ✅ AI-assisted, OR-Tools solver, availability, shift requests, publish workflow | Auto-conflict detection with labor law limits (predictive scheduling laws), multi-location shift swapping | Deputy: compliance alerts by state; 7shifts: labor-cost forecasting live against sales |
| **Inventory** | ✅ Stock, suppliers, movements, reorder points, audit history | Recipe costing (ties inventory usage to menu items), waste tracking, barcode/mobile count | MarginEdge: auto-pulls invoice line items into inventory via OCR — near-zero manual entry |
| **Finance/Accounting** | ✅ Double-entry ledger, chart of accounts, journal, trial balance, P&L, balance sheet | Bank feed reconciliation, multi-entity consolidated reporting | Restaurant365: real-time P&L by location, auto-categorized from POS + inventory data |
| **CRM/Customers** | ✅ Profiles, history, preferences | Loyalty/rewards points, marketing email/SMS triggers | Toast loyalty, Square Marketing — usually bolt-on modules even for the big guys |
| **Invoicing/Billing** | ✅ Draft/posted invoices, payments, vendor bills | Recurring billing, auto-reminders, ACH/card collection | Standard across the board — table stakes, not a differentiator |
| **Payroll** | ❌ Not built | Federal-only prep calculator now; embedded/licensed engine (Symmetry) later — see prior doc | Gusto/ADP: full-service filing. **Nobody in your price tier bundles this well** |
| **Booking/Appointments** | ❌ Not built | Customer-facing booking page, deposits, waitlist | Acuity/Square Appointments — usually a *separate* subscription even at chains |
| **POS / Sales Tracking** | ❌ Not built | Either (a) sales-tracking only, no payment processing, or (b) full POS with processing partner | Toast/Clover/Square — this is the highest-effort, highest-liability module (PCI compliance, hardware) |
| **Menu Creation** | ❌ Not built (mentioned as maybe-legacy) | Digital menu builder, QR ordering, allergen/nutrition tags | BentoBox stacks 3 separate fees ($119+$49+$19=$187/mo) for what could be one module |
| **Team Communication** | ✅ Internal messaging, announcements | Shift-specific channels, read receipts | Slack/Teams-lite feature set — decent as a bundled extra, not a standalone sell |
| **AI Assistant** | ✅ Claude-powered, reviewable scheduler actions | Extend to inventory reorder suggestions, financial anomaly flags, payroll estimate sanity-checks | **Nobody at this price tier has a real conversational AI layer across all modules — this is your sharpest edge** |
| **Multi-location/Tenancy** | ✅ Multiple workspaces, role-based access, tenant isolation | Cross-location rollup reporting | Restaurant365's whole value prop *is* this — you already have the foundation |
| **Analytics/Reporting** | ⚠️ Defined in registry, not built out | Forecasting, custom dashboards | This is what justifies the premium tier once modules 1-9 are solid |

### The honest read
You already have the **hardest, least glamorous stuff done** — real double-entry accounting, real multi-tenant isolation, a genuinely sophisticated scheduler. What's missing (payroll, POS, booking, menu) is mostly **the stuff competitors treat as separate paid add-ons anyway**. You don't need all four to compete — you need 1-2 of them polished, because even Restaurant365 and MarginEdge don't have everything natively (Toast API fee, payroll bolted on).

---

## PART 3: How to Actually Find These Customers

Your instinct — "if I only ask about scheduling I'll miss other problems, but if I ask generally people say everything's fine" — is a known, well-documented trap. There's a real methodology for it (Rob Fitzpatrick's **Mom Test**), and it directly answers your worry.

### The core rule: don't ask about your product, ask about their week

"Everything's fine, I don't need anything" is what people say to a vague, general question or a pitch. It is **not** what they say when asked to narrate something specific and recent. The fix isn't broader or narrower questions about *your* product — it's getting them to describe *their* actual process.

**Don't ask:** "Do you have problems with scheduling?" (invites "no, we're fine")
**Don't ask:** "What software problems do you have?" (too vague, gets a shrug)

**Ask instead:** "Walk me through how you built last week's schedule, start to finish." Then shut up and listen. Friction reveals itself in the story — a spreadsheet, a group text, someone manually checking against last month's sales, a moment where they say "yeah that part's annoying but whatever." That "but whatever" is the actual signal. Chase it.

[Source: Mom Test methodology summary](https://blog.uxtweak.com/the-mom-test/), [MIT Proto Ventures — finding real pain points](https://protoventures.substack.com/p/how-to-find-a-real-customer-pain)

### The single most important filter: have they already tried to fix it?

Fitzpatrick's core finding: **if they haven't already looked for a way to solve it — a spreadsheet workaround, a free tool, asking someone for advice, paying for a point solution — they're not a real prospect, no matter how much they complain in the conversation.** Idle complaining ("scheduling is a pain sometimes") is not purchase intent. A workaround they built themselves is purchase intent. This directly solves your fear: you're not trying to convince the "it's fine" crowd. You're listening for people who are already three duct-taped tools deep, because those people already paid in time and money to prove the pain is real.

[Source: Mom Test — past behavior over opinions](https://www.koji.so/blog/mom-test-customer-interviews-2026)

### Where to actually find these conversations (not just "talk to people")

1. **Accountants and bookkeepers serving small businesses** — this is your highest-leverage channel and most people skip it. They are the ones manually reconciling the mess between five disconnected systems for every client they have. They see the pain across dozens of businesses, not just one, and a good relationship with 2-3 local bookkeepers can turn into an ongoing referral pipeline, not a one-time lead.
2. **Local restaurant/retail owner Facebook groups and subreddits** (r/restaurantowners, r/smallbusiness, local chamber of commerce groups) — search these for existing complaint threads about scheduling, inventory, or "does anyone have a system that actually..." — you're finding people who already voiced the pain unprompted, which is stronger signal than anything you'd get asking cold.
3. **POS resellers, food/bar distributors, equipment vendors** — they're in these businesses constantly and hear the complaints in passing. A referral relationship here costs you nothing but a conversation.
4. **Do 10-15 unpaid, no-pitch conversations before you build or sell anything else.** Literally say: "I'm not selling anything, I'm trying to understand how [scheduling/inventory/whatever] actually works day to day for a place like yours." Log every specific friction point by name. Patterns emerge fast — usually by conversation 6-8 you'll see the same 2-3 things coming up unprompted.
5. **Only pitch the businesses that showed you a workaround.** Not "would you buy this" (worthless, per Fitzpatrick — people are bad predictors of their own future behavior) — instead "I'm building something for exactly the [named] problem you just described, want an early look when it's ready?"

### This also answers your original worry directly
You don't need to guess whether to ask broad or narrow. **Ask narrow about their day, broad about their whole operation** — "walk me through your week" surfaces scheduling, inventory, payroll, and money problems all in the same conversation, without you leading them toward any one module. You're not choosing between "only scheduling" and "too vague" — you're asking them to narrate reality, and letting the friction points sort themselves out.

---

## Sources
- [MarginEdge pricing review 2026](https://restauranttools.ai/tools/marginedge)
- [Restaurant365 vs MarginEdge accounting comparison](https://restaurantvelocity.com/blog/restaurant-accounting-software/)
- [Rezku POS pricing](https://www.capterra.com/p/157466/Rezku-POS/)
- [Point B — Hidden Costs of Disconnected Restaurant Systems](https://www.pointb.com/Insights/Articles/2025/08/The-Hidden-Costs-of-Disconnected-Systems)
- [Crunchtime — disconnected systems cost analysis](https://www.crunchtime.com/blog/why-disconnected-restaurant-systems-are-costing-you-more-than-you-think)
- [The Mom Test — customer discovery framework](https://www.momtestbook.com/)
- [UXtweak — Mom Test summary](https://blog.uxtweak.com/the-mom-test/)
- [MIT Proto Ventures — finding real customer pain](https://protoventures.substack.com/p/how-to-find-a-real-customer-pain)
