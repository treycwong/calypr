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
| **How they get there** | They type their email on `calypr.co/waitlist` | You flip a switch for them |
| **What they can do** | Nothing yet — we just have their email | Everything free users get **plus** the beta features |

### The most important thing to understand

**These two are not automatically connected.** A waitlist email is *not* an account. There is no
"user" behind it yet — no workspace, no projects, nothing to switch on.

So the order of operations is:

```
1. Someone joins the waitlist        → we store their email
2. You email them an invite          → (manual, see §6)
3. They sign up on the site          → NOW they have an account + a workspace
4. You flip them to "beta"           → they see the beta features
```

You **cannot** skip to step 4 from step 1. Until they sign up in step 3, there's no account to
upgrade. This is normal for a closed beta, but it's the thing people usually get surprised by.

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

### Step 1 — email them (manual for now)

We do **not** send emails automatically. Export the CSV above and email people yourself, from your
normal inbox, asking them to sign up at calypr.co. For 10–25 design partners this is fine — and a
personal note from the founder converts better than an automated one anyway.

### Step 2 — after they've signed up, flip them to beta

Once they've created an account, find their **workspace ID** by email:

```sql
SELECT w.id, w.name, w.plan
FROM workspace w
JOIN "user" u ON u.id = w.owner_user_id
WHERE lower(u.email) = lower('partner@example.com');
```

Then switch them on:

```bash
curl -X POST https://api.calypr.co/admin/workspaces/PASTE_WORKSPACE_ID_HERE/plan \
  -H "x-admin-token: your-token-here" \
  -H "content-type: application/json" \
  -d '{"plan": "beta", "email": "partner@example.com"}'
```

Including their `email` also stamps `invited_at` on their waitlist row, so your list stays honest
about who you've let in.

**To remove someone**, send the same command with `"plan": "free"`.

**To switch yourself on**, do exactly the same thing with your own workspace ID.

### If you'd rather just use SQL

```sql
UPDATE workspace SET plan = 'beta' WHERE id = 'the-workspace-uuid';
```

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

- **No automatic invite emails.** You email people yourself.
- **No self-serve beta.** Joining the waitlist doesn't get you in; you choose who.
- **No admin screen.** Everything above is a command in a terminal. Deliberate — a UI isn't worth
  building for 25 people.
- **Waitlist emails and accounts aren't linked automatically.** If someone signs up with a
  *different* email than they joined the waitlist with, nothing connects them. You'd match by hand.
- **Nothing charges money.** No Stripe, no credits, no upgrade prompts. That's the next block of
  work, already specced in `PRICING-SPEC.md`.

---

## 9. Quick reference

| I want to… | Do this |
|---|---|
| Set up admin access | `openssl rand -hex 32` → set as `CALYPR_ADMIN_TOKEN` in Railway |
| Export the waitlist to a spreadsheet | `./scripts/waitlist-export.sh waitlist.csv` (see §5) |
| Log in to test the app | calypr.co/**sign-in** — normal GitHub login, no special page |
| Give myself beta access | Find your workspace ID (§6), then the `POST .../plan` command |
| Let a partner into the beta | Same command with their workspace ID |
| Take someone out of the beta | Same command with `"plan":"free"` |
| Check if it's working | Look for `parse_applied` in PostHog |
| Turn the beta on for *everyone* | Change `has_roundtrip()` in `apps/api/src/calypr_api/entitlements.py` to always return true |

**Files, if you need to point an engineer at them:**
`apps/api/src/calypr_api/entitlements.py` (who gets what),
`apps/api/src/calypr_api/routers/waitlist.py` (signup + admin commands),
`apps/api/migrations/versions/0008_plan_and_waitlist.py` (the database change),
`scripts/waitlist-export.sh` (the CSV export).
