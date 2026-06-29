import { useState, useEffect, useRef, useCallback, createContext, useContext } from "react";
import { api, chatStream, createWS } from "./api";
import { THEMES } from "./themes";
import { Spinner, Modal, Chip, LogLine, Bubble, ChatInput } from "./components";

const ThemeCtx = createContext(THEMES.dark);
const useC = () => useContext(ThemeCtx);
const PLANNER_ICONS = ["🤖","🧠","⚡","🔬","🎯","🛠","🚀","🌐","💡","🔭","🧬","🎨"];

function GlobalStyle({ C }) {
  return <style>{`
    body { background:${C.bg}; color:${C.text}; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    input,button,textarea { font-family:inherit; font-size:inherit; }
  `}</style>;
}

function GradientOrb({ style }) {
  return <div style={{ position:"absolute", borderRadius:"50%", filter:"blur(80px)", pointerEvents:"none", ...style }} />;
}

function Logo({ themeName, onToggle, collapsed, onCollapse, C }) {
  return (
    <div style={{ padding: collapsed ? "14px 0" : "18px 20px 14px", display:"flex", alignItems:"center", gap:8 }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0,
        background: C.accentGrad, display:"flex", alignItems:"center", justifyContent:"center",
        fontSize: 14, fontWeight: 900, color: "#fff", fontFamily:"monospace",
        boxShadow: `0 4px 16px ${C.accentSoft}`
      }}>E</div>
      {!collapsed && (
        <>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:13, fontWeight:800, background:C.accentGrad, WebkitBackgroundClip:"text", backgroundClip:"text", WebkitTextFillColor:"transparent", color:"transparent", letterSpacing:2, fontFamily:"monospace", display:"inline-block" }}>ECHELON</div>
            <div style={{ fontSize:9, color:C.textDim, letterSpacing:1 }}>AI FRAMEWORK</div>
          </div>
          <button onClick={onToggle} style={{ background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid, borderRadius:6, padding:"3px 8px", cursor:"pointer", fontSize:13, backdropFilter:"blur(4px)" }}>
            {themeName==="light"?"☀":themeName==="dark"?"◑":"☾"}
          </button>
        </>
      )}
      <button onClick={onCollapse} style={{ background:"none", border:`1px solid ${C.glassBorder}`, color:C.textMid, borderRadius:6, padding:"3px 7px", cursor:"pointer", fontSize:12 }}>
        {collapsed?"›":"‹"}
      </button>
    </div>
  );
}

function NavItem({ planner, active, onSelect, onDelete, onOpenFolder, C }) {
  const [hov, setHov] = useState(false);
  return (
    <div onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      onClick={() => onSelect(planner)}
      style={{
        padding:"8px 12px", borderRadius:C.radius, marginBottom:2, cursor:"pointer",
        display:"flex", alignItems:"center", gap:8, position:"relative", transition:"all .15s",
        background: active ? C.accentSoft : hov ? C.glass : "transparent",
        border: `1px solid ${active ? C.userBorder : "transparent"}`,
      }}>
      <span style={{ fontSize:16, flexShrink:0 }}>{planner.icon||"🤖"}</span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontWeight:500, color:active?C.accent:C.text, fontSize:13, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{planner.id}</div>
        {planner.description && <div style={{ fontSize:10, color:C.textDim, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{planner.description}</div>}
      </div>
      {(hov||active) && (
        <div style={{ display:"flex", gap:2 }}>
          <button onClick={e=>{e.stopPropagation();onOpenFolder(planner.id);}}
            style={{ background:"none", border:"none", cursor:"pointer", fontSize:11, padding:"2px 4px", borderRadius:4, color:C.textDim }}
            onMouseEnter={e=>{e.currentTarget.style.background=C.accentSoft;e.currentTarget.textContent="📂";}}
            onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.textContent="📁";}}>📁</button>
          <button onClick={e=>{e.stopPropagation();onDelete(planner.id);}}
            style={{ background:"none", border:"none", cursor:"pointer", fontSize:11, padding:"2px 4px", borderRadius:4, color:C.textDim }}
            onMouseEnter={e=>{e.currentTarget.style.background="rgba(239,68,68,.15)";e.currentTarget.style.color="#ef4444";}}
            onMouseLeave={e=>{e.currentTarget.style.background="none";e.currentTarget.style.color=C.textDim;}}>✕</button>
        </div>
      )}
    </div>
  );
}

