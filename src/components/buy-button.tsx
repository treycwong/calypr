"use client";

import { useState } from "react";
import { useAuth, SignInButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

type BuyButtonProps = {
  templateId: string;
  disabled?: boolean;
};

export function BuyButton({ templateId, disabled }: BuyButtonProps) {
  const { isSignedIn } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleBuy = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ templateId }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <Button size="lg" className="w-full rounded-full h-11" disabled={disabled}>
          Buy Template
        </Button>
      </SignInButton>
    );
  }

  return (
    <Button
      size="lg"
      className="w-full rounded-full h-11"
      disabled={disabled || loading}
      onClick={handleBuy}
    >
      {loading ? "Redirecting..." : "Buy Template"}
    </Button>
  );
}
