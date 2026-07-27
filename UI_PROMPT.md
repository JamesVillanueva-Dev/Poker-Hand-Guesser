# UI/UX Prompt — Poker Hand Range Estimator

> Hand this document to a coding agent working in this repository. Read all of it before
> writing code. Everything below is about `frontend/`; the Python engine is correct and
> is not to be changed except where a task explicitly says so.

---

## 0. What is wrong

The engine was rebuilt and is now measurably good. The interface has not kept up, and it
is now the reason the tool is unpleasant to use. Three distinct problems:

**Problem 1 — the app is a scroll, not a screen.**
`App.tsx` renders ten panels stacked vertically at equal visual weight: guided flow,
calibration, recommendation, metrics, heatmap, top hands, explainer, timeline, charts,
player stats. The heatmap — the entire point of the product — sits roughly 1,800px down
the page. Every panel header is the same `text-sm font-semibold uppercase tracking-wide
text-zinc-600` label, so nothing is more important than anything else. Using this means
scrolling up and down between the controls at the top and the answer in the middle.

**Problem 2 — entering a hand is slow and error-prone.**
Logging one action requires: pick actor, pick action from a dropdown of all eight types
(most of which are illegal in the current spot), **manually retype the pot**, drag a
slider, click Apply. Hero and board cards are free-text fields parsed by a regex
(`GuidedHandFlow.tsx:62-69`) that silently drops anything malformed — type `Ah Kd` wrong
and the card just vanishes with no feedback. Meanwhile villain's cards at showdown use
rank/suit dropdowns (`:246-263`). Two different card-entry idioms in one component.

The pot field (`GuidedHandFlow.tsx:338`) is the worst of it. The user has to maintain
pot size by hand across four streets. It feeds `bet_fraction_pot`, which is a direct
input to the policy, so a mistyped pot silently corrupts the prediction. The app already
knows every bet and call in the hand. It should be computing this.

**Problem 3 — the frontend still fabricates data.**
The rebuild removed `demoRange()`, but missed this:

```ts
// frontend/src/components/RangeCharts.tsx:12-16
const trendData = timeline.map((entry, index) => ({
  sequence: entry.sequence,
  aggression: 1.3 + index * 0.12 + (entry.action?.action_type === "jam" ? 0.55 : 0),
  vpip: 24 + index * 0.6,
}));
```

That is an invented straight line, rendered as a filled area chart, labeled "Aggression",
next to a real entropy series. The backend returns real `profile.aggression` and
`profile.vpip` on every response. This chart is the same failure the rest of the app was
just fixed for.

### What it should be

> A tool you can drive through a whole hand without looking away from the answer, that
> never asks you for something it could work out itself, and that shows nothing it has
> not actually computed.

---

## 1. Principles (non-negotiable)

1. **The range is the product.** The heatmap and the recommendation are visible without
   scrolling, on a laptop screen, while you enter actions.
2. **Never ask for derivable state.** Pot size, legal actions, and street progression
   follow from the action history. Ask only for what the app cannot know.
3. **Never render an invented number.** Applies to charts, placeholders, and loading
   states as much as it did to the heatmap.
4. **Every control says what it will do and what happened.** No `title` attribute as the
   only label. No silently dropped input.
5. **Keyboard-complete.** A full hand can be entered without touching the mouse.
6. **Do not change the API contract.** Backend changes are allowed only where §4 says so,
   and only additively.

---

## 2. Task 1 — Delete what is not used (do this first, it is five minutes)

- `frontend/src/components/ActionControls.tsx` (140 lines) — superseded by
  `GuidedHandFlow`, imported by nothing. Delete.
- `frontend/src/components/HandSummary.tsx` (64 lines) — imported by nothing. Delete.
- Verify with `grep -rn "ActionControls\|HandSummary" frontend/src` before and after.

Do not "keep them just in case." They are in git history.

---

## 3. Task 2 — A design system, before any component work

Right now there are five hand-rolled panel classes in `index.css` (`.card-panel`,
`.hero-panel`, `.summary-tile`, `.metric-card`, `.explain-header`), inline
`style={{ borderRadius: 6 }}` scattered across at least eight components, and four
different gap values used with no rule. And in `tailwind.config.js:16`:

```js
copper: "#2563eb"   // this is blue
```

Both accent tokens (`felt`, `copper`) are the same blue hue, so nothing on screen can be
color-coded by meaning.

Establish in `tailwind.config.js` and `index.css`:

- **A radius scale.** One token. Delete every inline `borderRadius` in `frontend/src`.
- **A spacing rhythm.** Pick a scale (4/8/12/16/24) and one `gap` per nesting level.
- **A type scale** with a real hierarchy: page title, section title, body, caption,
  numeric. Panel headers must not all look identical — a section the user reads once
  should not compete with a number they check constantly.
- **Semantic colors**, not just hues: `positive` (value/gain/beats-baseline),
  `negative` (loss/below-baseline), `caution` (unvalidated/small-sample), `neutral`.
  Rename `copper` to what it actually is, or make it actually copper.