function Sidebar({ planners, selected, onSelect, onNew, onDelete, settings, onSettings, themeName, onToggleTheme, collapsed, onCollapse }) {
  const C = useC();
  return (
    <div style={{
      width: collapsed?54:240, minWidth: collapsed?54:240, height:"100%",
      background: C.surface, borderRight:`1px solid ${C.border}`,
      display:"flex", flexDirection:"column", transition:"width .2s ease", position:"relative", overflow:"hidden",
    }}>
      {!collapsed && <GradientOrb style={{ width:200, height:200, top:-60, left:-60, background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 70%)` }} />}
      <Logo themeName={themeName} onToggle={onToggleTheme} collapsed={collapsed} onCollapse={onCollapse} C={C} />
      {!collapsed && (
        <>
          <div style={{ padding:"0 12px 6px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <span style={{ fontSize:10, fontWeight:700, color:C.textDim, letterSpacing:1.5, textTransform:"uppercase" }}>Planners</span>
            <button onClick={onNew} style={{
              background: C.accentGrad, border:"none", color:"#fff", cursor:"pointer",
              fontSize:13, lineHeight:1, borderRadius:6, padding:"3px 8px", fontWeight:700,
              boxShadow:`0 2px 8px ${C.accentSoft}`
            }}>＋</button>
          </div>
          <div style={{ flex:1, overflowY:"auto", padding:"0 8px" }}>
            {planners.length===0 && <div style={{ padding:"16px 8px", color:C.textDim, fontSize:12, textAlign:"center" }}>暂无 Planner<br/><span style={{fontSize:11}}>点击 ＋ 创建</span></div>}
            {planners.map(p => (
              <NavItem key={p.id} planner={p} active={selected?.id===p.id} C={C}
                onSelect={onSelect} onDelete={onDelete} onOpenFolder={api.openPlannerFolder} />
            ))}
          </div>
          <div style={{ padding:"10px 12px", borderTop:`1px solid ${C.border}` }}>
            <button onClick={onSettings} style={{
              width:"100%", background:"none", border:`1px solid ${C.glassBorder}`,
              color:C.textMid, borderRadius:C.radius, padding:"8px 12px",
              cursor:"pointer", textAlign:"left", fontSize:12, display:"flex", alignItems:"center", gap:8,
              backdropFilter:"blur(4px)"
            }}>
              <span style={{ fontSize:14 }}>⚙</span>
              <span>API Key: {settings?.has_key ? <span style={{color:C.green}}>● 已配置</span> : <span style={{color:C.red}}>● 未配置</span>}</span>
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
          创建一个 Planner，与它对话规划任务。<br/>Planner 会自动调度 Butler + Worker 搭档执行。
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
        ＋ 创建第一个 Planner
      </button>
    </div>
  );
}

function InpStyle(C) {
  return { width:"100%", background:C.elevated, border:`1px solid ${C.border}`, color:C.text, padding:"9px 13px", borderRadius:C.radius, outline:"none", fontSize:13 };
}

function SettingsModal({ settings, onClose }) {
  const C = useC();
  const [val, setVal] = useState("");
  const [saved, setSaved] = useState(false);
  const save = async () => { if (!val.trim()) return; await api.setApiKey(val.trim()); setSaved(true); setTimeout(onClose, 800); };
  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ fontWeight:700, fontSize:16, marginBottom:4, color:C.text }}>⚙ 设置</div>
      <div style={{ color:C.textDim, fontSize:12, marginBottom:16 }}>当前：{settings?.has_key?settings.key_preview:"未配置"}</div>
      <input autoFocus style={InpStyle(C)} type="password" placeholder="输入 API Key（sk- 开头）" value={val} onChange={e=>setVal(e.target.value)} onKeyDown={e=>e.key==="Enter"&&save()} />
      <div style={{ display:"flex", gap:8, marginTop:16, justifyContent:"flex-end" }}>
        <button style={{ background:"none", border:`1px solid ${C.border}`, color:C.textMid, padding:"7px 16px", borderRadius:C.radius, cursor:"pointer" }} onClick={onClose}>取消</button>
        <button style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600, boxShadow:`0 2px 12px ${C.accentSoft}` }} onClick={save}>{saved?"✓ 已保存":"保存"}</button>
      </div>
    </Modal>
  );
}

function NewPlannerModal({ onClose, onCreated }) {
  const C = useC();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [icon, setIcon] = useState(() => PLANNER_ICONS[Math.floor(Math.random()*PLANNER_ICONS.length)]);
  const create = async () => { if (!name.trim()) return; await api.createPlanner(name.trim(), desc.trim(), icon); onCreated(name.trim()); };
  const s = InpStyle(C);
  return (
    <Modal onClose={onClose} C={C}>
      <div style={{ fontWeight:700, fontSize:16, marginBottom:16, color:C.text }}>新建 Planner</div>
      <div style={{ marginBottom:14 }}>
        <div style={{ fontSize:11, color:C.textDim, marginBottom:8, letterSpacing:1 }}>选择图标</div>
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
      <input autoFocus style={{ ...s, marginBottom:10 }} placeholder="名称（英文/拼音）" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <input style={{ ...s, marginBottom:18 }} placeholder="职责描述（选填）" value={desc} onChange={e=>setDesc(e.target.value)} onKeyDown={e=>e.key==="Enter"&&create()} />
      <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
        <button style={{ background:"none", border:`1px solid ${C.border}`, color:C.textMid, padding:"7px 16px", borderRadius:C.radius, cursor:"pointer" }} onClick={onClose}>取消</button>
        <button style={{ background:C.accentGrad, border:"none", color:"#fff", padding:"7px 16px", borderRadius:C.radius, cursor:"pointer", fontWeight:600, boxShadow:`0 2px 12px ${C.accentSoft}` }} onClick={create}>创建</button>
      </div>
    </Modal>
  );
}

function SessionPanel({ session, onClose, onDelete }) {
  const C = useC();
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [session?.lines?.length]);
  if (!session) return null;

  return (
    <div style={{
      width:340, minWidth:340, background:C.surface,
      borderLeft:`1px solid ${C.border}`, display:"flex", flexDirection:"column",
      animation:"slideRight .2s ease", position:"relative", overflow:"hidden"
    }}>
      <GradientOrb style={{ width:200, height:200, top:-60, right:-60, background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 70%)` }} />
      <div style={{ padding:"12px 16px", display:"flex", alignItems:"center", gap:8, borderBottom:`1px solid ${C.border}`, position:"relative" }}>
        <div style={{ position:"relative" }}>
          {session.done ? <span style={{color:C.green,fontSize:16}}>✓</span> : <Spinner size={12} C={C} />}
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontWeight:600, fontSize:12, color:session.done?C.green:C.cyan, letterSpacing:0.5 }}>
            Partner · {session.partner}
          </div>
        </div>
        <button onClick={()=>api.openPartnerFolder(session.partner)}
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

      <div style={{ padding:"8px 16px 10px", borderBottom:`1px solid ${C.border}` }}>
        <div style={{ height:3, background:C.border, borderRadius:2, overflow:"hidden" }}>
          <div style={{ height:"100%", width:`${session.progress||0}%`, background:C.accentGrad, transition:"width .5s ease", borderRadius:2 }} />
        </div>
        <div style={{ fontSize:10, color:C.textDim, marginTop:4 }}>{Math.round(session.progress||0)}% 完成</div>
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:"10px 16px", fontFamily:"'JetBrains Mono','Fira Code',ui-monospace,monospace", fontSize:11, background:C.logBg }}>
        {session.lines.map((l,i) => <LogLine key={i} line={l} C={C} />)}
        <div ref={bottomRef}/>
      </div>

      {session.report && (
        <div style={{ padding:"12px 16px", background:"rgba(34,197,94,0.05)", borderTop:`1px solid ${C.border}`, fontSize:12, color:C.text, lineHeight:1.7 }}>
          <div style={{ fontWeight:600, color:C.green, marginBottom:6, display:"flex", alignItems:"center", gap:6 }}>
            <span>✓</span> 验收报告
          </div>
          <div style={{ color:C.textMid, whiteSpace:"pre-wrap" }}>{session.report}</div>
        </div>
      )}

      <div style={{ padding:"8px 16px", borderTop:`1px solid ${C.border}`, fontSize:11, color:C.textDim, background:C.surface }}>
        任务：{session.task}
      </div>
    </div>
  );
}

