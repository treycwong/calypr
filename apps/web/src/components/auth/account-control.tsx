import { SignOutButton } from "@/components/auth/sign-out-button";
import { Button } from "@/components/ui/button";
import { betterAuthEnabled } from "@/lib/auth";

/** The signed-in account control: Better Auth sign-out in production, a dev sign-out otherwise. */
export function AccountControl() {
  if (betterAuthEnabled()) {
    return <SignOutButton />;
  }
  return (
    <form method="post" action="/api/auth/signout">
      <Button type="submit" variant="outline" size="sm" data-testid="sign-out">
        Sign out
      </Button>
    </form>
  );
}
