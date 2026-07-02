import { useState, useEffect, useRef, useCallback, createContext, useContext } from "react";
import { api, chatStream, createWS } from "./api";
import { THEMES } from "./themes";
import { Spinner, Modal, Chip, LogLine, Bubble, ChatInput, TokenBar } from "./components";

const ThemeCtx = createContext(THEMES.dark);
const useC = () => useContext(ThemeCtx);
const PLANNER_ICONS = ["🤖","🧠","⚡","🔬","🎯","🛠","🚀","🌐","💡","🔭","🧬","🎨"];
const PROVIDER_OPTIONS = [
  { value: "openai", label: "DeepSeek / OpenAI 兼容", placeholder: "https://api.deepseek.com", modelDefault: "deepseek-chat" },
  { value: "claude", label: "Claude（Anthropic）", placeholder: "https://api.anthropic.com（可留空）", modelDefault: "claude-opus-4-5" },
];

function GlobalStyle({ C }) {
  return <style>{`
    body { background:${C.bg}; color:${C.text}; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    input,button,textarea { font-family:inherit; font-size:inherit; }
    .resize-handle { transition: background .15s, opacity .15s; }
    .resize-handle:hover { background:${C.accent}; opacity:.75; }
  `}</style>;
}

function GradientOrb({ style }) {
  return <div style={{ position:"absolute", borderRadius:"50%", filter:"blur(80px)", pointerEvents:"none", ...style }} />;
}

function Logo({ themeName, onToggle, collapsed, onCollapse, C }) {
  if (collapsed) {
    return (
      <div style={{ padding:"12px 0", display:"flex", flexDirection:"column", alignItems:"center", gap:10 }}>
        <div style={{ width:32, height:32, borderRadius:9, background:C.name === "light" ? "linear-gradient(135deg,#2f3136,#5b5f66)" : C.accentGrad, display:"flex", alignItems:"center", justifyContent:"center", fontSize:14, fontWeight:900, color:"#fff", fontFamily:"monospace", boxShadow:`0 4px 16px ${C.accentSoft}` }}>E</div>
        <button onClick={onCollapse} style={{ background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid, borderRadius:6, padding:"3px 8px", cursor:"pointer", fontSize:12 }}>›</button>
      </div>
    );
  }
  return (
    <div style={{ padding:"18px 20px 14px", display:"flex", alignItems:"center", gap:8 }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0,
        background: C.name === "light" ? "linear-gradient(135deg,#2f3136,#5b5f66)" : C.accentGrad, display:"flex", alignItems:"center", justifyContent:"center",
        fontSize: 14, fontWeight: 900, color: "#fff", fontFamily:"monospace",
        boxShadow: `0 4px 16px ${C.accentSoft}`
      }}>E</div>
      <div style={{ flex:1 }}>
        <div style={{ fontSize:13, fontWeight:800, color:C.name === "light" ? C.text : "transparent", background:C.name === "light" ? "none" : C.accentGrad, WebkitBackgroundClip:"text", backgroundClip:"text", WebkitTextFillColor:C.name === "light" ? C.text : "transparent", letterSpacing:2, fontFamily:"monospace", display:"inline-block" }}>ECHELON</div>
        <div style={{ fontSize:9, color:C.textDim, letterSpacing:1 }}>AI FRAMEWORK</div>
      </div>
      <button onClick={onToggle} style={{ background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid, borderRadius:6, padding:"3px 8px", cursor:"pointer", fontSize:13, backdropFilter:"blur(4px)" }}>
        {themeName==="light"?"☀":themeName==="dark"?"◑":"☾"}
      </button>
      <button onClick={onCollapse} style={{ background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid, borderRadius:6, padding:"3px 7px", cursor:"pointer", fontSize:12 }}>‹</button>
    </div>
  );
}

function NavItem({ director, active, onSelect, onDelete, onOpenFolder, C }) {
  const [hov, setHov] = useState(false);
  return (
    <div onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      onClick={() => onSelect(director)}
      style={{
        padding:"8px 12px", borderRadius:C.radius, marginBottom:2, cursor:"pointer",
        display:"flex", alignItems:"center", gap:8, position:"relative", transition:"all .15s",
        background: active ? C.accentSoft : hov ? C.glass : "transparent",
        border: `1px solid ${active ? C.userBorder : "transparent"}`,
      }}>
      <span style={{ fontSize:16, flexShrink:0 }}>{director.icon||"🤖"}</span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontWeight:500, color:active?C.accent:C.text, fontSize:13, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{director.id}</div>
        {director.description && <div style={{ fontSize:10, color:C.textDim, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{director.description}</div>}
      </div>
      {(hov||active) && (
        <div style={{ display:"flex", gap:2 }}>
          <button onClick={e=>{e.stopPropagation();onOpenFolder(director.id);}}
            style={{ background:"none", border:"none", cursor:"pointer", fontSize:11, padding:"2px 4px", borderRadius:4, color:C.textDim }}
            onMouseEnter={e=>{e.currentTarget.style.background=C.accentSoft;e.currentTarget.textContent="📂";}}
            onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.textContent="📁";}}>📁</button>
          <button onClick={e=>{e.stopPropagation();onDelete(director.id);}}
            style={{ background:"none", border:"none", cursor:"pointer", fontSize:11, padding:"2px 4px", borderRadius:4, color:C.textDim }}
            onMouseEnter={e=>{e.currentTarget.style.background="rgba(239,68,68,.15)";e.currentTarget.style.color="#ef4444";}}
            onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.style.color=C.textDim;}}>✕</button>
        </div>
      )}
    </div>
  );
}

