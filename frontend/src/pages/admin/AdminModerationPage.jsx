import { useCallback, useEffect, useState } from "react";
import { AdminLayout } from "@/components/tls/AdminLayout";
import { api, formatRequestError } from "@/lib/api";
import { toast } from "sonner";

const STATUS = ["open", "reviewing", "resolved", "dismissed"];
const STATUS_LABEL = { open: "Offen", reviewing: "In Prüfung", resolved: "Erledigt", dismissed: "Verworfen" };

export default function AdminModerationPage() {
  const [reports, setReports] = useState([]);
  const [filter, setFilter] = useState("open");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/moderation/reports${filter ? `?status=${filter}` : ""}`);
      setReports(data || []);
    } catch (error) {
      toast.error(formatRequestError(error, "Meldungen konnten nicht geladen werden."));
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const update = async (report, status) => {
    setBusy(report.id);
    try {
      await api.patch(`/moderation/reports/${report.id}`, { status, resolution_note: null });
      toast.success("Moderationsstatus gespeichert.");
      await load();
    } catch (error) {
      toast.error(formatRequestError(error, "Status konnte nicht gespeichert werden."));
    } finally {
      setBusy("");
    }
  };

  return (
    <AdminLayout>
      <span className="text-[11px] font-bold uppercase tracking-[0.3em] text-[#29B6E8]">Community Safety</span>
      <h1 className="font-heading text-3xl md:text-4xl font-black uppercase mt-1 mb-6">Moderation</h1>
      <div className="flex flex-wrap gap-2 mb-5">
        <button type="button" onClick={() => setFilter("")} className={`px-3 py-2 border rounded-sm text-xs font-bold uppercase ${!filter ? "border-[#29B6E8] text-[#29B6E8]" : "border-white/10 text-white/55"}`}>Alle</button>
        {STATUS.map((status) => <button key={status} type="button" onClick={() => setFilter(status)} className={`px-3 py-2 border rounded-sm text-xs font-bold uppercase ${filter === status ? "border-[#29B6E8] text-[#29B6E8]" : "border-white/10 text-white/55"}`}>{STATUS_LABEL[status]}</button>)}
      </div>
      <div className="space-y-3">
        {reports.map((report) => (
          <article key={report.id} className="border border-white/10 bg-[#121212] rounded-sm p-4">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-[#FFD700]">{report.category} · {STATUS_LABEL[report.status] || report.status}</div>
                <div className="mt-1 text-sm text-white/80 whitespace-pre-wrap">{report.details}</div>
                <div className="mt-2 text-[11px] text-white/35">Meldung {report.id} · Ziel {report.target_user_id}{report.message_id ? ` · Nachricht ${report.message_id}` : ""} · {report.created_at && new Date(report.created_at).toLocaleString("de-DE")}</div>
              </div>
              <select value={report.status} disabled={busy === report.id} onChange={(event) => update(report, event.target.value)} className="h-10 bg-black/40 border border-white/10 px-3 text-sm">
                {STATUS.map((status) => <option key={status} value={status}>{STATUS_LABEL[status]}</option>)}
              </select>
            </div>
          </article>
        ))}
        {reports.length === 0 && <div className="border border-dashed border-white/10 p-10 text-center text-white/40">Keine Meldungen in diesem Status.</div>}
      </div>
    </AdminLayout>
  );
}
