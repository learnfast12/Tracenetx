import React, { useState, useEffect, useRef } from "react";
import Timeline from "./Timeline";

const COLORS = {
  critical: "#FF2D2D", high: "#FF6B00", medium: "#FFB800", low: "#00C853",
  gold: "#C9A84C", navy: "#0A0E1A", navyCard: "#0D1220", navyBorder: "#1A2035",
  navyAccent: "#151B2E", text: "#E2E8F0", textMuted: "#64748B", textDim: "#94A3B8",
};
const API = `${process.env.REACT_APP_API_URL}`;
const MONO = "'IBM Plex Mono', monospace";
const tierColor = (t) => ({ CRITICAL: COLORS.critical, HIGH: COLORS.high, MEDIUM: COLORS.medium }[t] || COLORS.low);
const inr = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;

const Stat = ({ label, value, color }) => (
  <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: 8, padding: "12px 16px", minWidth: 150 }}>
    <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: 1, textTransform: "uppercase", fontFamily: MONO }}>{label}</div>
    <div style={{ color: color || COLORS.gold, fontSize: "1.4em", fontWeight: 700, fontFamily: MONO }}>{value}</div>
  </div>
);

const Bar = ({ label, value, color }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.7em", color: COLORS.textDim, fontFamily: MONO }}>
    <span style={{ width: 74 }}>{label}</span>
    <div style={{ flex: 1, height: 6, background: COLORS.navyAccent, borderRadius: 3 }}>
      <div style={{ width: `${Math.min(value, 100)}%`, height: "100%", background: color, borderRadius: 3 }} />
    </div>
    <span style={{ width: 28, textAlign: "right" }}>{Math.round(value)}</span>
  </div>
);

