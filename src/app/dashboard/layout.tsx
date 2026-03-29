import { DashboardNav } from "@/components/dashboard-nav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-2xl font-medium tracking-tight mb-6">Dashboard</h1>
      <DashboardNav />
      <div className="mt-8">{children}</div>
    </div>
  );
}
