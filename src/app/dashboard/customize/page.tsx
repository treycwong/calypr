"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Purchase = {
  template_id: string;
  template_name: string;
};

export default function DashboardCustomizePage() {
  const { isLoaded, userId } = useAuth();
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isLoaded || !userId) return;
    fetch("/api/user")
      .then((r) => r.json())
      .then((data) => setPurchases(data.purchases || []));
  }, [isLoaded, userId]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const form = new FormData(e.currentTarget);
    const templateId = form.get("template") as string;
    const businessName = form.get("business") as string;
    const targetAudience = form.get("audience") as string;
    const brief = form.get("brief") as string;

    const res = await fetch("/api/customize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templateId, brief, businessName, targetAudience }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      setSubmitted(true);
    } else {
      const data = await res.json();
      setError(data.error || "Something went wrong");
    }
    setLoading(false);
  };

  if (submitted) {
    return (
      <div className="text-center py-16">
        <h2 className="text-lg font-medium mb-2">Brief submitted</h2>
        <p className="text-sm text-muted-foreground">
          We&apos;ll review your brief and open a GitHub Issue. You&apos;ll
          receive a PR with customizations.
        </p>
      </div>
    );
  }

  if (purchases.length === 0) {
    return (
      <div className="text-center py-16">
        <h2 className="text-lg font-medium mb-2">No purchased templates</h2>
        <p className="text-sm text-muted-foreground">
          Purchase a template first to request white-glove customization.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium mb-2">
        White-Glove Customization — $199
      </h2>
      <p className="text-sm text-muted-foreground mb-6">
        Fill out the brief below. Our team will customize your template and
        deliver a PR for your review.
      </p>
      <form className="max-w-md space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="template">Template</Label>
          <select
            id="template"
            name="template"
            required
            className="flex h-8 w-full rounded-md border border-input bg-background px-2.5 text-sm"
          >
            <option value="">Select template...</option>
            {purchases.map((p) => (
              <option key={p.template_id} value={p.template_id}>
                {p.template_name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="business">Business Name</Label>
          <Input id="business" name="business" placeholder="Your company or project" required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="audience">Target Audience</Label>
          <Input id="audience" name="audience" placeholder="Who is this site for?" required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief">Customization Brief</Label>
          <Textarea
            id="brief"
            name="brief"
            placeholder="Describe colors, content, sections to change..."
            rows={6}
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="sm" className="rounded-full" disabled={loading}>
          {loading ? "Submitting..." : "Submit Brief & Pay $199"}
        </Button>
      </form>
    </div>
  );
}
