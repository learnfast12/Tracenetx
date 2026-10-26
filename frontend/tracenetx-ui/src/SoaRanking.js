import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API = `${process.env.REACT_APP_API_URL}`;
const MONO = "'IBM Plex Mono', monospace";
const C = {
  gold: "#C9A84C", card: "#0D1220", border: "#1A2035", accent: "#151B2E",
  text: "#E2E8F0", muted: "#64748B", dim: "#94A3B8", crit: "#FF2D2D", high: "#FF6B00", med: "#FFB800", low: "#00C853",
  inColor: "#2ECC71", outColor: "#FF6B6B",
};
const SIGNAL_COLOR = {
  passthrough: "#C9A84C", fast_dwell: "#5BC0BE", fan: "#7C9CFF", burst: "#FF8A8A", round: "#B48EAD", shared: "#F2A65A",
};
const inr = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;
const short = (n) => (n >= 1e7 ? `₹${(n / 1e7).toFixed(1)} Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)} L` : inr(n));
const scoreColor = (s) => (s >= 65 ? C.crit : s >= 55 ? C.high : s >= 45 ? C.med : C.low);
const tail = (id) => (String(id).length > 6 ? `…${String(id).slice(-4)}` : String(id));

const Kpi = ({ label, value, sub, color }) => (
  <div style={{ flex: 1, minWidth: 150, background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px 16px" }}>
    <div style={{ color: C.muted, fontSize: "0.62em", letterSpacing: 1, textTransform: "uppercase", fontFamily: MONO }}>{label}</div>
    <div style={{ color: color || C.gold, fontSize: "1.5em", fontWeight: 700, fontFamily: MONO, lineHeight: 1.2 }}>{value}</div>
    {sub && <div style={{ color: C.muted, fontSize: "0.62em", fontFamily: MONO }}>{sub}</div>}
  </div>
);

const SectionTitle = ({ children }) => (
  <div style={{ color: C.gold, fontSize: "0.68em", letterSpacing: 1.5, fontFamily: MONO, textTransform: "uppercase", margin: "0 0 8px" }}>{children}</div>
);

/* stacked bar: each signal's points, so the score can be read at a glance */
function ContribBar({ contributions, height = 8 }) {
  return (
    <div style={{ display: "flex", height, background: C.accent, borderRadius: 4, overflow: "hidden", width: "100%" }}>
      {contributions.filter((c) => c.points != null).map((c) => (
        <div key={c.key} title={`${c.label}: ${c.points.toFixed(1)} pts`} style={{ width: `${c.points}%`, background: SIGNAL_COLOR[c.key] }} />
      ))}
    </div>
  );
}

function Breakdown({ contributions }) {
  const max = Math.max(...contributions.map((c) => c.points || 0), 1);
  return (
    <div>
      {contributions.map((c) => (
        <div key={c.key} style={{ display: "grid", gridTemplateColumns: "150px 1fr 120px", gap: 8, alignItems: "center", fontFamily: MONO, fontSize: "0.7em", color: C.dim, padding: "3px 0" }}>
          <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: SIGNAL_COLOR[c.key], marginRight: 6 }} />{c.label}</span>
          <span style={{ height: 6, background: C.accent, borderRadius: 3 }}>
            <span style={{ display: "block", height: "100%", width: `${((c.points || 0) / max) * 100}%`, background: SIGNAL_COLOR[c.key], borderRadius: 3 }} />
          </span>
          <span style={{ color: c.points == null ? C.muted : C.text, textAlign: "right" }}>{c.points == null ? `n/a · +${c.neutral_points} neutral` : `${c.points.toFixed(1)} pts`}</span>
        </div>
      ))}
      <div style={{ color: C.muted, fontSize: "0.62em", fontFamily: MONO, marginTop: 6 }}>
        Points add up to the score. Weights: {contributions.map((c) => `${c.label} ${Math.round(c.weight * 100)}%`).join(" · ")}.
        {contributions.some((c) => c.points == null) && " n/a = signal not available for this statement; it counts as neutral (50th percentile) so the holder is not ranked above accounts with full evidence."}
      </div>
    </div>
  );
}

