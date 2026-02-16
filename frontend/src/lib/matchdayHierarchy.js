const STATUS_LABELS = {
  pending: "Geplant",
  in_progress: "Aktiv",
  completed: "Abgeschlossen",
};

const toInt = (value, fallback = 0) => {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeStatus = (value) => {
  const status = String(value || "").trim().toLowerCase();
  return STATUS_LABELS[status] ? status : "pending";
};

const statusLabel = (value) => STATUS_LABELS[normalizeStatus(value)] || STATUS_LABELS.pending;

const formatDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("de-DE");
};

const formatRange = (start, end) => {
  const a = formatDate(start);
  const b = formatDate(end);
  if (!a || !b) return "";
  return `${a} - ${b}`;
};

const toIsoWeekData = (value) => {
  if (!value) return null;
  const raw = new Date(value);
  if (Number.isNaN(raw.getTime())) return null;
  const anchor = new Date(Date.UTC(raw.getUTCFullYear(), raw.getUTCMonth(), raw.getUTCDate()));
  const day = anchor.getUTCDay() || 7;
  const monday = new Date(anchor);
  monday.setUTCDate(anchor.getUTCDate() - day + 1);
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  const thursday = new Date(anchor);
  thursday.setUTCDate(anchor.getUTCDate() + 4 - day);
  const isoYear = thursday.getUTCFullYear();
  const yearStart = new Date(Date.UTC(isoYear, 0, 1));
  const isoWeek = Math.ceil((((thursday - yearStart) / 86400000) + 1) / 7);
  return {
    isoYear,
    isoWeek,
    weekId: `${isoYear}-KW${String(isoWeek).padStart(2, "0")}`,
    weekName: `KW ${String(isoWeek).padStart(2, "0")}`,
    weekRangeStart: monday.toISOString(),
    weekRangeEnd: sunday.toISOString(),
    weekRangeLabel: formatRange(monday.toISOString(), sunday.toISOString()),
  };
};

const getMatchdayAnchor = (day) => {
  if (day?.window_start) return day.window_start;
  const scheduled = (day?.matches || []).find((m) => m?.scheduled_for)?.scheduled_for;
  return scheduled || null;
};

const normalizeMatchday = (day) => {
  const status = normalizeStatus(day?.status);
  const anchor = getMatchdayAnchor(day);
  const iso = toIsoWeekData(anchor);
  const isoWeek = toInt(day?.iso_week, iso?.isoWeek || 0);
  const isoYear = toInt(day?.iso_year, iso?.isoYear || 0);
  const weekId = String(day?.week_id || iso?.weekId || "");
  const weekName = String(day?.week_name || iso?.weekName || (isoWeek ? `KW ${String(isoWeek).padStart(2, "0")}` : "KW"));
  const weekRangeStart = String(day?.week_range_start || iso?.weekRangeStart || "");
  const weekRangeEnd = String(day?.week_range_end || iso?.weekRangeEnd || "");
  const weekRangeLabel = String(day?.week_range_label || iso?.weekRangeLabel || formatRange(weekRangeStart, weekRangeEnd));

  return {
    ...day,
    matchday: toInt(day?.matchday, 0),
    status,
    status_label: String(day?.status_label || statusLabel(status)),
    window_label: String(day?.window_label || formatRange(day?.window_start, day?.window_end)),
    iso_week: isoWeek,
    iso_year: isoYear,
    week_id: weekId,
    week_name: weekName,
    week_range_start: weekRangeStart,
    week_range_end: weekRangeEnd,
    week_range_label: weekRangeLabel,
    week_label: String(day?.week_label || (weekRangeLabel ? `${weekName} (${weekRangeLabel})` : weekName)),
    total_matches: toInt(day?.total_matches, Array.isArray(day?.matches) ? day.matches.length : 0),
    completed_matches: toInt(day?.completed_matches, 0),
    disputed_matches: toInt(day?.disputed_matches, 0),
    scheduled_matches: toInt(day?.scheduled_matches, 0),
    matches: Array.isArray(day?.matches) ? day.matches : [],
  };
};

const aggregateStatus = (items) => {
  const statuses = (items || []).map((entry) => normalizeStatus(entry?.status));
  if (statuses.length > 0 && statuses.every((s) => s === "completed")) return "completed";
  if (statuses.some((s) => s === "in_progress" || s === "completed")) return "in_progress";
  return "pending";
};

