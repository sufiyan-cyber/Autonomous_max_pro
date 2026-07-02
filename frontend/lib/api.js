async function j(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status}`);
  }
  return res.json();
}

export const api = {
  state: () => j("GET", "/api/state"),
  newGame: () => j("POST", "/api/game/new"),
  interrogate: (npc_id, line) => j("POST", "/api/interrogate", { npc_id, line }),
  endDay: () => j("POST", "/api/day/end"),
  accuse: (npc_id) => j("POST", "/api/accuse", { npc_id }),
  corkboard: () => j("GET", "/api/corkboard"),
  session: (npc_id) => j("GET", `/api/session/${npc_id}`),
};
