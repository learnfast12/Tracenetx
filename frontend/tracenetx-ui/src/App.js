import React, { useState, useEffect } from "react";
import SpiderMap from "./SpiderMap";
import Sidebar from "./Sidebar";
import AlertSystem from "./AlertSystem";
import PathFinder from "./PathFinder";
import Dashboard from "./Dashboard";
import CityMap from "./CityMap";
import "./App.css";

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [filters, setFilters] = useState({ ip: "", phone: "", city: "", case_id: "" });
  const [loading, setLoading] = useState(true);
  const [activeCase, setActiveCase] = useState("ALL");
  const [activeTab, setActiveTab] = useState("map");
  const [exporting, setExporting] = useState(false);
  const [mlData, setMlData] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [intelData, setIntelData] = useState(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [evidenceData, setEvidenceData] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const fetchGraph = async (activeFilters = {}) => {
    setLoading(true);
    try {
      const hasFilter = activeFilters.ip || activeFilters.phone || activeFilters.city;
      let url = "http://localhost:8000/graph";
      const params = new URLSearchParams();
      if (activeFilters.case_id) params.append("case_id", activeFilters.case_id);
      if (hasFilter) {
        if (activeFilters.ip) params.append("ip", activeFilters.ip);
        if (activeFilters.phone) params.append("phone", activeFilters.phone);
        if (activeFilters.city) params.append("city", activeFilters.city);
        url = "http://localhost:8000/filter";
      }
      const query = params.toString();
      const res = await fetch(query ? url + "?" + query : url);
      const data = await res.json();
      setGraphData(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchAccount = async (id) => {
    const res = await fetch("http://localhost:8000/account/" + id);
    const data = await res.json();
    setSelectedNode(data);
  };

  const fetchML = async () => {
    setMlLoading(true);
    try {
      const res = await fetch("http://localhost:8000/ml/analyze");
      const data = await res.json();
      setMlData(data);
    } catch (e) { console.error(e); }
    setMlLoading(false);
  };

  const fetchIntelligence = async () => {
    setIntelLoading(true);
    try {
      const res = await fetch("http://localhost:8000/intelligence/full");
      const data = await res.json();
      setIntelData(data);
    } catch (e) { console.error(e); }
    setIntelLoading(false);
  };

  const fetchEvidence = async (accountId) => {
    setEvidenceLoading(true);
    try {
      const res = await fetch("http://localhost:8000/evidence/" + accountId);
      const data = await res.json();
      setEvidenceData(data);
    } catch (e) { console.error(e); }
    setEvidenceLoading(false);
  };

  const handleCaseSwitch = (caseId) => {
    setActiveCase(caseId);
    setSelectedNode(null);
    const newFilters = { ...filters, case_id: caseId === "ALL" ? "" : caseId };
    setFilters(newFilters);
    fetchGraph(newFilters);
  };

  const handleFilter = (f) => {
    const newFilters = { ...f, case_id: filters.case_id };
    setFilters(newFilters);
    fetchGraph(newFilters);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch("http://localhost:8000/export");
      const data = await res.json();
      const rows = data.flagged_accounts;
      const csv = ["Account ID,Risk Level,Risk Score,Flags",
        ...rows.map(r => `${r.account_id},${r.risk_level},${r.risk_score},"${r.flags}"`)
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tracenetx_v2_flagged_accounts.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
    setExporting(false);
  };

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    if (tab === "ml" && !mlData) fetchML();
    if (tab === "intelligence" && !intelData) fetchIntelligence();
  };

  const getRiskColor = (level) => {
    const colors = { CRITICAL: "#FF0000", HIGH: "#FF4500", MEDIUM: "#FFA500", LOW: "#FFD700", CLEAR: "#00CC44" };
    return colors[level] || "#888";
  };

  const getRiskBg = (level) => {
    const colors = { CRITICAL: "#2a0000", HIGH: "#1a0a00", MEDIUM: "#1a1000", LOW: "#1a1500", CLEAR: "#001a08" };
    return colors[level] || "#111";
  };

  useEffect(() => { fetchGraph(); }, []);

  const highRiskCount = graphData.nodes.filter(n => n.risk && n.risk.level === "HIGH").length;
  const medRiskCount = graphData.nodes.filter(n => n.risk && n.risk.level === "MEDIUM").length;
  const totalAmount = graphData.edges.reduce((s, e) => s + (e.amount || 0), 0);

  return (
    <div className="app">
      <AlertSystem />

      <header className="header">
        <div className="header-left">
          <div className="logo">🕸️</div>
          <div>
            <h1>TraceNetX <span style={{fontSize:"0.6em", color:"#00ff88"}}>v2.0</span></h1>
            <p>Mule Account Intelligence & Criminal Network Disruption</p>
          </div>
        </div>
        <div className="header-center">
          <div className="case-tabs">
            {["ALL", "CASE001", "CASE002"].map(c => (
              <button key={c} className={"case-tab" + (activeCase === c ? " active" : "")} onClick={() => handleCaseSwitch(c)}>
                {c === "ALL" ? "All Cases" : c === "CASE001" ? "Case 001 — Delhi" : "Case 002 — Mumbai"}
              </button>
            ))}
          </div>
        </div>
        <div className="header-right">
          <span className="badge">CYBERSHIELD 2026</span>
          <span className="badge team">OMEGA 404</span>
        </div>
      </header>

      <div className="summary-bar">
        <div className="summary-item"><span>Total Accounts</span><strong>{graphData.nodes.length}</strong></div>
        <div className="summary-item"><span>Transactions</span><strong>{graphData.edges.length}</strong></div>
        <div className="summary-item danger"><span>High Risk</span><strong>{highRiskCount}</strong></div>
        <div className="summary-item warning"><span>Medium Risk</span><strong>{medRiskCount}</strong></div>
        <div className="summary-item"><span>Total Amount</span><strong>₹{(totalAmount/100000).toFixed(1)}L</strong></div>
        <div className="tab-switcher">
          {[
            ["map","🕸 Spider Map"],
            ["ml","🤖 ML Analysis"],
            ["intelligence","🧠 Intelligence"],
            ["dashboard","📊 Dashboard"],
            ["citymap","🗺 City Map"]
          ].map(([id, label]) => (
            <button key={id} className={"view-tab" + (activeTab === id ? " active" : "")} onClick={() => handleTabSwitch(id)}>{label}</button>
          ))}
        </div>
        <button className="export-btn" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting..." : "⬇ Export CSV"}
        </button>
      </div>

      <div className="main">

        {/* SPIDER MAP TAB */}
        {activeTab === "map" && (
          <>
            <div className="left-panel">
              <div className="filter-panel">
                <h3>🔍 Filters</h3>
                <input placeholder="IP Address" onChange={e => handleFilter({ ...filters, ip: e.target.value })} />
                <input placeholder="Phone Number" onChange={e => handleFilter({ ...filters, phone: e.target.value })} />
                <input placeholder="City" onChange={e => handleFilter({ ...filters, city: e.target.value })} />
                <button className="btn-reset" onClick={() => { setFilters({ ip: "", phone: "", city: "", case_id: filters.case_id }); fetchGraph({ case_id: filters.case_id }); }}>Reset Filters</button>
              </div>
              <div className="legend">
                <h3>Risk Legend</h3>
                <div className="legend-item"><span className="dot" style={{background:"#FF0000"}}></span>Critical</div>
                <div className="legend-item"><span className="dot high"></span>High Risk</div>
                <div className="legend-item"><span className="dot medium"></span>Medium Risk</div>
                <div className="legend-item"><span className="dot low"></span>Low Risk</div>
                <div className="legend-item"><span className="dot" style={{background:"#00CC44"}}></span>Clear</div>
              </div>
              <PathFinder nodes={graphData.nodes} />
            </div>
            <div className="map-area">
              {loading ? <div className="loading">🔍 Analyzing money trail...</div> : <SpiderMap graphData={graphData} onNodeClick={fetchAccount} />}
            </div>
            <div className="right-panel">
              <Sidebar selectedNode={selectedNode} />
              {selectedNode && (
                <div style={{padding:"10px"}}>
                  <button
                    onClick={() => { fetchEvidence(selectedNode.account?.id); setActiveTab("evidence"); }}
                    style={{width:"100%", padding:"10px", background:"#ff4500", color:"white", border:"none", borderRadius:"6px", cursor:"pointer", fontWeight:"bold", marginTop:"10px"}}
                  >
                    📋 Generate Evidence Package
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* ML ANALYSIS TAB */}
        {activeTab === "ml" && (
          <div style={{flex:1, overflowY:"auto", padding:"20px"}}>
            <h2 style={{color:"#00ff88", marginBottom:"20px"}}>🤖 ML Analysis — DETECT Layer</h2>
            <p style={{color:"#888", marginBottom:"20px"}}>XGBoost + LightGBM + Random Forest ensemble + Isolation Forest anomaly detection + SHAP explainability</p>
            {mlLoading && <div className="loading">Running ML pipeline...</div>}
            {mlData && (
              <>
                <div style={{display:"flex", gap:"15px", marginBottom:"25px", flexWrap:"wrap"}}>
                  {[
                    ["CRITICAL", mlData.critical, "#FF0000"],
                    ["HIGH", mlData.high, "#FF4500"],
                    ["MEDIUM", mlData.medium, "#FFA500"],
                    ["LOW", mlData.low, "#FFD700"],
                    ["CLEAR", mlData.clear, "#00CC44"]
                  ].map(([level, count, color]) => (
                    <div key={level} style={{background:"#111", border:`1px solid ${color}`, borderRadius:"8px", padding:"15px 25px", textAlign:"center", minWidth:"100px"}}>
                      <div style={{color, fontSize:"2em", fontWeight:"bold"}}>{count}</div>
                      <div style={{color:"#888", fontSize:"0.85em"}}>{level}</div>
                    </div>
                  ))}
                </div>
                <div style={{display:"flex", flexDirection:"column", gap:"12px"}}>
                  {mlData.results.map(r => (
                    <div key={r.account_id} style={{background: getRiskBg(r.risk_level), border:`1px solid ${getRiskColor(r.risk_level)}`, borderRadius:"8px", padding:"15px"}}>
                      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"8px"}}>
                        <div style={{display:"flex", alignItems:"center", gap:"12px"}}>
                          <span style={{color: getRiskColor(r.risk_level), fontWeight:"bold", fontSize:"1.1em"}}>{r.account_id}</span>
                          <span style={{background: getRiskColor(r.risk_level), color:"black", padding:"2px 8px", borderRadius:"4px", fontSize:"0.75em", fontWeight:"bold"}}>{r.risk_level}</span>
                          {r.mule_type !== "N/A" && <span style={{background:"#333", color:"#ccc", padding:"2px 8px", borderRadius:"4px", fontSize:"0.75em"}}>{r.mule_type}</span>}
                        </div>
                        <div style={{display:"flex", alignItems:"center", gap:"10px"}}>
                          <div style={{width:"120px", height:"8px", background:"#333", borderRadius:"4px"}}>
                            <div style={{width:`${r.risk_score}%`, height:"100%", background: getRiskColor(r.risk_level), borderRadius:"4px"}}></div>
                          </div>
                          <span style={{color: getRiskColor(r.risk_level), fontWeight:"bold"}}>{r.risk_score.toFixed(1)}</span>
                        </div>
                      </div>
                      <div style={{color:"#aaa", fontSize:"0.82em", marginBottom:"6px"}}>
                        <strong style={{color:"#fff"}}>Action:</strong> {r.recommended_action}
                      </div>
                      {r.flags.length > 0 && (
                        <div style={{display:"flex", gap:"6px", flexWrap:"wrap", marginBottom:"6px"}}>
                          {r.flags.map((f,i) => <span key={i} style={{background:"#222", border:"1px solid #444", color:"#ccc", padding:"2px 8px", borderRadius:"12px", fontSize:"0.75em"}}>⚠ {f}</span>)}
                        </div>
                      )}
                      <div style={{color:"#666", fontSize:"0.78em", fontStyle:"italic"}}>
                        SHAP: {r.shap_explanation}
                      </div>
                      <button
                        onClick={() => { fetchEvidence(r.account_id); setActiveTab("evidence"); }}
                        style={{marginTop:"8px", padding:"4px 12px", background:"transparent", border:"1px solid #ff4500", color:"#ff4500", borderRadius:"4px", cursor:"pointer", fontSize:"0.8em"}}
                      >
                        📋 Evidence Package
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* INTELLIGENCE TAB */}
        {activeTab === "intelligence" && (
          <div style={{flex:1, overflowY:"auto", padding:"20px"}}>
            <h2 style={{color:"#00ff88", marginBottom:"20px"}}>🧠 Graph Intelligence — INVESTIGATE Layer</h2>
            {intelLoading && <div className="loading">Running graph intelligence...</div>}
            {intelData && (
              <div style={{display:"flex", flexDirection:"column", gap:"20px"}}>

                {/* Community Detection */}
                <div style={{background:"#0a0a1a", border:"1px solid #0044ff", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#4488ff", marginBottom:"15px"}}>🔵 Community Detection — Mule Clusters</h3>
                  <p style={{color:"#666", marginBottom:"15px"}}>{intelData.community_detection?.analysis}</p>
                  <div style={{display:"flex", flexDirection:"column", gap:"8px"}}>
                    {intelData.community_detection?.clusters?.map((c, i) => (
                      <div key={i} style={{background:"#111", border:"1px solid #0033aa", borderRadius:"6px", padding:"12px"}}>
                        <div style={{display:"flex", justifyContent:"space-between"}}>
                          <span style={{color:"#ff4500", fontWeight:"bold"}}>Coordinator: {c.coordinator}</span>
                          <span style={{background:"#ff4500", color:"white", padding:"2px 8px", borderRadius:"4px", fontSize:"0.75em"}}>{c.threat_level}</span>
                        </div>
                        <div style={{color:"#888", fontSize:"0.85em", marginTop:"6px"}}>
                          Mules: {c.mule_accounts.join(" → ")} ({c.inbound_count} inbound)
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Coordination Detection */}
                <div style={{background:"#1a0a00", border:"1px solid #ff6600", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#ff8800", marginBottom:"15px"}}>⚡ Coordination Detection — Synchronized Bursts</h3>
                  <p style={{color:"#666", marginBottom:"15px"}}>{intelData.coordination_detection?.analysis}</p>
                  <div style={{display:"flex", flexDirection:"column", gap:"8px"}}>
                    {intelData.coordination_detection?.coordinated_bursts?.map((b, i) => (
                      <div key={i} style={{background:"#111", border:"1px solid #aa4400", borderRadius:"6px", padding:"12px"}}>
                        <div style={{color:"#ff8800", fontWeight:"bold", marginBottom:"4px"}}>
                          ⚠ {b.alert}
                        </div>
                        <div style={{color:"#888", fontSize:"0.85em"}}>
                          Window: {b.window_start} → {b.window_end}
                        </div>
                        <div style={{color:"#888", fontSize:"0.85em"}}>
                          Accounts: {b.accounts_involved?.join(", ")} | Txns: {b.transaction_count} | Amount: ₹{(b.total_amount/100000).toFixed(1)}L
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Identity Fusion */}
                <div style={{background:"#0a1a0a", border:"1px solid #00aa44", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#00ff88", marginBottom:"15px"}}>🔗 Identity Fusion — Shared Identifiers</h3>
                  <p style={{color:"#666", marginBottom:"15px"}}>{intelData.identity_fusion?.analysis}</p>
                  <div style={{display:"flex", flexDirection:"column", gap:"8px"}}>
                    {intelData.identity_fusion?.identity_links?.map((l, i) => (
                      <div key={i} style={{background:"#111", border:"1px solid #005522", borderRadius:"6px", padding:"12px"}}>
                        <div style={{color:"#00ff88", fontWeight:"bold"}}>
                          {l.account1} ↔ {l.account2}
                        </div>
                        <div style={{color:"#888", fontSize:"0.85em"}}>
                          Shared IP: {l.shared_ip} | City: {l.city}
                        </div>
                        <div style={{color:"#ff8800", fontSize:"0.8em"}}>{l.alert}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Convergence Analysis */}
                <div style={{background:"#1a001a", border:"1px solid #aa00ff", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#cc44ff", marginBottom:"15px"}}>🎯 Convergence Analysis — Lieutenant Nodes</h3>
                  <p style={{color:"#666", marginBottom:"15px"}}>{intelData.convergence_analysis?.analysis}</p>
                  <div style={{display:"flex", flexDirection:"column", gap:"8px"}}>
                    {intelData.convergence_analysis?.potential_lieutenants?.map((l, i) => (
                      <div key={i} style={{background:"#111", border:"1px solid #660088", borderRadius:"6px", padding:"12px"}}>
                        <div style={{color:"#cc44ff", fontWeight:"bold"}}>
                          🎯 {l.account} — {l.source_count} source chains
                        </div>
                        <div style={{color:"#888", fontSize:"0.85em"}}>{l.threat}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Batch Recruitment */}
                <div style={{background:"#1a1a00", border:"1px solid #aaaa00", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#ffff00", marginBottom:"15px"}}>👥 Batch Recruitment Detection</h3>
                  <p style={{color:"#666", marginBottom:"15px"}}>{intelData.batch_recruitment?.analysis}</p>
                  <div style={{display:"flex", flexDirection:"column", gap:"8px"}}>
                    {intelData.batch_recruitment?.recruitment_batches?.map((b, i) => (
                      <div key={i} style={{background:"#111", border:"1px solid #666600", borderRadius:"6px", padding:"12px"}}>
                        <div style={{color:"#ffff00", fontWeight:"bold"}}>{b.alert}</div>
                        <div style={{color:"#888", fontSize:"0.85em"}}>City: {b.city} | IP: {b.shared_ip} | Accounts: {b.accounts?.join(", ")}</div>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            )}
          </div>
        )}

        {/* EVIDENCE TAB */}
        {activeTab === "evidence" && (
          <div style={{flex:1, overflowY:"auto", padding:"20px"}}>
            <h2 style={{color:"#00ff88", marginBottom:"20px"}}>📋 Evidence Package — ACT Layer</h2>
            {evidenceLoading && <div className="loading">Generating court-ready evidence package...</div>}
            {evidenceData && (
              <div style={{display:"flex", flexDirection:"column", gap:"20px"}}>

                {/* Header */}
                <div style={{background:"#111", border:"1px solid #333", borderRadius:"8px", padding:"20px"}}>
                  <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
                    <div>
                      <div style={{color:"#888", fontSize:"0.8em"}}>EVIDENCE ID</div>
                      <div style={{color:"#00ff88", fontFamily:"monospace", fontSize:"0.9em"}}>{evidenceData.evidence_id}</div>
                    </div>
                    <div style={{color:"#888", fontSize:"0.8em"}}>Generated: {evidenceData.generated_at}</div>
                  </div>
                </div>

                {/* Account Summary */}
                <div style={{background: getRiskBg(evidenceData.account_summary?.risk_level), border:`2px solid ${getRiskColor(evidenceData.account_summary?.risk_level)}`, borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color: getRiskColor(evidenceData.account_summary?.risk_level), marginBottom:"15px"}}>Account: {evidenceData.account_summary?.account_id}</h3>
                  <div style={{display:"flex", gap:"20px", flexWrap:"wrap"}}>
                    <div><div style={{color:"#888", fontSize:"0.8em"}}>RISK SCORE</div><div style={{color: getRiskColor(evidenceData.account_summary?.risk_level), fontSize:"2em", fontWeight:"bold"}}>{evidenceData.account_summary?.risk_score?.toFixed(1)}</div></div>
                    <div><div style={{color:"#888", fontSize:"0.8em"}}>RISK LEVEL</div><div style={{color: getRiskColor(evidenceData.account_summary?.risk_level), fontSize:"1.5em", fontWeight:"bold"}}>{evidenceData.account_summary?.risk_level}</div></div>
                    <div><div style={{color:"#888", fontSize:"0.8em"}}>CLASSIFICATION</div><div style={{color:"#fff", fontSize:"1em"}}>{evidenceData.account_summary?.mule_classification}</div></div>
                  </div>
                  <div style={{marginTop:"15px", padding:"10px", background:"#1a1a1a", borderRadius:"6px"}}>
                    <div style={{color:"#888", fontSize:"0.8em"}}>RECOMMENDED ACTION</div>
                    <div style={{color:"#ff8800", fontWeight:"bold"}}>{evidenceData.account_summary?.recommended_action}</div>
                  </div>
                </div>

                {/* ML Analysis */}
                <div style={{background:"#0a0a1a", border:"1px solid #0044ff", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#4488ff", marginBottom:"15px"}}>🤖 ML Analysis</h3>
                  <div style={{color:"#888", fontSize:"0.85em", marginBottom:"10px"}}>{evidenceData.ml_analysis?.detection_method}</div>
                  <div style={{display:"flex", gap:"6px", flexWrap:"wrap", marginBottom:"12px"}}>
                    {evidenceData.ml_analysis?.behavioral_flags?.map((f,i) => (
                      <span key={i} style={{background:"#1a1a00", border:"1px solid #ff8800", color:"#ffaa00", padding:"4px 10px", borderRadius:"12px", fontSize:"0.8em"}}>⚠ {f}</span>
                    ))}
                  </div>
                  <div style={{background:"#111", padding:"10px", borderRadius:"6px", color:"#888", fontSize:"0.82em", fontFamily:"monospace"}}>
                    SHAP: {evidenceData.ml_analysis?.shap_explanation}
                  </div>
                </div>

                {/* Regulatory Output */}
                <div style={{background:"#0a1a0a", border:"1px solid #00aa44", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#00ff88", marginBottom:"15px"}}>⚖ Regulatory Output</h3>
                  <div style={{display:"flex", gap:"10px", marginBottom:"15px", flexWrap:"wrap"}}>
                    <span style={{background: evidenceData.regulatory_output?.fiu_ind_str_required ? "#004400" : "#1a1a1a", border:"1px solid #00aa44", color:"#00ff88", padding:"6px 14px", borderRadius:"6px", fontSize:"0.85em"}}>
                      {evidenceData.regulatory_output?.fiu_ind_str_required ? "✅ STR Required" : "⬜ STR Not Required"}
                    </span>
                    <span style={{background: evidenceData.regulatory_output?.immediate_freeze_required ? "#440000" : "#1a1a1a", border:"1px solid #ff0000", color:"#ff4444", padding:"6px 14px", borderRadius:"6px", fontSize:"0.85em"}}>
                      {evidenceData.regulatory_output?.immediate_freeze_required ? "🚨 Immediate Freeze" : "⬜ No Immediate Freeze"}
                    </span>
                  </div>
                  {evidenceData.regulatory_output?.alerts?.map((a, i) => (
                    <div key={i} style={{background:"#111", border:"1px solid #005522", borderRadius:"6px", padding:"10px", marginBottom:"8px"}}>
                      <div style={{color:"#00ff88", fontWeight:"bold", fontSize:"0.9em"}}>{a.body}</div>
                      <div style={{color:"#888", fontSize:"0.82em"}}>{a.action}</div>
                      <span style={{background:"#ff4500", color:"white", padding:"1px 6px", borderRadius:"4px", fontSize:"0.72em"}}>{a.priority}</span>
                    </div>
                  ))}
                </div>

                {/* FIR Summary */}
                <div style={{background:"#111", border:"1px solid #555", borderRadius:"8px", padding:"20px"}}>
                  <h3 style={{color:"#fff", marginBottom:"15px"}}>📄 FIR Summary — Court Ready</h3>
                  <pre style={{color:"#ccc", fontSize:"0.82em", whiteSpace:"pre-wrap", fontFamily:"monospace", lineHeight:"1.6"}}>
                    {evidenceData.fir_summary}
                  </pre>
                </div>

              </div>
            )}
            {!evidenceData && !evidenceLoading && (
              <div style={{color:"#555", textAlign:"center", marginTop:"100px"}}>
                <div style={{fontSize:"3em"}}>📋</div>
                <div>Click "Evidence Package" on any account to generate court-ready evidence</div>
              </div>
            )}
          </div>
        )}

        {activeTab === "dashboard" && <div style={{ flex: 1, overflowY: "auto" }}><Dashboard /></div>}
        {activeTab === "citymap" && <div style={{ flex: 1 }}><CityMap graphData={graphData} /></div>}
      </div>
    </div>
  );
}

export default App;
