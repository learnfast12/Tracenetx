import React, { useEffect, useRef } from "react";

const RISK_COLOR = {
  CRITICAL: "#FF2D2D",
  HIGH:     "#FF6B00",
  MEDIUM:   "#FFB300",
  SAFE:     "#00C853",
  CLEAR:    "#00C853",
  LOW:      "#00C853",
};

const RISK_SIZE = {
  CRITICAL: 44,
  HIGH:     36,
  MEDIUM:   30,
  SAFE:     24,
  CLEAR:    24,
  LOW:      24,
};

const TIER_ORDER = ["CRITICAL","HIGH","MEDIUM","SAFE","CLEAR","LOW"];

const ROLE_COLOR = {
  CRIMINAL:     "#FF2D2D",
  RECRUITER:    "#FFA000",
  MULE:         "#00C853",
  INTERMEDIARY: "#FFD600",
  DEALER:       "#FF2D2D",
  CRYPTO:       "#FF6B00",
};
const ROLE_SIZE = { CRIMINAL: 44, RECRUITER: 34, MULE: 24, INTERMEDIARY: 32, DEALER: 44, CRYPTO: 32 };
const ROLE_TIER = { CRIMINAL: 0, RECRUITER: 1, MULE: 2, INTERMEDIARY: 3, DEALER: 4, CRYPTO: 4 };
let ROLES_ON = false;

function getTier(node) {
  const id = node.id.toUpperCase();
  if (ROLES_ON && node.role) return ROLE_TIER[node.role] !== undefined ? ROLE_TIER[node.role] : 2;
  if (id.includes("CRIMINAL")) return 0;
  if (id.includes("RECRUITER") || id.includes("RECR")) return 1;
  if (id.startsWith("ACC_") || id.includes("MULE")) return 2;
  if (id.includes("HAWALA") || id.includes("SHELL")) return 3;
  if (id.includes("DEALER") || id.includes("COLLECTOR")) return 4;
  if (id.includes("CRYPTO")) return 4;
  // Fallback for uploaded datasets with no named entity types (e.g. plain
  // ACC#### ids): spread by actual risk level instead of dumping every
  // account into one MULE-layer row.
  const level = node.risk && node.risk.level;
  if (level === "CRITICAL") return 1;
  if (level === "HIGH" || level === "MEDIUM") return 3;
  return 2;
}

function shortLabel(id) {
  if (id.length <= 9) return id;
  // RECRUITER1 -> RECR.1
  if (id.startsWith("RECRUITER")) return "RECR." + id.slice(-1);
  // CRYPTO_GW -> CRYPTO
  if (id.startsWith("CRYPTO")) return "CRYPTO";
  return id.slice(0, 8) + "…";
}

