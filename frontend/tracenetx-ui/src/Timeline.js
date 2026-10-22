import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";

const C = {
  navy: "#0A0E1A", card: "#0D1220", border: "#1A2035", accent: "#151B2E", gold: "#C9A84C",
  text: "#E2E8F0", muted: "#64748B", dim: "#94A3B8", inn: "#00C853", out: "#FF6B00", crit: "#FF2D2D", warn: "#FFB800",
};
const API = `${process.env.REACT_APP_API_URL}`;
const MONO = "'IBM Plex Mono', monospace";
const inr = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;
const fmt = (t) => String(t).slice(5, 16).replace("T", " ");

function Chart({ data }) {
  const W = 900, H = 260, PL = 64, PR = 16, PT = 16, PB = 34;
  const ev = data.events;
  const t0 = new Date(ev[0].timestamp).getTime();
  const t1 = Math.max(new Date(ev[ev.length - 1].timestamp).getTime(), t0 + 3600 * 1000);
  const comps = data.complaints.map((c) => ({ ...c, t: new Date(c.timestamp).getTime() }));
  const tMax = Math.max(t1, ...comps.map((c) => c.t));
  const x = (t) => PL + ((t - t0) / (tMax - t0 || 1)) * (W - PL - PR);
  const nets = ev.map((e) => e.net_position);
  const lo = Math.min(0, ...nets), hi = Math.max(1, ...nets);
  const y = (v) => PT + (1 - (v - lo) / (hi - lo || 1)) * (H - PT - PB);
  const maxAmt = Math.max(...ev.map((e) => e.amount));
  const bar = (a) => 6 + (a / maxAmt) * 38;

  let path = `M ${x(t0)} ${y(0)}`;
  let prev = 0;
  ev.forEach((e) => { const px = x(new Date(e.timestamp).getTime()); path += ` L ${px} ${y(prev)} L ${px} ${y(e.net_position)}`; prev = e.net_position; });
  path += ` L ${x(tMax)} ${y(prev)}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", background: C.card, border: `1px solid ${C.border}`, borderRadius: 8 }}>
      {data.bursts.map((b, i) => {
        const bx = x(new Date(b.start).getTime()), bw = Math.max(6, x(new Date(b.end).getTime()) - bx);
        return <rect key={i} x={bx - 2} y={PT} width={bw + 4} height={H - PT - PB} fill={C.warn} opacity="0.12" />;
      })}
      <line x1={PL} x2={W - PR} y1={y(0)} y2={y(0)} stroke={C.border} />
      {[lo, (lo + hi) / 2, hi].map((v, i) => (
        <g key={i}>
          <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke={C.border} strokeDasharray="2 4" />
          <text x={PL - 8} y={y(v) + 4} fill={C.muted} fontSize="10" textAnchor="end" fontFamily={MONO}>{inr(v)}</text>
        </g>
      ))}
      {ev.map((e, i) => {
        const px = x(new Date(e.timestamp).getTime());
        const h = bar(e.amount);
        return e.direction === "in"
          ? <rect key={i} x={px - 2} y={y(0) - h} width="4" height={h} fill={C.inn} opacity="0.8"><title>{`IN ${inr(e.amount)} from ${e.counterparty} @ ${e.timestamp}`}</title></rect>
          : <rect key={i} x={px - 2} y={y(0)} width="4" height={h} fill={C.out} opacity="0.8"><title>{`OUT ${inr(e.amount)} to ${e.counterparty} @ ${e.timestamp}`}</title></rect>;
      })}
      <path d={path} fill="none" stroke={C.gold} strokeWidth="1.6" />
      {comps.map((c, i) => (
        <g key={i}>
          <line x1={x(c.t)} x2={x(c.t)} y1={PT} y2={H - PB} stroke={C.crit} strokeDasharray="3 3" opacity="0.7" />
          <polygon points={`${x(c.t)},${PT} ${x(c.t) + 5},${PT + 7} ${x(c.t)},${PT + 14} ${x(c.t) - 5},${PT + 7}`} fill={C.crit}>
            <title>{`Complaint ${c.complaint_id}: ${inr(c.amount_lost)} (${c.fraud_type})`}</title>
          </polygon>
        </g>
      ))}
      <text x={PL} y={H - 10} fill={C.muted} fontSize="10" fontFamily={MONO}>{fmt(new Date(t0).toISOString())}</text>
      <text x={W - PR} y={H - 10} fill={C.muted} fontSize="10" textAnchor="end" fontFamily={MONO}>{fmt(new Date(tMax).toISOString())}</text>
    </svg>
  );
}

export default function Timeline({ accountId, onClose }) {
  const [data, setData] = useState(null);
  const [trail, setTrail] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    fetch(`${API}/timeline/${encodeURIComponent(accountId)}`)
      .then((r) => { if (!r.ok) throw new Error(`Timeline unavailable (${r.status})`); return r.json(); })
      .then(setData).catch((e) => setErr(e.message));
    fetch(`${API}/complaints/trail/${encodeURIComponent(accountId)}`).then((r) => r.json()).then(setTrail).catch(() => {});
  }, [accountId]);

  const fast = data ? data.pass_through.filter((p) => p.dwell_min <= 120) : [];
  return createPortal(
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(5,8,16,0.82)", zIndex: 10000, overflowY: "auto", padding: 24 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 960, margin: "40px auto", background: C.navy, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
          <div style={{ color: C.gold, fontFamily: MONO, fontWeight: 700 }}>TRANSACTION TIMELINE · {accountId}</div>
          <button onClick={onClose} style={{ marginLeft: "auto", background: "transparent", color: C.gold, border: `1px solid ${C.gold}`, borderRadius: 6, padding: "4px 12px", cursor: "pointer", fontFamily: MONO }}>Close</button>
        </div>
        {err && <div style={{ color: C.crit, fontFamily: MONO }}>{err}</div>}
        {!data && !err && <div style={{ color: C.muted, fontFamily: MONO }}>Loading…</div>}
        {data && (
          <>
            <div style={{ color: C.dim, fontSize: "0.85em", marginBottom: 10 }}>{data.summary}</div>
            <Chart data={data} />
            <div style={{ display: "flex", gap: 16, fontSize: "0.7em", color: C.muted, fontFamily: MONO, margin: "8px 0 16px" }}>
              <span style={{ color: C.inn }}>▮ inflow</span><span style={{ color: C.out }}>▮ outflow</span>
              <span style={{ color: C.gold }}>— net position</span><span style={{ color: C.crit }}>◆ complaint</span>
              <span style={{ color: C.warn }}>▒ burst window</span>
            </div>

            <div style={{ color: C.dim, fontSize: "0.7em", letterSpacing: 1, fontFamily: MONO, marginBottom: 6 }}>FAST PASS-THROUGH (≤ 2h dwell)</div>
            {fast.length === 0 && <div style={{ color: C.muted, fontSize: "0.8em", marginBottom: 14 }}>None: money did not leave within two hours of arriving.</div>}
            {fast.slice(0, 8).map((p, i) => (
              <div key={i} style={{ color: C.dim, fontSize: "0.78em", fontFamily: MONO, marginBottom: 3 }}>
                {fmt(p.in_time)} {p.from} → <span style={{ color: C.out }}>{inr(p.amount)}</span> → {p.to} {fmt(p.out_time)} <span style={{ color: C.warn }}>({Math.round(p.dwell_min)} min)</span>
              </div>
            ))}

            {trail && trail.reached && (
              <div style={{ marginTop: 18 }}>
                <div style={{ color: C.dim, fontSize: "0.7em", letterSpacing: 1, fontFamily: MONO, marginBottom: 6 }}>
                  HEAVIEST VICTIM-MONEY CHAIN · {inr(trail.tainted_amount)} from {trail.complaints_reaching} complaint(s) reached this account
                </div>
                {trail.chain.map((h, i) => (
                  <div key={i} style={{ color: C.dim, fontSize: "0.78em", fontFamily: MONO, marginBottom: 3 }}>
                    {fmt(h.timestamp)} {h.from} → {h.to} · <span style={{ color: C.crit }}>{inr(h.tainted_amount)} traceable</span> of {inr(h.amount)}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>,
    document.body
  );
}
