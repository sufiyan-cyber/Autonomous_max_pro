"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import Corkboard from "../components/Corkboard";

const PORTRAITS = { widow: "🕯️", doctor: "🩺", barmaid: "🍸", captain: "⚓", harbormaster: "🗒️" };

export default function Game() {
  const [state, setState] = useState(null);
  const [active, setActive] = useState(null);        // npc id being interrogated
  const [chat, setChat] = useState([]);              // current session lines
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [showBoard, setShowBoard] = useState(false);
  const [night, setNight] = useState(null);          // end-of-day payload
  const [accusing, setAccusing] = useState(false);
  const [error, setError] = useState("");
  const chatEnd = useRef(null);

  const refresh = useCallback(() => api.state().then(setState).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [chat]);

  async function startGame() {
    setBusy(true); setError("");
    try {
      setState(await api.newGame());
      setActive(null); setChat([]); setNight(null); setAccusing(false);
    } catch (e) { setError(String(e.message || e)); }
    setBusy(false);
  }

  function startOver() {
    if (window.confirm("Start over? The town forgets everything — all five memories are wiped and reseeded.")) {
      startGame();
    }
  }

  async function pickSuspect(id) {
    setActive(id);
    const s = await api.session(id).catch(() => ({ turns: [] }));
    setChat(
      s.turns.flatMap((t) => [
        { who: "detective", text: t.detective },
        { who: "npc", text: t.npc },
      ])
    );
  }

  async function ask() {
    const line = input.trim();
    if (!line || !active || busy) return;
    setInput("");
    setChat((c) => [...c, { who: "detective", text: line }]);
    setBusy(true); setError("");
    try {
      const r = await api.interrogate(active, line);
      setChat((c) => {
        const next = [...c, { who: "npc", text: r.dialogue }];
        if (r.caught_contradiction)
          next.push({ who: "contradiction", text: "They remember what was said before — and they caught you twisting it." });
        for (const t of r.new_threads)
          next.push({ who: "event", text: "EVIDENCE THREAD UNCOVERED — " + t });
        return next;
      });
      refresh();
    } catch (e) { setError(String(e.message || e)); }
    setBusy(false);
  }

  async function endDay() {
    setBusy(true); setError("");
    try {
      const r = await api.endDay();
      setNight(r);
      setActive(null); setChat([]);
      refresh();
    } catch (e) { setError(String(e.message || e)); }
    setBusy(false);
  }

  async function accuse(id) {
    setBusy(true); setError("");
    try {
      await api.accuse(id);
      setAccusing(false);
      refresh();
    } catch (e) { setError(String(e.message || e)); }
    setBusy(false);
  }

  if (!state) return <div className="title-screen"><span className="spinner">DEVELOPING FILM…</span></div>;

  // ----- endings -----
  if (state.game_over && state.ending) {
    const e = state.ending;
    return (
      <div className="overlay">
        <h2 className="serif">{e.epilogue}</h2>
        <div className="body">{e.narration}</div>
        <p style={{ marginTop: 24, color: e.correct ? "var(--teal)" : "var(--red)", letterSpacing: 2 }}>
          {e.correct ? "JUSTICE, FOR ONCE." : "THE KILLER WALKS."}
        </p>
        <button className="btn" style={{ marginTop: 30 }} onClick={startGame} disabled={busy}>
          {busy ? "…" : "REOPEN THE CASE"}
        </button>
      </div>
    );
  }

  // ----- title screen -----
  if (!state.started) {
    return (
      <div className="title-screen">
        <h1>ALIBI</h1>
        <div className="tagline typewriter">the town that remembers</div>
        <p className="case-brief typewriter">{state.case.setting}</p>
        <button className="btn" onClick={startGame} disabled={busy}>
          {busy ? "SEEDING FIVE MINDS…" : "TAKE THE CASE"}
        </button>
        {error && <p style={{ color: "var(--red)", marginTop: 14, fontSize: 12 }}>{error}</p>}
        <div className="powered">EVERY SUSPECT HAS A REAL MEMORY · POWERED BY COGNEE</div>
      </div>
    );
  }

  // ----- night transition -----
  if (night) {
    return (
      <div className="overlay">
        <h2 className="serif">{night.game_over ? "THE LAST NIGHT" : `NIGHT ${state.day - 1}`}</h2>
        <div className="body">
          {"Night falls on Grayharbor. Doors lock. Lamps burn low.\nAnd the town talks.\n"}
        </div>
        <div style={{ marginTop: 18, maxWidth: 640 }}>
          {night.gossip.length === 0 && <p className="gossip-item">The rain kept even the gossips indoors.</p>}
          {night.gossip.map((g, i) => (
            <p key={i} className="gossip-item typewriter">→ {g.to_npc.toUpperCase()} hears: “{g.rumor}”</p>
          ))}
        </div>
        {night.memories_faded > 0 && (
          <p className="fade-note">{night.memories_faded} small detail{night.memories_faded > 1 ? "s" : ""} faded from the town’s memory…</p>
        )}
        <button className="btn" style={{ marginTop: 30 }} onClick={() => { setNight(null); if (night.game_over) refresh(); }}>
          {night.game_over ? "FACE THE MORNING" : `BEGIN DAY ${state.day}`}
        </button>
      </div>
    );
  }

  const activeNpc = state.suspects.find((s) => s.id === active);

  return (
    <div className="shell">
      <div className="topbar">
        <h1>ALIBI</h1>
        <span className="sub typewriter">the town that remembers</span>
        <div className="meta">
          <span>DAY <b>{state.day}</b>/{state.days_total}</span>
          <span>QUESTIONS <b>{state.actions_left}</b></span>
          <span>THREADS <b>{state.threads_found.length}</b>/{state.threads_total}</span>
          <button className="btn small" onClick={startOver} disabled={busy} title="Wipe all memories and start a fresh case">
            START OVER
          </button>
        </div>
      </div>

      <div className="columns">
        {/* left: suspects */}
        <div>
          {state.suspects.map((s) => (
            <div key={s.id} className={"suspect-card" + (active === s.id ? " active" : "")} onClick={() => pickSuspect(s.id)}>
              <div className="portrait">{PORTRAITS[s.portrait] || "❓"}</div>
              <div className="name">{s.name}</div>
              <div className="role">{s.role}</div>
              <div className="story">{s.public_story}</div>
              <div className="trust" title={`trust ${s.trust}`}>
                {[-5,-4,-3,-2,-1,1,2,3,4,5].map((i) => (
                  <i key={i} className={s.trust >= i && i > 0 ? "pos" : s.trust <= i && i < 0 ? "neg" : ""} />
                ))}
              </div>
            </div>
          ))}
          <button className="btn small" style={{ width: "100%", marginTop: 6 }} onClick={() => setShowBoard(true)}>
            OPEN CORKBOARD
          </button>
          <button className="btn small danger" style={{ width: "100%", marginTop: 8 }} onClick={() => setAccusing(true)}>
            MAKE THE ACCUSATION
          </button>
          <button className="btn small" style={{ width: "100%", marginTop: 8 }} onClick={endDay} disabled={busy}>
            {busy ? "…" : "END THE DAY"}
          </button>
        </div>

        {/* center: interrogation */}
        <div className="interrogation">
          {activeNpc ? (
            <>
              <div className="header">
                <span style={{ fontSize: 24 }}>{PORTRAITS[activeNpc.portrait]}</span>
                <span className="who serif">{activeNpc.name}</span>
                <span className="hint">they remember every word — across every day</span>
              </div>
              <div className="chat">
                {chat.length === 0 && (
                  <div className="empty-slate typewriter">
                    {activeNpc.name} watches you take out your notebook.
                  </div>
                )}
                {chat.map((l, i) => (
                  <div key={i} className={"line " + l.who}>
                    {l.who === "detective" && <span className="tag">YOU</span>}
                    {l.who === "npc" && <span className="tag">{activeNpc.name.toUpperCase()}</span>}
                    {l.text}
                  </div>
                ))}
                {busy && <div className="spinner typewriter">they consider their words…</div>}
                <div ref={chatEnd} />
              </div>
              <div className="composer">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && ask()}
                  placeholder={state.actions_left > 0 ? "Ask your question, detective…" : "No questions left today — end the day."}
                  disabled={busy || state.actions_left <= 0}
                />
                <button onClick={ask} disabled={busy || state.actions_left <= 0}>ASK</button>
              </div>
            </>
          ) : (
            <div className="empty-slate typewriter">
              Fog on the glass. Five doors in Grayharbor,<br />
              and behind each one, somebody remembering.<br /><br />
              Choose who to question.
            </div>
          )}
        </div>

        {/* right: journal */}
        <div>
          <div className="rail-box">
            <h3>Evidence Threads</h3>
            <div className="threads">
              {Array.from({ length: state.threads_total }).map((_, i) => (
                <div key={i} className={"pip" + (i < state.threads_found.length ? " found" : "")} />
              ))}
            </div>
            <p className="thread-label">
              Convicting the killer takes at least two threads of hard evidence.
            </p>
          </div>
          <div className="rail-box">
            <h3>Case Journal</h3>
            {state.journal.length === 0 && <div className="entry">Nothing yet. Make them talk.</div>}
            {state.journal.slice().reverse().map((e, i) => (
              <div key={i} className={"entry" + (i === 0 ? " hot" : "")}>{e}</div>
            ))}
          </div>
          <div className="rail-box">
            <h3>Overheard</h3>
            {state.gossip_log.length === 0 && <div className="entry">The town is quiet. For now.</div>}
            {state.gossip_log.slice(-6).reverse().map((g, i) => (
              <div key={i} className="entry">night {g.day} → {g.to_npc}: “{g.rumor}”</div>
            ))}
          </div>
          {error && <div className="rail-box"><h3 style={{ color: "var(--red)" }}>Trouble</h3><div className="entry">{error}</div></div>}
        </div>
      </div>

      {showBoard && <Corkboard onClose={() => setShowBoard(false)} />}

      {accusing && (
        <div className="overlay">
          <h2 className="serif">POINT THE FINGER</h2>
          <div className="body" style={{ textAlign: "center" }}>
            One accusation. No second chances.{"\n"}
            You hold {state.threads_found.length} of {state.threads_total} evidence threads.
          </div>
          <div className="accuse-list">
            {state.suspects.map((s) => (
              <button key={s.id} className="btn danger" onClick={() => accuse(s.id)} disabled={busy}>
                {s.name.toUpperCase()}
              </button>
            ))}
          </div>
          <button className="btn small" style={{ marginTop: 26 }} onClick={() => setAccusing(false)}>
            NOT YET
          </button>
        </div>
      )}
    </div>
  );
}