function ChatView({ planner, session, setSession }) {
  const C = useC();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    wsRef.current = createWS((msg) => {
      if (msg.type==="session_line") setSession(prev=>prev?{...prev,lines:[...prev.lines,msg.line]}:prev);
      else if (msg.type==="session_progress") setSession(prev=>prev?{...prev,progress:msg.percent}:prev);
      else if (msg.type==="session_done") setSession(prev=>prev?{...prev,done:true,progress:100,report:msg.report}:prev);
    });
    return () => { wsRef.current?.close(); wsRef.current=null; };
  }, []);

  useEffect(() => {
    setMessages([]); setInput(""); setLoading(false);
    api.getHistory(planner.id).then(hist => setMessages(hist.map(m=>({role:m.role,content:m.content}))));
  }, [planner.id]);

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
      for await (const chunk of chatStream(planner.id, text)) {
        if (chunk.token) setMessages(prev=>prev.map(m=>m._id===sid?{...m,content:m.content+chunk.token}:m));
        if (chunk.done) {
          setMessages(prev=>prev.map(m=>m._id===sid?{...m,_streaming:false}:m));
          if (chunk.partners?.length) setSession({partner:chunk.partners[0].partner,task:chunk.partners[0].task,lines:["Butler × Worker 已启动…"],progress:0});
        }
      }
    } catch(err) {
      setMessages(prev=>prev.map(m=>m._id===sid?{...m,content:`⚠ 请求失败：${err.message}`,_streaming:false}:m));
    } finally { setLoading(false); }
  };

  return (
    <div style={{ flex:1, display:"flex", overflow:"hidden", position:"relative" }}>
      <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden", background:C.bg, position:"relative" }}>
        <GradientOrb style={{ width:400, height:400, top:-100, right:-100, background:`radial-gradient(circle, ${C.accentSoft} 0%, transparent 60%)`, opacity:0.5 }} />

        <div style={{ padding:"14px 20px 12px", borderBottom:`1px solid ${C.border}`, display:"flex", alignItems:"center", gap:10, background:C.surface, position:"relative" }}>
          <div style={{ width:34, height:34, borderRadius:C.radius, background:C.elevated, border:`1px solid ${C.border}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16 }}>{planner.icon||"🤖"}</div>
          <div>
            <div style={{ fontWeight:600, fontSize:15, color:C.text }}>{planner.id}</div>
            {planner.description && <div style={{ fontSize:11, color:C.textDim }}>{planner.description}</div>}
          </div>
          <div style={{ flex:1 }}/>
          {loading && <div style={{ display:"flex", alignItems:"center", gap:6, color:C.textDim, fontSize:12 }}><Spinner size={12} C={C} />思考中…</div>}
        </div>

        <div style={{ flex:1, overflowY:"auto", padding:"20px", display:"flex", flexDirection:"column", gap:14, position:"relative" }}>
          {messages.length===0 && (
            <div style={{ textAlign:"center", color:C.textDim, marginTop:80, fontSize:13, position:"relative" }}>
              <div style={{ fontSize:36, marginBottom:12 }}>{planner.icon||"🤖"}</div>
              <div style={{ color:C.textMid, fontWeight:500, marginBottom:4 }}>Hi, 我是 {planner.id}</div>
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
        <SessionPanel session={session}
          onClose={()=>setSession(null)}
          onDelete={async()=>{ await api.deletePartner(session.partner); setSession(null); }}
        />
      )}
    </div>
  );
}

export default function App() {
  const [themeName, setThemeName] = useState("light");
  const C = THEMES[themeName];
  const [planners, setPlanners] = useState([]);
  const [selected, setSelected] = useState(null);
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [session, setSession] = useState(null);

  const load = useCallback(() => { api.getPlanners().then(setPlanners); api.getSettings().then(setSettings); }, []);
  useEffect(() => { load(); }, [load]);

  const del = async (id) => {
    if (!confirm(`删除 Planner「${id}」？`)) return;
    await api.deletePlanner(id);
    if (selected?.id===id) setSelected(null);
    load();
  };

  const cycleTheme = () => {
    const ts = ["dark","midnight","light"];
    setThemeName(ts[(ts.indexOf(themeName)+1)%ts.length]);
  };

  return (
    <ThemeCtx.Provider value={C}>
      <GlobalStyle C={C} />
      <div style={{ display:"flex", height:"100vh", width:"100vw", overflow:"hidden", background:C.bg }}>
        <Sidebar planners={planners} selected={selected} onSelect={setSelected}
          onNew={()=>setShowNew(true)} onDelete={del}
          settings={settings} onSettings={()=>setShowSettings(true)}
          themeName={themeName} onToggleTheme={cycleTheme}
          collapsed={sidebarCollapsed} onCollapse={()=>setSidebarCollapsed(!sidebarCollapsed)}
        />
        <div style={{ flex:1, display:"flex", overflow:"hidden" }}>
          {selected
            ? <ChatView key={selected.id} planner={selected} session={session} setSession={setSession} />
            : <EmptyState onNew={()=>setShowNew(true)} />}
        </div>
      </div>
      {showSettings && <SettingsModal settings={settings} onClose={()=>{ setShowSettings(false); api.getSettings().then(setSettings); }} />}
      {showNew && <NewPlannerModal onClose={()=>setShowNew(false)} onCreated={name=>{ load(); setShowNew(false); api.getPlanners().then(ps=>{ const p=ps.find(x=>x.id===name); if(p) setSelected(p); }); }} />}
    </ThemeCtx.Provider>
  );
}
