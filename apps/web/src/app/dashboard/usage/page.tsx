import type { Metadata } from "next";

import { UsageView } from "@/components/dashboard/usage-view";

export const metadata: Metadata = { title: "Usage — Calypr" };

export default function UsagePage() {
  return <UsageView />;
}