- **A sequential ramp for the heatmap** that is legible at 40px and distinguishable by
  people with deuteranopia. The current `hsl(202 + i*12, ...)` ramp varies lightness and
  saturation together across one hue, which compresses the middle of the range into mush.

Then apply it. A component should not contain a raw hex value or an inline style.

---

## 4. Task 3 — Make hand entry fast (the biggest usability win)

### 4a. Compute the pot

Remove the "Pot Before" input from the action row (`GuidedHandFlow.tsx:336-339`).

Derive pot from the hand so far: starting pot plus every amount already logged. The
timeline the backend returns already contains `amount` and `pot_before` for every action.
Show the running pot as read-only text next to the amount control, and keep one editable
starting-pot field in the setup step for blinds/antes.

Add a small "override" affordance for the case where the user is reconstructing a hand
mid-stream and the derived pot is wrong. Default is derived; override is deliberate.

### 4b. Offer only legal actions

The backend already knows the legal action set — `engine/likelihood.py:legal_actions()`
derives it from the action history, and the rebuild made it authoritative. The UI still
renders all eight action types in a `<select>` (`GuidedHandFlow.tsx:331-335`), so a user
can pick `three_bet` with no raise in front, or `check` facing a bet.

**Backend (additive only):** include the legal action list for the *next* opponent
decision in `RangeResponse`. A new optional field — `next_legal_actions: list[str]` —
computed from the same `legal_actions()` the policy uses. Do not change any existing
field. Add a test asserting the field is present and never contains `check` when facing
a bet.

**Frontend:** replace the `<select>` with a row of buttons for the legal actions only,
each one labeled and keyboard-reachable. Fold/check/call/bet/raise are five keystrokes
away, not five clicks.

### 4c. One card picker, used everywhere

Build a single `<CardPicker>` component and use it for hero cards, board cards, and
villain's showdown cards. Requirements:

- Click a rank, click a suit, or type `ah` / `As` / `kd` and have it parse as you go.
- Suits are visually distinct beyond color (shape is already there — use it) so the
  picker is not red/black-only.
- Cards already used elsewhere in the hand are shown as taken and cannot be selected
  twice. The backend treats duplicates as dead cards and it will skew the range.
- Invalid input is rejected visibly, at the moment of entry. Never silently dropped.
- Delete the `parseCards` regex in both `rangeStore.ts` and `GuidedHandFlow.tsx` — one
  parser, in the picker.

### 4d. Bet sizing that matches how people think

Replace the raw slider (`GuidedHandFlow.tsx:340-346`) with pot-fraction quick buttons —
`33%` `50%` `66%` `100%` `all-in` — plus a numeric field for an exact amount. Show both
representations at once (`7.0 bb · 66% pot`), because the user thinks in one and the
model consumes the other.

### 4e. Keyboard

- `1`–`5` select the legal actions in the order shown.
- `Enter` applies the pending action.
- `→` advances the street, `←` steps the timeline back.
- `?` opens a shortcut overlay.

Show the shortcut hints inline on the buttons, not only in the overlay.

---

## 5. Task 4 — Rebuild the layout around the answer

Replace the single scrolling column in `App.tsx:26-64` with a two-region layout at
`lg` and above:

- **A persistent left rail (or top bar) for hand entry** — the current street, the legal
  action buttons, sizing, and the board. This is what the user touches. It does not
  scroll away.
- **A main region for the answer** — heatmap, top hands, recommendation, calibration.
  This is what the user reads.

Everything else — the explainer glossary, the charts, the full timeline, player stats —
moves behind tabs or a collapsed "details" section. They are reference material, not
things to scroll past on every action.

Below `lg`, stack it: entry first, answer second, details collapsed.

### The poker table visualizer

`PokerTableVisualizer.tsx` spends 480px of vertical height to show five card slots, a
pot chip, and the last action. It is absolutely positioned with percentage offsets
(`:67-116`) and does not reflow below `md`. Either earn that space — make it the primary
board display and the click target for entering board cards — or cut it to a compact
board strip. Do not leave it as decoration above the fold.

### States the layout must handle

- **Loading** — skeletons that match the shape of the real content. Not a frozen page
  with disabled buttons, which is what `loading` does today.
- **Hand complete** — `RangeResponse.hand_complete` is already returned and the UI
  ignores it. When true, disable the action controls, mark the range as final, and put
  "Start next hand" where the Apply button was. Right now the user clicks Apply, gets a
  409, and sees a blue box.
- **Errors** — `App.tsx:44` renders every error as the same blue banner with no action.
  Errors should say what to do: a 409 offers "Start next hand", a connection error
  offers "Retry", a validation error points at the field.

---

## 6. Task 5 — Make the data displays legible

### Heatmap (`RangeHeatmap.tsx`)

- Cells are `<button>` elements with no `onClick` (`:50-58`). They look pressable, do
  nothing, and put 169 tab stops in the keyboard path. Either give them a real behaviour
  — click a cell to pin that class and see its probability across the timeline — or make
  them non-interactive `<div>`s. Decide, do not leave it ambiguous.
