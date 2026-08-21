# Business-EOS: Modern Frontend Design System

## 🎨 Design Philosophy

**"Spacious. Breathing. Intentional."**

- Maximum whitespace
- Minimal visual noise
- Large, readable text
- Generous padding & margins
- Smooth interactions
- Futuristic but not gimmicky

---

## 🎯 Design System

### Color Palette

```
Primary:     #0F172A (Deep blue-black)
Accent:      #3B82F6 (Bright blue) 
Success:     #10B981 (Emerald green)
Warning:     #F59E0B (Amber)
Danger:      #EF4444 (Red)
Neutral:     #6B7280 (Slate gray)

Background Light:  #FFFFFF
Background Dark:   #F9FAFB
Surface:           #F3F4F6
Text Primary:      #111827
Text Secondary:    #6B7280
Text Muted:        #9CA3AF

Accents:
- Glass: rgba(255,255,255,0.1)
- Shadow: rgba(0,0,0,0.08)
- Glow: rgba(59,130,246,0.1)
```

### Typography

```
Font Stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif

Sizes:
- H1: 48px / 600 weight (hero titles)
- H2: 36px / 600 weight (section titles)
- H3: 28px / 600 weight (card titles)
- H4: 22px / 600 weight (subsections)
- Body Large: 18px / 400 weight (descriptions)
- Body Normal: 16px / 400 weight (content)
- Body Small: 14px / 400 weight (labels)
- Caption: 12px / 400 weight (hints)

Line Height:
- Headings: 1.2
- Body: 1.6
- Labels: 1.4
```

### Spacing Scale

```
xs:  4px   (micro-spacing)
sm:  8px   (small gaps)
md:  16px  (standard gap)
lg:  24px  (generous gap)
xl:  32px  (large section)
2xl: 48px  (extra large)
3xl: 64px  (hero spacing)

Usage:
- Padding: Always use at least md (16px)
- Margins: Between sections: lg-2xl
- Card padding: lg (24px)
- Component padding: sm-md (8-16px)
```

### Shadows & Depth

```
Subtle:      0 1px 2px rgba(0,0,0,0.05)
Card:        0 4px 6px rgba(0,0,0,0.07)
Hover:       0 10px 15px rgba(0,0,0,0.1)
Modal:       0 20px 25px rgba(0,0,0,0.15)
Float:       0 15px 30px rgba(59,130,246,0.15) (with glow accent)

Transitions: all 0.3s ease
```

### Borders & Radius

```
Border Width: 1px
Border Color: #E5E7EB (light gray)
Border Radius:
- Buttons: 8px
- Cards: 12px
- Modals: 16px
- Avatar: 50% (circles)
```

---

## 🖼️ Page Layouts

### 1. Landing / Login Page

**Goal:** Clean, minimal, professional

```
Layout:
┌─────────────────────────────────────┐
│                                     │
│     (64px top padding)              │
│                                     │
│   Logo (32px size)                  │
│                                     │
│   (32px spacing)                    │
│                                     │
│   "Welcome Back"                    │
│   H2 headline                       │
│                                     │
│   (16px spacing)                    │
│                                     │
│   "Sign in to your Business-EOS     │
│    account to get started."          │
│   Body text, text-secondary         │
│                                     │
│   (48px spacing)                    │
│                                     │
│   ┌─────────────────────────────┐   │
│   │ Email input field           │   │ (Full width, padding-lg)
│   └─────────────────────────────┘   │
│                                     │
│   (16px spacing)                    │
│                                     │
│   ┌─────────────────────────────┐   │
│   │ Password input field        │   │
│   └─────────────────────────────┘   │
│                                     │
│   (8px spacing)                     │
│                                     │
│   [Forgot password?] (link)         │
│                                     │
│   (32px spacing)                    │
│                                     │
│   ┌─────────────────────────────┐   │
│   │  → Sign In (button)         │   │ (Full width)
│   └─────────────────────────────┘   │
│                                     │
│   (24px spacing)                    │
│                                     │
│   ─────────────────────────────     │ (divider)
│                                     │
│   (24px spacing)                    │
│                                     │
│   "New to Business-EOS?"            │
│   [Create Business] (secondary btn)  │
│                                     │
│   (64px bottom padding)             │
│                                     │
└─────────────────────────────────────┘

Max Width: 480px (centered)
Color: White background, subtle shadows
```

