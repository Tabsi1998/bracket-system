import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Plus, Gamepad2, Trash2, Monitor, X as XIcon, Pencil, ChevronDown, ChevronRight,
  Map, Layers, Upload, Image as ImageIcon, Eye, EyeOff
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

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

// --- Sub Components ---

function SubGameSection({ game, subGame, isAdmin, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [addMapOpen, setAddMapOpen] = useState(false);
  const [editSubGameOpen, setEditSubGameOpen] = useState(false);
  const [newMap, setNewMap] = useState({ name: "", game_modes: [] });
  const [editForm, setEditForm] = useState({ name: "", short_name: "", release_year: 0, active: true });

  const modes = game.modes?.map(m => m.name) || [];
  const mapCount = subGame.maps?.length || 0;

  const handleAddMap = async () => {
    if (!newMap.name.trim()) { toast.error("Map-Name erforderlich"); return; }
    try {
      await axios.post(`${API}/games/${game.id}/sub-games/${subGame.id}/maps`, newMap);
      toast.success(`Map "${newMap.name}" hinzugefügt`);
      setNewMap({ name: "", game_modes: [] });
      setAddMapOpen(false);
      onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Hinzufügen");
    }
  };

  const handleDeleteMap = async (mapId, mapName) => {
    if (!window.confirm(`Map "${mapName}" wirklich löschen?`)) return;
    try {
      await axios.delete(`${API}/games/${game.id}/sub-games/${subGame.id}/maps/${mapId}`);
      toast.success(`Map "${mapName}" gelöscht`);
      onRefresh();
    } catch (e) {
      toast.error("Fehler beim Löschen");
    }
  };

  const handleEditSubGame = async () => {
    try {
      await axios.put(`${API}/games/${game.id}/sub-games/${subGame.id}`, editForm);
      toast.success("Sub-Game aktualisiert");
      setEditSubGameOpen(false);
      onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

  const handleDeleteSubGame = async () => {
    if (!window.confirm(`"${subGame.name}" und alle Maps wirklich löschen?`)) return;
    try {
      await axios.delete(`${API}/games/${game.id}/sub-games/${subGame.id}`);
      toast.success(`"${subGame.name}" gelöscht`);
      onRefresh();
    } catch (e) {
      toast.error("Fehler beim Löschen");
    }
  };

  const toggleMapMode = (mode) => {
    setNewMap(prev => ({
      ...prev,
      game_modes: prev.game_modes.includes(mode)
        ? prev.game_modes.filter(m => m !== mode)
        : [...prev.game_modes, mode]
    }));
  };

  const openEdit = () => {
    setEditForm({
      name: subGame.name,
      short_name: subGame.short_name || "",
      release_year: subGame.release_year || 0,
      active: subGame.active !== false,
    });
    setEditSubGameOpen(true);
  };

  return (
    <div data-testid={`sub-game-${subGame.id}`} className="border border-white/5 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-white/[0.02] transition-colors text-left"
        data-testid={`sub-game-toggle-${subGame.id}`}
      >
        {expanded ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
        <Layers className="w-4 h-4 text-cyan-400" />
        <div className="flex-1">
          <span className="text-white font-medium text-sm">{subGame.name}</span>
          {subGame.short_name && <span className="text-zinc-500 text-xs ml-2">({subGame.short_name})</span>}
          {subGame.release_year > 0 && <span className="text-zinc-600 text-xs ml-2">{subGame.release_year}</span>}
        </div>
        <Badge className={`text-[10px] ${subGame.active !== false ? "bg-green-500/10 text-green-400" : "bg-zinc-500/10 text-zinc-500"}`}>
          {subGame.active !== false ? "Aktiv" : "Inaktiv"}
        </Badge>
        <span className="text-xs text-zinc-500">{mapCount} Maps</span>
        {isAdmin && (
          <div className="flex gap-1" onClick={e => e.stopPropagation()}>
            <button onClick={openEdit} className="p-1 rounded hover:bg-white/5 text-zinc-500 hover:text-white">
              <Pencil className="w-3 h-3" />
            </button>
            <button onClick={handleDeleteSubGame} className="p-1 rounded hover:bg-red-500/10 text-zinc-500 hover:text-red-400">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-3 pt-0 space-y-2">
              {(subGame.maps || []).length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {subGame.maps.map(map => (
                    <div key={map.id} data-testid={`map-${map.id}`} className="group relative rounded-lg border border-white/5 p-2 bg-zinc-900/50 hover:border-cyan-500/20 transition-all">
                      {map.image_url ? (
                        <div className="aspect-video rounded overflow-hidden mb-2 bg-zinc-800">
                          <img src={map.image_url} alt={map.name} className="w-full h-full object-cover" />
                        </div>
                      ) : (
                        <div className="aspect-video rounded bg-zinc-800/50 flex items-center justify-center mb-2">
                          <Map className="w-5 h-5 text-zinc-700" />
                        </div>
                      )}
                      <p className="text-xs text-white font-medium truncate">{map.name}</p>
                      {map.game_modes?.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {map.game_modes.map(gm => (
                            <span key={gm} className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-zinc-500">{gm}</span>
                          ))}
                        </div>
                      )}
                      {isAdmin && (
                        <button
                          onClick={() => handleDeleteMap(map.id, map.name)}
                          className="absolute top-1 right-1 p-1 rounded bg-black/50 text-zinc-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-600 py-2">Keine Maps vorhanden</p>
              )}
              {isAdmin && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-cyan-400 hover:text-cyan-300 text-xs gap-1"
                  onClick={() => setAddMapOpen(true)}
                >
                  <Plus className="w-3 h-3" /> Map hinzufügen
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Map Dialog */}
      <Dialog open={addMapOpen} onOpenChange={setAddMapOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">Map zu {subGame.name} hinzufügen</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-zinc-400 text-sm">Map-Name *</Label>
              <Input
                data-testid="new-map-name"
                value={newMap.name}
                onChange={e => setNewMap({ ...newMap, name: e.target.value })}
                placeholder="z.B. Nuketown"
                className="bg-zinc-900 border-white/10 text-white mt-1"
              />
            </div>
            {modes.length > 0 && (
              <div>
                <Label className="text-zinc-400 text-sm">Unterstützte Modi</Label>
                <div className="flex gap-2 flex-wrap mt-2">
                  {modes.map(mode => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => toggleMapMode(mode)}
                      className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-all ${
                        newMap.game_modes.includes(mode)
                          ? "border-cyan-500 bg-cyan-500/10 text-cyan-400"
                          : "border-white/10 text-zinc-500 hover:border-white/20"
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <Button data-testid="submit-map-btn" onClick={handleAddMap} className="w-full bg-cyan-500 text-black hover:bg-cyan-400 font-semibold">
              Map hinzufügen
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Sub-Game Dialog */}
      <Dialog open={editSubGameOpen} onOpenChange={setEditSubGameOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">Sub-Game bearbeiten</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-zinc-400 text-sm">Name *</Label>
              <Input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} className="bg-zinc-900 border-white/10 text-white mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-zinc-400 text-sm">Kurzname</Label>
                <Input value={editForm.short_name} onChange={e => setEditForm({ ...editForm, short_name: e.target.value })} className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Release-Jahr</Label>
                <Input type="number" value={editForm.release_year} onChange={e => setEditForm({ ...editForm, release_year: parseInt(e.target.value) || 0 })} className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={editForm.active} onCheckedChange={v => setEditForm({ ...editForm, active: v })} />
              <Label className="text-zinc-400 text-sm">Aktiv</Label>
            </div>
            <Button onClick={handleEditSubGame} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">Speichern</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function GameCard({ game, isAdmin, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [addSubGameOpen, setAddSubGameOpen] = useState(false);
  const [editGameOpen, setEditGameOpen] = useState(false);
  const [newSubGame, setNewSubGame] = useState({ name: "", short_name: "", release_year: new Date().getFullYear(), active: true });
  const [editForm, setEditForm] = useState(null);

  const subGames = game.sub_games || [];
  const totalMaps = subGames.reduce((sum, sg) => sum + (sg.maps?.length || 0), 0);

  const handleAddSubGame = async () => {
    if (!newSubGame.name.trim()) { toast.error("Name erforderlich"); return; }
    try {
      await axios.post(`${API}/games/${game.id}/sub-games`, newSubGame);
      toast.success(`"${newSubGame.name}" hinzugefügt`);
      setNewSubGame({ name: "", short_name: "", release_year: new Date().getFullYear(), active: true });
      setAddSubGameOpen(false);
      onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

  const handleDeleteGame = async () => {
    if (!window.confirm(`"${game.name}" und alle Sub-Games/Maps wirklich löschen?`)) return;
    try {
      await axios.delete(`${API}/games/${game.id}`);
      toast.success(`"${game.name}" gelöscht`);
      onRefresh();
    } catch (e) {
      toast.error("Fehler beim Löschen");
    }
  };

  const openEditGame = () => {
    setEditForm({
      name: game.name,
      short_name: game.short_name || "",
      category: game.category || "other",
      image_url: game.image_url || "",
      modes: (game.modes || []).map(m => ({ name: m.name, team_size: m.team_size || 1, description: m.description || "" })),
      platforms: game.platforms || [],
    });
    setEditGameOpen(true);
  };

  const handleUpdateGame = async () => {
    if (!editForm.name.trim()) { toast.error("Spielname erforderlich"); return; }
    try {
      const payload = {
        ...editForm,
        modes: editForm.modes.filter(m => m.name.trim()).map(m => ({
          name: m.name.trim(),
          team_size: m.team_size || 1,
          description: m.description || "",
          settings_template: {},
        })),
        sub_games: game.sub_games || [],
      };
      await axios.put(`${API}/games/${game.id}`, payload);
      toast.success("Spiel aktualisiert");
      setEditGameOpen(false);
      onRefresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

  const togglePlatform = (p) => {
    setEditForm(prev => ({
      ...prev,
      platforms: prev.platforms.includes(p) ? prev.platforms.filter(x => x !== p) : [...prev.platforms, p]
    }));
  };

  return (
    <motion.div
      data-testid={`game-card-${game.id}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-white/5 overflow-hidden hover:border-yellow-500/20 transition-all"
    >
      {/* Game Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left"
        data-testid={`game-toggle-${game.id}`}
      >
        <div className="relative">
          <div className="aspect-[16/7] relative">
            {game.image_url ? (
              <img src={game.image_url} alt={game.name} className="absolute inset-0 w-full h-full object-cover" />
            ) : (
              <div className="absolute inset-0 bg-zinc-900 flex items-center justify-center">
                <Gamepad2 className="w-10 h-10 text-zinc-700" />
              </div>
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black via-black/60 to-transparent" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 p-4">
            <div className="flex items-start justify-between">
              <div>
                <Badge className={`text-[10px] border mb-1 ${categoryColors[game.category] || categoryColors.other}`}>
                  {game.category?.toUpperCase()}
                </Badge>
                <h3 className="font-['Barlow_Condensed'] text-xl font-bold text-white">{game.name}</h3>
                <p className="text-xs text-zinc-400 font-mono">{game.short_name}</p>
              </div>
              <div className="flex items-center gap-2">
                {expanded ? <ChevronDown className="w-5 h-5 text-zinc-400" /> : <ChevronRight className="w-5 h-5 text-zinc-400" />}
              </div>
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs text-zinc-400">
              {game.modes?.length > 0 && (
                <span className="flex items-center gap-1">
                  <Gamepad2 className="w-3 h-3" />{game.modes.length} Modi
                </span>
              )}
              {subGames.length > 0 && (
                <span className="flex items-center gap-1">
                  <Layers className="w-3 h-3" />{subGames.length} Versionen
                </span>
              )}
              {totalMaps > 0 && (
                <span className="flex items-center gap-1">
                  <Map className="w-3 h-3" />{totalMaps} Maps
                </span>
              )}
              {game.platforms?.length > 0 && (
                <span className="flex items-center gap-1">
                  <Monitor className="w-3 h-3" />{game.platforms.join(", ")}
                </span>
              )}
            </div>
          </div>
          {isAdmin && (
            <div className="absolute top-2 right-2 flex gap-1" onClick={e => e.stopPropagation()}>
              <button onClick={openEditGame} className="p-2 rounded-lg bg-black/60 text-zinc-300 hover:text-white">
                <Pencil className="w-4 h-4" />
              </button>
              {game.is_custom && (
                <button onClick={handleDeleteGame} className="p-2 rounded-lg bg-black/60 text-zinc-300 hover:text-red-400">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="p-4 space-y-4 border-t border-white/5 bg-zinc-950/50">
              {/* Modes */}
              {game.modes?.length > 0 && (
                <div>
                  <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Spielmodi</h4>
                  <div className="flex gap-2 flex-wrap">
                    {game.modes.map(m => (
                      <div key={m.name} className="px-3 py-1.5 rounded-lg bg-zinc-900 border border-white/5 text-xs">
                        <span className="text-white font-medium">{m.name}</span>
                        {m.description && <span className="text-zinc-600 ml-2">- {m.description}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sub-Games & Maps */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs text-zinc-500 uppercase tracking-wider">
                    {subGames.length > 0 ? "Versionen & Maps" : "Keine Sub-Games"}
                  </h4>
                  {isAdmin && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-yellow-500 hover:text-yellow-400 text-xs gap-1 h-7"
                      onClick={() => setAddSubGameOpen(true)}
                      data-testid="add-sub-game-btn"
                    >
                      <Plus className="w-3 h-3" /> Version hinzufügen
                    </Button>
                  )}
                </div>
                {subGames.length > 0 ? (
                  <div className="space-y-2">
                    {subGames.map(sg => (
                      <SubGameSection key={sg.id} game={game} subGame={sg} isAdmin={isAdmin} onRefresh={onRefresh} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-zinc-600 py-3">
                    Dieses Spiel hat keine Versionen/Sub-Games. Maps können über Sub-Games verwaltet werden.
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Sub-Game Dialog */}
      <Dialog open={addSubGameOpen} onOpenChange={setAddSubGameOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg">Version/Sub-Game zu {game.name} hinzufügen</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-zinc-400 text-sm">Name *</Label>
              <Input
                data-testid="new-sub-game-name"
                value={newSubGame.name}
                onChange={e => setNewSubGame({ ...newSubGame, name: e.target.value })}
                placeholder="z.B. Black Ops 6"
                className="bg-zinc-900 border-white/10 text-white mt-1"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-zinc-400 text-sm">Kurzname</Label>
                <Input
                  value={newSubGame.short_name}
                  onChange={e => setNewSubGame({ ...newSubGame, short_name: e.target.value })}
                  placeholder="z.B. BO6"
                  className="bg-zinc-900 border-white/10 text-white mt-1"
                />
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Release-Jahr</Label>
                <Input
                  type="number"
                  value={newSubGame.release_year}
                  onChange={e => setNewSubGame({ ...newSubGame, release_year: parseInt(e.target.value) || 0 })}
                  className="bg-zinc-900 border-white/10 text-white mt-1"
                />
              </div>
            </div>
            <Button data-testid="submit-sub-game-btn" onClick={handleAddSubGame} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
              Version hinzufügen
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Game Dialog */}
      <Dialog open={editGameOpen} onOpenChange={setEditGameOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg">Spiel bearbeiten</DialogTitle>
          </DialogHeader>
          {editForm && (
            <div className="space-y-4 mt-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-zinc-400 text-sm">Spielname *</Label>
                  <Input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} className="bg-zinc-900 border-white/10 text-white mt-1" />
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Kurzname</Label>
                  <Input value={editForm.short_name} onChange={e => setEditForm({ ...editForm, short_name: e.target.value })} className="bg-zinc-900 border-white/10 text-white mt-1" />
                </div>
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Kategorie</Label>
                <Select value={editForm.category} onValueChange={v => setEditForm({ ...editForm, category: v })}>
                  <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-white/10">
                    {categories.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Bild-URL</Label>
                <Input value={editForm.image_url} onChange={e => setEditForm({ ...editForm, image_url: e.target.value })} placeholder="https://..." className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Plattformen</Label>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {["PC", "PS5", "Xbox", "Switch", "Mobile"].map(p => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => togglePlatform(p)}
                      className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-all ${
                        editForm.platforms.includes(p)
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
                <Label className="text-zinc-400 text-sm">Spielmodi</Label>
                {(editForm.modes || []).map((mode, idx) => (
                  <div key={idx} className="mt-2 flex gap-2 items-center">
                    <Input
                      value={mode.name}
                      onChange={e => {
                        const modes = [...editForm.modes];
                        modes[idx] = { ...modes[idx], name: e.target.value };
                        setEditForm({ ...editForm, modes });
                      }}
                      placeholder="z.B. 5v5"
                      className="bg-zinc-900 border-white/10 text-white flex-1"
                    />
                    <Input
                      type="number"
                      min="1"
                      value={mode.team_size}
                      onChange={e => {
                        const modes = [...editForm.modes];
                        modes[idx] = { ...modes[idx], team_size: parseInt(e.target.value) || 1 };
                        setEditForm({ ...editForm, modes });
                      }}
                      className="bg-zinc-900 border-white/10 text-white w-20"
                      placeholder="Größe"
                    />
                    {editForm.modes.length > 1 && (
                      <Button variant="ghost" size="sm" onClick={() => setEditForm({ ...editForm, modes: editForm.modes.filter((_, i) => i !== idx) })} className="text-red-500 px-2">
                        <XIcon className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditForm({ ...editForm, modes: [...editForm.modes, { name: "", team_size: 1, description: "" }] })}
                  className="mt-2 text-yellow-500 text-xs"
                >
                  + Modus hinzufügen
                </Button>
              </div>
              <Button onClick={handleUpdateGame} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                Speichern
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

// --- Main Page ---

export default function GamesPage() {
  const { isAdmin } = useAuth();
  const [games, setGames] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [filterCat, setFilterCat] = useState("all");
  const [newGame, setNewGame] = useState({
    name: "", short_name: "", category: "fps", image_url: "",
    modes: [{ name: "", team_size: 1, description: "" }],
    platforms: [],
  });

  const fetchGames = useCallback(() => {
    axios.get(`${API}/games`).then(r => setGames(r.data)).catch(() => {});
  }, []);

  useEffect(() => { fetchGames(); }, [fetchGames]);

  const handleCreateGame = async () => {
    if (!newGame.name.trim()) { toast.error("Spielname erforderlich"); return; }
    const validModes = newGame.modes.filter(m => m.name.trim()).map(m => ({
      name: m.name.trim(), team_size: m.team_size || 1, description: m.description || "", settings_template: {},
    }));
    if (validModes.length === 0) { toast.error("Mindestens ein Modus erforderlich"); return; }
    try {
      await axios.post(`${API}/games`, { ...newGame, modes: validModes, sub_games: [] });
      toast.success("Spiel erstellt!");
      setCreateOpen(false);
      setNewGame({ name: "", short_name: "", category: "fps", image_url: "", modes: [{ name: "", team_size: 1, description: "" }], platforms: [] });
      fetchGames();
    } catch (e) {
      toast.error("Fehler beim Erstellen");
    }
  };

  const togglePlatform = (p) => {
    setNewGame(prev => ({
      ...prev,
      platforms: prev.platforms.includes(p) ? prev.platforms.filter(x => x !== p) : [...prev.platforms, p]
    }));
  };

  const filtered = filterCat === "all" ? games : games.filter(g => g.category === filterCat);

  return (
    <div data-testid="games-page" className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">
              Spiele & Maps
            </h1>
            <p className="text-sm text-zinc-500 mt-1">
              {games.length} Spiele &bull; {games.reduce((s, g) => s + (g.sub_games?.length || 0), 0)} Versionen &bull; {games.reduce((s, g) => s + (g.sub_games || []).reduce((ms, sg) => ms + (sg.maps?.length || 0), 0), 0)} Maps
            </p>
          </div>
          {isAdmin && (
            <Button
              data-testid="add-game-btn"
              onClick={() => setCreateOpen(true)}
              className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 active:scale-95 transition-transform"
            >
              <Plus className="w-4 h-4" />Spiel hinzufügen
            </Button>
          )}
        </div>

        {/* Category filter */}
        <div className="flex gap-2 mb-8 flex-wrap">
          <button
            data-testid="filter-all"
            onClick={() => setFilterCat("all")}
            className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all ${
              filterCat === "all" ? "border-yellow-500 bg-yellow-500/10 text-yellow-500" : "border-white/10 text-zinc-500 hover:border-white/20"
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
                filterCat === c.value ? "border-yellow-500 bg-yellow-500/10 text-yellow-500" : "border-white/10 text-zinc-500 hover:border-white/20"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Games Grid */}
        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map(game => (
            <GameCard key={game.id} game={game} isAdmin={isAdmin} onRefresh={fetchGames} />
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16 text-zinc-500">
            <Gamepad2 className="w-12 h-12 mx-auto mb-4 text-zinc-700" />
            <p>Keine Spiele in dieser Kategorie</p>
          </div>
        )}

        {/* Create Game Dialog */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-lg max-h-[85vh] overflow-y-auto">
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
                  <SelectTrigger data-testid="new-game-category" className="bg-zinc-900 border-white/10 text-white mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-white/10">
                    {categories.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
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
                      type="button"
                      data-testid={`platform-${p}`}
                      onClick={() => togglePlatform(p)}
                      className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-all ${
                        newGame.platforms.includes(p) ? "border-yellow-500 bg-yellow-500/10 text-yellow-500" : "border-white/10 text-zinc-500 hover:border-white/20"
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
                  <div key={idx} className="mt-2 flex gap-2 items-center">
                    <Input
                      data-testid={`mode-name-${idx}`}
                      value={mode.name}
                      onChange={e => {
                        const modes = [...newGame.modes];
                        modes[idx] = { ...modes[idx], name: e.target.value };
                        setNewGame({ ...newGame, modes });
                      }}
                      placeholder="z.B. 5v5"
                      className="bg-zinc-900 border-white/10 text-white flex-1"
                    />
                    <Input
                      data-testid={`mode-size-${idx}`}
                      type="number"
                      min="1"
                      value={mode.team_size}
                      onChange={e => {
                        const modes = [...newGame.modes];
                        modes[idx] = { ...modes[idx], team_size: parseInt(e.target.value) || 1 };
                        setNewGame({ ...newGame, modes });
                      }}
                      className="bg-zinc-900 border-white/10 text-white w-20"
                      placeholder="Größe"
                    />
                    {newGame.modes.length > 1 && (
                      <Button variant="ghost" size="sm" onClick={() => setNewGame({ ...newGame, modes: newGame.modes.filter((_, i) => i !== idx) })} className="text-red-500 px-2">
                        <XIcon className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={() => setNewGame({ ...newGame, modes: [...newGame.modes, { name: "", team_size: 1, description: "" }] })} className="mt-2 text-yellow-500 text-xs">
                  + Modus hinzufügen
                </Button>
              </div>
              <Button data-testid="submit-game-btn" onClick={handleCreateGame} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                Spiel erstellen
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
