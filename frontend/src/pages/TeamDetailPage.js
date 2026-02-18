import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Users, Trophy, Shield, Crown, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import SocialLinks from "@/components/SocialLinks";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function TeamDetailPage() {
  const { id } = useParams();
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [team, setTeam] = useState(null);
  const [subTeams, setSubTeams] = useState([]);
  const [tournaments, setTournaments] = useState([]);

  const fetchTeam = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/teams/${id}`);
      setTeam(res.data);
      
      // Main-team pages expose sub-teams publicly for better discoverability.
      if (!res.data.parent_team_id) {
        try {
          const subRes = await axios.get(`${API}/teams/${id}/sub-teams`);
          setSubTeams(Array.isArray(subRes.data) ? subRes.data : []);
        } catch {
          try {
            const publicRes = await axios.get(`${API}/teams/public`);
            const parentEntry = (Array.isArray(publicRes.data) ? publicRes.data : []).find((row) => row?.id === id);
            setSubTeams(Array.isArray(parentEntry?.sub_teams) ? parentEntry.sub_teams : []);
          } catch {
            setSubTeams([]);
          }
        }
      }
      
      // Fetch tournaments this team participated in
      const tournRes = await axios.get(`${API}/teams/${id}/tournaments`);
      setTournaments(Array.isArray(tournRes.data) ? tournRes.data : []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Team nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  const isOwner = user && team?.owner_id === user.id;
  const isMember = user && (team?.members || []).some(m => (m.id || m.user_id) === user.id);
  const canEdit = isAdmin || isOwner;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-zinc-500">Team wird geladen...</div>
      </div>
    );
  }

  if (!team) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Team nicht gefunden</h1>
          <Link to="/teams">
            <Button variant="outline">Zurück zu Teams</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="team-detail-page">
      {/* Banner & Profile Header */}
      <div className="relative mb-8">
        {/* Banner */}
        <div className="h-48 rounded-xl overflow-hidden bg-gradient-to-br from-zinc-900 to-zinc-800">
          {team.banner_url && (
            <img src={team.banner_url} alt="Banner" className="w-full h-full object-cover opacity-60" />
          )}
        </div>
        
        {/* Team Info */}
        <div className="relative -mt-16 px-6 flex flex-col sm:flex-row items-start sm:items-end gap-6">
          {/* Logo */}
          <div className="w-32 h-32 rounded-xl border-4 border-zinc-950 overflow-hidden bg-zinc-900 flex-shrink-0">
            {team.logo_url ? (
              <img src={team.logo_url} alt={team.name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Shield className="w-12 h-12 text-zinc-700" />
              </div>
            )}
          </div>
          
          {/* Name & Tag */}
          <div className="flex-1 pb-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white">
                {team.name}
              </h1>
              {team.tag && (
                <Badge className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 font-mono">
                  [{team.tag}]
                </Badge>
              )}
              {team.parent_team_id && (
                <Badge className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs">
                  Sub-Team
                </Badge>
              )}
            </div>
            <p className="text-zinc-500 mt-1 text-sm">
              {team.members?.length || 0} Mitglieder • Erstellt am {new Date(team.created_at).toLocaleDateString("de-DE")}
            </p>
          </div>
          
          {/* Actions */}
          <div className="flex gap-2">
            {canEdit && (
              <Link to="/teams">
                <Button variant="outline" className="border-white/10 text-white">
                  Im Team-Manager bearbeiten
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Social Links */}
      {(team.discord_url || team.twitter_url || team.instagram_url || team.twitch_url || team.youtube_url || team.website_url) && (
        <div className="mb-8">
          <SocialLinks entity={team} />
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="bg-zinc-950 border border-white/5 p-1">
          <TabsTrigger value="overview" className="data-[state=active]:bg-yellow-500 data-[state=active]:text-black">
            Übersicht
          </TabsTrigger>
          <TabsTrigger value="members" className="data-[state=active]:bg-yellow-500 data-[state=active]:text-black">
            Mitglieder
          </TabsTrigger>
          {!team.parent_team_id && (
            <TabsTrigger value="subteams" className="data-[state=active]:bg-yellow-500 data-[state=active]:text-black">
              Sub-Teams
            </TabsTrigger>
          )}
          <TabsTrigger value="tournaments" className="data-[state=active]:bg-yellow-500 data-[state=active]:text-black">
            Turniere
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Bio */}
            <div className="lg:col-span-2 glass rounded-xl p-6 border border-white/5">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase mb-4">
                Über das Team
              </h2>
              <div className="text-zinc-400 text-sm leading-relaxed whitespace-pre-wrap">
                {team.bio || "Keine Beschreibung vorhanden."}
              </div>
            </div>

            {/* Stats */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase">
                Statistiken
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500 flex items-center gap-2">
                    <Users className="w-4 h-4" /> Mitglieder
                  </span>
                  <span className="text-white font-bold">{team.members?.length || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500 flex items-center gap-2">
                    <Trophy className="w-4 h-4" /> Turniere
                  </span>
                  <span className="text-white font-bold">{tournaments.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-500 flex items-center gap-2">
                    <Shield className="w-4 h-4" /> Sub-Teams
                  </span>
                  <span className="text-white font-bold">{subTeams.length}</span>
                </div>
              </div>
              
              {team.join_code && (isMember || canEdit) && (
                <div className="border-t border-white/5 pt-4 mt-4">
                  <p className="text-xs text-zinc-500 mb-2">Beitrittscode</p>
                  <code className="block p-3 bg-zinc-900 rounded-lg text-yellow-500 font-mono text-sm">
                    {team.join_code}
                  </code>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members">
          <div className="glass rounded-xl border border-white/5 overflow-hidden">
            <div className="p-4 border-b border-white/5">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase">
                Team-Mitglieder ({team.members?.length || 0})
              </h2>
            </div>
            <div className="divide-y divide-white/5">
              {(team.members || []).map((member) => (
                <div key={member.id || member.user_id || member.username} className="p-4 flex items-center gap-4 hover:bg-white/[0.02] transition-colors">
                  <img
                    src={member.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${member.username}`}
                    alt={member.username}
                    className="w-12 h-12 rounded-lg object-cover bg-zinc-900"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{member.username}</span>
                      {(member.id || member.user_id) === team.owner_id && (
                        <Badge className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 text-xs">
                          <Crown className="w-3 h-3 mr-1" /> Owner
                        </Badge>
                      )}
                      {(team.leader_ids || []).includes(member.id || member.user_id) && (member.id || member.user_id) !== team.owner_id && (
                        <Badge className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs">
                          Leader
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-zinc-500">
                      Beigetreten: {member.joined_at ? new Date(member.joined_at).toLocaleDateString("de-DE") : "-"}
                    </p>
                  </div>
                  <Link to={`/profile/${member.id || member.user_id}`}>
                    <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-white">
                      <User className="w-4 h-4" />
                    </Button>
                  </Link>
                </div>
              ))}
              {(!team.members || team.members.length === 0) && (
                <div className="p-8 text-center text-zinc-500">
                  Keine Mitglieder
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Sub-Teams Tab */}
        {!team.parent_team_id && (
          <TabsContent value="subteams">
            <div className="glass rounded-xl border border-white/5 overflow-hidden">
              <div className="p-4 border-b border-white/5 flex items-center justify-between">
                <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase">
                  Sub-Teams ({subTeams.length})
                </h2>
                {canEdit && (
                  <Link to="/teams">
                    <Button size="sm" className="bg-yellow-500 text-black hover:bg-yellow-400">
                      Sub-Team im Team-Manager erstellen
                    </Button>
                  </Link>
                )}
              </div>
              <div className="divide-y divide-white/5">
                {subTeams.map((sub) => (
                  <Link key={sub.id} to={`/teams/${sub.id}`} className="block p-4 hover:bg-white/[0.02] transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-lg overflow-hidden bg-zinc-900 flex items-center justify-center">
                        {sub.logo_url ? (
                          <img src={sub.logo_url} alt={sub.name} className="w-full h-full object-cover" />
                        ) : (
                          <Shield className="w-6 h-6 text-zinc-700" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{sub.name}</span>
                          {sub.tag && (
                            <span className="text-xs text-zinc-500 font-mono">[{sub.tag}]</span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500">{sub.members?.length || 0} Mitglieder</p>
                      </div>
                    </div>
                  </Link>
                ))}
                {subTeams.length === 0 && (
                  <div className="p-8 text-center text-zinc-500">
                    Keine Sub-Teams vorhanden
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        )}

        {/* Tournaments Tab */}
        <TabsContent value="tournaments">
          <div className="glass rounded-xl border border-white/5 overflow-hidden">
            <div className="p-4 border-b border-white/5">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase">
                Turnier-Teilnahmen ({tournaments.length})
              </h2>
            </div>
            <div className="divide-y divide-white/5">
              {tournaments.map((t) => (
                <Link key={t.id} to={`/tournaments/${t.id}`} className="block p-4 hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-white font-medium">{t.name}</div>
                      <p className="text-xs text-zinc-500">{t.game_name} • {t.bracket_type?.replace("_", " ")}</p>
                    </div>
                    <Badge className={`text-xs ${
                      t.status === "completed" ? "bg-green-500/10 text-green-400" :
                      t.status === "live" ? "bg-red-500/10 text-red-400" :
                      "bg-zinc-500/10 text-zinc-400"
                    }`}>
                      {t.status === "completed" ? "Abgeschlossen" : t.status === "live" ? "LIVE" : t.status}
                    </Badge>
                  </div>
                </Link>
              ))}
              {tournaments.length === 0 && (
                <div className="p-8 text-center text-zinc-500">
                  Noch keine Turnier-Teilnahmen
                </div>
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
