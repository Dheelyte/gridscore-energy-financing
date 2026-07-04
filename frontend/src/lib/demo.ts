/** SHA-256 of the fixed seed used by the backend's demo borderline customer
 *  (SyntheticGenerator.demo_identity_hash). Lets the console jump straight to the
 *  reject→approve flip for the pitch. */
export async function demoIdentityHash(): Promise<string> {
  const data = new TextEncoder().encode("gridscore-demo-borderline-0001");
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
