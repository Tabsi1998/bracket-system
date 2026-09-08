import { credentialOptions, decodeCredentialBytes, encodeCredentialBytes, serializeCredential, passkeyError } from "./passkeys";

test("WebAuthn binary fields round-trip without base64 padding", () => {
  const bytes = Uint8Array.from([0, 127, 128, 254, 255]);
  const encoded = encodeCredentialBytes(bytes);
  expect(encoded).not.toMatch(/[+/=]/);
  expect(decodeCredentialBytes(encoded)).toEqual(bytes);
});

test("registration converts user, challenge and excluded keys without mutating server options", () => {
  const source = { challenge: "AAE", user: { id: "AgM", name: "User" }, excludeCredentials: [{ id: "BAU", type: "public-key" }] };
  const result = credentialOptions(source, true);
  expect(Array.from(result.challenge)).toEqual([0, 1]);
  expect(Array.from(result.user.id)).toEqual([2, 3]);
  expect(Array.from(result.excludeCredentials[0].id)).toEqual([4, 5]);
  expect(source.user.id).toBe("AgM");
});

test("authentication sends signature, client data and opaque user handle", () => {
  const result = serializeCredential({ id: "AAE", rawId: new Uint8Array([0, 1]), type: "public-key",
    response: { clientDataJSON: new Uint8Array([2]), authenticatorData: new Uint8Array([3]), signature: new Uint8Array([4]), userHandle: new Uint8Array([5]) },
    getClientExtensionResults: () => ({}),
  });
  expect(result.response).toEqual({ clientDataJSON: "Ag", authenticatorData: "Aw", signature: "BA", userHandle: "BQ" });
  expect(passkeyError({ name: "NotAllowedError" })).toContain("abgebrochen");
});