- Every cell prints a percentage at 11px (`:57`). At 169 cells that is noise. Show the
  hand label always; show the number on hover/focus and for the top N cells only.
- `min-w-[820px]` forces horizontal scroll on most laptops. Make the grid fluid.
- Add a legend that maps color to probability with real numbers on it.
- Blocked classes (probability exactly 0 after card removal) must be visually distinct
  from merely-unlikely ones. They are impossible, not improbable, and that is one of the
  most useful things on the screen.

### Charts (`RangeCharts.tsx`)

- **Delete `trendData` (`:12-16`).** Plot real `profile.aggression` and `profile.vpip`
  from the timeline, or plot neither.
- Entropy and aggression are on different scales and share a Y axis (`:43-51`). Split
  them or give the second series its own axis.
- Default Recharts tooltips and legends are unstyled. Match the design system from §3.

### Explainer (`RangeExplainer.tsx`)

The "Combo Count" copy at `:89-90` says pairs have 6 combos, suited 4, offsuit 12. That
is no longer true — the backend now reports *live* combos after card removal, so `AA` on
an ace-high board reports 3 or 1. **The glossary is now teaching the user something
false.** Fix the copy, and prefer showing the live number for the class in question over
a static definition.

More broadly: this panel is a permanently-open glossary occupying prime vertical space.
Move it behind a "What do these numbers mean?" disclosure.

### Timeline (`Timeline.tsx`)

Rewind is the best feature in the app and it is a horizontal scroll strip whose only
affordance is a `title` tooltip (`:19`). Make it look like a scrubber. Label the current
position. Show the entropy trend along it so the user can see where the range collapsed.

---

## 7. Task 6 — Accessibility, honestly

Not a checklist exercise; the current state fails basic use:

- Keyboard focus is the browser default in most places. Add a visible `:focus-visible`
  style that meets contrast on every interactive element.
- The heatmap encodes its entire meaning in color. Provide a text alternative — a sorted
  list view toggle satisfies this and is genuinely useful on small screens.
- `title` attributes are used as labels in at least four components. They are invisible
  to keyboard users and most screen readers. Use real labels or `aria-label`.
- Range updates change the whole screen with no announcement. Wrap the headline result in
  an `aria-live="polite"` region.
- Check contrast on `text-zinc-400` and `text-zinc-500` against the tinted panel
  backgrounds. Several are likely below 4.5:1.
- Respect `prefers-reduced-motion` — `animationDuration={450}` on the charts and
  `transition hover:scale-[1.03]` on 169 heatmap cells should both be conditional.

---

## 8. Non-goals

- Do not change the Python engine, the range math, the scoring loop, or the profile
  statistics. The one permitted backend change is the additive `next_legal_actions`
  field in §4b.
- Do not add a component library (MUI, Chakra, shadcn). Tailwind is already here and the
  surface is small.
- Do not add a routing library. Tabs are local state.
- Do not add animation libraries. CSS transitions are enough.
- Do not redesign for a marketing audience. This is a tool for one person entering hands
  quickly; density beats whitespace.
- Do not introduce fabricated placeholder content anywhere, including in loading states
  and empty states.

---

## 9. Order of work

1. **§2 Delete dead components** — clears the ground.
2. **§3 Design system** — everything after this depends on the tokens existing.
3. **§4 Hand entry** — the biggest usability win, and it is independent of layout.
4. **§5 Layout** — now the pieces are worth arranging.
5. **§6 Data displays** and **§7 accessibility** — polish on a structure that works.

After §4, enter a complete four-street hand end to end and count the interactions. Write
the number down. It should be at least half what it is today.

---

## 10. Definition of done

- [ ] Entering a full four-street hand requires no manual pot arithmetic.
- [ ] The action controls offer only actions that are legal in the current spot.
- [ ] One card-entry component is used for hero, board, and showdown cards; duplicate
      cards cannot be selected.
- [ ] A full hand can be entered from the keyboard alone.
- [ ] On a 1440×900 screen, the heatmap and the recommended action are both visible
      without scrolling while entering an action.
- [ ] `grep -rn "borderRadius" frontend/src` returns nothing.
- [ ] `grep -rn "ActionControls\|HandSummary\|trendData" frontend/src` returns nothing.
- [ ] No chart, panel, or placeholder renders a number the backend did not produce.
- [ ] `hand_complete` disables the action controls and offers the next hand.
- [ ] Every error state offers the action that resolves it.
- [ ] The combo-count explanation matches what the backend actually reports.
- [ ] Blocked hand classes are visually distinct from low-probability ones.
- [ ] `npx tsc --noEmit` and `npx vite build` both pass.
- [ ] Keyboard tab order reaches every control and never traps in the heatmap.

---

## 11. Reporting back

1. Interaction count to enter a full four-street hand, before and after.
2. A screenshot of the primary view at 1440×900, showing what is above the fold.
3. Anything in §1's principles you had to compromise on, and why.
4. Anything you found that was broken or dishonest and fixed outside the listed tasks.

If a task turns out to be wrong or infeasible, say so and finish the others. Do not
silently narrow scope.