### 2. Create Business / Signup Flow

**Multi-step with progress indicator**

**Step 1: Business Basics**
```
Progress: ━━━━━━ (1/4)

Headline: "Let's set up your business"
Subheading: "Tell us about your company"

Form Fields (stacked):
- Business Name (text input)
- Industry/Type (dropdown - shows presets)
- Location Name (text input)
- Timezone (dropdown with smart defaults)

Buttons:
[← Back]  [Next →] (right-aligned)
```

**Step 2: Choose Preset**
```
Progress: ━━━━━━━━ (2/4)

Headline: "Pick your profile"
Subheading: "Select the business type that fits you"

Grid (2 columns on desktop, 1 on mobile):
┌──────────────┐  ┌──────────────┐
│  🍔          │  │  💇          │
│ Restaurant   │  │ Salon/SPA    │
└──────────────┘  └──────────────┘
┌──────────────┐  ┌──────────────┐
│  📋          │  │  🛍️          │
│ Professional │  │ Retail       │
└──────────────┘  └──────────────┘
┌──────────────┐  ┌──────────────┐
│  🔧          │  │  ⚙️          │
│ Services     │  │ Custom       │
└──────────────┘  └──────────────┘

Cards have hover effect (lift + glow)
Selected card has blue border + background tint
```

**Step 3: Select Features**
```
Progress: ━━━━━━━━━━ (3/4)

Headline: "Choose your features"
Subheading: "Start with essentials, add more as you grow"

Toggle switches (each on its own row with description):

┌─────────────────────────────────────┐
│ Staff Scheduling                 [•] │
│ Smart scheduling with AI optimization
└─────────────────────────────────────┘
(16px gap)
┌─────────────────────────────────────┐
│ Public Booking Calendar          [ ] │
│ Let customers book appointments
└─────────────────────────────────────┘
... (more features)

Max visible: 5 features, scrollable
Each feature has:
- Clear title
- 1-line description
- Toggle switch (right-aligned)
```

**Step 4: Billing**
```
Progress: ━━━━━━━━━━━━ (4/4)

Headline: "Choose your plan"
Subheading: "You can change anytime"

Plan Cards (3 columns):
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Starter    │ │Professional │ │  Business   │
│  $10/mo     │ │  $49/mo     │ │  $129/mo    │
│             │ │ ⭐ Popular  │ │             │
│ ✓ Feature 1 │ │ ✓ Feature 1 │ │ ✓ Feature 1 │
│ ✓ Feature 2 │ │ ✓ Feature 2 │ │ ✓ Feature 2 │
│             │ │ ✓ Feature 3 │ │ ✓ Feature 3 │
│             │ │ ✓ Feature 4 │ │ ✓ Feature 4 │
│             │ │             │ │ ✓ Feature 5 │
│ [Select]    │ │ [Select]    │ │ [Select]    │
└─────────────┘ └─────────────┘ └─────────────┘

Middle card (Professional) has blue background highlight
Selected card has blue border
```

---

## 3. Dashboard Layout

**After login - main hub**