/* radial network: the holder in the middle, its biggest counterparties around it, linked holders on the right */
function Network({ net }) {
  const W = 640, H = 340, cx = 250, cy = 170;
  const holder = net.nodes.find((n) => n.kind === "holder");
  const cps = net.nodes.filter((n) => n.kind === "counterparty");
  const linked = net.nodes.filter((n) => n.kind === "linked");
  const maxVol = Math.max(...cps.map((n) => n.volume || 0), 1);
  const pos = { [holder.id]: { x: cx, y: cy } };
  cps.forEach((n, i) => {
    const a = (-Math.PI / 2) + (2 * Math.PI * i) / Math.max(cps.length, 1);
    pos[n.id] = { x: cx + 190 * Math.cos(a), y: cy + 135 * Math.sin(a) };
  });
  linked.forEach((n, i) => { pos[n.id] = { x: 590, y: cy + (i - (linked.length - 1) / 2) * 90 }; });
  const volOf = (id) => (net.nodes.find((n) => n.id === id) || {}).volume || 0;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", background: "#0A0F1C", border: `1px solid ${C.border}`, borderRadius: 8 }} role="img" aria-label="Counterparty network">
      {net.edges.map((e, i) => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return null;
        if (e.shared) {
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={C.high} strokeWidth={4} strokeDasharray="6 4" />
              <text x={(a.x + b.x) / 2 + 20} y={(a.y + b.y) / 2 - 8} fill={C.high} fontSize="11" fontFamily="monospace">{e.shared.toLocaleString("en-IN")} shared</text>
            </g>
          );
        }
        const incoming = e.target === holder.id;
        const other = incoming ? e.source : e.target;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={incoming ? C.inColor : C.outColor}
                     strokeOpacity="0.8" strokeWidth={1 + 5 * (volOf(other) / maxVol)} />;
      })}
      {cps.map((n) => (
        <g key={n.id}>
          <circle cx={pos[n.id].x} cy={pos[n.id].y} r={n.shared ? 11 : 8} fill={n.shared ? C.high : "#2A3552"} stroke={n.shared ? "#FFD2A8" : "#4A5878"} strokeWidth="1.5">
            <title>{`${n.id}: ${short(n.volume)}${n.shared ? " (also used by another holder)" : ""}`}</title>
          </circle>
          <text x={pos[n.id].x} y={pos[n.id].y + 22} fill={C.dim} fontSize="10" fontFamily="monospace" textAnchor="middle">{tail(n.id)}</text>
        </g>
      ))}
      {linked.map((n) => (
        <g key={n.id}>
          <circle cx={pos[n.id].x} cy={pos[n.id].y} r={20} fill="#3A1010" stroke={C.crit} strokeWidth="2"><title>{`Linked holder ${n.id}`}</title></circle>
          <text x={pos[n.id].x} y={pos[n.id].y + 36} fill={C.text} fontSize="10" fontFamily="monospace" textAnchor="middle">{n.id}</text>
        </g>
      ))}
      <circle cx={cx} cy={cy} r={28} fill={C.gold} stroke="#F3E3B0" strokeWidth="2" />
      <text x={cx} y={cy + 4} fill="#0A0E1A" fontSize="10" fontWeight="700" fontFamily="monospace" textAnchor="middle">{holder.id.replace("H_", "")}</text>
    </svg>
  );
}