function FileViewerModal({ file, onClose }) {
  const C = useC();
  if (!file) return null;
  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:12, marginBottom:12 }}>
        <div style={{ fontWeight:700, fontSize:14, color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>📄 {file.path}</div>
        {file.truncated && <span style={{ color:C.yellow, fontSize:11 }}>已截断</span>}
      </div>
      <textarea readOnly value={file.content || ""} style={{
        width:"100%", height:"58vh", resize:"vertical", background:C.logBg, color:C.text,
        border:`1px solid ${C.border}`, borderRadius:C.radius, padding:"12px",
        fontFamily:"'JetBrains Mono','Fira Code',ui-monospace,monospace", fontSize:12, lineHeight:1.6,
        outline:"none", whiteSpace:"pre",
      }} />
      <div style={{ display:"flex", justifyContent:"flex-end", marginTop:12 }}>
        <button onClick={onClose} style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600 }}>关闭</button>
      </div>
    </Modal>
  );
}

function FileTreeNode({ node, depth = 0, expanded, toggle, onOpenFile, C }) {
  const isDir = node.type === "dir";
  const key = node.path || node.name;
  const open = expanded[key] ?? depth < 1;
  return (
    <div>
      <div onClick={() => isDir ? toggle(key) : onOpenFile(node)} title={node.path || node.name} style={{
        display:"flex", alignItems:"center", gap:5, padding:"3px 6px", paddingLeft:6 + depth * 12,
        borderRadius:6, cursor:"pointer", color:isDir ? C.textMid : C.textDim,
        fontSize:11, whiteSpace:"nowrap", minWidth:"max-content",
      }}>
        <span style={{ width:12, color:isDir ? C.accent : C.textDim }}>{isDir ? (open ? "▾" : "▸") : ""}</span>
        <span>{isDir ? (open ? "📂" : "📁") : "📄"}</span>
        <span>{node.name}</span>
      </div>
      {isDir && open && node.children?.map(child => (
        <FileTreeNode key={`${child.path || child.name}-${depth}`} node={child} depth={depth + 1} expanded={expanded} toggle={toggle} onOpenFile={onOpenFile} C={C} />
      ))}
    </div>
  );
}

