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
  if (line.startsWith("📡 Director 监控")) {
    return <div style={{ color: C.magenta || "#a855f7", fontSize: 11, lineHeight: 1.7, margin: "3px 0", fontWeight: 600 }}>{line}</div>;
  }
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

// 轻量 Markdown 渲染器（无依赖）
function MarkdownRenderer({ content, C, streaming = false }) {
  if (!content) return streaming ? <span style={{ color: C.accent, animation: "blink 1s infinite" }}>▊</span> : null;

  const elements = [];
  const lines = content.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 代码块
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <div key={i} style={{ margin: "8px 0", borderRadius: 8, overflow: "hidden", border: `1px solid ${C.border}` }}>
          {lang && <div style={{ padding: "4px 12px", background: C.accentSoft, color: C.accent, fontSize: 10, fontWeight: 700, letterSpacing: 1 }}>{lang.toUpperCase()}</div>}
          <pre style={{ margin: 0, padding: "10px 14px", background: C.logBg, overflowX: "auto", fontSize: 12, lineHeight: 1.6, color: C.textMid, fontFamily: "'JetBrains Mono','Fira Code',monospace" }}>
            {codeLines.join("\n")}
          </pre>
        </div>
      );
      i++;
      continue;
    }

    // 水平分割线
    if (/^---+$/.test(line.trim())) {
      elements.push(<hr key={i} style={{ border: "none", borderTop: `1px solid ${C.border}`, margin: "10px 0" }} />);
      i++; continue;
    }

    // H1
    if (line.startsWith("# ")) {
      elements.push(<div key={i} style={{ fontSize: 17, fontWeight: 800, color: C.text, margin: "10px 0 4px", lineHeight: 1.4 }}>{renderInline(line.slice(2), C)}</div>);
      i++; continue;
    }
    // H2
    if (line.startsWith("## ")) {
      elements.push(<div key={i} style={{ fontSize: 15, fontWeight: 700, color: C.accent, margin: "8px 0 3px", lineHeight: 1.4 }}>{renderInline(line.slice(3), C)}</div>);
      i++; continue;
    }
    // H3
    if (line.startsWith("### ")) {
      elements.push(<div key={i} style={{ fontSize: 13, fontWeight: 700, color: C.text, margin: "6px 0 2px", lineHeight: 1.4 }}>{renderInline(line.slice(4), C)}</div>);
      i++; continue;
    }

    // 无序列表
    if (/^[-*+] /.test(line)) {
      elements.push(
        <div key={i} style={{ display: "flex", gap: 6, margin: "2px 0", alignItems: "flex-start" }}>
          <span style={{ color: C.accent, flexShrink: 0, marginTop: 2, fontSize: 10 }}>◆</span>
          <span style={{ color: C.text, fontSize: 14, lineHeight: 1.6 }}>{renderInline(line.slice(2), C)}</span>
        </div>
      );
      i++; continue;
    }

    // 有序列表
    const orderedMatch = line.match(/^(\d+)\. (.+)/);
    if (orderedMatch) {
      elements.push(
        <div key={i} style={{ display: "flex", gap: 6, margin: "2px 0", alignItems: "flex-start" }}>
          <span style={{ color: C.accent, flexShrink: 0, fontWeight: 700, fontSize: 12, minWidth: 18 }}>{orderedMatch[1]}.</span>
          <span style={{ color: C.text, fontSize: 14, lineHeight: 1.6 }}>{renderInline(orderedMatch[2], C)}</span>
        </div>
      );
      i++; continue;
    }

    // 引用块
    if (line.startsWith("> ")) {
      elements.push(
        <div key={i} style={{ margin: "4px 0", padding: "6px 12px", borderLeft: `3px solid ${C.accent}`, background: C.accentSoft, borderRadius: "0 6px 6px 0" }}>
          <span style={{ color: C.textMid, fontSize: 13, lineHeight: 1.6, fontStyle: "italic" }}>{renderInline(line.slice(2), C)}</span>
        </div>
      );
      i++; continue;
    }

    // 工具调用标记行
    if (line.includes("[正在调用工具:")) {
      const match = line.match(/\[正在调用工具:\s*([^\]]+)\]/);
      const toolName = match ? match[1].replace("...", "").trim() : line;
      elements.push(
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, margin: "4px 0" }}>
          <span style={{ background: C.accentSoft, color: C.accent, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>⚙ {toolName}</span>
        </div>
      );
      i++; continue;
    }

    // 空行
    if (!line.trim()) {
      elements.push(<div key={i} style={{ height: 6 }} />);
      i++; continue;
    }

    // 普通段落
    elements.push(
      <div key={i} style={{ color: C.text, fontSize: 13, lineHeight: 1.75, margin: "1px 0" }}>
        {renderInline(line, C)}
      </div>
    );
    i++;
  }

  return (
    <>
      {elements}
      {streaming && <span style={{ color: C.accent, animation: "blink 1s infinite", marginLeft: 2 }}>▊</span>}
    </>
  );
}

