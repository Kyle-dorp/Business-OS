/**
 * The icon set.
 *
 * The navigation used a typographic alphabet — ⌂ ◎ $ ↓ ≡ ↗ ✓ □ ◉ ◷ ▦ ◈ ⚖ ◑ ✦
 * ◇ ● ⛨ ⚙ — which was consistent, which is why the drawer looked deliberate.
 * It had two problems that consistency could not fix.
 *
 * Several carried no meaning. ◈ for Preflight, ◑ for Bookings, and ◇ ◉ ◎ are
 * near-indistinguishable at 16px.
 *
 * And two were doing double duty. `$` marked both Sales & invoices and
 * Finance; `◉` marked both Stock intelligence and Plan & billing, which are
 * not related by anything. Ten of twenty-two nav entries shared a glyph with
 * something else, so the icon could not be what you navigated by.
 *
 * lucide-react was already a dependency and entirely unused.
 *
 * Icons are addressed by key rather than imported at each call site, so the
 * set is enumerable — a test can check that every destination has one and that
 * no two destinations share one, which is the property that was broken.
 */

import {
  ArrowRightLeft,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CalendarCheck,
  CalendarDays,
  CheckSquare,
  ClipboardCheck,
  Clock,
  CreditCard,
  Landmark,
  LayoutDashboard,
  ListTree,
  Package,
  PackageSearch,
  Receipt,
  Scale,
  Send,
  Settings,
  Shield,
  ShoppingCart,
  Sparkles,
  Target,
  Users,
  Wallet,
} from "lucide-react";

/**
 * Key to component. The key is what a tab stores, so the navigation config
 * stays plain data and the icon it names can be checked without rendering it.
 */
export const ICONS = {
  today: LayoutDashboard,
  sales: Receipt,
  purchasing: ShoppingCart,
  bookkeeping: BookOpen,
  finance: Landmark,
  reports: BarChart3,
  scheduling: CalendarDays,
  availability: Clock,
  preflight: ClipboardCheck,
  compliance: Scale,
  assistant: Bot,
  inventory: Package,
  "inventory-intel": PackageSearch,
  bookings: CalendarCheck,
  contacts: Users,
  tasks: CheckSquare,
  notifications: Bell,
  ask: Sparkles,
  settings: Settings,
  billing: CreditCard,
  security: Shield,
  requests: Send,

  // Finance keeps its own subnav, which had the same problem the main
  // navigation did: a diamond for Dashboard and a circle for Payroll.
  "fin-dashboard": LayoutDashboard,
  "fin-budget": Target,
  "fin-cashflow": ArrowRightLeft,
  "fin-accounts": ListTree,
  "fin-payroll": Wallet,
};

/**
 * One icon, drawn the same way everywhere.
 *
 * Decorative by default: the label beside it already says where the link goes,
 * and a screen reader announcing "calendar days, Scheduling" is worse than
 * announcing "Scheduling". Pass a `label` only when the icon is alone.
 */
export function Icon({ name, size = 18, className = "", label }) {
  const Glyph = ICONS[name];
  if (!Glyph) return null;
  return (
    <Glyph
      size={size}
      strokeWidth={1.5}
      className={className}
      aria-hidden={label ? undefined : "true"}
      aria-label={label}
      role={label ? "img" : undefined}
      focusable="false"
    />
  );
}

export default Icon;