function FileTree({ groupId }) {
  const C = useC();
  const [tree, setTree] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [viewer, setViewer] = useState(null);
  const loadTree = useCallback(() => api.getFileTree(groupId).then(setTree), [groupId]);
  useEffect(() => { loadTree(); }, [loadTree]);
  const toggle = key => setExpanded(prev => ({ ...prev, [key]: !(prev[key] ?? false) }));
  const openFile = async node => setViewer(await api.getFileContent(groupId, node.path));
  return (
    <div style={{ borderTop:`1px solid ${C.border}`, padding:"8px 10px 10px", height:"32%", minHeight:140, overflow:"hidden", display:"flex", flexDirection:"column" }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 4px 6px", flexShrink:0 }}>
        <span style={{ fontSize:10, fontWeight:700, color:C.textDim, letterSpacing:1.5, textTransform:"uppercase" }}>文件树</span>
        <button onClick={loadTree} style={{ background:"none", border:"none", color:C.textDim, cursor:"pointer", fontSize:11 }}>刷新</button>
      </div>
      <div style={{ flex:1, overflow:"auto", paddingBottom:4 }}>
        {tree ? <FileTreeNode node={tree} expanded={expanded} toggle={toggle} onOpenFile={openFile} C={C} /> : <div style={{ color:C.textDim, fontSize:11, padding:6 }}>加载中…</div>}
      </div>
      {viewer && <FileViewerModal file={viewer} onClose={()=>setViewer(null)} />}
    </div>
  );
}

function Sidebar({ groups, selectedGroup, onSelectGroup, onNewGroup, onDeleteGroup,
                   directors, selected, onSelect, onNew, onDelete,
                   settings, onSettings, themeName, onToggleTheme, collapsed, onCollapse, width = 260 }) {
  const C = useC();
  const [hovGroup, setHovGroup] = useState(null);
  const sideWidth = collapsed ? 64 : width;
  return (
    <div style={{
      width: sideWidth, minWidth: sideWidth, height:"100%",
      background: C.surface, borderRight:`1px solid ${C.border}`,
      display:"flex", flexDirection:"column", transition: collapsed ? "width .2s ease" : "none", position:"relative", overflow:"hidden",
      boxShadow: collapsed ? `4px 0 18px ${C.glassBorder}` : "0 0 40px rgba(15,23,42,.025)",
      backdropFilter:"blur(18px)",
    }}>
      {!collapsed && <GradientOrb style={{ width:200, height:200, top:-60, left:-60, background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 70%)` }} />}
      <Logo themeName={themeName} onToggle={onToggleTheme} collapsed={collapsed} onCollapse={onCollapse} C={C} />
      {!collapsed && (
        <>
          {/* ── Group 选择栏 ───────────────────────────── */}
          <div style={{ padding:"0 12px 6px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <span style={{ fontSize:10, fontWeight:700, color:C.textDim, letterSpacing:1.5, textTransform:"uppercase" }}>项目组</span>
            <button onClick={onNewGroup} style={{
              background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid,
              cursor:"pointer", fontSize:11, borderRadius:5, padding:"2px 7px",
            }} title="新建项目组">＋</button>
          </div>
          <div style={{ padding:"0 8px 8px", display:"flex", flexWrap:"wrap", gap:4 }}>
            {groups.map(g => {
              const active = g.id === selectedGroup;
              return (
                <div key={g.id}
                  onMouseEnter={()=>setHovGroup(g.id)} onMouseLeave={()=>setHovGroup(null)}
                  style={{ display:"flex", alignItems:"center", gap:2 }}>
                  <button onClick={()=>onSelectGroup(g.id)} style={{
                    padding:"3px 10px", borderRadius:12, cursor:"pointer", fontSize:11, fontWeight:500,
                    border:`1px solid ${active ? C.accent : C.border}`,
                    background: active ? C.accentSoft : "transparent",
                    color: active ? C.accent : C.textMid, transition:"all .15s",
                  }}>{g.name || g.id}</button>
                  {hovGroup===g.id && g.id!=="default" && (
                    <button onClick={e=>{e.stopPropagation();onDeleteGroup(g.id);}} style={{
                      background:"none", border:"none", cursor:"pointer", fontSize:10,
                      padding:"1px 3px", borderRadius:4, color:C.textDim,
                    }}
                    onMouseEnter={e=>{e.currentTarget.style.color="#ef4444";}}
                    onMouseLeave={e=>{e.currentTarget.style.color=C.textDim;}}>✕</button>
                  )}
                </div>
              );
            })}
          </div>

          {/* ── 当前组的 Director 列表 ──────────────────── */}
          <div style={{ padding:"0 12px 6px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <span style={{ fontSize:10, fontWeight:700, color:C.textDim, letterSpacing:1.5, textTransform:"uppercase" }}>Directors</span>
            <div style={{ display:"flex", gap:4 }}>
              <button onClick={()=>api.openGroupFolder(selectedGroup)} title="打开组文件夹"
                style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, color:C.textDim, padding:"1px 4px" }}>📂</button>
              <button onClick={onNew} style={{
                background: C.accentGrad, border:"none", color:"#fff", cursor:"pointer",
                fontSize:13, lineHeight:1, borderRadius:6, padding:"3px 8px", fontWeight:700,
                boxShadow:`0 2px 8px ${C.accentSoft}`
              }}>＋</button>
            </div>
          </div>
          <div style={{ flex:1, overflowY:"auto", padding:"0 8px" }}>
            {directors.length===0 && <div style={{ padding:"16px 8px", color:C.textDim, fontSize:12, textAlign:"center" }}>暂无 Director<br/><span style={{fontSize:11}}>点击 ＋ 创建</span></div>}
            {directors.map(d => (
              <NavItem key={d.id} director={d} active={selected?.id===d.id} C={C}
                onSelect={onSelect} onDelete={onDelete}
                onOpenFolder={(name)=>api.openDirectorFolder(selectedGroup, name)} />
            ))}
          </div>
          <FileTree groupId={selectedGroup} />
          <div style={{ padding:"10px 12px", borderTop:`1px solid ${C.border}` }}>
            <button onClick={onSettings} style={{
              width:"100%", background:"none", border:`1px solid ${C.glassBorder}`,
              color:C.textMid, borderRadius:C.radius, padding:"8px 12px",
              cursor:"pointer", textAlign:"left", fontSize:12, display:"flex", alignItems:"center", gap:8,
              backdropFilter:"blur(4px)"
            }}>
              <span style={{ fontSize:14 }}>⚙</span>
              <span style={{ fontSize:11 }}>
                {settings?.provider === "claude" ? "Claude" : "OpenAI"}
                {" · "}
                {settings?.has_key ? <span style={{color:C.green}}>● 已配置</span> : <span style={{color:"#ef4444"}}>● 未配置</span>}
              </span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function EmptyState({ onNew }) {
  const C = useC();
  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:20, position:"relative", overflow:"hidden" }}>
      <GradientOrb style={{ width:500, height:500, top:"50%", left:"50%", transform:"translate(-50%,-50%)", background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 60%)` }} />
      <div style={{ fontSize:56, animation:"glow 3s ease-in-out infinite" }}>🤖</div>
      <div style={{ textAlign:"center", position:"relative" }}>
        <h2 style={{ fontSize:22, fontWeight:700, color:C.text, marginBottom:8 }}>开始使用 Echelon AI</h2>
        <p style={{ fontSize:13, color:C.textMid, lineHeight:1.8, maxWidth:320 }}>
          创建一个 Director，与它对话规划任务。<br/>Director 会自动调度 Mentor + Worker 搭档执行。
        </p>
      </div>
      <button onClick={onNew} style={{
        background: C.accentGrad, border:"none", color:"#fff",
        padding:"10px 24px", borderRadius:C.radius, cursor:"pointer",
        fontWeight:600, fontSize:14, boxShadow:`0 4px 20px ${C.accentSoft}`,
        transition:"transform .15s", position:"relative"
      }}
        onMouseEnter={e=>e.currentTarget.style.transform="translateY(-1px)"}
        onMouseLeave={e=>e.currentTarget.style.transform="none"}>
        ＋ 创建第一个 Director
      </button>
    </div>
  );
}

function InpStyle(C) {
  return { width:"100%", background:C.elevated, border:`1px solid ${C.border}`, color:C.text, padding:"9px 13px", borderRadius:C.radius, outline:"none", fontSize:13 };
}

function SettingsModal({ settings, onClose }) {
  const C = useC();
  const curProvider = settings?.provider || "openai";
  const [provider, setProvider] = useState(curProvider);
  const opt = PROVIDER_OPTIONS.find(o => o.value === provider) || PROVIDER_OPTIONS[0];
  const [key, setKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(settings?.base_url || "");
  const [model, setModel] = useState(settings?.model || opt.modelDefault);
  const [saved, setSaved] = useState(false);

  // 切换 provider 时重置 model 到默认值
  const handleProviderChange = (v) => {
    setProvider(v);
    const o = PROVIDER_OPTIONS.find(x => x.value === v);
    setModel(o?.modelDefault || "");
    setBaseUrl("");
  };

  const save = async () => {
    if (!key.trim() && !settings?.has_key) return;
    await api.setProvider({ provider, api_key: key.trim(), base_url: baseUrl.trim(), model: model.trim() });
    setSaved(true);
    setTimeout(onClose, 800);
  };

  const s = InpStyle(C);
  const labelStyle = { fontSize:11, color:C.textDim, marginBottom:4, letterSpacing:0.5 };

  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ fontWeight:700, fontSize:16, marginBottom:16, color:C.text }}>⚙ AI 服务配置</div>

      {/* Provider 选择 */}
      <div style={{ marginBottom:14 }}>
        <div style={labelStyle}>AI 服务商</div>
        <div style={{ display:"flex", gap:8 }}>
          {PROVIDER_OPTIONS.map(o => (
            <button key={o.value} onClick={() => handleProviderChange(o.value)} style={{
              flex:1, padding:"8px 10px", borderRadius:C.radius, cursor:"pointer", fontSize:12, fontWeight:500,
              border:`1px solid ${provider===o.value ? C.accent : C.border}`,
              background: provider===o.value ? C.accentSoft : "transparent",
              color: provider===o.value ? C.accent : C.textMid,
              transition:"all .15s",
            }}>{o.label}</button>
          ))}
        </div>
      </div>

      {/* API Key */}
      <div style={{ marginBottom:10 }}>
        <div style={labelStyle}>API Key {settings?.has_key && <span style={{color:C.green}}>（已配置：{settings.key_preview}）</span>}</div>
        <input style={s} type="password"
          placeholder={settings?.has_key ? "留空保持不变（重新填写则覆盖）" : "输入 API Key"}
          value={key} onChange={e=>setKey(e.target.value)} onKeyDown={e=>e.key==="Enter"&&save()} />
      </div>

      {/* Base URL */}
      <div style={{ marginBottom:10 }}>
        <div style={labelStyle}>
          Base URL
          {provider === "claude" && <span style={{color:C.textDim}}> — 只填域名，如 https://api.example.com（系统自动补 /v1/messages）</span>}
        </div>
        <input style={s} type="text" placeholder={opt.placeholder}
          value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} />
      </div>

      {/* Model */}
      <div style={{ marginBottom:18 }}>
        <div style={labelStyle}>模型名称</div>
        <input style={s} type="text" placeholder={opt.modelDefault}
          value={model} onChange={e=>setModel(e.target.value)} />
      </div>

      <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
        <button style={{ background:"none", border:`1px solid ${C.border}`, color:C.textMid, padding:"7px 16px", borderRadius:C.radius, cursor:"pointer" }} onClick={onClose}>取消</button>
        <button style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600, boxShadow:`0 2px 12px ${C.accentSoft}` }} onClick={save}>{saved?"✓ 已保存":"保存"}</button>
      </div>
    </Modal>
  );
}

