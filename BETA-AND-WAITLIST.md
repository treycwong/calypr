# Beta & Waitlist — a founder's guide

**Last updated:** 2026-07-21 · Describes what shipped in PR #32.

This explains the two groups of people we track, what actually exists in the product today, and
the exact commands to collect emails and let someone into the beta.

---

## 1. The two groups (they are not the same thing)

| | **Waitlist** | **Beta** |
|---|---|---|
| **What it is** | An email address. That's it. | A real signed-up account with extra features switched on. |
| **Have they signed up?** | ❌ No — just interested | ✅ Yes — they have an account |
| **Where it lives** | `waitlist` table (a list of emails) | `plan` column on their workspace |
| **How they get there** | They type their email on `calypr.co/waitlist` | You add their email to the invite list |
| **What they can do** | Nothing yet — we just have their email | Everything free users get **plus** the beta features |

### How they connect: the invite list

There's one list, with a flag on it. A `waitlist` row is either:

- **just signed up** → they're interested, nothing more; or
- **invited** (`invited_at` is set) → **this is the beta allowlist**.

Being on the waitlist is *not* enough. You explicitly invite an address, and from then on:

```
1. Someone joins the waitlist     → we store their email
2. You invite their email         → one command (§6) — this is the allowlist
3. You email them (manual)        → "you're in, sign up at calypr.co"
4. They sign in with that email   → beta switches on AUTOMATICALLY ✨
```

**Step 4 needs nothing from you.** When someone signs in, we compare their verified email against
the invite list; if it matches, their workspace flips to `beta` on the spot. No looking up ids.

> **The one thing that can go wrong:** they sign in with a *different* email than you invited —
> e.g. you invited their work address but their GitHub uses a personal one. Then the match fails
> and they stay on `free`. They'll see a note in the Code tab saying which address they're signed
> in as, so they can tell you, and you invite that one too (§6). Both addresses can be on the list.

### Beta is purely additive

A beta user gets **everything a free user gets** (saving projects, the dashboard) **plus** the beta
feature. It never takes anything away.

---

## 2. How the website now guides people

| Where | Button | Goes to | Why |
|---|---|---|---|
| Homepage hero | **Try Beta** | `/waitlist` | The beta is invite-only, so the main CTA collects an email instead of dropping strangers into the app. |
| Header (top right) | **Sign in** | `/sign-in` | How *you* and your invited partners get back into the app. |
| Header (top right) | **Join Waitlist** | `/waitlist` | Same as the hero, always reachable. |
| Further down the page | "Open the canvas" | `/canvas` | The canvas itself is still free to try — beta only gates the extra features. |

### "If Try Beta goes to the waitlist, how do I log in to test the app?"

**You sign in normally — there's no special admin login page, and you don't need one.**

Go to **calypr.co/sign-in** and continue with GitHub. That page has always existed; the button
change only affects what the homepage *advertises*, not which pages work. It's now linked from the
header so you (and your beta partners) always have a visible way in.

Beta access isn't a different *login* — it's a flag on your workspace **after** you log in. So the
flow for you is: sign in once → run the command in §6 pointing at your own workspace → you now see
the beta features. A separate admin login would be redundant and just add another thing to secure.

---

## 3. What "beta" actually unlocks right now

Just one thing today: **the code editor round-trip** — the "Apply to canvas" button.