```
┌────────────────────────────────────────────────────┐
│  Business-EOS           [Profile] [Settings] [?]   │  (Top bar)
├────────────────────────────────────────────────────┤
│  [≡] Sidebar (collapsible)                         │
├─────────┬──────────────────────────────────────────┤
│ SIDEBAR │   MAIN CONTENT AREA                      │
│         │                                           │
│ Home    │   ╔═════════════════════════════════════╗│
│ ─────   │   ║  Today Overview                     ║│
│         │   ║  ────────────────────────────────  ║│
│ Modules │   ║  Revenue: $2,340   Staff: 8/10     ║│
│ • Sched │   ║  Appointments: 12  Customers: 45   ║│
│ • Book  │   ║  ════════════════════════════════  ║│
│ • Sales │   ║                                     ║│
│ • CRM   │   ╚═════════════════════════════════════╝│
│ • Pay   │                                           │
│ • Team  │   (32px gap)                             │
│         │                                           │
│ Reports │   ╔═════════════════════════════════════╗│
│ Users   │   ║  This Week Trend                   ║│
│ Settings│   ║  [Chart visualization]              ║│
│         │   ╚═════════════════════════════════════╝│
│         │                                           │
│         │   (32px gap)                             │
│         │                                           │
│         │   ╔═════════════╗   ╔═════════════════╗ │
│         │   ║ Quick Link1 ║   ║ Quick Link 2    ║ │
│         │   ╚═════════════╝   ╚═════════════════╝ │
│         │                                           │
└─────────┴──────────────────────────────────────────┘

Sidebar: 
- 280px wide (desktop)
- Collapses on mobile
- Icons + labels
- Active item highlighted in blue
- Smooth hover states

Main content:
- Max width: 1400px
- Padding: xl (32px)
- Cards have subtle shadows
- Whitespace between sections
```

---

## 🧩 Component Design

### Buttons

```
Primary Button (CTA):
┌──────────────────┐
│  → Get Started   │  (arrow icon + text)
└──────────────────┘

Size: 48px height
Padding: 0 xl (32px)
Font: 16px / 600 weight
Color: White text on blue background
Hover: Darker blue + slight lift
Active: Pressed effect
Disabled: Gray, no hover

Secondary Button:
┌──────────────────┐
│  Learn More      │
└──────────────────┘

Outline style, blue border
Transparent background
Hover: Light blue background

Ghost Button:
Simple text link style
Hover: Color fade

Small Button (for dialogs):
32px height, sm padding
Used in modals & tables
```

### Form Inputs

```
Text Input:
┌─────────────────────────────────┐
│ Email Address              ✓     │
└─────────────────────────────────┘
- Border: 1px light gray
- Padding: md (16px)
- Radius: 8px
- Focus: Blue border + subtle glow
- Filled: Light background tint
- Error: Red border + error message below (8px gap)

Textarea (larger):
┌─────────────────────────────────┐
│ Notes                           │
│                                 │
│                                 │
└─────────────────────────────────┘
- Minimum height: 120px
- Resize: vertical only

Dropdown:
┌─────────────────────────────┐
│ Select Business Type    ▼   │
└─────────────────────────────┘
- Shows selected option
- Dropdown opens downward
- Options have hover state
- Keyboard navigable

Toggle Switch:
  [•] or [ ]
  - Blue when on
  - Gray when off
  - Smooth animation (0.3s)

Checkboxes & Radio:
[✓] Option A
[ ] Option B
- Size: 18px
- Accessible labels
```

### Cards

```
Standard Card:
┌─────────────────────────────────┐
│ Card Title                      │  (padding-lg: 24px)
│ ─────────────────────────────   │  (border-bottom)
│                                 │  (16px gap)
│ Card content goes here          │
│ Multiple lines of text          │
│                                 │
└─────────────────────────────────┘

Hover: Subtle lift + deeper shadow
Radius: 12px
Background: White
Border: 1px light gray (optional)
Shadow: Card shadow level

Feature Card (for preset selection):
┌─────────────────────────────┐
│        🍔                   │  (icon: 48px)
│                             │  (16px gap)
│    Restaurant               │  (heading)
│                             │
│ Smart scheduling for        │
│ food service operations     │  (description)
│                             │
└─────────────────────────────┘

Hover: Lift effect + glow
Selected: Blue border + tinted background
```

### Tables

```
Compact, clean table design:

Customer Name  | Email          | Status   | Actions
───────────────────────────────────────────────────
John Doe       | john@...       | Active   | ⋯
Jane Smith     | jane@...       | Inactive | ⋯
...

- Header: Bold, uppercase labels (12px)
- Rows: Normal weight (14px)
- Padding: md (16px) horizontal, sm (8px) vertical
- Hover: Light background on row
- Striping: Alternate row backgrounds (subtle)
- Actions: Dropdown menu (⋯)
- Mobile: Horizontal scroll or card view
```

### Modals

