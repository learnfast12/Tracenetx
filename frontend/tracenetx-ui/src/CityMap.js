import React, { useEffect, useRef } from "react";

const CITIES = {
  Delhi:     { x: 0.52, y: 0.22 },
  Mumbai:    { x: 0.35, y: 0.52 },
  Chennai:   { x: 0.52, y: 0.75 },
  Kolkata:   { x: 0.72, y: 0.38 },
  Bangalore: { x: 0.48, y: 0.70 },
  Pune:      { x: 0.38, y: 0.55 },
  Hyderabad: { x: 0.50, y: 0.60 },
  Ahmedabad: { x: 0.36, y: 0.35 },
};

const CASE_FLOWS = [
  { from: "Delhi", to: "Mumbai", amount: 48000, case_id: "CASE001", risk: "HIGH" },
  { from: "Delhi", to: "Mumbai", amount: 48000, case_id: "CASE001", risk: "HIGH" },
  { from: "Delhi", to: "Pune", amount: 47000, case_id: "CASE001", risk: "HIGH" },
  { from: "Delhi", to: "Hyderabad", amount: 47000, case_id: "CASE001", risk: "HIGH" },
  { from: "Mumbai", to: "Delhi", amount: 94000, case_id: "CASE001", risk: "HIGH" },
  { from: "Kolkata", to: "Mumbai", amount: 72000, case_id: "CASE002", risk: "HIGH" },
  { from: "Bangalore", to: "Mumbai", amount: 72000, case_id: "CASE002", risk: "HIGH" },
  { from: "Ahmedabad", to: "Mumbai", amount: 71000, case_id: "CASE002", risk: "HIGH" },
  { from: "Mumbai", to: "Mumbai", amount: 140000, case_id: "CASE002", risk: "HIGH" },
];

