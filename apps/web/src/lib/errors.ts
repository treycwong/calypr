/** Error `code` values the API sends on a stream `error` event. Kept in one place so the
 * "Fix it" affordance and the server copy can't drift apart. */
export const PROVIDER_KEY_REJECTED = "provider_key_rejected";

/** A block that runs only on the workspace's own key (Video) has no key on file. Distinct from
 *  a *rejected* key on the server — nothing was rejected, there is nothing there yet — but the
 *  fix is the same screen, so the UI treats them together. */
export const PROVIDER_KEY_REQUIRED = "provider_key_required";

/** Whether this error `code` is fixed by adding or replacing a key in Settings. */
export const isKeyProblem = (code?: string) =>
  code === PROVIDER_KEY_REJECTED || code === PROVIDER_KEY_REQUIRED;

/** Where a rejected provider key is fixed — the Workspace tab holds the LLM provider list. */
export const API_KEYS_HREF = "/dashboard/settings";
