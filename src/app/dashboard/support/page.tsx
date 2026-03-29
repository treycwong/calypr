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

export default function DashboardSupportPage() {
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
    const subject = form.get("subject") as string;
    const description = form.get("description") as string;

    const res = await fetch("/api/support", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templateId, subject, description }),
    });

    if (res.ok) {
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
        <h2 className="text-lg font-medium mb-2">Ticket submitted</h2>
        <p className="text-sm text-muted-foreground">
          We&apos;ll get back to you within 48 hours.
        </p>
      </div>
    );
  }

  if (purchases.length === 0) {
    return (
      <div className="text-center py-16">
        <h2 className="text-lg font-medium mb-2">No purchased templates</h2>
        <p className="text-sm text-muted-foreground">
          Purchase a template first to access support.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium mb-6">Support</h2>
      <p className="text-sm text-muted-foreground mb-6">
        Describe your issue. We&apos;ll respond within 48 hours.
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
          <Label htmlFor="subject">Subject</Label>
          <Input id="subject" name="subject" placeholder="Brief description" required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            name="description"
            placeholder="What happened? What did you expect?"
            rows={5}
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="sm" className="rounded-full" disabled={loading}>
          {loading ? "Submitting..." : "Submit Ticket"}
        </Button>
      </form>
    </div>
  );
}
