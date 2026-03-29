import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getStripe } from "@/lib/stripe";
import { getDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { templateId } = body;
  if (!templateId) {
    return NextResponse.json(
      { error: "templateId is required" },
      { status: 400 }
    );
  }

  const sql = getDb();
  const user = await currentUser();
  if (!user?.emailAddresses?.[0]?.emailAddress) {
    return NextResponse.json({ error: "No email on file" }, { status: 400 });
  }

  const email = user.emailAddresses[0].emailAddress;

  const [existingUser] = await sql`
    SELECT id FROM users WHERE clerk_id = ${userId}
  `;
  if (!existingUser) {
    await sql`
      INSERT INTO users (clerk_id, email) VALUES (${userId}, ${email})
    `;
  }

  const [template] = await sql`
    SELECT id, name, repo, price_cents, stripe_price_id FROM templates WHERE id = ${templateId}
  `;
  if (!template) {
    return NextResponse.json(
      { error: "Template not found" },
      { status: 404 }
    );
  }

  const [existingPurchase] = await sql`
    SELECT id FROM purchases
    WHERE user_id = (SELECT id FROM users WHERE clerk_id = ${userId})
    AND template_id = ${templateId}
    AND status = 'active'
  `;
  if (existingPurchase) {
    return NextResponse.json(
      { error: "Already purchased" },
      { status: 409 }
    );
  }

  const stripe = getStripe();
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    line_items: [
      {
        price: template.stripe_price_id,
        quantity: 1,
      },
    ],
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard/templates?purchased=${templateId}`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/templates/${templateId}`,
    metadata: {
      clerkUserId: userId,
      templateId,
      email,
    },
  });

  return NextResponse.json({ url: session.url });
}