// 行内格式：**bold**、*italic*、`code`、~~strike~~
function renderInline(text, C) {
  if (!text) return null;
  // 分割行内元素
  const parts = [];
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|~~(.+?)~~)/g;
  let last = 0, match;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(<span key={last}>{text.slice(last, match.index)}</span>);
    if (match[1].startsWith("**"))
      parts.push(<strong key={match.index} style={{ color: C.text, fontWeight: 700 }}>{match[2]}</strong>);
    else if (match[1].startsWith("*"))
      parts.push(<em key={match.index} style={{ color: C.textMid }}>{match[3]}</em>);
    else if (match[1].startsWith("`"))
      parts.push(<code key={match.index} style={{ background: C.elevated, color: C.accent, padding: "1px 5px", borderRadius: 3, fontSize: 12, fontFamily: "monospace" }}>{match[4]}</code>);
    else if (match[1].startsWith("~~"))
      parts.push(<s key={match.index} style={{ color: C.textDim }}>{match[5]}</s>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(<span key={last}>{text.slice(last)}</span>);
  return parts.length > 0 ? parts : text;
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
        maxWidth: isUser ? "62%" : "68%",
        padding: isUser ? "8px 12px" : "8px 2px",
        borderRadius: isUser ? "16px 16px 4px 16px" : "0",
        background: isUser ? C.userBg : "transparent",
        border: isUser ? `1px solid ${C.userBorder}` : "none",
        boxShadow: isUser ? "0 8px 24px rgba(15,23,42,.06)" : "none",
      }}>
        {isUser
          ? <div style={{ color: C.text, whiteSpace: "pre-wrap", lineHeight: 1.65, fontSize: 13 }}>{msg.content}</div>
          : <MarkdownRenderer content={msg.content} C={C} streaming={!!msg._streaming} />
        }
      </div>
    </div>
  );
}

function AgentTokenRow({ label, color, usage, limit, C }) {
  if (!usage) return null;
  const total = (usage.input || 0) + (usage.output || 0);
  const percent = Math.min(total / limit * 100, 100);
  const warn = percent > 80;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <span style={{
        color: color, width: 76, flexShrink: 0, overflow: "hidden",
        textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 600,
      }}>{label}</span>
      <div style={{ flex: 1, height: 3, background: C.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${percent}%`,
          background: warn ? (percent > 95 ? "#ef4444" : "#f59e0b") : color,
          transition: "width .4s ease", borderRadius: 2,
        }} />
      </div>
      <span style={{ color: warn ? (percent > 95 ? "#ef4444" : "#f59e0b") : C.textDim, width: 68, textAlign: "right", flexShrink: 0 }}>
        {(total / 1000).toFixed(1)}K / {(limit / 1000).toFixed(0)}K
      </span>
    </div>
  );
}

export function TokenBar({ tokens, C }) {
  if (!tokens) return null;
  const {
    input_limit, output_limit,
    mentor_name, worker_name,
    mentor, worker,
    input_percent, output_percent,
    generation = 0,
  } = tokens;
  const totalLimit = (input_limit || 176000) + (output_limit || 24000);
  return (
    <div style={{
      padding: "5px 12px 7px",
      borderTop: `1px solid ${C.border}`,
      background: C.surface,
      fontSize: 10,
      display: "flex",
      flexDirection: "column",
      gap: 4,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ color: C.textDim, fontSize: 9, letterSpacing: 0.5 }}>CONTEXT USAGE</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {generation > 0 && (
            <span style={{
              background: C.accentSoft, color: C.accent,
              padding: "1px 5px", borderRadius: 3, fontSize: 9, fontWeight: 700,
            }}>G{generation}</span>
          )}
          <span style={{ color: (input_percent > 80 || output_percent > 80) ? "#f59e0b" : C.textDim, fontSize: 9 }}>
            {Math.max(input_percent, output_percent).toFixed(0)}% token
          </span>
        </div>
      </div>
      <AgentTokenRow
        label={`🧠 ${mentor_name || "Mentor"}`}
        color={C.accent}
        usage={mentor}
        limit={totalLimit}
        C={C}
      />
      <AgentTokenRow
        label={`⚒ ${worker_name || "Worker"}`}
        color={C.cyan || "#06b6d4"}
        usage={worker}
        limit={totalLimit}
        C={C}
      />
    </div>
  );
}

export function ChatInput({ input, setInput, loading, onSend, C, textareaRef }) {
  return (
    <div style={{ padding: "0 24px 20px", maxWidth: 920, width: "100%", margin: "0 auto" }}>
      <div style={{
        display: "flex", alignItems: "flex-end", gap: 0,
        background: C.elevated, border: `1px solid ${C.borderHi}`,
        borderRadius: 18, overflow: "hidden",
        boxShadow: "0 16px 48px rgba(31,41,55,.08)",
        transition: "box-shadow .2s",
      }}>
        <textarea ref={textareaRef}
          style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            color: C.text, resize: "none", lineHeight: 1.6,
            padding: "11px 16px", maxHeight: 150, fontSize: 13,
            fontFamily: "inherit", minHeight: 44,
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
