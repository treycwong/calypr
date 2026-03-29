import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getDb } from "@/lib/db";

export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clerkUser = await currentUser();
  const email = clerkUser?.emailAddresses?.[0]?.emailAddress;

  const sql = getDb();

  const [user] = await sql`
    SELECT id, github_username FROM users WHERE clerk_id = ${userId}
  `;

  if (!user) {
    return NextResponse.json({
      purchases: [],
      supportTickets: [],
      githubUsername: null,
      email,
    });
  }

  const purchases = await sql`
    SELECT p.id, p.template_id, p.status, p.purchased_at, p.github_repo_access,
           t.name as template_name, t.repo, t.latest_version
    FROM purchases p
    JOIN templates t ON p.template_id = t.id
    WHERE p.user_id = ${user.id} AND p.status = 'active'
    ORDER BY p.purchased_at DESC
  `;

  const supportTickets = await sql`
    SELECT id, template_id, subject, status, created_at
    FROM support_tickets
    WHERE user_id = ${user.id}
    ORDER BY created_at DESC
    LIMIT 10
  `;

  return NextResponse.json({
    purchases,
    supportTickets,
    githubUsername: user.github_username,
    email,
  });
}

export async function PATCH(req: Request) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const sql = getDb();

  if (body.githubUsername) {
    await sql`
      UPDATE users SET github_username = ${body.githubUsername}
      WHERE clerk_id = ${userId}
    `;
  }

  return NextResponse.json({ success: true });
}
