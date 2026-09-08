import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/tls/Logo";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useSubmissionGuard } from "@/hooks/useSubmissionGuard";
import { AuthFormAlert, AuthPasswordField, AuthTextField } from "@/components/tls/AuthFormFields";
import { GoogleAuthButton } from "@/components/tls/GoogleAuthButton";
import { usePublicSiteSettings } from "@/hooks/usePublicSiteSettings";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { passkeyError, passkeysSupported, signInWithPasskey } from "@/lib/passkeys";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  useDocumentTitle("Login", "Login für Mitglieder und Community-User von THE LION SQUAD eSports.", { robots: "noindex, follow" });

  const { login, completeMfa, setUser } = useAuth();
  const settings = usePublicSiteSettings();
  const [params] = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaTicket, setMfaTicket] = useState(() => sessionStorage.getItem("tls.mfa.ticket") || "");
  const [showPw, setShowPw] = useState(false);
  const { submitting: loading, submitOnce } = useSubmissionGuard();
  const [err, setErr] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [passkeysEnabled, setPasskeysEnabled] = useState(false);
  useEffect(() => {
    if (passkeysSupported()) api.get("/auth/passkeys/status").then(({ data }) => setPasskeysEnabled(data.enabled === true)).catch(() => {});
  }, []);

  const passkeyLogin = async () => {
    setErr(null);
    const attempt = await submitOnce(signInWithPasskey);
    if (!attempt.started) return;
    if (attempt.error) { setErr(passkeyError(attempt.error)); return; }
    const data = attempt.value;
    if (data.mfa_required) {
      setMfaTicket(data.mfa_ticket);
      sessionStorage.setItem("tls.mfa.ticket", data.mfa_ticket);
    } else {
      setUser(data);
      toast.success("Willkommen zurück!");
      nav(next);
    }
  };

  const setField = (field, setter) => (value) => {
    setter(value);
    setErr(null);
    setVerificationRequired(false);
    setFieldErrors((current) => ({ ...current, [field]: null }));
  };

  const validate = () => {
    const errors = {};
    if (!email.trim()) errors["login-email"] = "Bitte gib deine E-Mail-Adresse ein.";
    else if (!EMAIL_RE.test(email.trim())) errors["login-email"] = "Bitte gib eine gültige E-Mail-Adresse ein.";
    if (!pw) errors["login-password"] = "Bitte gib dein Passwort ein.";

    setFieldErrors(errors);
    const firstError = ["login-email", "login-password"].find((id) => errors[id]);
    if (firstError) document.getElementById(firstError)?.focus();
    return Object.keys(errors).length === 0;
  };

  const submit = async (event) => {
    event.preventDefault();
    if (mfaTicket) {
      if (!mfaCode.trim()) {
        setErr("Bitte gib den sechsstelligen MFA- oder einen Wiederherstellungscode ein.");
        return;
      }
      const attempt = await submitOnce(() => completeMfa(mfaTicket, mfaCode.trim()));
      if (!attempt.started) return;
      const result = attempt.value;
      if (result?.ok) {
        sessionStorage.removeItem("tls.mfa.ticket");
        toast.success("Admin-Anmeldung bestätigt.");
        nav(next);
      } else {
        setErr(result?.error || "MFA-Anmeldung fehlgeschlagen.");
      }
      return;
    }
    if (!validate()) return;

    setErr(null);
    const attempt = await submitOnce(() => login(email.trim(), pw));
    if (!attempt.started) return;
    if (attempt.error) {
      setErr("Login konnte nicht abgeschlossen werden. Bitte versuche es erneut.");
      return;
    }
    const res = attempt.value;

    if (res.ok) {
      if (res.mfaRequired) {
        setMfaTicket(res.ticket);
        sessionStorage.setItem("tls.mfa.ticket", res.ticket);
        setErr(null);
        return;
      }
      toast.success("Willkommen zurück!");
      nav(next);
    } else {
      setErr(res.error);
      setVerificationRequired(!!res.verificationRequired);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex items-center justify-center p-6 bg-grid">
      <div className="w-full max-w-md border border-white/10 rounded-sm bg-[#121212] p-8 md:p-10">
        <div className="flex justify-center mb-8"><Logo size="xl" /></div>
        <h1 className="font-heading text-2xl font-black uppercase text-center">Login</h1>
        <p className="text-sm text-white/60 text-center mt-1">{mfaTicket ? "Bestätige deine Admin-Anmeldung." : "Willkommen bei THE LION SQUAD."}</p>

        {mfaTicket ? (
          <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
            <AuthTextField
              id="login-mfa-code"
              label="MFA- oder Wiederherstellungscode"
              value={mfaCode}
              onChange={(value) => { setMfaCode(value); setErr(null); }}
              autoComplete="one-time-code"
              inputMode="text"
              required
              testId="login-mfa-code"
            />
            {err && <AuthFormAlert id="login-error">{err}</AuthFormAlert>}
            <button disabled={loading} type="submit" className="w-full py-3 bg-[#29B6E8] text-black font-bold uppercase tracking-wider rounded-sm disabled:opacity-50" data-testid="login-mfa-submit">
              {loading ? "Prüfe …" : "Anmeldung bestätigen"}
            </button>
            <button type="button" disabled={loading} onClick={() => { setMfaTicket(""); setMfaCode(""); setErr(null); sessionStorage.removeItem("tls.mfa.ticket"); }} className="w-full text-xs text-white/45 hover:text-white">Zurück zum Login</button>
          </form>
        ) : settings.password_login_enabled !== false ? <form onSubmit={submit} className="mt-8 space-y-4" noValidate aria-describedby={err ? "login-error" : undefined}>
          <AuthTextField
            id="login-email"
            label="E-Mail"
            type="email"
            value={email}
            onChange={setField("login-email", setEmail)}
            required
            autoComplete="email"
            error={fieldErrors["login-email"]}
            testId="login-email"
          />
          <AuthPasswordField
            id="login-password"
            label="Passwort"
            value={pw}
            onChange={setField("login-password", setPw)}
            show={showPw}
            onToggle={() => setShowPw((value) => !value)}
            required
            autoComplete="current-password"
            error={fieldErrors["login-password"]}
            testId="login-password"
          />
          {err && <AuthFormAlert id="login-error">{err}</AuthFormAlert>}
          {verificationRequired && (
            <div className="space-y-2 text-sm" data-testid="login-verification-recovery">
              <p className="text-white/70">Dein Konto bleibt bestehen. Bestätige zuerst deine E-Mail-Adresse; danach meldest du dich mit deinem bisherigen Passwort und gegebenenfalls MFA an.</p>
              <Link to="/verify-email" state={{ email: email.trim() }} className="inline-block py-2 text-[#29B6E8] underline">Bestätigungslink anfordern</Link>
            </div>
          )}
          <button
            data-testid="login-submit"
            disabled={loading}
            type="submit"
            className="w-full py-3 bg-[#29B6E8] text-black font-bold uppercase tracking-wider rounded-sm hover:bg-[#1E95C2] disabled:opacity-50 transition"
          >
            {loading ? "Login ..." : "Einloggen"}
          </button>
        </form> : (
          <div className="mt-8 border border-white/10 bg-white/5 p-4 text-sm text-white/60" data-testid="password-login-disabled">
            Die Anmeldung mit E-Mail und Passwort ist derzeit deaktiviert.
          </div>
        )}
        {!mfaTicket && <GoogleAuthButton label="Mit Google einloggen" returnPath={next} intent="login" />}
        {!mfaTicket && passkeysEnabled && (
          <div className="mt-4 space-y-2">
            <button type="button" disabled={loading} onClick={passkeyLogin} data-testid="login-passkey"
              className="w-full min-h-11 py-3 border border-[#29B6E8]/60 text-[#29B6E8] rounded-sm font-bold disabled:opacity-50">Mit Passkey anmelden</button>
            <p className="text-xs text-white/60 text-center">Bereits im Profil eingerichtet? Verwende deinen gespeicherten Passkey.</p>
            {settings.password_login_enabled === false && err && <AuthFormAlert id="passkey-error">{err}</AuthFormAlert>}
          </div>
        )}
        <div className="mt-6 text-sm text-white/60 text-center space-y-2">
          {settings.registration_enabled !== false && (
            <div>Kein Account? <Link to="/register" className="text-[#29B6E8] hover:text-white font-bold">Registrieren</Link></div>
          )}
          <div><Link to="/forgot-password" className="text-white/45 hover:text-[#29B6E8]">Passwort vergessen?</Link></div>
          <div><Link to="/verify-email" state={{ email: email.trim() }} className="text-white/60 hover:text-[#29B6E8]">Keine Bestätigungs-E-Mail erhalten?</Link></div>
        </div>
      </div>
    </div>
  );
}
