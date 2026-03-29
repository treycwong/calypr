import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getDb } from "@/lib/db";
import { createIssue } from "@/lib/github";

const RATE_LIMIT_PER_DAY = 3;

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { templateId, subject, description } = body;
  if (!templateId || !subject || !description) {
    return NextResponse.json(
      { error: "templateId, subject, and description are required" },
      { status: 400 }
    );
  }

  const sql = getDb();

  const [user] = await sql`
    SELECT id FROM users WHERE clerk_id = ${userId}
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

  const today = new Date().toISOString().split("T")[0];
  const [{ count }] = await sql`
    SELECT COUNT(*)::int as count FROM support_tickets
    WHERE user_id = ${user.id} AND created_at::date = ${today}
  `;
  if (count >= RATE_LIMIT_PER_DAY) {
    return NextResponse.json(
      { error: "Rate limit exceeded (3 per day)" },
      { status: 429 }
    );
  }

  const clerkUser = await currentUser();
  const email = clerkUser?.emailAddresses?.[0]?.emailAddress || "unknown";
  const supportRepo = process.env.GITHUB_SUPPORT_REPO || "calypr-support";

  const issue = await createIssue(
    supportRepo,
    `[Support] ${subject}`,
    `**Template:** ${templateId}\n**User:** ${email}\n\n${description}`,
    ["support"]
  );

  await sql`
    INSERT INTO support_tickets (user_id, template_id, github_issue_number, subject, description)
    VALUES (${user.id}, ${templateId}, ${issue.number}, ${subject}, ${description})
  `;

  return NextResponse.json({ issueNumber: issue.number, issueUrl: issue.url });
}
