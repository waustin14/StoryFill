# StoryFill Testing Findings

Findings from end-to-end browser testing of the multiplayer and solo flows. Each item includes the root cause, affected files, and what the fix should accomplish.

---

## Critical Bugs

### 1. ~~WebSocket connection immediately closes in a loop~~ FIXED

**Severity:** Critical — all real-time features are broken.

**Status:** Fixed. Wrapped `pubsub.get_message` in a lambda in `api/app/routes/ws.py` so kwargs are forwarded correctly. Verified via browser testing: lobby shows "Live" status, no reconnect loop, real-time player list updates work.

**Symptom:** The lobby, waiting, and reveal pages all show a persistent "Connection lost. Reconnecting..." banner. The API logs show a rapid cycle of `connection open` / `connection closed` entries. Players never receive state transition events (game start, story reveal, etc.) and get stuck on stale pages.

**Root cause:** In `api/app/routes/ws.py` lines 108-112, keyword arguments are passed to `anyio.to_thread.run_sync()`, which does not forward kwargs to the target function:

```python
# BROKEN — run_sync does not accept kwargs for the target callable
msg = await anyio.to_thread.run_sync(
    pubsub.get_message,
    ignore_subscribe_messages=True,
    timeout=1.0,
)
```

This raises a `TypeError` on every iteration, which is silently caught by the broad `except Exception` at line 130, causing the task group to exit and the WebSocket to close. The client reconnects and hits the same error in a tight loop.

**Fix:** Wrap the call so the kwargs reach `pubsub.get_message`:

```python
msg = await anyio.to_thread.run_sync(
    lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
)
```

**Files:** `api/app/routes/ws.py`

---

### 2. ~~Players get stuck and never transition between game phases~~ FIXED

**Severity:** Critical — direct consequence of bug #1.

**Status:** Fixed by bug #1 fix. Verified via browser testing: host clicking "Start game" triggers automatic page transition to the prompting screen.

**Symptom:** When the host starts the game, player browsers remain on the template selection / lobby page. When the host reveals the story, players remain on the waiting page showing "Waiting for host." Players must manually navigate to the correct URL to continue.

