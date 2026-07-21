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
2. You email them an invite          → (manual, see §5)
3. They sign up on the site          → NOW they have an account + a workspace
4. You flip them to "beta"           → they see the beta features
```

You **cannot** skip to step 4 from step 1. Until they sign up in step 3, there's no account to
upgrade. This is normal for a closed beta, but it's the thing people usually get surprised by.

---

## 2. What "beta" actually unlocks right now

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

## 3. How we collect emails

### The flow

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

Two things worth knowing:

- **Duplicates are handled.** If someone submits twice, we don't create a second row and we don't
  show them an error. Same email = one row.
- **The list can't be scraped.** The public form can only *write*. There's no public way to read
  the list back, so nobody can harvest our signups.

> **Heads up — this was broken before.** Until PR #32, the waitlist form looked like it worked
> (it showed "You're on the list") but **threw the email away**. Any signups collected before
> this ships are gone. Worth knowing if you were counting on early numbers.

---

## 4. Reading the list of signups

You need an admin password (technically a token) set on the server as `CALYPR_ADMIN_TOKEN`.
Pick a long random string and set it in the API's environment variables (Railway).

**Important:** if that variable isn't set, the admin commands below simply don't exist — they
return "not found". That's on purpose, so an unset password can never mean "open to everyone".

### See everyone who signed up

```bash
curl https://api.calypr.co/admin/waitlist \
  -H "x-admin-token: YOUR_ADMIN_TOKEN"
```

You'll get back a list like:

```json
[
  { "email": "ada@example.com", "source": "landing",
    "created_at": "2026-07-21T10:00:00Z", "invited_at": null }
]
```

`"invited_at": null` means you haven't invited them yet.

---

## 5. Inviting someone into the beta

### Step 1 — email them (manual for now)

We do **not** send emails automatically. Export the list above and email them yourself, from
your normal inbox, asking them to sign up at calypr.co. For 10–25 design partners this is fine —
and a personal email from the founder converts better than an automated one anyway.

### Step 2 — after they've signed up, flip them to beta

Once they've created an account, you need their **workspace ID**. Find it by email:

```sql
SELECT w.id, w.name, w.plan
FROM workspace w
JOIN "user" u ON u.id = w.owner_user_id
WHERE lower(u.email) = lower('partner@example.com');
```

Then switch them on:

```bash
curl -X POST https://api.calypr.co/admin/workspaces/PASTE_WORKSPACE_ID_HERE/plan \
  -H "x-admin-token: YOUR_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{"plan": "beta", "email": "partner@example.com"}'
```

Including their `email` also stamps `invited_at` on their waitlist row, so your list stays
honest about who you've let in.

**To remove someone**, send the same command with `"plan": "free"`.

### If you'd rather just use SQL

```sql
UPDATE workspace SET plan = 'beta' WHERE id = 'the-workspace-uuid';
```

---

## 6. What to watch once the beta is running

The whole reason for running this beta is one number: **when someone hits the limits of the
visual canvas and drops into the code, do they come back and keep building — or do they leave?**

Three events show up in PostHog:

| Event | Meaning |
|---|---|
| `parse_applied` | Someone edited code and successfully brought it back to the canvas 🎉 |
| `parse_degraded` | It worked, but we didn't fully understand part of their edit |
| `parse_failed` | We couldn't read their code at all |

`parse_applied` is the one that matters — it's the product's core promise actually happening.
There's also `waitlist_joined` for signups.

This is why the feature had to go live to *someone*: while it was switched off for everyone,
these events never fired, so we had no way to know whether the idea works.

---

## 7. What is NOT built yet

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

## 8. Quick reference

| I want to… | Do this |
|---|---|
| See who joined the waitlist | `GET /admin/waitlist` with the admin token |
| Let someone into the beta | Find their workspace ID (§5), then `POST /admin/workspaces/{id}/plan` with `"plan":"beta"` |
| Take someone out of the beta | Same command with `"plan":"free"` |
| Check if it's working | Look for `parse_applied` in PostHog |
| Turn the beta on for *everyone* | Change `has_roundtrip()` in `apps/api/src/calypr_api/entitlements.py` to always return true |

**Files, if you need to point an engineer at them:**
`apps/api/src/calypr_api/entitlements.py` (who gets what),
`apps/api/src/calypr_api/routers/waitlist.py` (signup + admin commands),
`apps/api/migrations/versions/0008_plan_and_waitlist.py` (the database change).
