const BASE = "";

export const api = {
  getSettings: () => fetch(`${BASE}/api/settings`).then(r => r.json()),
  setApiKey: (key) => fetch(`${BASE}/api/settings/apikey`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key: key }) }).then(r => r.json()),
  getPlanners: () => fetch(`${BASE}/api/planners`).then(r => r.json()),
  createPlanner: (name, description, icon = "") => fetch(`${BASE}/api/planners`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, description, icon }) }).then(r => r.json()),
  deletePlanner: (name) => fetch(`${BASE}/api/planners/${name}`, { method: "DELETE" }).then(r => r.json()),
  getHistory: (name) => fetch(`${BASE}/api/planners/${name}/history`).then(r => r.json()),
  chat: (name, message) => fetch(`${BASE}/api/planners/${name}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  }).then(r => r.json()),
  openPlannerFolder: (name) => fetch(`${BASE}/api/planners/${name}/open`).then(r => r.json()),
  openSquadFolder: (name) => fetch(`${BASE}/api/squads/${name}/open`).then(r => r.json()),
  deleteSquad: (name) => fetch(`${BASE}/api/squads/${name}`, { method: "DELETE" }).then(r => r.json()),
  openFolder: (path) => fetch(`${BASE}/api/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  }).then(r => r.json()),
};

export async function* chatStream(name, message) {
  const resp = await fetch(`${BASE}/api/planners/${name}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}

export function createWS(onMessage) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