function Detail({ id, fallback }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    setD(null);
    fetch(`${API}/soa/holder/${encodeURIComponent(id)}`).then((r) => r.json()).then(setD).catch(() => setD({ error: true }));
  }, [id]);
  if (!d) return <div style={{ padding: 16, color: C.muted, fontFamily: MONO }}>Loading…</div>;
  if (d.error || d.detail) return <div style={{ padding: 16, color: C.crit, fontFamily: MONO }}>Could not load detail.</div>;
  const pt = d.pass_through || { events: [] };
  const sharedKeys = Object.keys(d.shares_counterparties_with || {});
  return (
    <div style={{ padding: 16, background: C.accent, borderTop: `1px solid ${C.border}`, display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div>
          <SectionTitle>Why this score</SectionTitle>
          <Breakdown contributions={d.contributions && d.contributions.length ? d.contributions : fallback} />
        </div>
        <div>
          <SectionTitle>Money trail · credits passed on within {pt.window_hours || 6} h</SectionTitle>
          {pt.share_of_credits != null && (
            <div style={{ color: C.dim, fontSize: "0.72em", fontFamily: MONO, marginBottom: 6 }}>
              {(pt.share_of_credits * 100).toFixed(1)}% of credits are followed by a debit of about the same size (±10%) inside that window.
              Totals can balance without this being high, so read both numbers.
            </div>
          )}
          {pt.events.length === 0 ? (
            <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO }}>No matching events, or timestamps are not usable for this statement.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: MONO, fontSize: "0.68em", color: C.dim }}>
              <thead><tr style={{ color: C.muted, textAlign: "left" }}><th>Credit</th><th>Amount</th><th>Debit</th><th>Amount</th><th>Gap</th></tr></thead>
              <tbody>
                {pt.events.slice(0, 6).map((e, i) => (
                  <tr key={i} style={{ borderTop: `1px solid ${C.border}` }}>
                    <td>{e.in_ts}</td><td style={{ color: C.inColor }}>{short(e.in_amt)}</td>
                    <td>{e.out_ts}</td><td style={{ color: C.outColor }}>{short(e.out_amt)}</td><td style={{ color: C.text }}>{e.hours} h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div>
          <SectionTitle>Monthly money in vs out</SectionTitle>
          {d.timestamps_usable && d.monthly.length > 0 ? (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={d.monthly}>
                <XAxis dataKey="month" tick={{ fill: C.muted, fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis tick={{ fill: C.muted, fontSize: 9 }} tickFormatter={short} width={60} />
                <Tooltip formatter={(v) => inr(v)} contentStyle={{ background: "#161b22", border: `1px solid ${C.border}` }} />
                <Legend wrapperStyle={{ fontFamily: MONO, fontSize: 11 }} />
                <Bar dataKey="in" fill={C.inColor} name="Money in" />
                <Bar dataKey="out" fill={C.outColor} name="Money out" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO }}>
              Timestamps in this statement are not usable (scrambled dates), so no time chart is shown.
            </div>
          )}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <SectionTitle>Counterparty network</SectionTitle>
          {d.network.nodes.length > 1 ? (
            <>
              <Network net={d.network} />
              <div style={{ color: C.muted, fontSize: "0.62em", fontFamily: MONO, marginTop: 4 }}>
                <span style={{ color: C.inColor }}>green</span> = money in · <span style={{ color: C.outColor }}>red</span> = money out ·
                <span style={{ color: C.high }}> orange</span> = also used by another holder · line width = volume
              </div>
            </>
          ) : (
            <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO }}>No counterparty column in this statement (behaviour only).</div>
          )}
        </div>
        {sharedKeys.length > 0 && (
          <div style={{ background: "#2A1608", border: `1px solid ${C.high}`, borderRadius: 8, padding: "8px 12px", color: "#FFD2A8", fontFamily: MONO, fontSize: "0.72em" }}>
            ⚠ Shares {d.shares_counterparties_with[sharedKeys[0]].toLocaleString("en-IN")} counterparties with {sharedKeys[0]}. Treat as a lead for review, not a proven ring.
          </div>
        )}
        <div>
          <SectionTitle>Top counterparties</SectionTitle>
          {d.top_counterparties.slice(0, 5).map((c) => (
            <div key={c.counterparty} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontFamily: MONO, fontSize: "0.7em", color: C.dim }}>
              <span>{c.counterparty}</span><span style={{ color: C.text }}>{short(c.volume)} · {c.txns}× · {c.direction}</span>
            </div>
          ))}
          {d.top_counterparties.length === 0 && <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO }}>None (no counterparty column).</div>}
        </div>
        <a href={`${API}/soa/report/${encodeURIComponent(id)}`} target="_blank" rel="noreferrer"
           style={{ alignSelf: "flex-start", background: "#C9A84C18", border: `1px solid ${C.gold}`, color: C.gold, padding: "8px 14px", borderRadius: 6, fontFamily: MONO, fontSize: "0.72em", textDecoration: "none" }}>
          📄 OPEN CASE REPORT (print / save as PDF)
        </a>
      </div>
    </div>
  );
}

