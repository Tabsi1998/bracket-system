import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Trophy, Gamepad2, Plus, Menu, X } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function Navbar() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = [
    { to: "/tournaments", label: "Turniere", icon: Trophy },
    { to: "/games", label: "Spiele", icon: Gamepad2 },
  ];

  const isActive = (path) => location.pathname === path;

  return (
    <nav
      data-testid="main-navbar"
      className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/5"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link
            to="/"
            data-testid="navbar-logo"
            className="flex items-center gap-2 group"
          >
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

          <div className="hidden md:flex items-center gap-3">
            <Link to="/tournaments/create" data-testid="nav-create-tournament">
              <Button className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 active:scale-95 transition-transform">
                <Plus className="w-4 h-4" />
                Turnier erstellen
              </Button>
            </Link>
          </div>

          {/* Mobile toggle */}
          <button
            data-testid="mobile-menu-toggle"
            className="md:hidden text-zinc-400 hover:text-white"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
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
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                >
                  <Button
                    variant="ghost"
                    className={`w-full justify-start gap-2 ${
                      isActive(link.to)
                        ? "text-yellow-500 bg-yellow-500/10"
                        : "text-zinc-400"
                    }`}
                  >
                    <link.icon className="w-4 h-4" />
                    {link.label}
                  </Button>
                </Link>
              ))}
              <Link to="/tournaments/create" onClick={() => setMobileOpen(false)}>
                <Button className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 mt-2">
                  <Plus className="w-4 h-4" />
                  Turnier erstellen
                </Button>
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