const normalizeWeek = (week) => {
  const days = Array.isArray(week?.matchdays) ? week.matchdays.map(normalizeMatchday).sort((a, b) => a.matchday - b.matchday) : [];
  const status = normalizeStatus(week?.status || aggregateStatus(days));
  const rangeStart = String(week?.range_start || days[0]?.week_range_start || "");
  const rangeEnd = String(week?.range_end || days[0]?.week_range_end || "");
  const rangeLabel = String(week?.range_label || formatRange(rangeStart, rangeEnd) || days[0]?.week_range_label || "");
  const isoWeek = toInt(week?.iso_week, days[0]?.iso_week || 0);
  const isoYear = toInt(week?.iso_year, days[0]?.iso_year || 0);
  const name = String(week?.name || (isoWeek ? `KW ${String(isoWeek).padStart(2, "0")}` : "KW"));
  return {
    ...week,
    id: String(week?.id || days[0]?.week_id || `${isoYear}-KW${String(isoWeek).padStart(2, "0")}`),
    name,
    iso_week: isoWeek,
    iso_year: isoYear,
    range_start: rangeStart,
    range_end: rangeEnd,
    range_label: rangeLabel,
    label: String(week?.label || (rangeLabel ? `${name} (${rangeLabel})` : name)),
    status,
    status_label: String(week?.status_label || statusLabel(status)),
    matchdays: days,
    matchday_count: toInt(week?.matchday_count, days.length),
    total_matches: toInt(week?.total_matches, days.reduce((acc, day) => acc + toInt(day.total_matches, 0), 0)),
    completed_matches: toInt(week?.completed_matches, days.reduce((acc, day) => acc + toInt(day.completed_matches, 0), 0)),
    disputed_matches: toInt(week?.disputed_matches, days.reduce((acc, day) => acc + toInt(day.disputed_matches, 0), 0)),
    scheduled_matches: toInt(week?.scheduled_matches, days.reduce((acc, day) => acc + toInt(day.scheduled_matches, 0), 0)),
  };
};

const sortWeeks = (weeks) => {
  return [...weeks].sort((a, b) => {
    if (a.iso_year !== b.iso_year) return a.iso_year - b.iso_year;
    return a.iso_week - b.iso_week;
  });
};

const buildWeeksFromMatchdays = (matchdays) => {
  const map = new Map();
  (matchdays || []).forEach((day) => {
    const entry = normalizeMatchday(day);
    const key = entry.week_id || `${entry.iso_year}-KW${String(entry.iso_week).padStart(2, "0")}`;
    if (!map.has(key)) {
      map.set(key, {
        id: key,
        name: entry.week_name,
        iso_year: entry.iso_year,
        iso_week: entry.iso_week,
        range_start: entry.week_range_start,
        range_end: entry.week_range_end,
        range_label: entry.week_range_label,
        label: entry.week_label,
        matchdays: [],
      });
    }
    map.get(key).matchdays.push(entry);
  });
  return sortWeeks([...map.values()].map(normalizeWeek));
};

export const buildMatchdayHierarchy = (payload) => {
  const responseHierarchy = payload?.hierarchy || payload?.matchday_hierarchy || {};
  const payloadMatchdays = Array.isArray(payload?.matchdays) ? payload.matchdays : [];

  const weeksSource = Array.isArray(responseHierarchy?.weeks) && responseHierarchy.weeks.length > 0
    ? responseHierarchy.weeks
    : buildWeeksFromMatchdays(payloadMatchdays);
  const weeks = sortWeeks(weeksSource.map(normalizeWeek));
  const matchdays = Array.isArray(responseHierarchy?.matchdays) && responseHierarchy.matchdays.length > 0
    ? responseHierarchy.matchdays.map(normalizeMatchday).sort((a, b) => a.matchday - b.matchday)
    : weeks.flatMap((week) => week.matchdays);

  const seasonStatus = normalizeStatus(responseHierarchy?.season?.status || aggregateStatus(weeks));
  const seasonStart = String(responseHierarchy?.season?.start || weeks[0]?.range_start || "");
  const seasonEnd = String(responseHierarchy?.season?.end || weeks[weeks.length - 1]?.range_end || "");
  let seasonName = String(responseHierarchy?.season?.name || "");
  if (!seasonName && seasonStart && seasonEnd) {
    const startYear = new Date(seasonStart).getUTCFullYear();
    const endYear = new Date(seasonEnd).getUTCFullYear();
    seasonName = startYear === endYear ? `Saison ${startYear}` : `Saison ${startYear}/${endYear}`;
  }
  if (!seasonName) seasonName = "Saison";

  return {
    season: {
      ...(responseHierarchy?.season || {}),
      name: seasonName,
      status: seasonStatus,
      status_label: String(responseHierarchy?.season?.status_label || statusLabel(seasonStatus)),
      start: seasonStart,
      end: seasonEnd,
    },
    weeks,
    matchdays,
    summary: {
      week_count: toInt(responseHierarchy?.summary?.week_count, weeks.length),
      matchday_count: toInt(responseHierarchy?.summary?.matchday_count, matchdays.length),
      match_count: toInt(
        responseHierarchy?.summary?.match_count,
        matchdays.reduce((acc, day) => acc + toInt(day.total_matches, 0), 0),
      ),
    },
  };
};

export const matchdayStatusBadgeClass = (status) => {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "bg-green-500/10 text-green-400 border border-green-500/20";
  if (normalized === "in_progress") return "bg-blue-500/10 text-blue-400 border border-blue-500/20";
  return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
};

export { normalizeStatus, statusLabel };
