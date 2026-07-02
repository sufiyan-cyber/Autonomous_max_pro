"use client";
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { api } from "../lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const COLORS = {
  suspect: "#d9a441",
  victim: "#b3402e",
  claim: "#e8ddc4",
  lie: "#c0392b",
  entity: "#4d7c74",
  default: "#8a7d5e",
};

export default function Corkboard({ onClose }) {
  const [data, setData] = useState(null);
  const [source, setSource] = useState("");
  const [dims, setDims] = useState({ w: 800, h: 500 });
  const fgRef = useRef();

  useEffect(() => {
    api.corkboard().then((g) => {
      setData({ nodes: g.nodes, links: g.links });
      setSource(g.graph_source);
    });
    const measure = () => setDims({ w: window.innerWidth, h: window.innerHeight - 110 });
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  return (
    <div className="board-wrap">
      <div className="board-head">
        <h2 className="serif">THE CORKBOARD</h2>
        <span className="src">
          {source === "cognee"
            ? "live knowledge graph — pulled from Cognee memory"
            : "testimony ledger view"}
        </span>
        <button className="btn small" onClick={onClose}>CLOSE</button>
      </div>
      <div className="board-body">
        {data ? (
          <ForceGraph2D
            ref={fgRef}
            width={dims.w}
            height={dims.h}
            graphData={data}
            backgroundColor="#0d0b08"
            nodeLabel={(n) => `${n.label} (${n.type})`}
            nodeCanvasObject={(node, ctx, scale) => {
              const color = COLORS[node.type] || COLORS.default;
              const big = node.type === "suspect" || node.type === "victim";
              const r = big ? 9 : 4.5;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
              if (node.type === "lie") {
                ctx.strokeStyle = "#e8ddc4";
                ctx.lineWidth = 1;
                ctx.stroke();
              }
              if (big || scale > 1.6) {
                const label = node.label.length > 42 ? node.label.slice(0, 42) + "…" : node.label;
                ctx.font = `${big ? 5 : 3.5}px "IBM Plex Mono", monospace`;
                ctx.fillStyle = big ? "#e8ddc4" : "#8a7d5e";
                ctx.textAlign = "center";
                ctx.fillText(label, node.x, node.y + r + 5);
              }
            }}
            linkColor={(l) => (l.dataset === "claims" ? "rgba(192,57,43,0.55)" : "rgba(138,125,94,0.3)")}
            linkWidth={(l) => (l.dataset === "claims" ? 1.4 : 0.6)}
            linkDirectionalParticles={0}
            cooldownTicks={120}
          />
        ) : (
          <div className="empty-slate">pinning photographs, stretching string…</div>
        )}
      </div>
      <div className="legend">
        <span><i style={{ background: COLORS.suspect }} /> suspect</span>
        <span><i style={{ background: COLORS.victim }} /> victim</span>
        <span><i style={{ background: COLORS.claim }} /> testimony</span>
        <span><i style={{ background: COLORS.lie }} /> known lie</span>
        <span><i style={{ background: COLORS.entity }} /> memory entity</span>
      </div>
    </div>
  );
}
