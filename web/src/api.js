const BASE = "";

export const api = {
  // ── Settings ──────────────────────────────────────────────────
  getSettings: () => fetch(`${BASE}/api/settings`).then(r => r.json()),
  setApiKey: (key) => fetch(`${BASE}/api/settings/apikey`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: key }),
  }).then(r => r.json()),
  setProvider: (cfg) => fetch(`${BASE}/api/settings/provider`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  }).then(r => r.json()),

  // ── Groups ────────────────────────────────────────────────────
  getGroups: () => fetch(`${BASE}/api/groups`).then(r => r.json()),
  createGroup: (id, name, description = "") => fetch(`${BASE}/api/groups`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, name, description }),
  }).then(r => r.json()),
  deleteGroup: (id) => fetch(`${BASE}/api/groups/${id}`, { method: "DELETE" }).then(r => r.json()),
  openGroupFolder: (id) => fetch(`${BASE}/api/groups/${id}/open`).then(r => r.json()),

  // ── Directors（group 作用域）──────────────────────────────────
  getDirectors: (groupId = "default") => fetch(`${BASE}/api/groups/${groupId}/directors`).then(r => r.json()),
  createDirector: (groupId = "default", name, description, icon = "", role = "executor", custom_system = "") => fetch(`${BASE}/api/groups/${groupId}/directors`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, icon, role, custom_system }),
  }).then(r => r.json()),
  deleteDirector: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/directors/${name}`, { method: "DELETE" }).then(r => r.json()),
  getHistory: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/directors/${name}/history`).then(r => r.json()),
  openDirectorFolder: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/directors/${name}/open`).then(r => r.json()),

  // ── Squads（group 作用域）─────────────────────────────────────
  getSquads: (groupId = "default") => fetch(`${BASE}/api/groups/${groupId}/squads`).then(r => r.json()),
  getSquadLog: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/squads/${name}/log`).then(r => r.json()),
  stopSquad: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/squads/${name}/stop`, { method: "POST" }).then(r => r.json()),
  continueSquad: (groupId = "default", name, message = "") => fetch(`${BASE}/api/groups/${groupId}/squads/${name}/continue`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  }).then(r => r.json()),
  deleteSquad: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/squads/${name}`, { method: "DELETE" }).then(r => r.json()),
  openSquadFolder: (groupId = "default", name) => fetch(`${BASE}/api/groups/${groupId}/squads/${name}/open`).then(r => r.json()),
  getFileTree: (groupId = "default") => fetch(`${BASE}/api/groups/${groupId}/tree`).then(r => r.json()),
  getFileContent: (groupId = "default", path) => fetch(`${BASE}/api/groups/${groupId}/file?path=${encodeURIComponent(path)}`).then(r => r.json()),

  // ── 文件夹 ─────────────────────────────────────────────────────
  openFolder: (path) => fetch(`${BASE}/api/open-folder`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  }).then(r => r.json()),
};

export async function* chatStream(groupId = "default", name, message, signal) {
  const resp = await fetch(`${BASE}/api/groups/${groupId}/directors/${name}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
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
