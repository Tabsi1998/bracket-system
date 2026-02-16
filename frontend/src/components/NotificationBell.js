import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Check, MessageSquare, Clock, Trophy } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const typeIcons = {
  comment: MessageSquare,
  schedule: Clock,
  match: Trophy,
};

export default function NotificationBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const ref = useRef(null);

  const fetchNotifications = async () => {
    try {
      const [nRes, cRes] = await Promise.all([
        axios.get(`${API}/notifications`),
        axios.get(`${API}/notifications/unread-count`),
      ]);
      setNotifications(nRes.data);
      setUnreadCount(cRes.data.count);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (!user) return;
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [user]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await axios.put(`${API}/notifications/read-all`);
      setUnreadCount(0);
      setNotifications(notifications.map(n => ({ ...n, read: true })));
    } catch { /* ignore */ }
  };

  const handleClick = async (notif) => {
    if (!notif.read) {
      await axios.put(`${API}/notifications/${notif.id}/read`).catch(() => {});
      setUnreadCount(Math.max(0, unreadCount - 1));
    }
    setOpen(false);
    if (notif.link) navigate(notif.link);
  };

  if (!user) return null;

  const timeAgo = (date) => {
    const diff = Date.now() - new Date(date).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "jetzt";
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  return (
    <div className="relative" ref={ref}>
      <button
        data-testid="notification-bell"
        onClick={() => setOpen(!open)}
        className="relative p-2 text-zinc-400 hover:text-white transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            className="absolute right-0 top-full mt-2 w-80 glass rounded-xl border border-white/10 overflow-hidden z-50"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <span className="text-sm font-semibold text-white">Benachrichtigungen</span>
              {unreadCount > 0 && (
                <Button data-testid="mark-all-read" variant="ghost" size="sm" onClick={handleMarkAllRead} className="text-xs text-yellow-500 hover:text-yellow-400 h-auto py-1">
                  <Check className="w-3 h-3 mr-1" />Alle gelesen
                </Button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <p className="text-sm text-zinc-600 text-center py-8">Keine Benachrichtigungen</p>
              ) : (
                notifications.slice(0, 20).map(n => {
                  const Icon = typeIcons[n.type] || Bell;
                  return (
                    <button
                      key={n.id}
                      data-testid={`notification-item-${n.id}`}
                      onClick={() => handleClick(n)}
                      className={`w-full text-left px-4 py-3 flex gap-3 hover:bg-white/5 transition-colors border-b border-white/5 ${!n.read ? "bg-yellow-500/5" : ""}`}
                    >
                      <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${!n.read ? "text-yellow-500" : "text-zinc-600"}`} />
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${!n.read ? "text-white" : "text-zinc-400"}`}>{n.message}</p>
                        <span className="text-xs text-zinc-600">{timeAgo(n.created_at)}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