function NewGroupModal({ onClose, onCreated }) {
  const C = useC();
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const create = async () => {
    if (!id.trim()) return;
    await api.createGroup(id.trim(), name.trim() || id.trim(), desc.trim());
    onCreated(id.trim());
  };
  const s = InpStyle(C);
  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ fontWeight:700, fontSize:16, marginBottom:16, color:C.text }}>新建项目组</div>
      <input autoFocus style={{ ...s, marginBottom:10 }} placeholder="组 ID（英文/拼音，用作目录名）" value={id} onChange={e=>setId(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <input style={{ ...s, marginBottom:10 }} placeholder="组名称（显示用，选填）" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <input style={{ ...s, marginBottom:18 }} placeholder="描述（选填）" value={desc} onChange={e=>setDesc(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
        <button style={{ background:"none", border:`1px solid ${C.border}`, color:C.textMid, padding:"7px 16px", borderRadius:C.radius, cursor:"pointer" }} onClick={onClose}>取消</button>
        <button style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600, boxShadow:`0 2px 12px ${C.accentSoft}` }} onClick={create}>创建</button>
      </div>
    </Modal>
  );
}

const ROLE_OPTIONS = [
  { value: "executor",  label: "项目执行者", desc: "将任务分配给 Squad 执行，可读取蓝图规划师的蓝图" },
  { value: "architect", label: "蓝图规划师", desc: "深度需求分析，生成结构化蓝图文档供执行者使用" },
  { value: "manager",   label: "项目管理员", desc: "专职文件归档、进度记录和项目状态管理" },
  { value: "custom",    label: "自定义",     desc: "无预设提示词，完全由你自定义角色行为" },
];

