import React, { useState, useEffect, useRef } from "react";

const COLORS = {
  critical: "#FF2D2D",
  high: "#FF6B00",
  medium: "#FFB800",
  low: "#00C853",
  clear: "#00C853",
  gold: "#C9A84C",
  navy: "#0A0E1A",
  navyCard: "#0D1220",
  navyBorder: "#1A2035",
  navyAccent: "#151B2E",
  text: "#E2E8F0",
  textMuted: "#64748B",
  textDim: "#94A3B8",
};

const getRiskColor = (level) => {
  const map = { CRITICAL: COLORS.critical, HIGH: COLORS.high, MEDIUM: COLORS.medium, LOW: COLORS.low, CLEAR: COLORS.clear };
  return map[level] || COLORS.textMuted;
};

const API = `${process.env.REACT_APP_API_URL}`;

function Dataset({ onViewMLAnalysis, onDatasetActivated }) {
  const [datasets, setDatasets] = useState([]);
  const [activeId, setActiveId] = useState("demo");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [switching, setSwitching] = useState(false);
  const fileInputRef = useRef(null);

  const fetchList = async () => {
    try {
      const res = await fetch(`${API}/dataset/list`);
      const data = await res.json();
      setDatasets(data.datasets || []);
      setActiveId(data.active);
    } catch (e) { console.error(e); }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API}/ml/analyze`);
      const data = await res.json();
      setSummary(data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { fetchList(); fetchSummary(); }, []);

  const handleFileSelect = async (file) => {
    if (!file) return;
    if (!file.name.endsWith(".csv")) {
      setError("Only .csv files are supported.");
      return;
    }
    setUploading(true);
    setError(null);
    setSummary(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/dataset/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Upload failed.");
        setUploading(false);
        return;
      }
      await fetchList();
      await fetchSummary();
    } catch (e) {
      setError("Upload failed — check console for details.");
      console.error(e);
    }
    setUploading(false);
  };

  const handleActivate = async (id) => {
    setSwitching(true);
    setError(null);
    setSummary(null);
    try {
      const res = await fetch(`${API}/dataset/activate/${id}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Failed to switch dataset.");
        setSwitching(false);
        return;
      }
      await fetchList();
      await fetchSummary();
      if (onDatasetActivated) onDatasetActivated();
    } catch (e) {
      setError("Failed to switch dataset.");
      console.error(e);
    }
    setSwitching(false);
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
      <div style={{ marginBottom: "24px" }}>
        <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>DATA LAYER</div>
        <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>Dataset Manager</h2>
        <p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Upload a custom transaction dataset — the full ML pipeline retrains and re-flags automatically</p>
      </div>

      {/* Upload dropzone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleFileSelect(e.dataTransfer.files[0]); }}
        onClick={() => fileInputRef.current?.click()}
        style={{
          background: COLORS.navyCard,
          border: `1px dashed ${COLORS.gold}66`,
          borderRadius: "8px",
          padding: "32px",
          textAlign: "center",
          cursor: "pointer",
          marginBottom: "20px",
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={(e) => handleFileSelect(e.target.files[0])}
        />
        <div style={{ fontSize: "2em", marginBottom: "8px", opacity: 0.6 }}>⬆</div>
        <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em", fontWeight: "700" }}>
          {uploading ? "UPLOADING & RETRAINING..." : "CLICK OR DROP A .CSV FILE HERE"}
        </div>
        <div style={{ color: COLORS.textMuted, fontSize: "0.72em", marginTop: "8px" }}>
          Required columns: <code style={{ color: COLORS.textDim }}>sender_id, receiver_id, amount, timestamp</code>
        </div>
        <div style={{ color: COLORS.textMuted, fontSize: "0.68em", marginTop: "4px" }}>
          Optional (auto-filled if missing): sender_ip, sender_city, sender_phone, receiver_ip, transfer_type, case_id
        </div>
      </div>

      {error && (
        <div style={{ background: "#1A0505", border: `1px solid ${COLORS.critical}88`, borderRadius: "6px", padding: "14px 18px", color: COLORS.critical, fontSize: "0.82em", marginBottom: "20px", fontFamily: "'IBM Plex Mono', monospace" }}>
          ⚠ {error}
        </div>
      )}

      {/* Quick summary after upload/switch */}
      {summary && !uploading && !switching && (
        <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `3px solid ${COLORS.gold}`, borderRadius: "6px", padding: "18px 20px", marginBottom: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <div style={{ color: COLORS.gold, fontWeight: "700", fontSize: "0.85em", fontFamily: "'IBM Plex Mono', monospace" }}>
              ✓ ML PIPELINE RETRAINED — {summary.total_accounts_analyzed} ACCOUNTS ANALYZED
            </div>
            <button onClick={onViewMLAnalysis} style={{
              padding: "6px 14px",
              background: "#C9A84C18",
              border: `1px solid ${COLORS.gold}88`,
              color: COLORS.gold,
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "0.72em",
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: "600",
            }}>VIEW FULL ML ANALYSIS →</button>
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {[
              ["CRITICAL", summary.critical, COLORS.critical],
              ["HIGH", summary.high, COLORS.high],
              ["MEDIUM", summary.medium, COLORS.medium],
              ["LOW", summary.low, COLORS.low],
              ["CLEAR", summary.clear, COLORS.clear],
            ].map(([level, count, color]) => (
              <div key={level} style={{
                background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`,
                borderTop: `2px solid ${color}`,
                borderRadius: "6px", padding: "10px 16px", textAlign: "center", minWidth: "80px",
              }}>
                <div style={{ color, fontSize: "1.4em", fontWeight: "800", fontFamily: "'IBM Plex Mono', monospace" }}>{count}</div>
                <div style={{ color: COLORS.textMuted, fontSize: "0.6em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace" }}>{level}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dataset switcher table */}
      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "10px" }}>
        DATASET REGISTRY
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {datasets.map((ds) => (
          <div key={ds.id} style={{
            background: COLORS.navyCard,
            border: `1px solid ${ds.id === activeId ? COLORS.gold : COLORS.navyBorder}`,
            borderRadius: "6px",
            padding: "14px 18px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <div>
              <div style={{ color: COLORS.text, fontWeight: "700", fontSize: "0.85em", fontFamily: "'IBM Plex Mono', monospace" }}>
                {ds.name} {ds.id === activeId && <span style={{ color: COLORS.gold, fontSize: "0.85em" }}>● ACTIVE</span>}
              </div>
              <div style={{ color: COLORS.textMuted, fontSize: "0.72em", marginTop: "4px" }}>
                {ds.rows != null ? `${ds.rows} rows` : "built-in demo network"}
                {ds.uploaded_at && ` · uploaded ${new Date(ds.uploaded_at).toLocaleString()}`}
              </div>
            </div>
            {ds.id !== activeId && (
              <button onClick={() => handleActivate(ds.id)} disabled={switching} style={{
                padding: "6px 14px",
                background: "transparent",
                border: `1px solid ${COLORS.navyBorder}`,
                color: COLORS.textDim,
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.72em",
                fontFamily: "'IBM Plex Mono', monospace",
              }}>{switching ? "SWITCHING..." : "ACTIVATE"}</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dataset;