export default function SoaRanking() {
  const [data, setData] = useState(null);
  const [ov, setOv] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    fetch(`${API}/soa/ranked`).then((r) => r.json()).then(setData).catch(() => setData({ available: false, holders: [], hint: "Backend not reachable." }));
    fetch(`${API}/soa/overview`).then((r) => r.json()).then(setOv).catch(() => {});
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
    <div style={{ padding: 24, maxWidth: 1300, margin: "0 auto" }}>
      <div style={{ color: C.gold, fontFamily: MONO, fontSize: "1.1em", fontWeight: 700 }}>Mule-risk investigation workspace · C-DAC statements</div>
      <div style={{ color: C.muted, fontSize: "0.72em", fontFamily: MONO, margin: "6px 0 14px", lineHeight: 1.6 }}>
        Unsupervised: the dataset has no labels, so scores are relative percentile ranks among these accounts (not probabilities).
        Every score shows the points each signal contributed. Click a holder to open the case.
      </div>

      {ov && ov.available && (
        <>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
            <Kpi label="Statement holders" value={ov.holders} sub={`${ov.behaviour_only_holders} behaviour-only`} />
            <Kpi label="Transactions" value={ov.transactions.toLocaleString("en-IN")} sub={`${ov.counterparties.toLocaleString("en-IN")} counterparties`} />
            <Kpi label="Value transacted" value={short(ov.volume)} />
            <Kpi label={`Flagged (score ≥ ${ov.flag_threshold})`} value={ov.flagged} color={C.crit} sub="of the holders above" />
            <Kpi label="Usable timestamps" value={`${ov.timestamps_usable_pct}%`} color={ov.timestamps_usable_pct < 90 ? C.med : C.low} sub={ov.source_files ? `${ov.source_files} files · ${ov.layouts || "?"} formats` : null} />
          </div>
          {ov.linked_pairs.length > 0 && (
            <div style={{ background: "#2A1608", border: `1px solid ${C.high}`, borderRadius: 8, padding: "10px 14px", marginBottom: 14, color: "#FFD2A8", fontFamily: MONO, fontSize: "0.75em" }}>
              ⚠ Linked holders: {ov.linked_pairs.map((p) => `${p.a} ↔ ${p.b} share ${p.shared.toLocaleString("en-IN")} counterparties`).join(" · ")}. The only link between any two statements. A lead for investigators.
            </div>
          )}
        </>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, margin: "0 0 10px", fontFamily: MONO, fontSize: "0.62em", color: C.muted }}>
        {data.holders[0] && data.holders[0].contributions.map((c) => (
          <span key={c.key}><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: SIGNAL_COLOR[c.key], marginRight: 5 }} />{c.label}</span>
        ))}
      </div>

      {data.holders.map((h, i) => (
        <div key={h.holder} style={{ background: C.card, border: `1px solid ${open === h.holder ? C.gold : C.border}`, borderRadius: 8, marginBottom: 8, overflow: "hidden" }}>
          <div onClick={() => setOpen(open === h.holder ? null : h.holder)}
               style={{ display: "grid", gridTemplateColumns: "34px 110px 1fr 120px 120px", gap: 12, alignItems: "center", padding: "10px 14px", cursor: "pointer", fontFamily: MONO, fontSize: "0.75em" }}>
            <span style={{ color: C.muted }}>#{i + 1}</span>
            <span style={{ color: C.text, fontWeight: 700 }}>{h.holder}</span>
            <span>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ flex: 1 }}><ContribBar contributions={h.contributions} /></span>
                <span style={{ color: scoreColor(h.risk_score), fontWeight: 700, width: 40, textAlign: "right" }}>{h.risk_score}</span>
              </span>
              <span style={{ display: "block", color: C.dim, fontSize: "0.9em", marginTop: 4 }}>
                {h.reasons}{h.graph_coverage !== "yes" && <span style={{ color: C.muted }}> · behaviour only</span>}
              </span>
            </span>
            <span style={{ color: C.dim }}>in {short(h.total_in)}</span>
            <span style={{ color: C.dim }}>out {short(h.total_out)}</span>
          </div>
          {open === h.holder && <Detail id={h.holder} fallback={h.contributions} />}
        </div>
      ))}
    </div>
  );
}
