import { UserButton } from "@clerk/nextjs";

import { Button } from "@/components/ui/button";
import { clerkEnabled } from "@/lib/auth";

/** The signed-in account menu: Clerk's UserButton in production, a dev sign-out otherwise. */
export function AccountControl() {
  if (clerkEnabled()) {
    return <UserButton />;
  }
  return (
    <form method="post" action="/api/auth/signout">
      <Button type="submit" variant="outline" size="sm" data-testid="sign-out">
        Sign out
      </Button>
    </form>
  );
}
