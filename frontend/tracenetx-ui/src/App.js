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
      a.download = "tracenetx_flagged_accounts.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
    setExporting(false);
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
            <h1>TraceNetX</h1>
            <p>Money Trail Intelligence Platform</p>
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
          <span className="badge">RED SHIELD HACKATHON 2026</span>
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
          {[["map","🕸 Spider Map"],["dashboard","📊 Dashboard"],["citymap","🗺 City Map"]].map(([id, label]) => (
            <button key={id} className={"view-tab" + (activeTab === id ? " active" : "")} onClick={() => setActiveTab(id)}>{label}</button>
          ))}
        </div>
        <button className="export-btn" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting..." : "⬇ Export CSV"}
        </button>
      </div>

      <div className="main">
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
                <div className="legend-item"><span className="dot high"></span>High Risk</div>
                <div className="legend-item"><span className="dot medium"></span>Medium Risk</div>
                <div className="legend-item"><span className="dot low"></span>Low Risk</div>
              </div>
              <PathFinder nodes={graphData.nodes} />
            </div>
            <div className="map-area">
              {loading ? <div className="loading">🔍 Analyzing money trail...</div> : <SpiderMap graphData={graphData} onNodeClick={fetchAccount} />}
            </div>
            <div className="right-panel">
              <Sidebar selectedNode={selectedNode} />
            </div>
          </>
        )}
        {activeTab === "dashboard" && <div style={{ flex: 1, overflowY: "auto" }}><Dashboard /></div>}
        {activeTab === "citymap" && <div style={{ flex: 1 }}><CityMap graphData={graphData} /></div>}
      </div>
    </div>
  );
}

export default App;
