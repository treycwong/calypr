// Server-side PostHog capture for the few events only the server sees — today, a new account.
//
// One `fetch` to PostHog's public capture endpoint rather than `posthog-node`: it is one event per
// sign-up, and the project key is already public (it ships to every browser as
// NEXT_PUBLIC_POSTHOG_KEY). Never throws and never blocks for long: analytics must not be able to
// fail a sign-in.

const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";

export async function captureServer(
  event: string,
  distinctId: string,
  properties: Record<string, unknown> = {},
): Promise<void> {
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return;
  try {
    await fetch(`${HOST}/capture/`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ api_key: key, event, distinct_id: distinctId, properties }),
      signal: AbortSignal.timeout(2000),
    });
  } catch {
    // Dropped event, not a failed sign-up.
  }
}
