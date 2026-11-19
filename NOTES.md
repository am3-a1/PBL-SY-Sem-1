# Redesign Summary and Engineering Notes

## What Changed

The FeedPulse frontend was redesigned from a generic dark-indigo dashboard into a deliberate, restraint-oriented professional feedback triage tool.

### Design Tokens and Theme
- **Color Tokens:** Replaced the dark indigo/violet palette with a clean light theme:
  - `paper`: `#F5F6F8` (page background)
  - `surface`: `#FFFFFF` (card and panel background)
  - `ink`: `#1B232B` (primary text, passes WCAG AAA)
  - `muted`: `#5B6670` (secondary text, passes WCAG AA 4.5:1 on paper)
  - `line`: `#DDE1E6` (dividers and borders)
  - `negative`: `#C23B2A` (sentiment only)
  - `positive`: `#2F7A63` (sentiment only)
  - `neutral`: `#8C96A0` (sentiment only)
  - `action`: `#2A46C9` (interactive states only: focus rings, selected tabs, links, primary buttons)
- **Border Radii:** Standardized to two radii only: `4px` (small inputs, buttons, pills) and `8px` (cards, panels, modals).
- **Typography:** Adopted Instrument Sans (Google Fonts 400, 500, 600) and removed Inter. Enabled `font-variant-numeric: tabular-nums` globally on all numbers. Replaced all sub-12px text sizes (`text-[10px]`, `text-[11px]`) with a minimum of 12px (`text-xs`).
- **Clean Styling:** Removed all colored glows, shadows, gradients, and backdrop blurs. Neutralized scrollbars and replaced the generic layer favicon with an ink pulse line. Added global `:focus-visible` (2px action outline) and `@media (prefers-reduced-motion: reduce)`.

### Header (`Header.jsx`)
- Replaced the gradient logo tile, animate-ping dot, "Triage Sentinel" pill, and subtitle with a plain text wordmark "FeedPulse".
- Replaced the segmented pill control with underline text tabs ("Analytics", "Triage board"), keeping the review count as plain text.
- Replaced the dark button with a clean 1px border button "Import and alerts". Retained the refresh button with `aria-label="Refresh data"`.
- Removed developer actions ("Load demo data" and "Clear all") from the header and relocated them into the modal.

### Filter Bar (`FilterBar.jsx`)
- Restyled as a flat row on the page background without card wrappers or shadows.
- Added visible text labels for Channel, Sentiment, and Theme select dropdowns with clear focus outlines.
- Formatted review counter as plain text (`Showing X of Y reviews`).
- Added a removable Theme filter chip that stays in sync when selecting themes from the Analytics view.
- **Bug Fix:** Wired filters to apply directly to both the Kanban board and the Analytics overview.

### Triage Board & Drawer (`KanbanBoard.jsx`, `ReviewCard.jsx`, `ReviewDrawer.jsx`)
- **Columns:** Replaced boxed panels with full-height 1px vertical column dividers. Removed per-column icon badges, subtitles, and internal scrollbars so the page scrolls as one. Empty columns show single-line muted text ("Nothing here. Drag a review in.").
- **Cards:** White surface with 1px `line` border, 8px radius, and a 3px left edge bar colored by sentiment (`negative`/`neutral`/`positive`) with an accessible `sr-only` sentiment label. Removed emoji icons, colored channel tags, numeric sentiment scores, and the per-card status dropdown. Cards clamp review text to 4 lines and show a muted meta line with channel, rating ("4/5" or "Thread"), and date.
- **Review Drawer:** Added a slide-in drawer component (150ms transform, disabled on reduced motion, light scrim) accessible by clicking or pressing Enter on focused cards. Displays full review text, author, channel, date, rating, sentiment label, theme, an interactive status select (firing status PATCH updates), and up to 5 related reviews within the same theme. Traps focus and closes on Escape.

### Analytics (`AnalyticsOverview.jsx`)
- Removed the four KPI cards and the invented Churn Risk Index. Replaced with a single plain sentence-style line above the chart: `{total} reviews · {negPct}% negative · {openCritical} open critical`.
- Replaced smoothed line chart with a full-width stacked daily bar chart colored by negative, neutral, and positive sentiment tokens with plain date labels. Flags days exceeding the configured negative spike threshold.
- Replaced theme bar chart with a ranked horizontal list showing theme name, review count, and neutral inline proportion bars. Clicking any theme sets the filter and navigates to the board.
- Replaced channel bar chart and sentiment donut with a compact, color-neutral table showing review count, negative share, and inline progress indicators.
- Derived all analytics calculations from the active `filteredReviews` dataset.

### Spike Banner and Modal (`App.jsx`, `ImportSettingsModal.jsx`)
- Replaced glowing red spike banner with a flat, bordered surface bar with a 4px negative-colored left edge and concise text.
- Restyled Import and Alerts modal to design tokens (white surface, 8px radius, no glow). Grouped Demo Data, CSV upload, and Clear All under a "Data" tab. Added an inline confirmation dialog before clearing database records.

