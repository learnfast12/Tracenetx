import React, { useEffect, useState } from "react";

function AlertSystem() {
  const [alerts, setAlerts] = useState([]);
  const [dismissed, setDismissed] = useState([]);
  const [visible, setVisible] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/alerts")
      .then(r => r.json())
      .then(data => {
        const top = data.alerts.slice(0, 3);
        setAlerts(top);
        top.forEach((_, i) => {
          setTimeout(() => setVisible(v => [...v, i]), i * 600 + 500);
          setTimeout(() => setDismissed(d => [...d, i]), i * 600 + 5000);
        });
      });
  }, []);

  const active = alerts.filter((_, i) => visible.includes(i) && !dismissed.includes(i));
  if (!active.length) return null;

  return (
    <div style={{
      position: "fixed", top: 75, right: 16,
      zIndex: 9999, display: "flex",
      flexDirection: "column", gap: 8, width: 300
    }}>
      {active.map((alert, i) => (
        <div key={i} style={{
          background: "linear-gradient(135deg, #1a0000, #2a0808)",
          border: "1px solid #e74c3c",
          borderLeft: "4px solid #e74c3c",
          borderRadius: 10,
          padding: "12px 14px",
          animation: "slideIn 0.4s ease",
          boxShadow: "0 4px 24px rgba(231,76,60,0.3)",
          display: "flex", justifyContent: "space-between", alignItems: "flex-start"
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 14 }}>🚨</span>
              <span style={{ color: "#e74c3c", fontSize: 11, fontWeight: "bold", letterSpacing: 1 }}>
                HIGH RISK DETECTED
              </span>
            </div>
            <div style={{ color: "#fff", fontSize: 15, fontWeight: "bold", marginBottom: 4 }}>
              {alert.account_id}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <div style={{
                background: "#e74c3c",
                borderRadius: 20, padding: "2px 8px",
                color: "#fff", fontSize: 11, fontWeight: "bold"
              }}>
                {alert.score}/100
              </div>
              <div style={{ color: "#8b949e", fontSize: 11 }}>Risk Score</div>
            </div>
            {alert.flags.slice(0, 2).map((f, j) => (
              <div key={j} style={{ color: "#aaa", fontSize: 11, marginTop: 2 }}>
                ⚠ {f}
              </div>
            ))}
          </div>
          <button
            onClick={() => setDismissed(d => [...d, alerts.indexOf(alert)])}
            style={{
              background: "none", border: "none",
              color: "#555", cursor: "pointer",
              fontSize: 16, padding: "0 4px", marginLeft: 8,
              lineHeight: 1
            }}>✕</button>
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(60px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default AlertSystem;
