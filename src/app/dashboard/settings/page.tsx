"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardSettingsPage() {
  const { isLoaded, userId } = useAuth();
  const [githubUsername, setGithubUsername] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isLoaded || !userId) return;
    fetch("/api/user")
      .then((r) => r.json())
      .then((data) => {
        setGithubUsername(data.githubUsername || "");
        setEmail(data.email || "");
      });
  }, [isLoaded, userId]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    await fetch("/api/user", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ githubUsername }),
    });
    setSaving(false);
    setSaved(true);
  };

  return (
    <div>
      <h2 className="text-lg font-medium mb-6">Settings</h2>
      <div className="max-w-md space-y-6">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            disabled
            className="opacity-60"
          />
          <p className="text-xs text-muted-foreground">
            Managed by your sign-in provider
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="github">GitHub Username</Label>
          <Input
            id="github"
            placeholder="your-github-username"
            value={githubUsername}
            onChange={(e) => setGithubUsername(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Required for template repo access
          </p>
        </div>
        <Button
          size="sm"
          className="rounded-full"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving..." : saved ? "Saved" : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
