# Business-EOS: Market Rate Analysis, Railway Scaling & Payroll Strategy

*Researched August 2026*

---

## PART 1: Railway Scaling Thresholds — What Does $X Actually Buy?

### Raw Railway Unit Costs
```
vCPU:            $20/month  ($0.000463/vCPU-minute)
RAM:             $10/GB/month  ($0.000231/GB-minute)
Egress:          $0.05/GB
Volume storage:  $0.15/GB/month
Hobby plan:      $5/mo (includes $5 usage credit)
Pro plan:        $20/mo/seat (includes $20 usage credit)
```
[Source: Railway Docs](https://docs.railway.com/pricing/plans)

**Key mechanic:** your subscription fee IS your usage credit. On Hobby, if you use $3 of compute you just pay the $5 flat. Only once combined usage exceeds the plan's included credit do you pay overage.

### Realistic Sizing for a FastAPI + React + Postgres App Like Yours

This is a CRUD-heavy app (scheduling, inventory, CRM, invoicing) with occasional AI calls — not compute-intensive. Bottleneck is almost always **concurrent request handling + DB connections**, not raw CPU.

| Tier | Resources | Monthly Cost | Realistic Ceiling |
|---|---|---|---|
| **Starter** | 0.5 vCPU / 0.5GB RAM + 1GB Postgres | ~$18-22/mo | 1-5 businesses, ~50 total users, low concurrency |
| **Small** | 1 vCPU / 1GB RAM + 2GB Postgres | ~$35-40/mo | ~20 businesses, ~300 total users |
| **Medium** | 2 vCPU / 2GB RAM + 5GB Postgres | ~$70-80/mo | ~75 businesses, ~1,500 total users |
| **Growth** | 4 vCPU / 4GB RAM + 15GB Postgres | ~$150-170/mo | ~250 businesses, ~5,000 total users |
| **Scale** | 8 vCPU / 8GB RAM + 40GB Postgres | ~$300-340/mo | ~600+ businesses, ~15,000 total users |

**Caveat:** these are estimates based on typical FastAPI throughput (a single vCPU handles roughly 200-500 req/s for simple JSON endpoints, less for heavy DB joins/reports). Actual ceiling depends on:
- How chatty your frontend is (polling vs. websockets)
- Report/analytics query complexity (P&L, balance sheet generation is expensive)
- Whether you add caching (Redis adds ~$10-15/mo but massively raises the ceiling)

**Practical takeaway:** the "hypothetically each user does 30 hrs/month" framing barely matters for infra cost — what matters is **request volume**, not hours logged in. A person with a tab open doing nothing costs you ~$0. A person hammering the reports page or triggering AI calls constantly costs real money. Infra scales with *actions*, not *seat-hours*.

**Bottom line:** you could run 500-1,000 paying users on <$100/month of Railway infra if the app isn't AI/report-heavy. Infra is genuinely the cheap part of this business. The AI token cost (Part 2 of your original ask) and your own time are the real cost centers.

---

## PART 2: Market Rate Breakdown, By Module

I pulled live 2026 pricing for each category you listed so you're pricing against reality, not vibes.

### Scheduling
| Product | Price | Notes |
|---|---|---|
| When I Work | $2.50/user/mo | Cheapest, barebones |
| Deputy | $5–$9/user/mo (Lite/Core/Pro tiers) | Mid-tier, decent AI-assist scheduling |
| Homebase | Free ≤20 employees/1 location, then $24.95/mo/location | Popular with small shops |
| 7shifts | $39.99/location/mo | Payroll is a separate add-on: +$39.99/location +$6/employee |

[Sources: Homebase blog](https://www.joinhomebase.com/blog/retail-scheduling-software), [7shifts vs Homebase pricing](https://www.stackscored.com/pricing/employee-scheduling/compare/7shifts-vs-homebase/)

**Your scheduler is described as "very high end" (AI-assisted, OR-Tools solver).** That's a real differentiator — most of these are rule-based, not true constraint-solved optimization. That justifies pricing at or above Deputy/7shifts, not at When I Work's floor.

---

### Payroll
| Product | Price | Notes |
|---|---|---|
| Patriot (self-service) | $20/mo + $4/employee | You still file your own taxes |
| Roll by ADP | $39/mo + $5/employee | Full-service, mobile-first |
| Gusto Simple | $49/mo + $6/employee | Full-service |
| Gusto Plus | $80/mo + $12/employee | Multi-state |
| Gusto Premium | $180/mo + $22/employee | HR add-ons |
| ADP RUN Essential | ~$79/mo + $4/employee (unconfirmed, quote-based) | Enterprise-grade |
| PEO (co-employment) | $59–$250/employee/mo or 2-6% of payroll | Different model entirely — see Part 3 |

[Sources: Gusto pricing 2026](https://whichpayroll.com/pricing/gusto), [PEO vs payroll guide](https://onpay.com/insights/peo-payroll-outsourcing-guide/)

**This is the single most expensive category to build yourself** because of tax compliance liability — see Part 3 for how to offer it without becoming a licensed payroll company.

---

### Inventory Management
| Product | Price | Notes |
|---|---|---|
| Zoho Inventory | Free tier, then $29/$79/$129/$249/mo | Scales with order volume + users |
| Sortly | $49–$79/mo entry | Simple, visual, good for small ops |
| inFlow | $129/$349/$699/mo | 2026 repricing pushed this up significantly |

[Source: ERP Software Blog cost guide](https://erpsoftwareblog.com/2026/07/inventory-management-software-cost/)

Typical small-business inventory spend: **$30–$150/mo** standalone.

---

### Booking / Appointments
| Product | Price | Notes |
|---|---|---|
| Calendly | Free / $10 / $16 per seat/mo | Generic scheduling, not industry-specific |
| Acuity Scheduling | $20 / $34 / $61 /mo | Client-facing booking + payments |
| Square Appointments | Free 1 location, then $49/mo/location | Bundles with Square payments |

[Source: Koalendar Calendly vs Acuity](https://koalendar.com/blog/calendly-vs-acuity)

---

### POS / Sales Tracking
| Product | Software Fee | Transaction Fee | Notes |
|---|---|---|---|
| Square | Free–$60/mo | 2.4–2.6% + 15¢ | Best free tier |
| Toast | $69/mo (+$50-100/mo integrations) | 2.99% + 15¢ | Restaurant-focused, 2-yr contract |
| Clover | $135/mo cheapest hospitality plan | 2.3% + 10¢ | Plus $9.95–$34.95/device |

[Source: Beancount.io Toast/Square/Clover guide](https://beancount.io/blog/2026/07/29/square-toast-clover-pos-comparison-guide)

**Note:** transaction fees are the real money-maker in POS — software fees are almost a loss-leader for these companies. If you build "just sales tracking" (no actual card processing), you're competing only against the software fee, which is a much easier price point to beat.

---

### Menu Creation / Digital Menu
| Product | Price | Notes |
|---|---|---|
| Juuno | $18/screen/mo | Digital signage focus |
| vMenu | $39/mo (3-yr contract) | Locked-in pricing |
| BentoBox | $119/mo website + $49/mo ordering + $19/mo QR | Adds up fast — $187/mo for full stack |

[Source: MenuTiger digital menu guide](https://www.menutiger.com/blog/best-digital-menu-for-restaurants)

This is a **low-cost module to build** (mostly CRUD + image storage) but bundlers stack fees aggressively. Bundling it free-with-tier is a strong differentiator.

---

### Full-Stack "All-in-One" Comparables (closest thing to what you're building)
| Product | Price | What's included |
|---|---|---|
| HotSchedules | Free ≤30 employees/1 location, then from $34.99/mo | Scheduling-first, some HR |
| Toast (POS+Payroll bundle) | $69/mo + $9/employee | POS + payroll only |
| Restaurant365 | ~$435/mo single location | Accounting + inventory + scheduling |
| Typical full-featured suite | **$400–$1,200/mo** depending on modules enabled | This is your real competitive set |

[Source: FoodDocs restaurant management software guide](https://www.fooddocs.com/post/restaurant-management-software), [Orocube buyer's guide](https://www.orocube.com/restaurant-management-software/)

**This is the number that matters most.** A business stitching together scheduling + payroll + inventory + booking + POS + menu + accounting today is realistically paying:
```
Scheduling:     $40-100/mo
Payroll:        $80-180/mo (+ per employee)
Inventory:      $30-150/mo
Booking:        $20-60/mo
POS software:   $50-135/mo
Menu:           $40-190/mo
Accounting:     $0-70/mo (often bolted onto payroll)
───────────────────────────
STITCHED TOTAL: $260-885/mo, PLUS the integration headache of none of it talking to each other
```

**You already have a built-in pitch:** "one login, one price, everything talks to each other." That's worth a real premium over any single-purpose competitor, and it's *cheaper* than stitching 5-7 tools together even at a $299-399/mo price point.

---

## PART 3: How to Offer Payroll Without Becoming a Licensed Payroll Company

You asked the right question — this is the part that kills most indie SaaS payroll features.

### The problem
Real payroll means: calculating withholding correctly per state/locality, filing federal/state tax forms (941, state UI, etc.), remitting withheld taxes on schedule, issuing W-2s/1099s, and staying current on constantly-changing tax law. Getting this wrong exposes *you* to IRS penalties and exposes your customers to compliance risk. This is not a "build it yourself" module.

### Three real paths

**1. Embedded Payroll (recommended)**
Companies like **Check (check.dev)**, **Gusto Embedded**, **Deel**, and **Rippling API** exist specifically so SaaS platforms like yours can offer "payroll" without becoming the licensed employer/filer. They hold the tax licenses, do the actual filing and remittance, and expose an API. You build the UI inside your product, mark up their per-employee fee, and the compliance liability sits with them, not you.
- Typical embedded payroll cost to you: **$4-8/employee/month wholesale**, letting you retail it at $10-15/employee and keep a real margin without touching tax law.
- This is exactly how Toast, Homebase, and dozens of vertical SaaS tools offer "payroll" — almost none of them are the actual filer.

**2. Payroll *Prep* Only (no filing) — cheapest to build, lowest liability**
Build the calculator: track hours → compute gross pay → compute standard withholding estimates → generate a pay stub / CSV export for the business owner or their accountant to actually run through a filer (or write checks manually for very small crews). You explicitly do **not** remit taxes or file anything. This matches the accounting boundary language already in your own README (`"Tax filing, jurisdiction-specific payroll compliance... require additional integrations and professional review before commercial claims are made"`) — you're already positioned correctly for this option. Add a clear disclaimer in-product and you're fine.

**3. Become a Licensed Payroll Provider — not recommended**
Requires state-by-state registration, IRS e-file provider status, surety bonds in some states, and ongoing compliance overhead. This is a full company in itself. Skip it unless payroll becomes your entire business.

### Recommendation
Ship **Option 2 (payroll prep)** now — it's basically free to build on top of what you have (timesheets already exist via scheduling) and keeps you legally clean. Layer in **Option 1 (Check.dev or Gusto Embedded)** as a paid upgrade once you have real customers asking for full-service payroll — that's a partnership integration, not a rebuild.

---

## PART 4: Suggested Pricing Given "Top of Line" Quality

Since you're assuming heavy investment into making each module genuinely best-in-class, and you have a real structural advantage (unified platform vs. stitched tools), price toward the top of the comparable range, not the bottom:

| Tier | Price | Positioning |
|---|---|---|
| **Starter** | $49/mo (base) + no per-user fee up to 5 users | Undercuts stitching 2-3 point solutions ($150-250/mo) |
| **Growth** | $149/mo, up to 25 users | Undercuts a mid-size stitched stack ($400-600/mo) by 65%+ |
| **Pro** | $349/mo, up to 75 users, all modules incl. AI | Still 40-60% cheaper than Restaurant365-tier suites ($435-1,200/mo) |
| **Enterprise** | Custom, 75+ users | Match/beat custom quotes from ADP/Toast enterprise deals |

Payroll and heavy AI usage should be **metered add-ons on top of the base tier**, not bundled flat — those are your two genuinely variable costs (per-employee payroll fees, per-token AI costs). Everything else (scheduling, inventory, CRM, booking, menu, POS-lite) is nearly fixed-cost to run per Part 1, so bundle it freely.

---

## Sources
- [Railway Pricing Plans](https://docs.railway.com/pricing/plans)
- [Railway Pricing Explained 2026](https://livemy.app/blog/railway-pricing)
- [Homebase: Retail Scheduling Software 2026](https://www.joinhomebase.com/blog/retail-scheduling-software)
- [7shifts vs Homebase Pricing](https://www.stackscored.com/pricing/employee-scheduling/compare/7shifts-vs-homebase/)
- [Gusto Pricing 2026](https://whichpayroll.com/pricing/gusto)
- [PEO vs Payroll Outsourcing Guide](https://onpay.com/insights/peo-payroll-outsourcing-guide/)
- [Inventory Management Software Cost 2026](https://erpsoftwareblog.com/2026/07/inventory-management-software-cost/)
- [Calendly vs Acuity 2026](https://koalendar.com/blog/calendly-vs-acuity)
- [Toast vs Square vs Clover 2026](https://beancount.io/blog/2026/07/29/square-toast-clover-pos-comparison-guide)
- [MenuTiger Digital Menu Guide 2026](https://www.menutiger.com/blog/best-digital-menu-for-restaurants)
- [Restaurant Management Software Guide 2026](https://www.fooddocs.com/post/restaurant-management-software)
- [Orocube Restaurant Management Buyer's Guide](https://www.orocube.com/restaurant-management-software/)