```
┌──────────────────────────────────┐
│ ┌──────────────────────────────┐ │
│ │ Delete Appointment      [×]  │ │
│ │                              │ │
│ │ Are you sure you want to    │ │
│ │ delete this appointment?    │ │
│ │                              │ │
│ │ [Cancel]  [Delete]          │ │
│ └──────────────────────────────┘ │
│                                  │
└──────────────────────────────────┘

- Dark overlay (rgba 0,0,0,0.4)
- Card centered on screen
- Max width: 600px
- Padding: 2xl (48px)
- Radius: 16px
- Close button (×) in top-right
- Focus trap
- Escape key closes

Backdrop click closes (optional)
```

---

## 🎬 Interactions

### Hover States

```
All interactive elements:
- Subtle color shift
- Slight lift (transform: translateY(-2px))
- Shadow increase
- Duration: 0.3s ease
- No harsh transitions
```

### Loading States

```
Skeleton loaders (instead of spinners):
┌──────────┐
│░░░░░░░░░░│  (animated pulse)
│░░░░░░░░░░│
│░░░░░░░░░░│
└──────────┘

Spinners (when used):
  ⟳ (subtle rotation)
  Duration: 0.8s
  Color: Blue accent
```

### Animations

```
Page transitions: 0.3s fade
Card entrance: 0.4s slide-up + fade
Modal open: 0.3s scale + fade
Button press: 0.2s scale (98%)
```

---

## 📱 Responsive Breakpoints

```
Desktop:  1280px+  (3-column layouts)
Tablet:   768-1279 (2-column layouts)
Mobile:   <768px   (1-column, full width)

Sidebar: 
- Desktop: 280px fixed
- Tablet: Collapsible drawer
- Mobile: Hidden by default, hamburger menu

Cards:
- Desktop: 4 per row
- Tablet: 2-3 per row
- Mobile: 1 per row (full width)

Modals:
- Desktop: 600px max width
- Tablet: 90vw max width
- Mobile: 100vw - 32px margin
```

---

## 🎨 Usage Guidelines

### Whitespace

- **Never** crowd content
- **Always** use at least md (16px) between elements
- **Between sections:** lg-2xl (24-48px)
- **Inside cards:** lg (24px)
- **Mobile:** Reduce to md (16px)

### Typography Hierarchy

1. **H1** - Page titles
2. **H2** - Section headers
3. **H3** - Card titles
4. **Body Large** - Descriptions, previews
5. **Body** - Main content
6. **Small** - Labels, hints
7. **Caption** - Timestamps, metadata

### Color Usage

- **Blue** - Primary CTAs, highlights, active states
- **Green** - Success, positive actions
- **Amber** - Warnings, caution
- **Red** - Errors, destructive actions
- **Gray** - Disabled, secondary, inactive
- **White/Light** - Backgrounds, content areas

### No "Crowded" Anti-patterns

❌ Don't:
- Pile 10 cards in a row
- Use tiny fonts
- Remove breathing room for "efficiency"
- Add unnecessary borders/lines
- Overuse colors

✅ Do:
- Max 4 items per row
- Readable font sizes (16px minimum)
- Generous padding & margins
- One primary color per section
- Let the UI breathe

---

## 📐 Implementation Notes

**React/Vue/Svelte Structure:**
```
components/
├── Button/
├── Input/
├── Card/
├── Modal/
├── Table/
├── Sidebar/
└── DashboardLayout/

layouts/
├── AuthLayout (login, signup)
├── DashboardLayout (sidebar + main)
└── MinimalLayout (full-width)

pages/
├── Login.tsx
├── CreateBusiness/
│   ├── Step1.tsx (basics)
│   ├── Step2.tsx (preset)
│   ├── Step3.tsx (features)
│   └── Step4.tsx (billing)
├── Dashboard.tsx
└── [module pages]
```

**CSS-in-JS / Tailwind:**
- Use design tokens for consistency
- Spacing: Use 8px scale (8, 16, 24, 32, 48, 64)
- No hardcoded colors - use palette tokens
- Responsive utilities for breakpoints

---

This is your design system. **Keep it spacious. Keep it clean. Keep it intentional.**
