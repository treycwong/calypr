/** Error `code` values the API sends on a stream `error` event. Kept in one place so the
 * "Fix it" affordance and the server copy can't drift apart. */
export const PROVIDER_KEY_REJECTED = "provider_key_rejected";

/** Whether this error `code` is fixed by adding or replacing a key in Settings.
 *
 *  A `provider_key_required` code used to sit alongside this one, for a Video block with no BYO
 *  fal key. 3D and Video are credit-only now — they run on the platform key — so nothing emits
 *  it and the only key problem left is a provider rejecting one we hold. */
export const isKeyProblem = (code?: string) => code === PROVIDER_KEY_REJECTED;

/** Where a rejected provider key is fixed — the Workspace tab holds the LLM provider list. */
export const API_KEYS_HREF = "/dashboard/settings";
