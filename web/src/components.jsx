import { useRef, useEffect } from "react";

export function Spinner({ size = 14, C }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size,
      border: `1.5px solid ${C.border}`, borderTopColor: C.accent,
      borderRadius: "50%", animation: "spin .6s linear infinite", flexShrink: 0
    }} />
  );
}

export function Modal({ onClose, children, C }) {
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(0,0,0,.7)", backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center"
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: C.surface, border: `1px solid ${C.glassBorder}`,
        borderRadius: C.radiusLg, padding: "28px 28px 24px",
        width: 420, boxShadow: "0 24px 80px rgba(0,0,0,.6)",
        animation: "modalIn .2s ease"
      }}>
        {children}
      </div>
    </div>
  );
}

export function Chip({ icon, text, color, bg }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: bg, color: color,
      padding: "2px 8px", borderRadius: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: 0.3
    }}>
      {icon && <span>{icon}</span>}
      {text}
    </span>
  );
}

export function LogLine({ line, C }) {
  if (!line) return null;
  if (line.includes("━━━")) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0 4px", opacity: 0.5 }}>
        <div style={{ flex: 1, height: 1, background: C.border }} />
        <span style={{ fontSize: 10, color: C.textDim, whiteSpace: "nowrap" }}>{line.replace(/━/g, "").trim()}</span>
        <div style={{ flex: 1, height: 1, background: C.border }} />
      </div>
    );
  }
  if (line.startsWith("  ⚙") || line.includes("⚙ ")) {
    const content = line.replace(/^\s*⚙\s*/, "");
    const [toolName, ...rest] = content.split(/\s{2,}/);
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6, margin: "3px 0", flexWrap: "wrap" }}>
        <span style={{
          background: C.accentSoft, color: C.accent,
          padding: "1px 7px", borderRadius: 4, fontSize: 11, fontWeight: 600
        }}>⚙ {toolName}</span>
        {rest.length > 0 && <span style={{ color: C.textDim, fontSize: 11 }}>{rest.join(" ")}</span>}
      </div>
    );
  }
  if (line.includes("  └")) {
    return <div style={{ color: C.textDim, fontSize: 10, paddingLeft: 14, lineHeight: 1.5, margin: "1px 0" }}>{line.replace(/^\s*└\s*/, "")}</div>;
  }
  if (line.includes("✓") && line.includes("通过")) {
    return <div style={{ margin: "3px 0" }}><Chip icon="✓" text={line.replace(/^\s*✓\s*/, "")} color={C.green} bg={`${C.green}1f`} /></div>;
  }
  if (line.includes("⚡") || (line.includes("纠正") && !line.includes("工作"))) {
    return <div style={{ margin: "3px 0" }}><Chip icon="⚡" text={line.replace(/^\s*⚡\s*/, "")} color="#ef4444" bg="rgba(239,68,68,0.12)" /></div>;
  }
  if (line.includes("❓")) {
    return <div style={{ margin: "3px 0" }}><Chip icon="❓" text={line.replace(/^\s*❓\s*/, "")} color="#f59e0b" bg="rgba(245,158,11,0.12)" /></div>;
  }
  if (line.includes("📖")) {
    return <div style={{ color: C.accent, fontSize: 11, paddingLeft: 10, margin: "2px 0", lineHeight: 1.6 }}>{line}</div>;
  }
  if (line.includes("✓") && line.includes("完成")) {
    return (
      <div style={{ margin: "6px 0", padding: "6px 10px", background: `${C.green}14`, borderRadius: 6, borderLeft: `2px solid ${C.green}` }}>
        <Chip icon="✓" text="任务完成" color={C.green} bg="transparent" />
      </div>
    );
  }
  if (line.includes("错误") || line.startsWith("[Worker 错误]")) {
    return <div style={{ color: "#ef4444", fontSize: 11, margin: "2px 0" }}>{line}</div>;
  }
  return <div style={{ color: C.textMid, fontSize: 11, lineHeight: 1.75 }}>{line}</div>;
}

export function Bubble({ msg, C }) {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex", gap: 10, animation: "fadeUp .2s ease",
      flexDirection: isUser ? "row-reverse" : "row", alignItems: "flex-start"
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13,
        background: isUser ? C.accentSoft : C.elevated,
        border: `1px solid ${isUser ? C.userBorder : C.border}`,
        marginTop: 2,
      }}>{isUser ? "👤" : "🤖"}</div>
      <div style={{
        maxWidth: "76%",
        padding: "10px 14px",
        borderRadius: isUser ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
        background: isUser ? C.userBg : C.elevated,
        border: `1px solid ${isUser ? C.userBorder : C.border}`,
        color: C.text, whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: 14,
        boxShadow: "0 2px 8px rgba(0,0,0,.15)",
      }}>
        {msg.content}
        {msg._streaming && <span style={{ color: C.accent, animation: "blink 1s infinite", marginLeft: 3 }}>▊</span>}
      </div>
    </div>
  );
}

export function ChatInput({ input, setInput, loading, onSend, C, textareaRef }) {
  return (
    <div style={{ padding: "0 16px 16px" }}>
      <div style={{
        display: "flex", alignItems: "flex-end", gap: 0,
        background: C.elevated, border: `1px solid ${C.borderHi}`,
        borderRadius: C.radiusLg, overflow: "hidden",
        boxShadow: `0 0 0 1px ${C.glassBorder}, 0 4px 20px rgba(0,0,0,.2)`,
        transition: "box-shadow .2s",
      }}>
        <textarea ref={textareaRef}
          style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            color: C.text, resize: "none", lineHeight: 1.6,
            padding: "12px 16px", maxHeight: 160, fontSize: 14,
            fontFamily: "inherit", minHeight: 48,
          }}
          placeholder={loading ? "Planner 正在思考…" : "发送消息 (Enter 发送，Shift+Enter 换行)"}
          value={input} rows={1}
          onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; }}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          disabled={loading}
        />
        <button onClick={onSend} disabled={loading || !input.trim()} style={{
          margin: "8px 10px 8px 0", width: 36, height: 36, borderRadius: "50%",
          background: (loading || !input.trim()) ? C.border : C.accentGrad,
          border: "none", color: "#fff", cursor: (loading || !input.trim()) ? "default" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16, flexShrink: 0, transition: "all .2s",
          boxShadow: (loading || !input.trim()) ? "none" : `0 2px 12px ${C.accentSoft}`,
        }}>↑</button>
      </div>
    </div>
  );
}
