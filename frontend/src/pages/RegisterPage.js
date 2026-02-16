import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { UserPlus, Mail, Lock, User, Trophy } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !email || !password) { toast.error("Alle Felder ausfüllen"); return; }
    if (password.length < 6) { toast.error("Passwort muss mindestens 6 Zeichen haben"); return; }
    setLoading(true);
    try {
      await register(username, email, password);
      toast.success("Konto erstellt!");
      navigate("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Registrierung fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="register-page" className="pt-20 min-h-screen flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <div className="glass rounded-2xl p-8 border border-white/5">
          <div className="flex items-center justify-center gap-3 mb-8">
            <div className="w-10 h-10 bg-yellow-500 rounded-lg flex items-center justify-center">
              <Trophy className="w-6 h-6 text-black" />
            </div>
            <h1 className="font-['Barlow_Condensed'] text-3xl font-bold text-white uppercase tracking-tight">
              Registrieren
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <Label className="text-zinc-400 text-sm">Benutzername</Label>
              <div className="relative mt-1">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                <Input
                  data-testid="register-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Benutzername"
                  className="pl-10 bg-zinc-900 border-white/10 text-white"
                />
              </div>
            </div>
            <div>
              <Label className="text-zinc-400 text-sm">E-Mail</Label>
              <div className="relative mt-1">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                <Input
                  data-testid="register-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="deine@email.de"
                  className="pl-10 bg-zinc-900 border-white/10 text-white"
                />
              </div>
            </div>
            <div>
              <Label className="text-zinc-400 text-sm">Passwort</Label>
              <div className="relative mt-1">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                <Input
                  data-testid="register-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 6 Zeichen"
                  className="pl-10 bg-zinc-900 border-white/10 text-white"
                />
              </div>
            </div>
            <Button
              data-testid="register-submit-btn"
              type="submit"
              disabled={loading}
              className="w-full bg-yellow-500 text-black hover:bg-yellow-400 h-11 font-bold uppercase tracking-wide active:scale-95 transition-transform"
            >
              {loading ? "Wird erstellt..." : <><UserPlus className="w-4 h-4 mr-2" />Konto erstellen</>}
            </Button>
          </form>

          <p className="text-center text-sm text-zinc-500 mt-6">
            Bereits registriert?{" "}
            <Link to="/login" data-testid="go-to-login" className="text-yellow-500 hover:underline font-semibold">
              Einloggen
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
