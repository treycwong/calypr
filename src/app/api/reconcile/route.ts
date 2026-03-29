import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { addCollaborator } from "@/lib/github";

export async function GET() {
  const cronSecret = process.env.CRON_SECRET;
  if (!cronSecret) {
    return NextResponse.json(
      { error: "CRON_SECRET not configured" },
      { status: 500 }
    );
  }

  const sql = getDb();

  const orphans = await sql`
    SELECT p.id, p.stripe_session_id, p.user_id, t.repo, u.github_username, u.email, u.clerk_id
    FROM purchases p
    JOIN templates t ON p.template_id = t.id
    JOIN users u ON p.user_id = u.id
    WHERE p.github_repo_access = false AND p.status = 'active'
  `;

  const results = { checked: orphans.length, fixed: 0, errors: 0 };

  for (const purchase of orphans) {
    if (!purchase.github_username) continue;
    try {
      await addCollaborator(purchase.repo, purchase.github_username);
      await sql`
        UPDATE purchases SET github_repo_access = true WHERE id = ${purchase.id}
      `;
      results.fixed++;
    } catch {
      results.errors++;
    }
  }

  return NextResponse.json(results);
}