function NewDirectorModal({ onClose, onCreated, groupId = "default" }) {
  const C = useC();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [icon, setIcon] = useState(() => PLANNER_ICONS[Math.floor(Math.random()*PLANNER_ICONS.length)]);
  const [role, setRole] = useState("executor");
  const [customSystem, setCustomSystem] = useState("");

  const create = async () => {
    const res = await api.createDirector(groupId, name.trim(), desc.trim(), icon, role, customSystem.trim());
    onCreated(res.id);
  };
  const s = InpStyle(C);
  const labelStyle = { fontSize:11, color:C.textDim, marginBottom:6, letterSpacing:0.5 };

  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ fontWeight:700, fontSize:16, marginBottom:16, color:C.text }}>新建 Director</div>

      {/* 图标 */}
      <div style={{ marginBottom:14 }}>
        <div style={labelStyle}>选择图标</div>
        <div style={{ display:"flex", flexWrap:"wrap", gap:6 }}>
          {PLANNER_ICONS.map(ic=>(
            <button key={ic} onClick={()=>setIcon(ic)} style={{
              fontSize:18, padding:"6px 8px", borderRadius:C.radius,
              border:`1px solid ${icon===ic?C.accent:C.border}`,
              background: icon===ic ? C.accentSoft : "transparent",
              cursor:"pointer", transition:"all .15s",
              boxShadow: icon===ic ? `0 0 0 1px ${C.accent}` : "none"
            }}>{ic}</button>
          ))}
        </div>
      </div>

      {/* 角色选择 */}
      <div style={{ marginBottom:14 }}>
        <div style={labelStyle}>角色职责</div>
        <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
          {ROLE_OPTIONS.map(opt => (
            <button key={opt.value} onClick={()=>setRole(opt.value)} style={{
              padding:"8px 12px", borderRadius:C.radius, cursor:"pointer", textAlign:"left",
              border:`1px solid ${role===opt.value ? C.accent : C.border}`,
              background: role===opt.value ? C.accentSoft : "transparent",
              transition:"all .15s",
            }}>
              <div style={{ fontSize:12, fontWeight:600, color: role===opt.value ? C.accent : C.text }}>{opt.label}</div>
              <div style={{ fontSize:11, color:C.textDim, marginTop:2 }}>{opt.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 自定义提示词（仅 custom） */}
      {role === "custom" && (
        <div style={{ marginBottom:14 }}>
          <div style={labelStyle}>自定义系统提示词</div>
          <textarea style={{ ...s, minHeight:80, resize:"vertical" }}
            placeholder="在此输入你的自定义角色提示词..."
            value={customSystem} onChange={e=>setCustomSystem(e.target.value)} />
        </div>
      )}

      <input autoFocus style={{ ...s, marginBottom:10 }} placeholder="名称（选填，默认 Director；重名自动编号）" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <input style={{ ...s, marginBottom:18 }} placeholder="职责描述（选填）" value={desc} onChange={e=>setDesc(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />

      <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
        <button style={{ background:"none", border:`1px solid ${C.border}`, color:C.textMid, padding:"7px 16px", borderRadius:C.radius, cursor:"pointer" }} onClick={onClose}>取消</button>
        <button style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600, boxShadow:`0 2px 12px ${C.accentSoft}` }} onClick={create}>创建</button>
      </div>
    </Modal>
  );
}

function SessionPanel({ session, groupId = "default", width = 340, onResizeStart, onStop, onContinue, onClose, onDelete }) {
  const C = useC();
  const bottomRef = useRef(null);
  const [showReport, setShowReport] = useState(false);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [session?.lines?.length]);
  if (!session) return null;

  const isError = session.isError;
  const headerColor = isError ? "#ef4444" : session.done ? C.green : C.cyan;
  const statusIcon = isError ? "✗" : session.done ? "✓" : null;

  return (
    <div style={{
      width, minWidth:260, maxWidth:"52vw", background:C.surface,
      borderLeft:`1px solid ${isError ? "rgba(239,68,68,0.32)" : C.border}`,
      display:"flex", flexDirection:"column",
      animation:"slideRight .2s ease", position:"relative", overflow:"hidden", backdropFilter:"blur(18px)"
    }}>
      <div className="resize-handle" onMouseDown={onResizeStart} style={{ position:"absolute", left:0, top:0, bottom:0, width:5, cursor:"col-resize", zIndex:4, opacity:.35 }} />
      <GradientOrb style={{ width:200, height:200, top:-60, right:-60, background:`radial-gradient(circle, ${isError ? "rgba(239,68,68,0.08)" : C.accentSoft} 0%, transparent 70%)` }} />

      {/* 标题栏 */}
      <div style={{ padding:"10px 14px", display:"flex", alignItems:"center", gap:8, borderBottom:`1px solid ${C.border}`, position:"relative" }}>
        <div style={{ position:"relative" }}>
          {statusIcon
            ? <span style={{color:headerColor, fontSize:16}}>{statusIcon}</span>
            : <Spinner size={12} C={C} />}
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontWeight:600, fontSize:12, color:headerColor, letterSpacing:0.5 }}>
            Squad · {session.squad}
          </div>
          {/* 实时状态文本 */}
          {!session.done && session.lastLine && (
            <div style={{
              fontSize:10, color:C.textDim, marginTop:2,
              overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
              maxWidth:160,
            }}>
              {session.lastLine.replace(/^[━\s⚙✓⚡❓📖🚀📋\[\]]+/, "").trim() || "处理中…"}
            </div>
          )}
        </div>
        <button onClick={onStop}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, padding:"3px 5px", borderRadius:6, color:C.textDim }}
          onMouseEnter={e=>{e.currentTarget.style.background="rgba(239,68,68,.15)";e.currentTarget.style.color="#ef4444";}}
          onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.style.color=C.textDim;}}>⏹</button>
        {(session.done || session.isError) && <button onClick={onContinue}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, padding:"3px 5px", borderRadius:6, color:C.green }}
          onMouseEnter={e=>{e.currentTarget.style.background=`${C.green}22`;}}
          onMouseLeave={e=>{e.currentTarget.style.background="none";}}>▶</button>}
        <button onClick={()=>api.openSquadFolder(groupId, session.squad)}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, padding:"3px 5px", borderRadius:6, color:C.textDim }}
          onMouseEnter={e=>{e.currentTarget.style.background=C.accentSoft;e.currentTarget.textContent="📂";}}
          onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.textContent="📁";}}>📁</button>
        <button onClick={onDelete}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, padding:"3px 5px", borderRadius:6, color:C.textDim }}
          onMouseEnter={e=>{e.currentTarget.style.background="rgba(239,68,68,.15)";e.currentTarget.style.color="#ef4444";}}
          onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.style.color=C.textDim;}}>🗑</button>
        <button onClick={onClose}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, padding:"3px 5px", borderRadius:6, color:C.textDim }}
          onMouseEnter={e=>{e.currentTarget.style.background=C.elevated;e.currentTarget.style.color=C.text;}}
          onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.style.color=C.textDim;}}>✕</button>
      </div>

      {/* 进度条 */}
      <div style={{ padding:"7px 14px 9px", borderBottom:`1px solid ${C.border}` }}>
        <div style={{ height:3, background:C.border, borderRadius:2, overflow:"hidden" }}>
          <div style={{
            height:"100%", width:`${session.progress||0}%`,
            background: isError ? "#ef4444" : C.accentGrad,
            transition:"width .5s ease", borderRadius:2,
          }} />
        </div>
        <div style={{ display:"flex", justifyContent:"space-between", marginTop:4 }}>
          <div style={{ fontSize:10, color: isError ? "#ef4444" : C.textDim }}>
            {isError ? "⚠ 执行出错" : `${Math.round(session.progress||0)}% 完成`}
          </div>
          {session.progressStatus && !isError && (
            <div style={{ fontSize:10, color:C.accent, maxWidth:180, textAlign:"right", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
              {session.progressStatus}
            </div>
          )}
        </div>
      </div>

      {/* 日志 */}
      <div style={{ flex:1, overflowY:"auto", padding:"8px 14px", fontFamily:"'JetBrains Mono','Fira Code',ui-monospace,monospace", fontSize:10, background:C.logBg }}>
        {session.lines.length === 0 && (
          <div style={{ color:C.textDim, fontSize:11, textAlign:"center", marginTop:20 }}>
            <Spinner size={14} C={C} />
            <div style={{ marginTop:8 }}>等待 Squad 启动…</div>
          </div>
        )}
        {session.lines.map((l,i) => <LogLine key={i} line={l} C={C} />)}
        <div ref={bottomRef}/>
      </div>

      {/* 错误报告 */}
      {isError && session.report && showReport && (
        <div style={{ maxHeight:160, overflowY:"auto", padding:"12px 16px", background:"rgba(239,68,68,0.06)", borderTop:`1px solid rgba(239,68,68,0.2)`, fontSize:12 }}>
          <div style={{ fontWeight:600, color:"#ef4444", marginBottom:6, display:"flex", alignItems:"center", justifyContent:"space-between", gap:6 }}>
            <span>⚠ 错误详情</span>
            <button onClick={()=>setShowReport(false)} style={{ background:"none", border:"none", color:C.textDim, cursor:"pointer" }}>✕</button>
          </div>
          <div style={{ color:"#ef4444", whiteSpace:"pre-wrap", opacity:0.85, fontSize:11 }}>{session.report}</div>
        </div>
      )}

      {/* 完成报告入口 */}
      {session.report && !showReport && (
        <button onClick={()=>setShowReport(true)} style={{ margin:"8px 16px 0", background:"none", border:`1px solid ${C.border}`, color:C.textDim, borderRadius:8, padding:"6px 10px", cursor:"pointer", fontSize:11 }}>
          {isError ? "查看错误详情" : "查看验收摘要"}
        </button>
      )}
      {!isError && session.report && showReport && (
        <div style={{ maxHeight:150, overflowY:"auto", padding:"10px 16px", background:"rgba(34,197,94,0.05)", borderTop:`1px solid ${C.border}`, fontSize:12, color:C.text, lineHeight:1.7 }}>
          <div style={{ fontWeight:600, color:C.green, marginBottom:6, display:"flex", alignItems:"center", justifyContent:"space-between", gap:6 }}>
            <span>✓ 验收摘要</span>
            <button onClick={()=>setShowReport(false)} style={{ background:"none", border:"none", color:C.textDim, cursor:"pointer" }}>✕</button>
          </div>
          <div style={{ color:C.textMid, whiteSpace:"pre-wrap" }}>{session.report}</div>
        </div>
      )}

      <div style={{ padding:"7px 14px", borderTop:`1px solid ${C.border}`, fontSize:10, color:C.textDim, background:C.surface, maxHeight:54, overflow:"auto", lineHeight:1.55 }}>
        任务：{session.task}
      </div>
      <TokenBar tokens={session.tokens} C={C} />
    </div>
  );
}