A beta user can open the Code tab, hand-edit the generated Python, and press *Apply to canvas* to
turn their edits back into visual nodes. Free users see the Code tab as read-only (they can still
view, copy, and download the code — that hasn't changed).

We put it behind beta because it's brand new, not because it's a premium feature. **The plan is to
make it free for everyone once it's proven** — it's the core "you own your code, there's no
ceiling" promise, and we open-source the parser behind it later anyway. We'll charge on capacity
(number of projects, credits, model access) instead — that's all laid out in `PRICING-SPEC.md`.

There are three tiers in the system: `free` (default), `beta`, and `plus`. `plus` exists so the
billing work later slots straight in; nothing charges money yet.

---

## 4. How we collect emails

```
Visitor types email on /waitlist
        ↓
Website sends it to our API
        ↓
Saved in the "waitlist" table in Postgres  ✅
```

Yes — **a Postgres table called `waitlist`**. Each row stores:

| Column | What it means |
|---|---|
| `email` | Their address, cleaned up (trimmed, lowercased) |
| `source` | Where they came from (currently always `"landing"`) |
| `created_at` | When they signed up |
| `invited_at` | When you invited them — empty until you do |

Three things worth knowing:

- **Duplicates are handled.** Submitting twice doesn't create a second row and doesn't show an
  error. Same email = one row.
- **Junk is rejected.** Pasting `Ada <ada@x.com>` or a comma-separated list gets a polite error
  rather than polluting the list.
- **The list can't be scraped.** The public form can only *write*. There's no public way to read
  the list back, so nobody can harvest our signups.

> **Heads up — this was broken before.** Until PR #32, the waitlist form looked like it worked
> (it showed "You're on the list") but **threw the email away**. Any signups collected before
> this ships are gone. Worth knowing if you were counting on early numbers.

---

## 5. Getting the emails out

### First: set your admin password

`CALYPR_ADMIN_TOKEN` isn't something you look up — **it doesn't exist until you create it.** It's a
password you invent, and the server checks against it.

**1. Generate one** (any long random string works):

```bash
openssl rand -hex 32
```

**2. Set it on the API** — Railway → your API service → **Variables** → add
`CALYPR_ADMIN_TOKEN` = the value you just generated. Redeploy.

**3. Save it in your password manager.** There's no way to recover it from the server, but you can
always set a new one.

> **Safety note:** if this variable is *not* set, the admin commands below return "not found".
> That's deliberate — an unset password can never accidentally mean "open to the whole internet".

### Then: export to a spreadsheet

```bash
CALYPR_API_URL=https://api.calypr.co \
CALYPR_ADMIN_TOKEN=your-token-here \
./scripts/waitlist-export.sh waitlist.csv
```

That writes `waitlist.csv`, which opens directly in Excel or Google Sheets:

```csv
email,source,signed_up_at,invited_at
ada@example.com,landing,2026-07-21T08:13:36Z,
grace@example.com,landing,2026-07-20T11:02:04Z,2026-07-21T09:00:00Z
```

An empty `invited_at` means you haven't invited them yet.

### Or just look at it in the terminal

```bash
curl https://api.calypr.co/admin/waitlist -H "x-admin-token: your-token-here"
```

---

## 6. Inviting someone into the beta

### Step 1 — add their email to the invite list

```bash
CALYPR_API_URL=https://api.calypr.co \
CALYPR_ADMIN_TOKEN=your-token-here \
./scripts/beta-invite.sh ada@example.com grace@example.com
```

Or feed it a file (one address per line):

```bash
CALYPR_ADMIN_TOKEN=xxx ./scripts/beta-invite.sh < invites.txt
```

It prints what changed:

```
  invited        ada@example.com
  already on it  grace@example.com

They get beta automatically the next time they sign in with that address.
```

Works whether or not they ever joined the waitlist — inviting an unknown address just adds it.
Re-running is safe.

**To invite yourself**, put your own email in — the same one your GitHub account uses.

### Step 2 — email them (manual for now)

We do **not** send emails automatically. Email people yourself, from your normal inbox, asking
them to sign up at calypr.co. For 10–25 design partners this is fine — and a personal note from
the founder converts better than an automated one anyway.

### Step 3 — nothing. It's automatic.

The next time they sign in with an invited address, their account flips to `beta` by itself.

### Removing someone

Un-inviting doesn't downgrade an account that's already been switched on (the grant is one-way on
purpose). To actually remove access, set them back to free:

```bash
curl -X POST https://api.calypr.co/admin/workspaces/THEIR_WORKSPACE_ID/plan \
  -H "x-admin-token: your-token-here" \
  -H "content-type: application/json" \
  -d '{"plan": "free"}'
```

Find the workspace ID by email:

```sql
SELECT w.id, w.name, w.plan
FROM workspace w
JOIN "user" u ON u.id = w.owner_user_id
WHERE lower(u.email) = lower('partner@example.com');
```

> Note: also remove them from the invite list (clear `invited_at`), or the next sign-in re-grants
> it: `UPDATE waitlist SET invited_at = NULL WHERE email = 'partner@example.com';`

---

## 7. What to watch once the beta is running

The whole reason for running this beta is one number: **when someone hits the limits of the visual
canvas and drops into the code, do they come back and keep building — or do they leave?**

Events in PostHog:

| Event | Meaning |
|---|---|
| `waitlist_joined` | Someone signed up for the waitlist |
| `parse_applied` | Someone edited code and successfully brought it back to the canvas 🎉 |
| `parse_degraded` | It worked, but we didn't fully understand part of their edit |
| `parse_failed` | We couldn't read their code at all |

`parse_applied` is the one that matters — it's the product's core promise actually happening.

This is why the feature had to go live to *someone*: while it was switched off for everyone, these
events never fired, so we had no way to know whether the idea works.

---

## 8. What is NOT built yet

Being straight about the rough edges:

- **No automatic invite emails.** The invite *list* is automatic; the actual email isn't. You
  write to people yourself.
- **No self-serve beta.** Joining the waitlist doesn't get you in; you choose who.
- **No admin screen.** Everything above is a command in a terminal. Deliberate — a UI isn't worth
  building for 25 people.
- **Email mismatches need a nudge.** If someone signs in with a different address than you
  invited, they stay on free until you invite that address too. The Code tab tells them which
  address they're signed in as, so it's self-diagnosing — but it isn't automatic.
- **Nothing charges money.** No Stripe, no credits, no upgrade prompts. That's the next block of
  work, already specced in `PRICING-SPEC.md`.

---

## 9. Quick reference

| I want to… | Do this |
|---|---|
| Set up admin access | `openssl rand -hex 32` → set as `CALYPR_ADMIN_TOKEN` in Railway |
| Export the waitlist to a spreadsheet | `./scripts/waitlist-export.sh waitlist.csv` (§5) |
| Give myself beta access | `./scripts/beta-invite.sh my-github-email@example.com`, then sign in |
| Let a partner into the beta | `./scripts/beta-invite.sh them@example.com` — automatic on their next sign-in |
| Log in to test the app | calypr.co/**sign-in** — normal GitHub login, no special page |
| Take someone out of the beta | Clear `invited_at`, then set their workspace to `free` (§6) |
| See who's been invited | `./scripts/waitlist-export.sh` — the `invited_at` column |
| Check if it's working | Look for `parse_applied` in PostHog |
| Turn the beta on for *everyone* | Change `has_roundtrip()` in `apps/api/src/calypr_api/entitlements.py` to always return true |

**Files, if you need to point an engineer at them:**
`apps/api/src/calypr_api/entitlements.py` (who gets what + the auto-grant),
`apps/api/src/calypr_api/routers/waitlist.py` (signup + admin commands),
`apps/api/migrations/versions/0008_plan_and_waitlist.py` (the database change),
`scripts/beta-invite.sh` (invites), `scripts/waitlist-export.sh` (the CSV export).