---

## Known Follow-ups (Outside Frontend Scope)

1. **Hybrid Rating & Sentiment Scoring:**
   The current VADER sentiment model occasionally mislabels negative user feedback as positive due to polite language or sarcasm (for example, a 1-star review: *"You charged my credit card twice for the annual subscription ($89.99 x 2) and your in-app restore purchase button says 'No active license found'!"* receives a positive compound score of `+0.7177`). The backend ingestion pipeline should incorporate star ratings (e.g. 1-2 stars automatic Negative weighting) alongside text sentiment for store reviews.

2. **Themes as First-Class Entities:**
   Currently, `category_theme` is a string attribute per review. Promoting themes to a first-class API entity would allow product and support teams to triage, assign, or batch-update the status of an entire theme cluster (e.g. escalating all "Login Crash" tickets to Engineering in a single action).


---

## Additional Engineering Documentation & Fixes

### 1. Cause of the Inline Bar Rendering Bug
- **Diagnosed Root Cause:** In `tailwind.config.js`, the color `ink` was mapped to `var(--color-ink)` (or `var(--ink)`), which resolves to a hex code (`#1B232B`). Tailwind CSS v3 cannot evaluate opacity modifiers (like `bg-ink/20`) on CSS variables defined as hex codes without RGB channel separators. Consequently, the utility class `.bg-ink\/20` was not generated at all by the Tailwind compiler.
- **Visual Consequence:** The inner fill elements for both the Top Themes list and the Channels table had no background color (transparent). Thus, users only saw the empty grey track (`bg-line` / `bg-track`), making every bar appear as an empty identical grey line.
- **Resolution:**
  - Track and fill elements are now explicitly `display: block` with a fixed height of `6px` (`h-[6px]`) and `4px` radius (`rounded`).
  - Replaced the missing class with semantic token utilities: `bg-muted` for theme proportion bars (scaled `count / maxThemeCount`) and `bg-negative` for channel bars (scaled `negative_reviews / total_channel_reviews`).
  - Added `aria-hidden="true"` to decorative bar containers since exact quantitative values are presented in the adjacent tabular text.

### 2. Spike Rule Used
- **Eligibility Criteria:** A calendar day is flagged as a negative feedback spike if and only if:
  1. The day has **at least 3 total reviews** (`grp.total >= 3`), preventing statistical distortion from single-review days.
  2. The negative feedback percentage meets or exceeds the user-configured alert threshold from `alertConfig.negative_threshold_pct` (defaulting dynamically to the configured value in the database, e.g. 30%).
- **Visual Representation:**
  - A 6px downward-pointing triangle marker rendered in the negative token color above the corresponding stacked bar using Recharts `<ReferenceDot>` with an SVG polygon.
  - An explicit multi-modal indicator in the tooltip stating: `"Spike: X of Y negative (Z%)"`.
  - When no days breach the threshold, the subtitle and legend spike indicator are completely hidden.

### 3. Theme Token Table & Contrast Verification

All tokens are defined in `src/index.css` under `:root` (light) and `:root[data-theme="dark"]`, mapped in `tailwind.config.js`, and accessible dynamically in charts via `useThemeColors`.

| Token Name | Light Value | Dark Value | Purpose & Usage | WCAG AA Status |
| :--- | :--- | :--- | :--- | :--- |
| `--paper` | `#F5F6F8` | `#12161B` | Page background | Base background |
| `--surface` | `#FFFFFF` | `#1A2027` | Card, panel, and modal background | Base surface |
| `--ink` | `#1B232B` | `#E8ECEF` | Primary text and headings | > 13.8:1 (AAA) |
| `--muted` | `#5B6670` | `#9AA5B0` | Secondary text, labels, and theme fills | > 5.4:1 (AA) |
| `--line` | `#DDE1E6` | `#2B333B` | Borders, dividers, and subtle lines | UI boundary |
| `--negative` | `#C23B2A` | `#E0624F` | Negative sentiment only & spike markers | > 4.7:1 (AA) |
| `--neutral` | `#8C96A0` | `#8C96A0` | Neutral sentiment only | 3.0:1 (Graphics) / 5.4:1 dark |
| `--positive` | `#2F7A63` | `#4CAF8E` | Positive sentiment only | > 4.7:1 (AA) |
| `--action` | `#2A46C9` | `#7C93FF` | Focus rings, selected tab, primary buttons | > 5.8:1 (AA) |
| `--track` | `rgba(27,35,43,0.10)` | `rgba(232,236,239,0.12)` | Inline bar track background | Non-text UI |
| `--scrim` | `rgba(27,35,43,0.20)` | `rgba(0,0,0,0.50)` | Drawer and modal light scrim backdrop | Overlay |