function ChatView({ director, groupId = "default", session, setSession, sessionWidth, onSessionResizeStart }) {
  const C = useC();
  const storageKey = `chat:${groupId}:${director.id}`;
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const wsRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    wsRef.current = createWS((msg) => {
      if (msg.type==="session_line") {
        setSession(prev => {
          if (!prev) return prev;
          // 只接收属于当前 Squad 的消息
          if (msg.squad && msg.squad !== prev.squad) return prev;
          const isError = msg.line?.includes("错误") || msg.line?.startsWith("[");
          return {
            ...prev,
            lines: [...prev.lines, msg.line],
            lastLine: msg.line,
            hasError: prev.hasError || isError,
          };
        });
      }
      else if (msg.type==="session_progress") {
        setSession(prev => {
          if (!prev) return prev;
          if (msg.squad && msg.squad !== prev.squad) return prev;
          return {...prev, progress: msg.percent, progressStatus: msg.status||""};
        });
      }
      else if (msg.type==="token_update") {
        setSession(prev => {
          if (!prev) return prev;
          if (msg.squad && msg.squad !== prev.squad) return prev;
          return {...prev, tokens: msg};
        });
      }
      else if (msg.type==="director_report") {
        setMessages(prev=>[...prev,{role:"assistant",content:`📡 ${msg.report}`}]);
      }
      else if (msg.type==="session_done") {
        setSession(prev => {
          if (!prev) return prev;
          if (msg.squad && msg.squad !== prev.squad) return prev;
          return {
            ...prev,
            done: true,
            progress: 100,
            report: msg.report,
            isError: msg.status === "error",
          };
        });
      }
    });
    return () => { wsRef.current?.close(); wsRef.current=null; };
  }, []);

  useEffect(() => {
    setInput(""); setLoading(false);
    const cached = localStorage.getItem(storageKey);
    if (cached) {
      try { setMessages(JSON.parse(cached)); } catch { setMessages([]); }
    } else {
      setMessages([]);
    }
    api.getHistory(groupId, director.id).then(hist => {
      const serverMessages = hist.map(m=>({role:m.role,content:m.content}));
      setMessages(serverMessages);
      localStorage.setItem(storageKey, JSON.stringify(serverMessages));
    });
  }, [director.id, groupId, storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(messages.filter(m => m.content || m._streaming)));
  }, [messages, storageKey]);

  useEffect(() => { bottomRef.current?.scrollIntoView({behavior:"smooth"}); }, [messages.length, session?.lines?.length]);

  const send = async () => {
    const text = input.trim();
    if (!text||loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height="auto";
    setLoading(true);
    setMessages(prev=>[...prev,{role:"user",content:text}]);
    const sid = Date.now();
    setMessages(prev=>[...prev,{role:"assistant",content:"",_id:sid,_streaming:true}]);
    try {
      abortRef.current = new AbortController();
      for await (const chunk of chatStream(groupId, director.id, text, abortRef.current.signal)) {
        if (chunk.token) setMessages(prev=>prev.map(m=>m._id===sid?{...m,content:m.content+chunk.token}:m));
        if (chunk.error) {
          setMessages(prev=>prev.map(m=>m._id===sid?{...m,content:`⚠ ${chunk.error}`,_streaming:false}:m));
          return;
        }
        if (chunk.done) {
          setMessages(prev=>prev.map(m=>m._id===sid?{...m,_streaming:false}:m));
          if (chunk.squads?.length) setSession({squad:chunk.squads[0].squad,task:chunk.squads[0].task,lines:["Mentor × Worker 已启动…"],progress:0});
        }
      }
    } catch(err) {
      const msg = err.name === "AbortError" ? "已打断，可继续输入新指令" : `⚠ 请求失败：${err.message}`;
      setMessages(prev=>prev.map(m=>m._id===sid?{...m,content:msg,_streaming:false}:m));
    } finally { abortRef.current = null; setLoading(false); }
  };

  const interruptDirector = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  return (
    <div style={{ flex:1, display:"flex", overflow:"hidden", position:"relative" }}>
      <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden", background:C.bg, position:"relative" }}>
        <GradientOrb style={{ width:400, height:400, top:-100, right:-100, background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 60%)`, opacity:0.5 }} />

        <div style={{ padding:"12px 18px", borderBottom:`1px solid ${C.border}`, display:"flex", alignItems:"center", gap:10, background:C.surface, backdropFilter:"blur(18px)", position:"relative" }}>
          <div style={{ width:32, height:32, borderRadius:10, background:C.elevated, border:`1px solid ${C.border}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:15, boxShadow:"0 8px 24px rgba(15,23,42,.05)" }}>{director.icon||"🤖"}</div>
          <div>
            <div style={{ fontWeight:650, fontSize:14, color:C.text }}>{director.id}</div>
            {director.description && <div style={{ fontSize:11, color:C.textDim }}>{director.description}</div>}
          </div>
          <div style={{ flex:1 }}/>
          {loading && <button onClick={interruptDirector} style={{ background:"rgba(239,68,68,.12)", border:`1px solid rgba(239,68,68,.25)`, color:"#ef4444", borderRadius:8, padding:"5px 10px", cursor:"pointer", fontSize:12 }}>打断</button>}
          {loading && <div style={{ display:"flex", alignItems:"center", gap:6, color:C.textDim, fontSize:12 }}><Spinner size={12} C={C} />思考中…</div>}
        </div>

        <div style={{ flex:1, overflowY:"auto", padding:"26px 32px", display:"flex", flexDirection:"column", gap:16, position:"relative", maxWidth:920, width:"100%", alignSelf:"center" }}>
          {messages.length===0 && (
            <div style={{ textAlign:"center", color:C.textDim, marginTop:80, fontSize:13, position:"relative" }}>
              <div style={{ fontSize:36, marginBottom:12 }}>{director.icon||"🤖"}</div>
              <div style={{ color:C.textMid, fontWeight:500, marginBottom:4 }}>Hi, 我是 {director.id}</div>
              <div style={{ fontSize:12 }}>告诉我你想完成什么任务</div>
            </div>
          )}
          {messages.map((m,i) => <Bubble key={i} msg={m} C={C} />)}
          <div ref={bottomRef}/>
        </div>

        <div style={{ position:"relative", background:C.bg }}>
          <ChatInput input={input} setInput={setInput} loading={loading} onSend={send} C={C} textareaRef={textareaRef} />
        </div>
      </div>

      {session && (
        <SessionPanel session={session} groupId={groupId} width={sessionWidth} onResizeStart={onSessionResizeStart}
          onStop={async()=>{ await api.stopSquad(groupId, session.squad); setSession(prev=>prev?{...prev,done:true,isError:false,report:"已由用户停止"}:prev); }}
          onContinue={async()=>{ await api.continueSquad(groupId, session.squad, "从上次中断或错误处继续执行"); setSession(prev=>prev?{...prev,done:false,isError:false,report:"",lines:[...prev.lines,"▶ 用户要求继续运行…"],progress:prev.progress||0}:prev); }}
          onClose={()=>setSession(null)}
          onDelete={async()=>{ await api.deleteSquad(groupId, session.squad); setSession(null); }}
        />
      )}
    </div>
  );
}

