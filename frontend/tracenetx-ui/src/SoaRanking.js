import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API = `${process.env.REACT_APP_API_URL}`;
const MONO = "'IBM Plex Mono', monospace";
const C = {
  gold: "#C9A84C", card: "#0D1220", border: "#1A2035", accent: "#151B2E",
  text: "#E2E8F0", muted: "#64748B", dim: "#94A3B8", crit: "#FF2D2D", high: "#FF6B00", med: "#FFB800", low: "#00C853",
};
const inr = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;
const short = (n) => (n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : inr(n));
const scoreColor = (s) => (s >= 65 ? C.crit : s >= 55 ? C.high : s >= 45 ? C.med : C.low);

function Detail({ id }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    setD(null);
    fetch(`${API}/soa/holder/${encodeURIComponent(id)}`).then((r) => r.json()).then(setD).catch(() => setD({ error: true }));
  }, [id]);
  if (!d) return <div style={{ padding: 16, color: C.muted, fontFamily: MONO }}>Loading…</div>;
  if (d.error || d.detail) return <div style={{ padding: 16, color: C.crit, fontFamily: MONO }}>Could not load detail.</div>;
  const sharedKeys = Object.keys(d.shares_counterparties_with || {});
  return (
    <div style={{ padding: 16, background: C.accent, borderTop: `1px solid ${C.border}`, display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>
      <div>
        <div style={{ color: C.gold, fontSize: "0.7em", letterSpacing: 1, fontFamily: MONO, marginBottom: 6 }}>MONTHLY MONEY IN vs OUT</div>
        {d.timestamps_usable && d.monthly.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.monthly}>
              <XAxis dataKey="month" tick={{ fill: C.muted, fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: C.muted, fontSize: 9 }} tickFormatter={short} width={56} />
              <Tooltip formatter={(v) => inr(v)} contentStyle={{ background: "#161b22", border: `1px solid ${C.border}` }} />
              <Legend />
              <Bar dataKey="in" fill={C.low} name="Money in" />
              <Bar dataKey="out" fill={C.crit} name="Money out" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: C.muted, fontSize: "0.75em", fontFamily: MONO }}>
            Timestamps in this holder's statement are not usable (scrambled dates), so no time chart is shown.
          </div>
        )}
      </div>
      <div style={{ fontFamily: MONO, fontSize: "0.72em", color: C.dim }}>
        <div style={{ color: C.gold, letterSpacing: 1, marginBottom: 6 }}>TOP COUNTERPARTIES</div>
        {d.top_counterparties.length === 0 && <div style={{ color: C.muted }}>No counterparty column in this statement (behaviour only).</div>}
        {d.top_counterparties.slice(0, 6).map((c) => (
          <div key={c.counterparty} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
            <span>{c.counterparty}</span><span style={{ color: C.text }}>{short(c.volume)} · {c.txns}×</span>
          </div>
        ))}
        <div style={{ color: C.gold, letterSpacing: 1, margin: "12px 0 6px" }}>CHANNELS</div>
        <div>{Object.entries(d.channels).map(([k, v]) => `${k} ${v.toLocaleString("en-IN")}`).join(" · ")}</div>
        {sharedKeys.length > 0 && (
          <div style={{ marginTop: 12, color: C.high }}>
            ⚠ Shares {d.shares_counterparties_with[sharedKeys[0]].toLocaleString("en-IN")} counterparties with {sharedKeys[0]}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SoaRanking() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    fetch(`${API}/soa/ranked`).then((r) => r.json()).then(setData).catch(() => setData({ available: false, holders: [], hint: "Backend not reachable." }));
  }, []);
  if (!data) return <div style={{ padding: 24, color: C.muted, fontFamily: MONO }}>Loading ranking…</div>;
  if (!data.available) {
    return (
      <div style={{ padding: 24, color: C.dim, fontFamily: MONO, fontSize: "0.85em" }}>
        No statement ranking found. {data.hint}
      </div>
    );
  }
  return (
    <div style={{ padding: 24, maxWidth: 1250, margin: "0 auto" }}>
      <div style={{ color: C.gold, fontFamily: MONO, fontSize: "1.1em", fontWeight: 700 }}>Mule-risk ranking · C-DAC statements</div>
      <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO, margin: "6px 0 16px", lineHeight: 1.6 }}>
        {data.holders.length} statement holders ranked by behaviour. Unsupervised: the dataset has no labels, so scores are relative
        percentile ranks among these accounts (not probabilities). Every score lists the rules that drove it.
      </div>
      {data.holders.map((h, i) => (
        <div key={h.holder} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, marginBottom: 8, overflow: "hidden" }}>
          <div onClick={() => setOpen(open === h.holder ? null : h.holder)}
               style={{ display: "grid", gridTemplateColumns: "34px 120px 150px 110px 110px 1fr", gap: 12, alignItems: "center", padding: "10px 14px", cursor: "pointer", fontFamily: MONO, fontSize: "0.75em" }}>
            <span style={{ color: C.muted }}>#{i + 1}</span>
            <span style={{ color: C.text, fontWeight: 700 }}>{h.holder}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ flex: 1, height: 6, background: C.accent, borderRadius: 3 }}>
                <span style={{ display: "block", width: `${h.risk_score}%`, height: "100%", background: scoreColor(h.risk_score), borderRadius: 3 }} />
              </span>
              <span style={{ color: scoreColor(h.risk_score), fontWeight: 700 }}>{h.risk_score}</span>
            </span>
            <span style={{ color: C.dim }}>in {short(h.total_in)}</span>
            <span style={{ color: C.dim }}>out {short(h.total_out)}</span>
            <span style={{ color: C.dim, fontSize: "0.95em" }}>
              {h.reasons}{h.graph_coverage !== "yes" && <span style={{ color: C.muted }}> · {h.graph_coverage}</span>}
            </span>
          </div>
          {open === h.holder && <Detail id={h.holder} />}
        </div>
      ))}
    </div>
  );
}
