import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Logo } from "@/components/tls/Logo";
import { AuthFormAlert, AuthTextField } from "@/components/tls/AuthFormFields";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export default function EmailVerificationPage() {
  useDocumentTitle("E-Mail bestätigen", "E-Mail-Adresse für den Community-Account bestätigen.", { robots: "noindex, nofollow" });
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [email, setEmail] = useState(params.get("email") || "");
  const [status, setStatus] = useState(token ? "checking" : "sent");
  const [message, setMessage] = useState("");
  const handled = useRef(false);

  useEffect(() => {
    if (!token || handled.current) return;
    handled.current = true;
    api.post("/auth/verify-email", { token })
      .then(() => {
        setStatus("success");
        setMessage("Deine E-Mail-Adresse ist bestätigt. Du kannst dich jetzt anmelden.");
      })
      .catch((error) => {
        setStatus("error");
        setMessage(formatApiError(error.response?.data?.detail) || "Der Bestätigungslink ist ungültig oder abgelaufen.");
      });
  }, [token]);

  const resend = async (event) => {
    event.preventDefault();
    if (!email.trim()) return;
    setStatus("checking");
    try {
      await api.post("/auth/resend-verification", { email: email.trim() });
      setStatus("sent");
      setMessage("Falls eine Bestätigung aussteht, wurde ein neuer Link gesendet.");
    } catch (error) {
      setStatus("error");
      setMessage(formatApiError(error.response?.data?.detail) || "Der Link konnte nicht gesendet werden.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex items-center justify-center p-6 bg-grid">
      <div className="w-full max-w-md border border-white/10 rounded-sm bg-[#121212] p-8 md:p-10">
        <div className="flex justify-center mb-8"><Logo size="xl" /></div>
        <h1 className="font-heading text-2xl font-black uppercase text-center">E-Mail bestätigen</h1>
        <p className="text-sm text-white/60 text-center mt-2">Öffne den Link aus deiner E-Mail, bevor du dich anmeldest.</p>
        <div className="mt-6">
          {status === "checking" && <AuthFormAlert id="verify-status" tone="info">Bestätigung wird geprüft …</AuthFormAlert>}
          {status === "success" && <AuthFormAlert id="verify-success" tone="success">{message}</AuthFormAlert>}
          {status === "error" && <AuthFormAlert id="verify-error">{message}</AuthFormAlert>}
          {status === "sent" && <AuthFormAlert id="verify-sent" tone="success">{message || "Bitte prüfe dein Postfach und auch den Spam-Ordner."}</AuthFormAlert>}
        </div>
        {status !== "success" && (
          <form onSubmit={resend} className="mt-6 space-y-3">
            <AuthTextField id="verify-email" label="E-Mail" type="email" value={email} onChange={setEmail} autoComplete="email" required />
            <button type="submit" disabled={status === "checking"} className="w-full py-3 border border-[#29B6E8]/50 text-[#29B6E8] font-bold uppercase rounded-sm disabled:opacity-50">
              Bestätigungslink erneut senden
            </button>
          </form>
        )}
        <div className="mt-6 text-sm text-center"><Link to="/login" className="text-white/50 hover:text-[#29B6E8]">Zum Login</Link></div>
      </div>
    </div>
  );
}