export default function App() {
  const [themeName, setThemeName] = useState("light");
  const C = THEMES[themeName];
  const [groups, setGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState("default");
  const [directors, setDirectors] = useState([]);
  const [selected, setSelected] = useState(null);
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(() => Number(localStorage.getItem("layout:sidebarWidth")) || 228);
  const [sessionWidth, setSessionWidth] = useState(() => Number(localStorage.getItem("layout:sessionWidth")) || 320);
  const [session, setSession] = useState(() => {
    const cached = localStorage.getItem("activeSession");
    if (!cached) return null;
    try { return JSON.parse(cached); } catch { return null; }
  });

  const loadGroups = useCallback(() => { api.getGroups().then(gs => setGroups(gs.length ? gs : [{id:"default",name:"默认组",description:""}])); }, []);
  const loadDirectors = useCallback(() => { api.getDirectors(selectedGroup).then(setDirectors); }, [selectedGroup]);
  const load = useCallback(() => { loadGroups(); loadDirectors(); api.getSettings().then(setSettings); }, [loadGroups, loadDirectors]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDirectors(); setSelected(null); }, [selectedGroup]);
  useEffect(() => {
    if (session) localStorage.setItem("activeSession", JSON.stringify(session));
    else localStorage.removeItem("activeSession");
  }, [session]);

  const startSidebarResize = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sidebarWidth;
    const move = ev => {
      const next = Math.min(420, Math.max(200, startWidth + ev.clientX - startX));
      setSidebarWidth(next);
      localStorage.setItem("layout:sidebarWidth", String(next));
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const startSessionResize = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = sessionWidth;
    const move = ev => {
      const next = Math.min(window.innerWidth * 0.62, Math.max(260, startWidth - ev.clientX + startX));
      setSessionWidth(next);
      localStorage.setItem("layout:sessionWidth", String(next));
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const del = async (id) => {
    if (!confirm(`删除 Director「${id}」？`)) return;
    await api.deleteDirector(selectedGroup, id);
    if (selected?.id===id) setSelected(null);
    loadDirectors();
  };

  const delGroup = async (id) => {
    if (!confirm(`删除项目组「${id}」及其所有数据？此操作不可撤销。`)) return;
    await api.deleteGroup(id);
    if (selectedGroup === id) setSelectedGroup("default");
    loadGroups();
  };

  const cycleTheme = () => {
    const ts = ["dark","midnight","light"];
    setThemeName(ts[(ts.indexOf(themeName)+1)%ts.length]);
  };

  return (
    <ThemeCtx.Provider value={C}>
      <GlobalStyle C={C} />
      <div style={{ display:"flex", height:"100vh", width:"100vw", overflow:"hidden", background:C.bg }}>
        <Sidebar
          groups={groups} selectedGroup={selectedGroup}
          onSelectGroup={setSelectedGroup} onNewGroup={()=>setShowNewGroup(true)} onDeleteGroup={delGroup}
          directors={directors} selected={selected} onSelect={setSelected}
          onNew={()=>setShowNew(true)} onDelete={del}
          settings={settings} onSettings={()=>setShowSettings(true)}
          themeName={themeName} onToggleTheme={cycleTheme}
          collapsed={sidebarCollapsed} onCollapse={()=>setSidebarCollapsed(!sidebarCollapsed)} width={sidebarWidth}
        />
        {!sidebarCollapsed && <div className="resize-handle" onMouseDown={startSidebarResize} style={{ width:5, cursor:"col-resize", background:C.border, opacity:.45 }} />}
        <div style={{ flex:1, display:"flex", overflow:"hidden" }}>
          {selected
            ? <ChatView key={`${selectedGroup}/${selected.id}`} director={selected} groupId={selectedGroup} session={session} setSession={setSession} sessionWidth={sessionWidth} onSessionResizeStart={startSessionResize} />
            : <EmptyState onNew={()=>setShowNew(true)} />}
        </div>
      </div>
      {showSettings && <SettingsModal settings={settings} onClose={()=>{ setShowSettings(false); api.getSettings().then(setSettings); }} />}
      {showNew && <NewDirectorModal groupId={selectedGroup} onClose={()=>setShowNew(false)} onCreated={name=>{
        loadDirectors(); setShowNew(false);
        api.getDirectors(selectedGroup).then(ds=>{ const d=ds.find(x=>x.id===name); if(d) setSelected(d); });
      }} />}
      {showNewGroup && <NewGroupModal onClose={()=>setShowNewGroup(false)} onCreated={gid=>{ loadGroups(); setShowNewGroup(false); setSelectedGroup(gid); }} />}
    </ThemeCtx.Provider>
  );
}
