import { NextRequest, NextResponse } from "next/server";
import { headers } from "next/headers";
import { getStripe } from "@/lib/stripe";
import { getDb } from "@/lib/db";
import { addCollaborator, removeCollaborator } from "@/lib/github";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const headersList = await headers();
  const sig = headersList.get("stripe-signature");
  if (!sig) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  const stripe = getStripe();
  let event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const sql = getDb();

  const [existingEvent] = await sql`
    SELECT id FROM purchases WHERE stripe_event_id = ${event.id}
  `;
  if (existingEvent) {
    return NextResponse.json({ received: true });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const { clerkUserId, templateId, email } = session.metadata || {};
    if (!clerkUserId || !templateId) {
      return NextResponse.json(
        { error: "Missing metadata" },
        { status: 400 }
      );
    }

    const [user] = await sql`
      SELECT id, github_username FROM users WHERE clerk_id = ${clerkUserId}
    `;
    if (!user) {
      await sql`
        INSERT INTO users (clerk_id, email) VALUES (${clerkUserId}, ${email || "unknown"})
        ON CONFLICT (clerk_id) DO NOTHING
      `;
    }

    const userId = user?.id || (
      await sql`SELECT id FROM users WHERE clerk_id = ${clerkUserId}`
    )[0]?.id;

    const [template] = await sql`
      SELECT repo, price_cents FROM templates WHERE id = ${templateId}
    `;
    if (!template) {
      return NextResponse.json(
        { error: "Template not found" },
        { status: 400 }
      );
    }

    await sql`
      INSERT INTO purchases (user_id, template_id, stripe_session_id, stripe_event_id, amount_cents, status)
      VALUES (${userId}, ${templateId}, ${session.id}, ${event.id}, ${template.price_cents}, 'active')
    `;

    if (user?.github_username) {
      try {
        await addCollaborator(template.repo, user.github_username);
        await sql`
          UPDATE purchases SET github_repo_access = true
          WHERE stripe_session_id = ${session.id}
        `;
      } catch {
        await sql`
          INSERT INTO failed_operations (operation_type, reference_id, payload, error)
          VALUES ('add_collaborator', ${session.id}, ${JSON.stringify({
            repo: template.repo,
            username: user.github_username,
          })}, 'GitHub API failed')
        `;
      }
    }
  }

  if (event.type === "charge.refunded") {
    const charge = event.data.object;
    const sessionId = charge.payment_intent
      ? (
          await stripe.checkout.sessions.list({
            payment_intent: charge.payment_intent as string,
            limit: 1,
          })
        ).data[0]?.id
      : null;

    if (sessionId) {
      await sql`
        UPDATE purchases SET status = 'refunded', refunded_at = now()
        WHERE stripe_session_id = ${sessionId} AND status = 'active'
      `;

      const [purchase] = await sql`
        SELECT p.user_id, u.github_username, t.repo
        FROM purchases p
        JOIN users u ON p.user_id = u.id
        JOIN templates t ON p.template_id = t.id
        WHERE p.stripe_session_id = ${sessionId}
      `;

      if (purchase?.github_username) {
        try {
          await removeCollaborator(purchase.repo, purchase.github_username);
        } catch {
          await sql`
            INSERT INTO failed_operations (operation_type, reference_id, payload, error)
            VALUES ('remove_collaborator', ${sessionId}, ${JSON.stringify({
              repo: purchase.repo,
              username: purchase.github_username,
            })}, 'GitHub API failed on refund')
          `;
        }
      }
    }
  }

  return NextResponse.json({ received: true });
}