function Investigation({ onOpenEvidence, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [timelineFor, setTimelineFor] = useState(null);
  const fileRef = useRef(null);

  const load = async () => {
    try {
      setError(null);
      const res = await fetch(`${API}/investigation/priority?top=20`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setData(await res.json());
    } catch (e) { setError(e.message); }
  };
  useEffect(() => { load(); }, [refreshKey]);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/complaints/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
      await load();
    } catch (e) { setError(e.message); }
    setUploading(false);
  };

  if (error && !data) return <div style={{ padding: 24, color: COLORS.critical, fontFamily: MONO }}>Could not load investigation view: {error}</div>;
  if (!data) return <div style={{ padding: 24, color: COLORS.textMuted, fontFamily: MONO }}>Correlating complaints with the transaction graph…</div>;

  const s = data.complaint_stats || {};
  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24, background: COLORS.navy }}>
      {timelineFor && <Timeline accountId={timelineFor} onClose={() => setTimelineFor(null)} />}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <div>
          <div style={{ color: COLORS.gold, fontSize: "1.1em", fontWeight: 700, fontFamily: MONO }}>INVESTIGATION · PRIORITISED LEADS</div>
          <div style={{ color: COLORS.textMuted, fontSize: "0.75em" }}>
            Priority = {Math.round(data.weights.ml * 100)}% ML risk + {Math.round(data.weights.complaints * 100)}% complaint correlation + {Math.round(data.weights.baseline * 100)}% baseline deviation. Every score is shown, nothing is hidden.
          </div>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <input ref={fileRef} type="file" accept=".csv" style={{ display: "none" }} onChange={(e) => upload(e.target.files[0])} />
          <button onClick={() => fileRef.current.click()} disabled={uploading} style={{
            background: "transparent", color: COLORS.gold, border: `1px solid ${COLORS.gold}`, borderRadius: 6,
            padding: "8px 14px", cursor: "pointer", fontFamily: MONO, fontSize: "0.75em",
          }}>{uploading ? "Uploading…" : "Upload complaints CSV"}</button>
        </div>
      </div>
      {error && <div style={{ color: COLORS.critical, fontSize: "0.8em", marginBottom: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <Stat label="Complaints" value={s.complaints ?? 0} />
        <Stat label="Distinct victims" value={s.distinct_victims ?? 0} />
        <Stat label="Reported loss" value={inr(s.total_reported_loss)} color={COLORS.critical} />
        <Stat label="Incident clusters" value={(data.incident_clusters || []).length} />
        <Stat label="Funds-consistent" value={`${Math.round((s.funds_consistent_share || 0) * 100)}%`} color={COLORS.low} />
      </div>

      <div style={{ color: COLORS.textDim, fontSize: "0.7em", letterSpacing: 1, fontFamily: MONO, marginBottom: 8 }}>TOP INVESTIGATIVE LEADS</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 12, marginBottom: 24 }}>
        {data.leads.map((l, i) => (
          <div key={l.account_id} style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `3px solid ${tierColor(l.priority_tier)}`, borderRadius: 8, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: COLORS.textMuted, fontFamily: MONO, fontSize: "0.8em" }}>#{i + 1}</span>
              <span style={{ color: COLORS.text, fontWeight: 700, fontFamily: MONO }}>{l.account_id}</span>
              <span style={{ color: COLORS.textMuted, fontSize: "0.7em", fontFamily: MONO }}>{l.role}</span>
              <span style={{ marginLeft: "auto", color: tierColor(l.priority_tier), fontWeight: 700, fontFamily: MONO }}>{l.priority_score} · {l.priority_tier}</span>
            </div>
            <div style={{ margin: "10px 0", display: "grid", gap: 4 }}>
              <Bar label="ML risk" value={l.sub_scores.ml} color={COLORS.high} />
              <Bar label="Complaints" value={l.sub_scores.complaints} color={COLORS.critical} />
              <Bar label="Baseline" value={l.sub_scores.baseline} color={COLORS.medium} />
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, color: COLORS.textDim, fontSize: "0.78em", lineHeight: 1.5 }}>
              {l.reasons.slice(0, 4).map((r, j) => <li key={j}>{r}</li>)}
            </ul>
            <button onClick={() => setTimelineFor(l.account_id)} style={{
              marginTop: 10, marginRight: 8, background: COLORS.navyAccent, color: COLORS.gold, border: `1px solid ${COLORS.navyBorder}`,
              borderRadius: 6, padding: "6px 12px", cursor: "pointer", fontFamily: MONO, fontSize: "0.72em",
            }}>Timeline + money trail →</button>
            {onOpenEvidence && (
              <button onClick={() => onOpenEvidence(l.account_id)} style={{
                marginTop: 10, background: COLORS.navyAccent, color: COLORS.gold, border: `1px solid ${COLORS.navyBorder}`,
                borderRadius: 6, padding: "6px 12px", cursor: "pointer", fontFamily: MONO, fontSize: "0.72em",
              }}>Open evidence package →</button>
            )}
          </div>
        ))}
      </div>

      <div style={{ color: COLORS.textDim, fontSize: "0.7em", letterSpacing: 1, fontFamily: MONO, marginBottom: 8 }}>INCIDENT CLUSTERS</div>
      <div style={{ display: "grid", gap: 10 }}>
        {(data.incident_clusters || []).map((c) => (
          <div key={c.cluster_id} style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: 8, padding: 14 }}>
            <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ color: COLORS.gold, fontWeight: 700, fontFamily: MONO }}>{c.cluster_id}</span>
              <span style={{ color: COLORS.textDim, fontSize: "0.8em" }}>{c.complaints} complaints · {c.distinct_victims} victims · {inr(c.total_loss)} · {c.accounts.length} accounts</span>
              {c.likely_collector && (
                <span style={{ color: COLORS.critical, fontSize: "0.8em", fontFamily: MONO }}>
                  Likely collector: {c.likely_collector.account} (fed by {c.likely_collector.fed_by_complained_accounts} complained accounts)
                </span>
              )}
            </div>
            <a href={`${API}/report/incident/${c.cluster_id}`} target="_blank" rel="noreferrer" style={{
              float: "right", color: COLORS.gold, border: `1px solid ${COLORS.navyBorder}`, borderRadius: 6,
              padding: "4px 10px", fontFamily: MONO, fontSize: "0.72em", textDecoration: "none",
            }}>Incident report (PDF) →</a>
            <div style={{ color: COLORS.textMuted, fontSize: "0.72em", marginTop: 6 }}>
              {c.fraud_types.join(" · ")}{c.shared_phones.length ? ` · shared scammer phones: ${c.shared_phones.length}` : ""}
            </div>
          </div>
        ))}
      </div>

      {(data.unmatched_complaint_accounts || []).length > 0 && (
        <div style={{ marginTop: 18, color: COLORS.medium, fontSize: "0.78em" }}>
          Complaints reference accounts not present in the transaction data: {data.unmatched_complaint_accounts.join(", ")}. Request statements from the holding bank to extend the trail.
        </div>
      )}
    </div>
  );
}

export default Investigation;
