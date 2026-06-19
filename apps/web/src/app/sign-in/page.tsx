import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Props = { searchParams: Promise<{ next?: string }> };

export default async function SignInPage({ searchParams }: Props) {
  const { next } = await searchParams;
  const action = `/api/auth/dev${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <main className="flex min-h-full flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to Calypr</CardTitle>
          <CardDescription>
            Development sign-in. Clerk (org = tenant) wires in here later.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form method="post" action={action}>
            <Button type="submit" className="w-full" data-testid="dev-sign-in">
              Continue (dev)
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