function CityMap() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, W, H);

    // dot grid
    ctx.fillStyle = "rgba(255,255,255,0.03)";
    for (let x = 20; x < W; x += 35)
      for (let y = 20; y < H; y += 35) {
        ctx.beginPath();
        ctx.arc(x, y, 1, 0, 2 * Math.PI);
        ctx.fill();
      }

    // India outline - realistic shape
    const india = [
      [0.50,0.05],[0.55,0.06],[0.62,0.08],[0.68,0.12],[0.72,0.18],
      [0.75,0.25],[0.78,0.30],[0.80,0.38],[0.78,0.45],[0.74,0.50],
      [0.70,0.55],[0.65,0.62],[0.60,0.68],[0.58,0.74],[0.55,0.80],
      [0.52,0.85],[0.50,0.88],[0.48,0.85],[0.46,0.80],[0.44,0.74],
      [0.40,0.68],[0.35,0.62],[0.30,0.56],[0.26,0.48],[0.24,0.40],
      [0.25,0.32],[0.28,0.25],[0.32,0.18],[0.37,0.12],[0.42,0.08],
      [0.47,0.06],[0.50,0.05],
    ];

    ctx.beginPath();
    india.forEach(([px, py], i) => {
      const x = px * W; const y = py * H;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "rgba(88,166,255,0.06)");
    grad.addColorStop(1, "rgba(88,166,255,0.02)");
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = "rgba(88,166,255,0.25)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw flow lines
    CASE_FLOWS.forEach(flow => {
      if (flow.from === flow.to) return;
      const from = CITIES[flow.from];
      const to = CITIES[flow.to];
      if (!from || !to) return;

      const sx = from.x * W, sy = from.y * H;
      const tx = to.x * W, ty = to.y * H;
      const isHigh = flow.risk === "HIGH";

      // curved arc
      const mx = (sx + tx) / 2;
      const my = (sy + ty) / 2 - Math.sqrt((tx-sx)**2 + (ty-sy)**2) * 0.25;

      const lineGrad = ctx.createLinearGradient(sx, sy, tx, ty);
      if (isHigh) {
        lineGrad.addColorStop(0, "rgba(231,76,60,0.8)");
        lineGrad.addColorStop(1, "rgba(231,76,60,0.2)");
      } else {
        lineGrad.addColorStop(0, "rgba(88,166,255,0.6)");
        lineGrad.addColorStop(1, "rgba(88,166,255,0.1)");
      }

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.quadraticCurveTo(mx, my, tx, ty);
      ctx.strokeStyle = lineGrad;
      ctx.lineWidth = isHigh ? 2.5 : 1.5;
      ctx.stroke();

      // arrowhead at destination
      const angle = Math.atan2(ty - my, tx - mx);
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(tx - 10*Math.cos(angle-0.4), ty - 10*Math.sin(angle-0.4));
      ctx.lineTo(tx - 10*Math.cos(angle+0.4), ty - 10*Math.sin(angle+0.4));
      ctx.closePath();
      ctx.fillStyle = isHigh ? "rgba(231,76,60,0.9)" : "rgba(88,166,255,0.7)";
      ctx.fill();

      // amount label on arc
      const lx = (sx + 2*mx + tx) / 4;
      const ly = (sy + 2*my + ty) / 4 - 8;
      ctx.font = "bold 10px monospace";
      ctx.fillStyle = isHigh ? "#ff8888" : "#88aaff";
      ctx.textAlign = "center";
      ctx.fillText("₹" + (flow.amount/1000).toFixed(0) + "K", lx, ly);
    });

    // Draw city nodes
    Object.entries(CITIES).forEach(([city, pos]) => {
      const x = pos.x * W;
      const y = pos.y * H;

      const isActive = CASE_FLOWS.some(f => f.from === city || f.to === city);
      const isHighRisk = CASE_FLOWS.some(f => (f.from === city || f.to === city) && f.risk === "HIGH");

      // glow
      if (isHighRisk) {
        const glow = ctx.createRadialGradient(x, y, 4, x, y, 20);
        glow.addColorStop(0, "rgba(231,76,60,0.4)");
        glow.addColorStop(1, "rgba(231,76,60,0)");
        ctx.beginPath();
        ctx.arc(x, y, 20, 0, 2*Math.PI);
        ctx.fillStyle = glow;
        ctx.fill();
      }

      // node circle
      ctx.beginPath();
      ctx.arc(x, y, isActive ? 9 : 6, 0, 2*Math.PI);
      ctx.fillStyle = isHighRisk ? "#e74c3c" : isActive ? "#58a6ff" : "#30363d";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // city label
      ctx.font = "bold 12px monospace";
      ctx.fillStyle = isHighRisk ? "#ff8888" : "#e6edf3";
      ctx.textAlign = "center";
      ctx.fillText(city, x, y - 16);

      // total flow amount
      const totalFlow = CASE_FLOWS
        .filter(f => f.from === city || f.to === city)
        .reduce((s, f) => s + f.amount, 0);
      if (totalFlow > 0) {
        ctx.font = "10px monospace";
        ctx.fillStyle = "#8b949e";
        ctx.fillText("₹" + (totalFlow/1000).toFixed(0) + "K", x, y + 22);
      }
    });

    // Legend
    const lx = 20, ly = H - 80;
    ctx.fillStyle = "rgba(22,27,34,0.9)";
    ctx.beginPath();
    ctx.roundRect(lx, ly, 200, 65, 8);
    ctx.fill();
    ctx.strokeStyle = "#30363d";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.font = "bold 11px monospace";
    ctx.fillStyle = "#e6edf3";
    ctx.textAlign = "left";
    ctx.fillText("🗺 India Money Flow Map", lx + 12, ly + 18);

    ctx.beginPath(); ctx.arc(lx+20, ly+36, 5, 0, 2*Math.PI);
    ctx.fillStyle = "#e74c3c"; ctx.fill();
    ctx.font = "10px monospace"; ctx.fillStyle = "#8b949e";
    ctx.fillText("High Risk Flow", lx+32, ly+40);

    ctx.beginPath(); ctx.arc(lx+20, ly+52, 5, 0, 2*Math.PI);
    ctx.fillStyle = "#58a6ff"; ctx.fill();
    ctx.fillText("Normal Flow", lx+32, ly+56);

  }, []);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", background: "#0d1117" }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
    </div>
  );
}

export default CityMap;