function SpiderMap({ graphData, onNodeClick, organized = true }) {
  const canvasRef = useRef(null);
  const stateRef  = useRef({ selectedId: null, pulseFrame: 0, particles: [], animId: null });

  useEffect(() => {
    if (!graphData.nodes.length) return;
    ROLES_ON = graphData.nodes.some(function (x) { return x.role && x.role !== "MULE"; });

    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");
    const rect   = canvas.getBoundingClientRect();
    const DPR    = window.devicePixelRatio || 1;
    canvas.width  = rect.width  * DPR;
    canvas.height = rect.height * DPR;
    ctx.scale(DPR, DPR);
    const W = rect.width;
    const H = rect.height;

    const state = stateRef.current;
    const edges = graphData.edges || [];
    const nodes = graphData.nodes || [];

    /* ── TIER TARGET POSITIONS ────────────────────────────────── */
    const tiers = { 0:[], 1:[], 2:[], 3:[], 4:[] };
    nodes.forEach(n => { tiers[getTier(n)].push(n); });

    const TIER_Y = { 0:H*0.08, 1:H*0.26, 2:H*0.50, 3:H*0.72, 4:H*0.90 };

    const tierTargets = {};
    const MIN_NODE_SPACING = 92; // px — below this, labels start overlapping
    const ROW_HEIGHT = 42;
    [0,1,2,3,4].forEach(ti => {
      const group = tiers[ti];
      if (!group.length) return;
      const pad = 80;
      const usableWidth = W - pad*2;
      const maxPerRow = Math.max(1, Math.floor(usableWidth / MIN_NODE_SPACING));
      group.forEach((n, i) => {
        const row = Math.floor(i / maxPerRow);
        const rowStart = row * maxPerRow;
        const countInRow = Math.min(maxPerRow, group.length - rowStart);
        const col = i - rowStart;
        const step = usableWidth / Math.max(countInRow, 1);
        tierTargets[n.id] = {
          x: countInRow === 1 ? W/2 : pad + step*col + step/2,
          y: TIER_Y[ti] + row*ROW_HEIGHT,
        };
      });
    });

    /* ── FORCE-DIRECTED RAW POSITIONS ──────────────────────────── */
    const positions = {};
    nodes.forEach((n, i) => {
      const angle = (2*Math.PI*i)/nodes.length - Math.PI/2;
      const r = Math.min(W,H)*0.35;
      positions[n.id] = {
        x: W/2 + r*Math.cos(angle),
        y: H/2 + r*Math.sin(angle),
        vx: 0, vy: 0, node: n,
      };
    });

    /* lerp factor — animates between raw and organized */
    state.lerpT      = state.lerpT ?? (organized ? 1 : 0);
    state.lerpTarget = organized ? 1 : 0;

    /* ── PHYSICS TICK ──────────────────────────────────────────── */
    function tick() {
      /* lerp toward target layout */
      const tgt = state.lerpTarget;
      state.lerpT += (tgt - state.lerpT) * 0.06;
      if (state.lerpT > 0.95) state.lerpT = 1.0;

      const ids = Object.keys(positions);

      if (state.lerpT < 1.0) {
        /* force-directed when in raw mode */
        for (let i = 0; i < ids.length; i++) {
          for (let j = i+1; j < ids.length; j++) {
            const a = positions[ids[i]], b = positions[ids[j]];
            const dx = b.x-a.x, dy = b.y-a.y;
            const dist = Math.sqrt(dx*dx+dy*dy)||1;
            const aCritical = a.node?.risk?.level === "CRITICAL";
            const bCritical = b.node?.risk?.level === "CRITICAL";
            const boost = (aCritical || bCritical) ? 1.1 : 1;
            const force = (12000*boost)/(dist*dist);
            const fx = dx/dist*force, fy = dy/dist*force;
            a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
          }
        }
        edges.forEach(e => {
          const a = positions[e.source], b = positions[e.target];
          if (!a||!b) return;
          const dx=b.x-a.x, dy=b.y-a.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
          const aCritical = a.node?.risk?.level === "CRITICAL";
          const bCritical = b.node?.risk?.level === "CRITICAL";
          const targetDist = (aCritical || bCritical) ? 240 : 180;
          const force=(dist-targetDist)*0.03;
          const fx=dx/dist*force, fy=dy/dist*force;
          a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy;
        });
        ids.forEach(id => {
          const p = positions[id];
          const isCriminal = ROLES_ON ? (positions[id].node && positions[id].node.role === "CRIMINAL") : id.toUpperCase().includes("CRIMINAL");
          const isDealer = ROLES_ON ? (positions[id].node && positions[id].node.role === "DEALER") : id.toUpperCase().includes("DEALER");
          let pullX = W/2, pullY = H/2, pull = 0.004;
          if (isCriminal) {
            pullX = W/2; pullY = H * 0.3; pull = 0.05;
          } else if (isDealer) {
            pullX = W/2; pullY = H * 0.8; pull = 0.05;
          }
          p.vx += (pullX-p.x)*pull; p.vy += (pullY-p.y)*pull;
          p.vx *= 0.6; p.vy *= 0.6;
          p.x = Math.max(55, Math.min(W-55, p.x+p.vx));
          p.y = Math.max(55, Math.min(H-55, p.y+p.vy));
        });
      }

      /* lerp all nodes toward tier target */
      const lt = Math.min(state.lerpT, 1);
      ids.forEach(id => {
        const p = positions[id];
        const tgt = tierTargets[id];
        if (!tgt) return;
        if (lt > 0.01) {
          const dx = tgt.x - p.x, dy = tgt.y - p.y;
          if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            p.x += dx * lt * 0.12;
            p.y += dy * lt * 0.12;
          } else {
            p.x = tgt.x; p.y = tgt.y;
          }
        }
      });
    }

        /* ── PARTICLES ─────────────────────────────────────────────── */
    state.particles = [];
    edges.forEach((e, ei) => {
      const count = (e.transfer_type === "SUSPECTED_CASH") ? 1 : 3;
      for (let p = 0; p < count; p++) {
        state.particles.push({
          ei, progress: Math.random(),
          speed: 0.0012 + Math.random() * 0.0012,
        });
      }
    });

    /* ── DRAW ──────────────────────────────────────────────────── */
    function draw() {
      ctx.clearRect(0, 0, W, H);

      /* grid dots */
      ctx.fillStyle = "rgba(255,255,255,0.025)";
      for (let x = 40; x < W; x += 55)
        for (let y = 40; y < H; y += 55) {
          ctx.beginPath(); ctx.arc(x, y, 1, 0, 2*Math.PI); ctx.fill();
        }

      /* tier band labels — only claim a named-entity role (CRIMINAL/RECRUITER/etc)
         when a node in that tier actually matched that naming pattern; otherwise
         label the band by what it really is: a risk-severity grouping */
      const namedTier = { 0:false, 1:false, 2:false, 3:false, 4:false };
      nodes.forEach(n => {
        const id = n.id.toUpperCase();
        if (id.includes("CRIMINAL")) namedTier[0] = true;
        if (id.includes("RECRUITER") || id.includes("RECR")) namedTier[1] = true;
        if (id.includes("HAWALA") || id.includes("SHELL")) namedTier[3] = true;
        if (id.includes("DEALER") || id.includes("COLLECTOR") || id.includes("CRYPTO")) namedTier[4] = true;
      });
      const bands = [
        { y: TIER_Y[0], label: (ROLES_ON || namedTier[0]) ? "CRIMINAL LAYER" : "CRITICAL RISK",        col: "rgba(255,45,45,0.08)"  },
        { y: TIER_Y[1], label: (ROLES_ON || namedTier[1]) ? "RECRUITER LAYER" : "CRITICAL RISK",       col: "rgba(255,107,0,0.06)"  },
        { y: TIER_Y[2], label: "STANDARD ACCOUNTS",                                      col: "rgba(0,200,83,0.04)"   },
        { y: TIER_Y[3], label: (ROLES_ON || namedTier[3]) ? "INTERMEDIARY LAYER" : "ELEVATED RISK",    col: "rgba(255,179,0,0.06)"  },
        { y: TIER_Y[4], label: (ROLES_ON || namedTier[4]) ? "COLLECTION / EXIT" : "ELEVATED RISK",     col: "rgba(0,100,255,0.07)"  },
      ];
      if (state.lerpT > 0.1) bands.forEach(b => {
        ctx.fillStyle = b.col;
        ctx.fillRect(0, b.y - 52, W, 104);
        ctx.font = "bold 10px 'IBM Plex Mono', monospace";
        ctx.fillStyle = "rgba(255,255,255,0.10)";
        ctx.textAlign = "left";
        ctx.globalAlpha = Math.min(state.lerpT, 1);
        ctx.fillText(b.label, 14, b.y - 36);
        ctx.globalAlpha = 1;
      });

      /* ── EDGES ─────────────────────────────────────────────── */
      edges.forEach(e => {
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return;

        const isCash     = e.transfer_type === "SUSPECTED_CASH";
        const sLevel     = s.node.risk?.level || "CLEAR";
        const isSelected = state.selectedId === e.source || state.selectedId === e.target;

        const edgeColor = isCash
          ? (isSelected ? "rgba(255,220,80,0.9)" : "rgba(255,220,80,0.4)")
          : sLevel === "CRITICAL"
            ? (isSelected ? "rgba(255,45,45,0.95)" : "rgba(255,45,45,0.5)")
            : sLevel === "HIGH"
              ? (isSelected ? "rgba(255,107,0,0.9)" : "rgba(255,107,0,0.35)")
              : (isSelected ? "rgba(88,166,255,0.8)" : "rgba(88,166,255,0.18)");

        /* curve control point */
        const cx = (s.x + t.x) / 2;
        const cy = (s.y + t.y) / 2;

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.quadraticCurveTo(cx, cy, t.x, t.y);

        if (isCash) {
          ctx.setLineDash([6, 5]);
          ctx.lineWidth = isSelected ? 2 : 1.5;
        } else {
          ctx.setLineDash([]);
          ctx.lineWidth = isSelected ? 2.8 : (sLevel === "CRITICAL" ? 2 : 1.2);
        }
        ctx.strokeStyle = edgeColor;
        ctx.stroke();
        ctx.setLineDash([]);

        /* arrowhead at target */
        const angle = Math.atan2(t.y - cy, t.x - cx);
        const rNode = RISK_SIZE[t.node?.risk?.level] || 24;
        const ax = t.x - (rNode + 2) * Math.cos(angle);
        const ay = t.y - (rNode + 2) * Math.sin(angle);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - 10*Math.cos(angle-0.42), ay - 10*Math.sin(angle-0.42));
        ctx.lineTo(ax - 10*Math.cos(angle+0.42), ay - 10*Math.sin(angle+0.42));
        ctx.closePath();
        ctx.fillStyle = isCash ? "rgba(255,220,80,0.7)" : edgeColor;
        ctx.fill();

        /* amount label */
        const midX = 0.25*s.x + 0.5*cx + 0.25*t.x;
        const midY = 0.25*s.y + 0.5*cy + 0.25*t.y - 7;
        if (Math.abs(t.x - s.x) + Math.abs(t.y - s.y) > 60) {
          ctx.font = "9px 'IBM Plex Mono', monospace";
          ctx.fillStyle = isSelected ? "#fff" : (isCash ? "rgba(255,220,80,0.7)" : "rgba(150,150,150,0.7)");
          ctx.textAlign = "center";
          ctx.fillText(
            (isCash ? "💵 " : "") + "₹" + (e.amount/1000).toFixed(0) + "K",
            midX, midY
          );
        }
      });

      /* ── PARTICLES ─────────────────────────────────────────── */
      state.particles.forEach(p => {
        const e = edges[p.ei];
        if (!e) return;
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return;
        if (e.transfer_type === "SUSPECTED_CASH") { p.progress += p.speed; if(p.progress>1) p.progress=0; return; }
        const sLevel = s.node?.risk?.level;
        const t2 = p.progress;
        const cx = (s.x+t.x)/2;
        const cy = (s.y+t.y)/2;
        const px = (1-t2)*(1-t2)*s.x + 2*(1-t2)*t2*cx + t2*t2*t.x;
        const py = (1-t2)*(1-t2)*s.y + 2*(1-t2)*t2*cy + t2*t2*t.y;
        ctx.beginPath();
        ctx.arc(px, py, sLevel==="CRITICAL" ? 3.5 : 2.5, 0, 2*Math.PI);
        ctx.fillStyle = sLevel==="CRITICAL"
          ? "rgba(255,45,45,0.95)"
          : sLevel==="HIGH" ? "rgba(255,107,0,0.85)"
          : "rgba(88,166,255,0.6)";
        ctx.fill();
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;
      });

      /* ── NODES ─────────────────────────────────────────────── */
      Object.values(positions).forEach(p => {
        const n      = p.node;
        const level  = n.risk?.level || "CLEAR";
        const roleOn = ROLES_ON && n.role;
        const color  = roleOn ? ROLE_COLOR[n.role] : (RISK_COLOR[level] || "#00C853");
        const r      = roleOn ? ROLE_SIZE[n.role] : (RISK_SIZE[level] || 24);
        const isSelected = state.selectedId === n.id;

        /* CRITICAL pulse ring */
        if (roleOn ? (n.role === "CRIMINAL" || n.role === "DEALER") : level === "CRITICAL") {
          const pulse = Math.sin(state.pulseFrame * 0.13) * 0.5 + 0.5;
          /* outer glow */
          const grd = ctx.createRadialGradient(p.x, p.y, r, p.x, p.y, r+28);
          grd.addColorStop(0, `rgba(255,45,45,${0.25 + pulse*0.25})`);
          grd.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(p.x, p.y, r+28, 0, 2*Math.PI);
          ctx.fillStyle = grd; ctx.fill();
          /* pulse ring */
          ctx.beginPath(); ctx.arc(p.x, p.y, r+10+pulse*10, 0, 2*Math.PI);
          ctx.strokeStyle = `rgba(255,45,45,${0.5+pulse*0.4})`;
          ctx.lineWidth = 2; ctx.stroke();
        }

        /* HIGH glow */
        if (level === "HIGH") {
          const grd = ctx.createRadialGradient(p.x, p.y, r, p.x, p.y, r+18);
          grd.addColorStop(0, "rgba(255,107,0,0.3)");
          grd.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(p.x, p.y, r+18, 0, 2*Math.PI);
          ctx.fillStyle = grd; ctx.fill();
        }

        /* selected ring */
        if (isSelected) {
          const pulse = Math.sin(state.pulseFrame * 0.1) * 0.5 + 0.5;
          ctx.beginPath(); ctx.arc(p.x, p.y, r+13+pulse*5, 0, 2*Math.PI);
          ctx.strokeStyle = `rgba(255,255,255,${0.4+pulse*0.4})`;
          ctx.lineWidth = 2.5; ctx.stroke();
        }

        /* node fill */
        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 2*Math.PI);
        /* radial gradient fill for depth */
        const fill = ctx.createRadialGradient(p.x-r*0.3, p.y-r*0.3, 1, p.x, p.y, r);
        fill.addColorStop(0, color + "ff");
        fill.addColorStop(1, color + "99");
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = isSelected ? "#fff" : color;
        ctx.lineWidth   = isSelected ? 3 : 1.8;
        ctx.stroke();

        /* label inside node */
        const label = shortLabel(n.id);
        const fs = r >= 36 ? 11 : r >= 28 ? 10 : 9;
        ctx.font = `bold ${fs}px 'IBM Plex Mono', monospace`;
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(label, p.x, p.y);

        /* risk badge below node — only for non-mule accounts */
        if (!n.id.startsWith('ACC_')) {
          ctx.font = "bold 8px 'IBM Plex Mono', monospace";
          ctx.fillStyle = color;
          ctx.textBaseline = "top";
          const badge = level === "CLEAR" ? "SAFE" : level;
          ctx.fillText(roleOn ? "" : badge, p.x, p.y + r + 4);
        }
      });

      state.pulseFrame++;
    }

    // Run simulation fully offline - freeze before first draw
    for (let i = 0; i < 600; i++) tick();
    Object.values(positions).forEach(p => { p.vx = 0; p.vy = 0; });

    function loop() {
      // positions are frozen - only particles and pulse animate
      draw();
      state.animId = requestAnimationFrame(loop);
    }
    loop();

    const handleClick = e => {
      const br = canvas.getBoundingClientRect();
      const mx = e.clientX - br.left;
      const my = e.clientY - br.top;
      for (const id in positions) {
        const p = positions[id];
        if (Math.sqrt((mx-p.x)**2 + (my-p.y)**2) < 50) {
          state.selectedId = id;
          onNodeClick(id);
          break;
        }
      }
    };
    canvas.addEventListener("click", handleClick);
    return () => { cancelAnimationFrame(state.animId); canvas.removeEventListener("click", handleClick); };
  }, [graphData, organized]);

  return (
    <canvas ref={canvasRef} style={{
      width:"100%", height:"100%",
      background:"#0d1117",
      borderRadius:"12px",
      cursor:"crosshair",
      display:"block",
    }} />
  );
}

export default SpiderMap;