**Root cause:** The frontend relies on WebSocket `room.snapshot` events to detect state changes and call `router.push()` to the next page. Because the WebSocket is broken (bug #1), these events never arrive.

**Fix:** Fixing bug #1 resolves this. As a defense-in-depth measure, consider adding HTTP polling as a fallback so players can recover even if the WebSocket drops temporarily.

**Files:** `api/app/routes/ws.py` (primary), `web/src/app/lobby/lobby-client.tsx`, `web/src/app/waiting/waiting-client.tsx`

---

## Data Bugs

### 3. ~~Duplicate template: "Turbulence and Snacks"~~ FIXED

**Severity:** Medium

**Status:** Fixed. Migration `0002_template_description_and_cleanup` deletes the stale `t-unexpected-plane-vacation-mini` row and adds a unique constraint on `templates.title` to prevent recurrence.

**Symptom:** The template selection list shows "Turbulence and Snacks" twice, each selectable independently.

**Root cause:** Two database rows exist with the same title but different IDs:

| id | title |
|----|-------|
| `t-unexpected-plane-vacation-mini` | Turbulence and Snacks |
| `t-turbulence-and-snacks` | Turbulence and Snacks |

The older row (`t-unexpected-plane-vacation-mini`) was likely renamed but never removed.

**Fix:** Delete the stale `t-unexpected-plane-vacation-mini` row from the `templates` table, and add a unique constraint on `title` (or at minimum on `id`) to prevent recurrence. If this template was seeded by a migration, update the migration or seed script to remove it.

**Files:** Database migration or seed script under `api/alembic/versions/`

---

### 4. ~~All templates share identical generic descriptions~~ FIXED

**Severity:** Low — cosmetic but hurts usability.

**Status:** Fixed. Added a `description` field to every template definition in `api/app/data/templates.py`, a `description` column to the DB model, and updated the frontend to render `template.description` instead of the hardcoded string.

**Symptom:** Every template card displays the same text: "Curated story framework with fresh prompts and a ready-to-reveal ending." Users cannot tell templates apart by description.

**Fix:** Add a unique `description` or `tagline` field to each template in the database/seed data, and display it in the frontend template cards. The genre and content_rating tags already differ, but a one-sentence description per template would make selection much more meaningful.

**Files:** `api/app/data/templates.py` (seed data), template DB migration if the column doesn't exist, `web/src/app/` template selection components

---

## UX Issues

### 5. Internal round ID exposed to users on the reveal page

**Severity:** Low

**Symptom:** The reveal page displays `Round: round_u9h03-b2F_w` — a raw internal identifier that is meaningless to players.

**Fix:** Either hide the round ID entirely or display a friendly label like "Round 1" using the `round_index` field from the room state.

**Files:** `web/src/app/reveal/reveal-client.tsx`

---

### 6. Room codes use ambiguous characters (O/0, I/1)

**Severity:** Low — causes confusion when sharing codes verbally.

**Symptom:** Room codes like `S0TJE0` contain both the digit `0` and the letter `O`, which are easily confused when read aloud or typed.

**Root cause:** `api/app/data/rooms.py` line 406 generates codes from `token_urlsafe(8)` uppercased and truncated to 6 characters. The base64url alphabet includes both `O` and `0`, `I` and `1`, etc.

**Fix:** Generate codes from a restricted alphabet that excludes ambiguous characters. For example, use only `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (no I, O, 0, 1).

**Files:** `api/app/data/rooms.py`

---

### 7. Host is shown as "Player 1" with no visual distinction

**Severity:** Low

**Symptom:** In the lobby player list, the host appears as "Player 1" with the same styling as other players. There is no badge, icon, or label indicating which player is the host.

**Fix:** Add a "Host" badge or indicator next to the host's name in the player list. The room state already tracks which token is the host token, so this is a frontend-only change.

**Files:** `web/src/app/lobby/lobby-client.tsx`

---

## Code Quality

### 8. Broad `except Exception: pass` throughout WebSocket handler

**Severity:** Medium — this masked the critical WebSocket bug (item #1).

**Location:** `api/app/routes/ws.py` lines 69-70, 93-94, 130-131, 136-137

**Problem:** Four separate bare `except Exception` blocks silently swallow all errors, including the `TypeError` that causes the WebSocket loop. This makes debugging extremely difficult.

**Fix:** At minimum, add `logger.exception(...)` calls in each handler. For the task group exception handler (line 130), consider catching only `WebSocketDisconnect` or `anyio.get_cancelled_exc_class()` and letting unexpected errors propagate or be logged.

**Files:** `api/app/routes/ws.py`

---

### 9. `env()` helper treats empty string as missing

**Severity:** Low

**Location:** `api/app/core/config.py` line 6

**Problem:** The helper uses `return value if value else default`, which means setting an environment variable to an empty string (e.g., `WEB_ORIGINS=""`) falls back to the default value instead of honoring the empty string.

**Fix:** Change to `return value if value is not None else default`.

**Files:** `api/app/core/config.py`

---

### 10. `wsBaseUrl()` function duplicated across three files

**Severity:** Low

**Problem:** The identical WebSocket URL builder function is copy-pasted in:
- `web/src/app/lobby/lobby-client.tsx`
- `web/src/app/waiting/waiting-client.tsx`
- `web/src/app/reveal/reveal-client.tsx`

Each also duplicates the `API_BASE_URL` constant.

**Fix:** Extract `wsBaseUrl()` and `API_BASE_URL` into a shared utility file (e.g., `web/src/lib/api.ts`) and import from there.

**Files:** `web/src/lib/api.ts` (new), `web/src/app/lobby/lobby-client.tsx`, `web/src/app/waiting/waiting-client.tsx`, `web/src/app/reveal/reveal-client.tsx`

---

## UI Spec Compliance

The following deviations were found by comparing the live frontend against the UI/UX Spec (`artifacts/ui-design/UI_UX_Spec.md`), branding guide (`artifacts/ui-design/branding.md`), and component cookbook (`artifacts/ui-design/components.md`).

### What the frontend gets right

- Theme tokens (light and dark) match the Parchment Pop values from the branding guide exactly.
- Skip-to-content link is present and visible on Tab.
- Visible focus rings on all interactive elements (`focus-visible` styling).
- `prefers-reduced-motion: reduce` is respected via a global CSS rule.
- Story canvas uses the specified styling: `text-xl md:text-2xl`, `leading-relaxed`, `max-w-[70ch]`, with `role="region"` and `aria-label="Completed story"`.
- Error states use `role="alert"` for screen reader announcements.
- `accent` color token is correctly reserved and not used as general UI chrome.
- Dark mode is implemented and toggleable.
- Typography follows the Inter / sans-serif stack guidance.
- Card-based layout keeps screens clean and low-noise.

---

### 11. Prompts are shown all-at-once instead of one-at-a-time

**Spec reference:** Section 6.5 — Prompt Input Screen

> Elements: Prompt label (e.g., "Noun", "Sound") / **Single input field** / Submit button
> Behavior: **One prompt at a time**

**Symptom:** All 3 assigned prompts are displayed simultaneously in a grid layout. The spec calls for a single-input, one-at-a-time flow to minimize cognitive load and support the "no reading required" principle.

**Fix:** Refactor the prompting screen to show one prompt at a time with a next/submit button, advancing through each prompt sequentially. Consider a progress indicator (e.g., "Prompt 2 of 3") to orient the user.

**Files:** `web/src/app/prompting/prompting-client.tsx`

---

### 12. Lobby is missing a shareable room link / copy button

**Spec reference:** Section 6.3 — Room Lobby (Host)

> Elements: **Shareable room link** / Player list / Start Game button
> Accessibility: **Copy link accessible via keyboard**

**Symptom:** The lobby only shows the raw room code in a chip. There is no shareable URL, no copy-to-clipboard button, and no invite link. The spec requires a shareable room link as a primary lobby element with keyboard-accessible copy functionality.

**Fix:** Add a "Copy invite link" or "Copy room code" button next to the room code chip. Construct a join URL (e.g., `{WEB_BASE_URL}/room?code={ROOM_CODE}`) and copy it to the clipboard. Show a toast confirmation ("Link copied") per the component cookbook.

**Files:** `web/src/app/lobby/lobby-client.tsx`

---

### 13. Error states use color alone — no icons

**Spec reference:** Branding guide section 8 / Components section 0

> Error states always include **icon + text**, not color alone.
> Error state = color + icon + text

**Symptom:** Every error alert across the app (prompting, lobby, waiting, reveal, template selection) uses a red/rose-colored `div` with text but **no icon**. The `AlertTriangle` icon from Lucide (specified in the approved icon mapping) is never imported or used anywhere in the app.

**Fix:** Add an `AlertTriangle` (or equivalent) icon to all error alert components. The component cookbook provides the exact pattern:

```tsx
<Alert variant="destructive">
  <AlertTriangle className="h-4 w-4" />
  <AlertTitle>Error title</AlertTitle>
  <AlertDescription>Error message here.</AlertDescription>
</Alert>
```

**Files:** All files containing `role="alert"`: `prompting-client.tsx`, `lobby-client.tsx`, `waiting-client.tsx`, `reveal-client.tsx`, `room-lobby-client.tsx`, `template-select-client.tsx`, `mode-select-client.tsx`

---

### 14. Buttons lack icons specified in the branding guide

**Spec reference:** Branding guide section 5 / Components section 1

> Label first, icon second (icons support comprehension, not decoration)
> Approved icon mapping: Start: `Play`, Reveal: `Sparkles` or `BookOpen`, Share: `Share2`, Copy: `Copy`

**Symptom:** Action buttons ("Start game", "Reveal Story", "Submit Prompts", "Create share link") are text-only with no supporting icons. The branding guide specifies that primary action buttons should include an icon to aid comprehension, particularly to support the "no reading required" UX principle.

**Fix:** Add the mapped Lucide icons to primary action buttons:
- "Start game" -> `Play` icon
- "Reveal Story" -> `Sparkles` icon
- "Share" -> `Share2` icon
- "Generate narration" -> `Volume2` icon

**Files:** `web/src/app/lobby/lobby-client.tsx`, `web/src/app/reveal/reveal-client.tsx`, `web/src/app/waiting/waiting-client.tsx`

---

### 15. Player lobby (non-host) does not match spec layout

**Spec reference:** Section 6.4 — Room Lobby (Player)

> Elements: "Waiting for host" message / **Player list** / **Visual progress indicator**
> Behavior: No controls other than exit

**Symptom:** When a player joins a room, they are shown the template selection page with all templates visible (greyed out) and a message "You joined as a player. The host will confirm the template selection." The spec says non-host players should see a simple lobby with a "Waiting for host" message, the player list, and a progress indicator — not the full template grid.

**Fix:** Route non-host players directly to a dedicated waiting/lobby view instead of showing them the template selection screen. The lobby view should show the player list, a "Waiting for host to start" message, and a visual indicator.

**Files:** `web/src/app/templates/template-select-client.tsx`, `web/src/app/lobby/lobby-client.tsx`

---

### 16. Destructive actions (Kick player) lack confirmation dialogs

**Spec reference:** Components cookbook section 6

> Use dialogs for: "Kick player?" (host) / Always confirm destructive actions.

**Symptom:** The "Kick" buttons on the waiting page fire immediately with no confirmation dialog. The component cookbook explicitly requires a confirmation dialog for destructive host actions.

**Fix:** Wrap the kick action in a `Dialog` component with a confirmation prompt ("Remove this player?" / Cancel / Remove).

**Files:** `web/src/app/waiting/waiting-client.tsx`
