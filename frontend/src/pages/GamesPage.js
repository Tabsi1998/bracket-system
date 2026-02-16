import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Plus, Gamepad2, Trash2, Monitor, X as XIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const categories = [
  { value: "fps", label: "FPS" },
  { value: "sports", label: "Sport" },
  { value: "racing", label: "Racing" },
  { value: "fighting", label: "Fighting" },
  { value: "moba", label: "MOBA" },
  { value: "battle_royale", label: "Battle Royale" },
  { value: "strategy", label: "Strategie" },
  { value: "other", label: "Andere" },
];

const categoryColors = {
  fps: "bg-red-500/10 text-red-400 border-red-500/20",
  sports: "bg-green-500/10 text-green-400 border-green-500/20",
  racing: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  fighting: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  moba: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  battle_royale: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  strategy: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  other: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
};

export default function GamesPage() {
  const [games, setGames] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [filterCat, setFilterCat] = useState("all");
  const [newGame, setNewGame] = useState({
    name: "",
    short_name: "",
    category: "fps",
    image_url: "",
    modes: [{ name: "", team_size: 1, description: "" }],
    platforms: [],
  });

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = () => {
    axios.get(`${API}/games`).then(r => setGames(r.data)).catch(() => {});
  };

  const handleCreateGame = async () => {
    if (!newGame.name.trim()) { toast.error("Spielname erforderlich"); return; }
    const validModes = newGame.modes.filter(m => m.name.trim());
    if (validModes.length === 0) { toast.error("Mindestens ein Modus erforderlich"); return; }
    try {
      await axios.post(`${API}/games`, { ...newGame, modes: validModes });
      toast.success("Spiel erstellt!");
      setCreateOpen(false);
      setNewGame({ name: "", short_name: "", category: "fps", image_url: "", modes: [{ name: "", team_size: 1, description: "" }], platforms: [] });
      fetchGames();
    } catch (e) {
      toast.error("Fehler beim Erstellen");
    }
  };

  const handleDeleteGame = async (gameId) => {
    try {
      await axios.delete(`${API}/games/${gameId}`);
      toast.success("Spiel gelöscht");
      fetchGames();
    } catch (e) {
      toast.error("Fehler beim Löschen");
    }
  };

  const addMode = () => setNewGame({ ...newGame, modes: [...newGame.modes, { name: "", team_size: 1, description: "" }] });
  const removeMode = (idx) => setNewGame({ ...newGame, modes: newGame.modes.filter((_, i) => i !== idx) });
  const updateMode = (idx, field, value) => {
    const modes = [...newGame.modes];
    modes[idx][field] = field === "team_size" ? parseInt(value) || 1 : value;
    setNewGame({ ...newGame, modes });
  };

  const togglePlatform = (p) => {
    const platforms = newGame.platforms.includes(p) ? newGame.platforms.filter(x => x !== p) : [...newGame.platforms, p];
    setNewGame({ ...newGame, platforms });
  };

  const filtered = filterCat === "all" ? games : games.filter(g => g.category === filterCat);

  return (
    <div data-testid="games-page" className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">
              Spiele
            </h1>
            <p className="text-sm text-zinc-500 mt-1">{games.length} Spiele in der Datenbank</p>
          </div>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button data-testid="add-game-btn" className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 active:scale-95 transition-transform">
                <Plus className="w-4 h-4" />Spiel hinzufügen
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Neues Spiel erstellen</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-zinc-400 text-sm">Spielname *</Label>
                    <Input data-testid="new-game-name" value={newGame.name} onChange={e => setNewGame({ ...newGame, name: e.target.value })} placeholder="z.B. Apex Legends" className="bg-zinc-900 border-white/10 text-white mt-1" />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-sm">Kurzname</Label>
                    <Input data-testid="new-game-short" value={newGame.short_name} onChange={e => setNewGame({ ...newGame, short_name: e.target.value })} placeholder="z.B. APEX" className="bg-zinc-900 border-white/10 text-white mt-1" />
                  </div>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Kategorie</Label>
                  <Select value={newGame.category} onValueChange={v => setNewGame({ ...newGame, category: v })}>
                    <SelectTrigger data-testid="new-game-category" className="bg-zinc-900 border-white/10 text-white mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      {categories.map(c => (
                        <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Bild-URL</Label>
                  <Input data-testid="new-game-image" value={newGame.image_url} onChange={e => setNewGame({ ...newGame, image_url: e.target.value })} placeholder="https://..." className="bg-zinc-900 border-white/10 text-white mt-1" />
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Plattformen</Label>
                  <div className="flex gap-2 mt-2">
                    {["PC", "PS5", "Xbox", "Switch", "Mobile"].map(p => (
                      <button
                        key={p}
                        data-testid={`platform-${p}`}
                        onClick={() => togglePlatform(p)}
                        className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-all ${
                          newGame.platforms.includes(p)
                            ? "border-yellow-500 bg-yellow-500/10 text-yellow-500"
                            : "border-white/10 text-zinc-500 hover:border-white/20"
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Spielmodi *</Label>
                  {newGame.modes.map((mode, idx) => (
                    <div key={idx} className="flex gap-2 mt-2">
                      <Input
                        data-testid={`mode-name-${idx}`}
                        value={mode.name}
                        onChange={e => updateMode(idx, "name", e.target.value)}
                        placeholder="z.B. 5v5"
                        className="bg-zinc-900 border-white/10 text-white flex-1"
                      />
                      <Input
                        data-testid={`mode-size-${idx}`}
                        type="number"
                        min="1"
                        value={mode.team_size}
                        onChange={e => updateMode(idx, "team_size", e.target.value)}
                        className="bg-zinc-900 border-white/10 text-white w-20"
                      />
                      {newGame.modes.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeMode(idx)} className="text-red-500 hover:text-red-400 px-2">
                          <XIcon className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                  <Button variant="ghost" size="sm" onClick={addMode} className="mt-2 text-yellow-500">+ Modus hinzufügen</Button>
                </div>
                <Button data-testid="submit-game-btn" onClick={handleCreateGame} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                  Spiel erstellen
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Category filter */}
        <div className="flex gap-2 mb-8 flex-wrap">
          <button
            data-testid="filter-all"
            onClick={() => setFilterCat("all")}
            className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all ${
              filterCat === "all"
                ? "border-yellow-500 bg-yellow-500/10 text-yellow-500"
                : "border-white/10 text-zinc-500 hover:border-white/20"
            }`}
          >
            Alle
          </button>
          {categories.map(c => (
            <button
              key={c.value}
              data-testid={`filter-${c.value}`}
              onClick={() => setFilterCat(c.value)}
              className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all ${
                filterCat === c.value
                  ? "border-yellow-500 bg-yellow-500/10 text-yellow-500"
                  : "border-white/10 text-zinc-500 hover:border-white/20"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Games Grid */}
        <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map((game, i) => (
            <motion.div
              key={game.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              data-testid={`game-card-${i}`}
              className="group relative overflow-hidden rounded-xl border border-white/5 hover:border-yellow-500/30 transition-all duration-300 game-card-hover"
            >
              <div className="aspect-[3/4] relative">
                {game.image_url ? (
                  <img src={game.image_url} alt={game.name} className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                ) : (
                  <div className="absolute inset-0 bg-zinc-900 flex items-center justify-center">
                    <Gamepad2 className="w-12 h-12 text-zinc-700" />
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent opacity-80 group-hover:opacity-60 transition-opacity" />

                {/* Content overlay */}
                <div className="absolute bottom-0 left-0 right-0 p-4">
                  <Badge className={`text-xs border mb-2 ${categoryColors[game.category] || categoryColors.other}`}>
                    {game.category?.toUpperCase()}
                  </Badge>
                  <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white">{game.name}</h3>
                  <p className="text-xs text-zinc-400 font-mono mt-1">{game.short_name}</p>

                  <div className="flex flex-wrap gap-1 mt-2">
                    {game.modes?.map(m => (
                      <span key={m.name} className="text-xs px-2 py-0.5 rounded bg-white/10 text-zinc-300">
                        {m.name}
                      </span>
                    ))}
                  </div>

                  {game.platforms && game.platforms.length > 0 && (
                    <div className="flex items-center gap-1 mt-2 text-zinc-500">
                      <Monitor className="w-3 h-3" />
                      <span className="text-xs">{game.platforms.join(", ")}</span>
                    </div>
                  )}
                </div>

                {/* Delete button for custom games */}
                {game.is_custom && (
                  <button
                    data-testid={`delete-game-${game.id}`}
                    onClick={() => handleDeleteGame(game.id)}
                    className="absolute top-3 right-3 p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
