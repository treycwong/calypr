import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getStripe } from "@/lib/stripe";
import { getDb } from "@/lib/db";
import { createIssue } from "@/lib/github";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { templateId, brief, businessName, targetAudience } = body;
  if (!templateId || !brief) {
    return NextResponse.json(
      { error: "templateId and brief are required" },
      { status: 400 }
    );
  }

  const sql = getDb();

  const [user] = await sql`
    SELECT id, github_username FROM users WHERE clerk_id = ${userId}
  `;
  if (!user) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  const [purchase] = await sql`
    SELECT id FROM purchases
    WHERE user_id = ${user.id} AND template_id = ${templateId} AND status = 'active'
  `;
  if (!purchase) {
    return NextResponse.json(
      { error: "Template not purchased" },
      { status: 403 }
    );
  }

  const clerkUser = await currentUser();
  const email = clerkUser?.emailAddresses?.[0]?.emailAddress || "unknown";
  const supportRepo = process.env.GITHUB_SUPPORT_REPO || "calypr-support";

  const issue = await createIssue(
    supportRepo,
    `[White-Glove] Customization for ${businessName || templateId}`,
    `**Template:** ${templateId}\n**Business:** ${businessName || "N/A"}\n**Audience:** ${targetAudience || "N/A"}\n**User:** ${email}\n\n${brief}`,
    ["white-glove"]
  );

  await sql`
    INSERT INTO customization_requests (user_id, template_id, github_issue_number, brief, business_name, target_audience, status)
    VALUES (${user.id}, ${templateId}, ${issue.number}, ${brief}, ${businessName}, ${targetAudience}, 'pending')
  `;

  const stripe = getStripe();
  const customizePriceId = process.env.NEXT_PUBLIC_STRIPE_PRICE_CUSTOMIZE;
  if (!customizePriceId) {
    return NextResponse.json({ issueUrl: issue.url });
  }

  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    line_items: [{ price: customizePriceId, quantity: 1 }],
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard/customize?confirmed=true`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard/customize`,
    metadata: {
      clerkUserId: userId,
      templateId,
      issueNumber: String(issue.number),
      type: "customization",
    },
  });

  await sql`
    UPDATE customization_requests SET stripe_session_id = ${session.id} WHERE github_issue_number = ${issue.number}
  `;

  return NextResponse.json({ url: session.url, issueUrl: issue.url });
}
