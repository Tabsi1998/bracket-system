import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Trophy, Gamepad2, Plus, Menu, X, Users, Shield, LogIn, LogOut, User } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import NotificationBell from "@/components/NotificationBell";

export default function Navbar() {
  const location = useLocation();
  const { user, logout, isAdmin } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = [
    { to: "/tournaments", label: "Turniere", icon: Trophy },
    { to: "/games", label: "Spiele", icon: Gamepad2 },
    ...(user ? [{ to: "/teams", label: "Teams", icon: Users }] : []),
    ...(isAdmin ? [{ to: "/admin", label: "Admin", icon: Shield }] : []),
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <nav data-testid="main-navbar" className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-yellow-500 rounded flex items-center justify-center">
              <Trophy className="w-5 h-5 text-black" />
            </div>
            <span className="font-['Barlow_Condensed'] text-xl font-bold tracking-tight text-white group-hover:text-yellow-500 transition-colors">
              ARENA
            </span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <Link key={link.to} to={link.to} data-testid={`nav-${link.label.toLowerCase()}`}>
                <Button
                  variant="ghost"
                  className={`gap-2 text-sm ${
                    isActive(link.to)
                      ? "text-yellow-500 bg-yellow-500/10"
                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <link.icon className="w-4 h-4" />
                  {link.label}
                </Button>
              </Link>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-2">
            {user && <NotificationBell />}
            {isAdmin && (
              <Link to="/tournaments/create" data-testid="nav-create-tournament">
                <Button className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 active:scale-95 transition-transform">
                  <Plus className="w-4 h-4" />
                  Turnier erstellen
                </Button>
              </Link>
            )}
            {user ? (
              <div className="flex items-center gap-2 ml-1">
                <Link to={`/profile/${user.id}`} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900/50 border border-white/5 hover:border-yellow-500/20 transition-all">
                  <img
                    src={user.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.username}`}
                    className="w-6 h-6 rounded-full"
                    alt=""
                  />
                  <span data-testid="user-display-name" className="text-sm text-white font-medium">{user.username}</span>
                  {isAdmin && <Shield className="w-3 h-3 text-yellow-500" />}
                </Link>
                <Button data-testid="logout-btn" variant="ghost" size="sm" onClick={logout} className="text-zinc-500 hover:text-red-400">
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <Link to="/login" data-testid="nav-login">
                <Button variant="outline" className="border-white/10 text-white hover:bg-white/5 gap-2">
                  <LogIn className="w-4 h-4" />Login
                </Button>
              </Link>
            )}
          </div>

          {/* Mobile toggle */}
          <div className="flex items-center gap-2 md:hidden">
            {user && <NotificationBell />}
            <button data-testid="mobile-menu-toggle" className="text-zinc-400 hover:text-white" onClick={() => setMobileOpen(!mobileOpen)}>
              {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-white/5 bg-[#050505]"
          >
            <div className="px-4 py-4 space-y-2">
              {links.map((link) => (
                <Link key={link.to} to={link.to} onClick={() => setMobileOpen(false)}>
                  <Button variant="ghost" className={`w-full justify-start gap-2 ${isActive(link.to) ? "text-yellow-500 bg-yellow-500/10" : "text-zinc-400"}`}>
                    <link.icon className="w-4 h-4" />{link.label}
                  </Button>
                </Link>
              ))}
              {isAdmin && (
                <Link to="/tournaments/create" onClick={() => setMobileOpen(false)}>
                  <Button className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 mt-2">
                    <Plus className="w-4 h-4" />Turnier erstellen
                  </Button>
                </Link>
              )}
              {user ? (
                <div className="pt-3 mt-3 border-t border-white/5 space-y-2">
                  <Link to={`/profile/${user.id}`} onClick={() => setMobileOpen(false)}>
                    <Button variant="ghost" className="w-full justify-start gap-2 text-zinc-300">
                      <User className="w-4 h-4" />
                      Konto
                    </Button>
                  </Link>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <img src={user.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.username}`} className="w-6 h-6 rounded-full" alt="" />
                      <span className="text-sm text-white">{user.username}</span>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => { logout(); setMobileOpen(false); }} className="text-zinc-500 hover:text-red-400">
                      <LogOut className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <Link to="/login" onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full border-white/10 text-white hover:bg-white/5 gap-2 mt-2">
                    <LogIn className="w-4 h-4" />Login
                  </Button>
                </Link>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
