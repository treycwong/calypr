import { NextRequest, NextResponse } from "next/server";
import { addCollaborator } from "@/lib/github";

export async function POST(req: NextRequest) {
  const adminKey = req.headers.get("x-admin-key");
  if (adminKey !== process.env.ADMIN_API_KEY) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { repo, username } = body;
  if (!repo || !username) {
    return NextResponse.json(
      { error: "repo and username required" },
      { status: 400 }
    );
  }

  try {
    await addCollaborator(repo, username);
    return NextResponse.json({ success: true });
  } catch (e) {
    return NextResponse.json(
      { error: (e as Error).message },
      { status: 500 }
    );
  }
}
