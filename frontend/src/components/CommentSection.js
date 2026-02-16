import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { MessageSquare, Send } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function CommentSection({ targetType, targetId }) {
  const { user } = useAuth();
  const [comments, setComments] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const endpoint = targetType === "tournament"
    ? `${API}/tournaments/${targetId}/comments`
    : `${API}/matches/${targetId}/comments`;

  const fetchComments = async () => {
    try {
      const res = await axios.get(endpoint);
      setComments(res.data);
    } catch { /* ignore */ }
  };

  useEffect(() => { fetchComments(); }, [targetId]);

  const handleSubmit = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      await axios.post(endpoint, { message });
      setMessage("");
      fetchComments();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kommentar fehlgeschlagen");
    } finally { setLoading(false); }
  };

  const timeAgo = (date) => {
    const diff = Date.now() - new Date(date).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "gerade eben";
    if (mins < 60) return `vor ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `vor ${hrs}h`;
    return `vor ${Math.floor(hrs / 24)}d`;
  };

  return (
    <div data-testid="comment-section" className="space-y-4">
      <h4 className="font-['Barlow_Condensed'] text-base font-bold text-white flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-yellow-500" />
        Kommentare ({comments.length})
      </h4>

      {user ? (
        <div className="flex gap-2">
          <img src={user.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user.username}`} className="w-8 h-8 rounded-full flex-shrink-0 mt-1" alt="" />
          <div className="flex-1 flex gap-2">
            <Textarea
              data-testid="comment-input"
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Kommentar schreiben..."
              className="bg-zinc-900 border-white/10 text-white min-h-[40px] h-10 resize-none"
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }}
            />
            <Button data-testid="submit-comment-btn" onClick={handleSubmit} disabled={loading || !message.trim()} size="sm" className="bg-yellow-500 text-black hover:bg-yellow-400 h-10 px-3">
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-zinc-600">Einloggen um zu kommentieren</p>
      )}

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {comments.map((c, i) => (
          <motion.div key={c.id} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
            className="flex gap-2"
          >
            <img src={c.author_avatar || `https://api.dicebear.com/7.x/avataaars/svg?seed=${c.author_name}`} className="w-7 h-7 rounded-full flex-shrink-0 mt-0.5" alt="" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">{c.author_name}</span>
                <span className="text-xs text-zinc-600">{timeAgo(c.created_at)}</span>
              </div>
              <p className="text-sm text-zinc-400 break-words">{c.message}</p>
            </div>
          </motion.div>
        ))}
        {comments.length === 0 && <p className="text-sm text-zinc-600 text-center py-4">Noch keine Kommentare</p>}
      </div>
    </div>
  );
}
