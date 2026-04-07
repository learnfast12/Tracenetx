import React, { useEffect, useRef, useState } from "react";

const riskColor = (level) => {
  if (level === "HIGH") return "#E74C3C";
  if (level === "MEDIUM") return "#F39C12";
  return "#27AE60";
};

function SpiderMap({ graphData, onNodeClick }) {
  const canvasRef = useRef(null);
  const stateRef = useRef({
    positions: {},
    frame: 0,
    animId: null,
    selectedId: null,
    pulseFrame: 0,
    particles: [],
  });

  useEffect(() => {
    if (!graphData.nodes.length) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    const W = rect.width;
    const H = rect.height;

    const state = stateRef.current;
    const positions = {};
    graphData.nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / graphData.nodes.length - Math.PI / 2;
      const r = Math.min(W, H) * 0.42;
      positions[n.id] = {
        x: W / 2 + r * Math.cos(angle),
        y: H / 2 + r * Math.sin(angle),
        vx: 0, vy: 0,
        node: n,
      };
    });
    state.positions = positions;
    state.frame = 0;
    state.particles = [];

    const edges = graphData.edges;

    // init particles on edges
    edges.forEach((e, ei) => {
      for (let p = 0; p < 2; p++) {
        state.particles.push({
          edgeIndex: ei,
          progress: Math.random(),
          speed: 0.003 + Math.random() * 0.002,
        });
      }
    });

    function tick() {
      const ids = Object.keys(positions);
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = positions[ids[i]], b = positions[ids[j]];
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.sqrt(dx*dx + dy*dy) || 1;
          const force = 12000 / (dist * dist);
          const fx = (dx/dist)*force, fy = (dy/dist)*force;
          a.vx -= fx; a.vy -= fy;
          b.vx += fx; b.vy += fy;
        }
      }
      edges.forEach(e => {
        const a = positions[e.source], b = positions[e.target];
        if (!a || !b) return;
        const dx = b.x-a.x, dy = b.y-a.y;
        const dist = Math.sqrt(dx*dx+dy*dy)||1;
        const target = 180;
        const force = (dist-target)*0.04;
        const fx = (dx/dist)*force, fy = (dy/dist)*force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      });
      ids.forEach(id => {
        const p = positions[id];
        p.vx += (W/2 - p.x)*0.005;
        p.vy += (H/2 - p.y)*0.005;
        p.vx *= 0.8; p.vy *= 0.8;
        p.x = Math.max(55, Math.min(W-55, p.x+p.vx));
        p.y = Math.max(55, Math.min(H-55, p.y+p.vy));
      });
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);

      // dot grid
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      for (let x = 30; x < W; x += 40)
        for (let y = 30; y < H; y += 40) {
          ctx.beginPath();
          ctx.arc(x, y, 1.2, 0, 2*Math.PI);
          ctx.fill();
        }

      // edges
      edges.forEach((e, ei) => {
        const s = positions[e.source], t = positions[e.target];
        if (!s || !t) return;
        const isHigh = s.node.risk?.level==="HIGH" || t.node.risk?.level==="HIGH";
        const isSelected = state.selectedId === e.source || state.selectedId === e.target;

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = isSelected
          ? (isHigh ? "rgba(231,76,60,0.9)" : "rgba(88,166,255,0.8)")
          : (isHigh ? "rgba(231,76,60,0.35)" : "rgba(88,166,255,0.15)");
        ctx.lineWidth = isSelected ? 2.5 : (isHigh ? 1.8 : 1);
        ctx.stroke();

        // arrowhead
        const angle = Math.atan2(t.y-s.y, t.x-s.x);
        const rNode = 32;
        const ax = t.x - rNode*Math.cos(angle);
        const ay = t.y - rNode*Math.sin(angle);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax-9*Math.cos(angle-0.4), ay-9*Math.sin(angle-0.4));
        ctx.lineTo(ax-9*Math.cos(angle+0.4), ay-9*Math.sin(angle+0.4));
        ctx.closePath();
        ctx.fillStyle = isHigh ? "rgba(231,76,60,0.7)" : "rgba(88,166,255,0.4)";
        ctx.fill();

        // amount label
        const dx = t.x-s.x, dy = t.y-s.y;
        const dist = Math.sqrt(dx*dx+dy*dy);
        if (dist > 80) {
          const mx = (s.x+t.x)/2, my = (s.y+t.y)/2;
          ctx.font = "bold 10px monospace";
          ctx.fillStyle = isSelected ? "#fff" : "#8b949e";
          ctx.textAlign = "center";
          ctx.fillText("₹"+(e.amount/1000).toFixed(0)+"K", mx, my-6);
        }
      });

      // moving particles on edges
      state.particles.forEach(p => {
        const e = edges[p.edgeIndex];
        if (!e) return;
        const s = positions[e.source], t = positions[e.target];
        if (!s || !t) return;
        const isHigh = s.node.risk?.level==="HIGH" || t.node.risk?.level==="HIGH";
        const px = s.x + (t.x-s.x)*p.progress;
        const py = s.y + (t.y-s.y)*p.progress;
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, 2*Math.PI);
        ctx.fillStyle = isHigh ? "rgba(231,76,60,0.9)" : "rgba(88,166,255,0.7)";
        ctx.fill();
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;
      });

      // nodes
      Object.values(positions).forEach(p => {
        const n = p.node;
        const color = riskColor(n.risk?.level);
        const isHigh = n.risk?.level==="HIGH";
        const isMed = n.risk?.level==="MEDIUM";
        const isSelected = state.selectedId === n.id;
        const r = isHigh ? 34 : isMed ? 29 : 25;

        // selected ring pulse
        if (isSelected) {
          const pulse = Math.sin(state.pulseFrame * 0.1) * 0.5 + 0.5;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r + 12 + pulse*6, 0, 2*Math.PI);
          ctx.strokeStyle = `rgba(255,255,255,${0.3 + pulse*0.3})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // glow for high risk
        if (isHigh) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, r+14, 0, 2*Math.PI);
          const grd = ctx.createRadialGradient(p.x, p.y, r, p.x, p.y, r+14);
          grd.addColorStop(0, "rgba(231,76,60,0.35)");
          grd.addColorStop(1, "rgba(231,76,60,0)");
          ctx.fillStyle = grd;
          ctx.fill();
        }

        // node circle
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 2*Math.PI);
        ctx.fillStyle = color + (isSelected ? "ff" : "cc");
        ctx.fill();
        ctx.strokeStyle = isSelected ? "#fff" : (isHigh ? "#ff5555" : "rgba(255,255,255,0.4)");
        ctx.lineWidth = isSelected ? 3 : (isHigh ? 2.5 : 1.2);
        ctx.stroke();

        // label
        ctx.font = `bold ${isSelected ? 12 : 11}px monospace`;
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(n.id.length > 8 ? n.id.slice(0,7)+"…" : n.id, p.x, p.y);

        // risk label
        ctx.font = "9px monospace";
        ctx.fillStyle = isHigh ? "#ff8888" : "#8b949e";
        ctx.textBaseline = "top";
        ctx.fillText(n.risk?.level||"LOW", p.x, p.y+r+4);
      });

      state.pulseFrame++;
    }

    let animId;
    function loop() {
      if (state.frame < 120) { tick(); state.frame++; }
      draw();
      animId = requestAnimationFrame(loop);
    }
    loop();
    state.animId = animId;

    const handleClick = (e) => {
      const br = canvas.getBoundingClientRect();
      const mx = (e.clientX - br.left);
      const my = (e.clientY - br.top);
      for (const id in positions) {
        const p = positions[id];
        const dist = Math.sqrt((mx-p.x)**2 + (my-p.y)**2);
        if (dist < 40) {
          state.selectedId = id;
          state.pulseFrame = 0;
          onNodeClick(id);
          break;
        }
      }
    };
    canvas.addEventListener("click", handleClick);

    return () => {
      cancelAnimationFrame(state.animId);
      canvas.removeEventListener("click", handleClick);
    };
  }, [graphData]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: "100%", height: "100%",
        background: "#0d1117",
        borderRadius: "12px",
        cursor: "crosshair",
        display: "block",
      }}
    />
  );
}

export default SpiderMap;
