import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";
import { normalizeApiPath } from "@/lib/apiInvalidation";
import { useApiInvalidation } from "@/hooks/useApiInvalidation";
import { toast } from "sonner";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);
  const [error, setError] = useState(null);
  const [googleProcessing, setGoogleProcessing] = useState(false);

  const fetchMe = useCallback(async () => {
    try {
      let response = await api.get("/auth/me");
      if (response.headers?.["x-session-refresh"] === "required") {
        await api.post("/auth/refresh", null, { skipInvalidation: true });
        response = await api.get("/auth/me");
      }
      setUser(response.data || null);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const googleAuthenticate = useCallback(async (credential, options = {}) => {
    setGoogleProcessing(true);
    setError(null);
    try {
      const { data } = await api.post("/auth/google/session", {
        credential,
        intent: options.intent || "login",
        accept_privacy: !!options.acceptPrivacy,
        accept_terms: !!options.acceptTerms,
        newsletter_consent: !!options.newsletterConsent,
      });
      if (data?.mfa_required) return { ok: true, mfaRequired: true, ticket: data.mfa_ticket };
      setUser(data);
      return { ok: true, data };
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || "Google-Anmeldung fehlgeschlagen.";
      setError(msg);
      return { ok: false, error: msg };
    } finally {
      setGoogleProcessing(false);
    }
  }, []);

  const googleLink = useCallback(async (credential) => {
    setGoogleProcessing(true);
    setError(null);
    try {
      const { data } = await api.post("/auth/google/link", { credential, intent: "link" });
      await fetchMe();
      return { ok: true, data };
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || "Google-Verknüpfung fehlgeschlagen.";
      setError(msg);
      return { ok: false, error: msg };
    } finally {
      setGoogleProcessing(false);
    }
  }, [fetchMe]);
  const refreshCurrentUser = useCallback((event) => {
    const path = normalizeApiPath(event?.path);
    if (path === "auth/me" || path === "users/me" || path.startsWith("auth/")) {
      return fetchMe();
    }
    if (path.startsWith("membership/applications")) {
      return fetchMe();
    }
    if (user?.id && (path === `users/${user.id}` || path === `membership/user/${user.id}`)) {
      return fetchMe();
    }
    return undefined;
  }, [fetchMe, user?.id]);
  useApiInvalidation(refreshCurrentUser, ["auth", "users", "membership"]);

  const login = async (email, password) => {
    setError(null);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data?.mfa_required) {
        return { ok: true, mfaRequired: true, ticket: data.mfa_ticket };
      }
      setUser(data);
      return { ok: true };
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || e.message;
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const completeMfa = async (ticket, code) => {
    setError(null);
    try {
      const { data } = await api.post("/auth/mfa/complete", { ticket, code, client: "web" });
      setUser(data);
      return { ok: true, data };
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || "MFA-Code konnte nicht bestätigt werden.";
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const register = async (payload) => {
    setError(null);
    try {
      const { data } = await api.post("/auth/register", payload);
      if (data?.verification_required) setUser(null);
      else setUser(data);
      return { ok: true, data };
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || e.message;
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
      setUser(null);
      return true;
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || "Logout fehlgeschlagen.";
      setError(msg);
      toast.error(msg);
      return false;
    }
  };

  const isAdmin = user && ["tournament_admin", "club_admin", "superadmin"].includes(user.role);
  const isModerator = user && (user.is_tournament_staff || ["moderator", "tournament_admin", "club_admin", "superadmin"].includes(user.role));
  const isSuperAdmin = user?.role === "superadmin";
  const isClubMember = !!user?.is_club_member;
  const userType = user?.user_type || (user ? "community_user" : "guest");

  return (
    <AuthContext.Provider value={{ user, setUser, login, completeMfa, register, logout, error, isAdmin, isModerator, isSuperAdmin, isClubMember, userType, refresh: fetchMe, googleAuthenticate, googleLink, googleProcessing }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
