import { api, formatApiError } from "./api";

export function passkeysSupported() {
  return Boolean(window.isSecureContext && window.PublicKeyCredential && navigator.credentials?.create && navigator.credentials?.get);
}

export function decodeCredentialBytes(value) {
  const encoded = value.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")), (char) => char.charCodeAt(0));
}

export function encodeCredentialBytes(value) {
  return btoa(Array.from(new Uint8Array(value), (byte) => String.fromCharCode(byte)).join(""))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function credentialOptions(options, registration = false) {
  const publicKey = { ...options, challenge: decodeCredentialBytes(options.challenge) };
  for (const field of ["allowCredentials", "excludeCredentials"]) {
    if (options[field]) publicKey[field] = options[field].map((item) => ({ ...item, id: decodeCredentialBytes(item.id) }));
  }
  if (registration) publicKey.user = { ...options.user, id: decodeCredentialBytes(options.user.id) };
  return publicKey;
}

export function serializeCredential(credential) {
  if (!credential) throw new Error("Passkey-Vorgang wurde abgebrochen.");
  const response = { clientDataJSON: encodeCredentialBytes(credential.response.clientDataJSON) };
  for (const field of ["attestationObject", "authenticatorData", "signature", "userHandle"]) {
    const value = credential.response[field];
    if (value) response[field] = encodeCredentialBytes(value);
  }
  if (credential.response.getTransports) response.transports = credential.response.getTransports();
  return { id: credential.id, rawId: encodeCredentialBytes(credential.rawId), type: credential.type,
    response, clientExtensionResults: credential.getClientExtensionResults() };
}

export function passkeyError(error) {
  if (error?.name === "NotAllowedError" || error?.name === "AbortError") return "Passkey-Vorgang abgebrochen oder kein passender Passkey verfügbar.";
  if (error?.name === "InvalidStateError") return "Dieser Passkey ist bereits auf dem Gerät eingerichtet.";
  if (error?.name === "SecurityError") return "Bitte Passkeys direkt über die sichere Website-Adresse verwenden.";
  return error?.response?.data?.detail ? formatApiError(error.response.data.detail) : "Passkey-Vorgang fehlgeschlagen. Bitte erneut versuchen.";
}

export async function signInWithPasskey() {
  const { data: options } = await api.post("/auth/passkeys/login/options", {}, { skipInvalidation: true });
  const credential = await navigator.credentials.get({ publicKey: credentialOptions(options) });
  const { data } = await api.post("/auth/passkeys/login/verify", { credential: serializeCredential(credential) }, { skipInvalidation: true });
  return data;
}

export async function enrollPasskey(name, password) {
  const { data: options } = await api.post("/auth/passkeys/register/options", { name, current_password: password }, { skipInvalidation: true });
  const credential = await navigator.credentials.create({ publicKey: credentialOptions(options, true) });
  await api.post("/auth/passkeys/register/verify", { credential: serializeCredential(credential) }, { skipInvalidation: true });
}
