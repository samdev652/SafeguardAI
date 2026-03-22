"use client";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";

const EMERGENCY_WORDS = [
  "help", "sos", "emergency", "stuck", "trapped", "niokoe", "msaada", "nimezingirwa", "nimeumia"
];

const RISK_LEVELS = [
  { key: "critical", label: "Critical", color: "var(--critical)" },
  { key: "high", label: "High", color: "var(--high)" },
  { key: "medium", label: "Medium", color: "var(--medium)" },
  { key: "safe", label: "Safe", color: "var(--safe)" },
];

function getSessionId() {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem("safeguard_chatbot_session");
  if (!id) {
    id = Math.random().toString(36).slice(2) + Date.now();
    localStorage.setItem("safeguard_chatbot_session", id);
  }
  return id;
}

export default function ChatbotWidget({ wardName, threatCount }: { wardName?: string; threatCount: number }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant" | "emergency"; content: string; meta?: any }>>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [welcome, setWelcome] = useState(true);
  const [error, setError] = useState("");
  const [riskLevel, setRiskLevel] = useState("safe");
  const [stats, setStats] = useState<{counties: number, threats: number, alerts: number} | null>(null);
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionId = getSessionId();

  useEffect(() => {
    if (open && messages.length === 0 && welcome) {
      // Fetch stats for welcome pills
      fetch("http://localhost:8000/api/stats/public/")
        .then(r => r.json())
        .then(data => setStats(data))
        .catch(() => setStats(null));
      setMessages([
        {
          role: "assistant",
          content: "Welcome to Safeguard AI. How can I help you stay safe today?"
        }
      ]);
      setWelcome(false);
    }
  }, [open, messages.length, welcome]);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, loading]);

  useEffect(() => {
    // Suggestion chips based on threatCount
    const base = [
      "What is the flood risk in my area?",
      "How do I evacuate safely?",
      "Who do I call for help?",
      "Is it safe to travel today?"
    ];
    setSuggestions(base);
  }, [threatCount]);

  const sendMessage = async (msg: string) => {
    if (!msg.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setInput("");
    setLoading(true);
    setTyping(true);
    setError("");
    try {
      const res = await fetch("http://localhost:8000/api/hazards/chatbot/message/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          ward_name: wardName,
          session_id: sessionId
        })
      });
      const data = await res.json();
      if (data.response) {
        // Emergency detection
        if (data.emergency) {
          setMessages((prev) => [...prev, { role: "emergency", content: data.emergency, meta: data.meta }]);
        } else {
          setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
        }
        if (data.risk_level) setRiskLevel(data.risk_level);
      } else {
        setError("No response from assistant.");
      }
    } catch (e) {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
      setTyping(false);
    }
  };

  const handleSend = () => {
    if (input.trim()) sendMessage(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Collapsed bubble */}
      {!open && (
        <button
          aria-label="Open Safeguard AI Assistant"
          className="sgcb-floating-btn"
          onClick={() => setOpen(true)}
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            width: 56,
            height: 56,
            background: "var(--safe)",
            borderRadius: "50%",
            boxShadow: "0 6px 24px rgba(0,0,0,0.32)",
            zIndex: 9999,
            border: "none",
            outline: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.18s"
          }}
        >
          <span className="relative" style={{ display: "flex", alignItems: "center" }}>
            {/* Chat icon */}
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <circle cx="14" cy="14" r="14" fill="#0A0F1E" />
              <path d="M8.5 19.5L19.5 14L8.5 8.5V19.5Z" fill="#00D4AA" />
            </svg>
            {threatCount > 0 && (
              <span style={{
                position: "absolute",
                top: -6,
                right: -6,
                background: "var(--critical)",
                color: "#fff",
                fontWeight: 700,
                fontSize: 13,
                borderRadius: 999,
                minWidth: 22,
                height: 22,
                display: "grid",
                placeItems: "center",
                border: "2px solid #0A0F1E",
                boxShadow: "0 0 0 2px var(--critical)",
                animation: "sgcb-pulse 1.2s infinite"
              }} aria-live="polite">
                {threatCount}
              </span>
            )}
          </span>
        </button>
      )}
      {/* Expanded chat */}
      {open && (
        <div
          className="sgcb-widget-shell"
          tabIndex={-1}
          style={{
            position: "fixed",
            zIndex: 9999,
            bottom: 0,
            right: 0,
            width: "100vw",
            maxWidth: 380,
            borderRadius: 18,
            background: "#0A0F1E",
            boxShadow: "0 12px 48px rgba(0,0,0,0.45)",
            display: "flex",
            flexDirection: "column",
            height: "min(90vh,600px)",
            maxHeight: 600,
            outline: open ? "2px solid var(--safe)" : undefined,
            transition: "transform 0.22s cubic-bezier(.4,1.4,.6,1), opacity 0.22s",
            animation: "sgcb-scalein 0.32s cubic-bezier(.4,1.4,.6,1)"
          }}
          aria-modal="true"
          role="dialog"
        >
          {/* Header */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 18px 10px 18px",
            borderBottom: "1px solid #1e2a3a",
            background: "#0A0F1E"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {/* Logo */}
              <span style={{ display: "grid", placeItems: "center", width: 32, height: 32, borderRadius: 8, background: "linear-gradient(145deg,#00D4AA 0%,#0A0F1E 100%)" }}>
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="11" fill="#0A0F1E"/><path d="M6.5 15.5L15.5 11L6.5 6.5V15.5Z" fill="#00D4AA"/></svg>
              </span>
              <span style={{ fontFamily: 'Space Grotesk, sans-serif', fontWeight: 500, fontSize: 18, color: "#fff" }}>Disaster Assistant</span>
              {/* Live risk badge */}
              <span className={`risk-badge badge-${riskLevel}`} style={{ marginLeft: 8, fontWeight: 700, fontSize: 13, padding: "4px 10px", borderRadius: 999, background: `rgba(${riskLevel === "critical" ? "239,68,68,0.18" : riskLevel === "high" ? "249,115,22,0.18" : riskLevel === "medium" ? "245,158,11,0.18" : "0,212,170,0.18"})`, color: riskLevel === "critical" ? "#ffabab" : riskLevel === "high" ? "#ffc29f" : riskLevel === "medium" ? "#ffd284" : "#7df0d7" }} aria-live="polite">{riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)}</span>
            </div>
            <button
              aria-label="Close chatbot"
              onClick={() => setOpen(false)}
              style={{
                background: "none",
                border: "none",
                color: "#00D4AA",
                fontSize: 28,
                fontWeight: 500,
                cursor: "pointer",
                outline: "none",
                borderRadius: 8,
                padding: 4,
                transition: "background 0.18s"
              }}
              tabIndex={0}
              onKeyDown={e => { if (e.key === "Enter" || e.key === " " ) setOpen(false); }}
            >×</button>
          </div>
          {/* Welcome message with logo and stats pills */}
          {messages.length === 1 && stats && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", margin: "32px 0 18px 0" }}>
              <span style={{ display: "grid", placeItems: "center", width: 54, height: 54, borderRadius: 12, background: "linear-gradient(145deg,#00D4AA 0%,#0A0F1E 100%)", marginBottom: 10 }}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="16" fill="#0A0F1E"/><path d="M10 22l12-6-12-6v12z" fill="#00D4AA"/></svg>
              </span>
              <div style={{ color: "#fff", fontWeight: 500, fontSize: 18, textAlign: "center", marginBottom: 10 }}>Welcome to Safeguard AI</div>
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <span className="sgcb-pill" style={{ background: "#1e2a3a", color: "#00D4AA" }}>{stats.counties} counties covered</span>
                <span className="sgcb-pill" style={{ background: "#1e2a3a", color: "#EF4444" }}>{stats.threats} active threats</span>
                <span className="sgcb-pill" style={{ background: "#1e2a3a", color: "#F59E0B" }}>{stats.alerts} alerts sent today</span>
              </div>
            </div>
          )}
          {/* Message area */}
          <div
            ref={scrollRef}
            className="sgcb-messages"
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "0 0 0 0",
              background: "#0A0F1E",
              display: "flex",
              flexDirection: "column",
              gap: 0,
              outline: "none",
              scrollbarWidth: "thin",
              scrollbarColor: "#00D4AA #1e2a3a"
            }}
            aria-live="polite"
          >
            {messages.map((m, i) => (
              m.role === "emergency" ? (
                <div key={i} className="sgcb-emergency-card" style={{
                  border: "2px solid var(--critical)",
                  background: "#1e2a3a",
                  color: "#fff",
                  borderRadius: 14,
                  margin: "16px 12px 8px 12px",
                  padding: 16,
                  fontWeight: 500,
                  fontSize: 16,
                  boxShadow: "0 2px 12px rgba(239,68,68,0.12)",
                  outline: "none"
                }} aria-live="assertive">
                  <div style={{ fontWeight: 700, color: "#EF4444", marginBottom: 8, fontSize: 17 }}>EMERGENCY RESPONSE</div>
                  <div style={{ marginBottom: 10 }}>{m.content}</div>
                  {Array.isArray(m.meta?.phones) && m.meta.phones.map((phone: string, idx: number) => (
                    <a
                      key={phone}
                      href={`tel:${phone}`}
                      style={{
                        display: "block",
                        background: "#EF4444",
                        color: "#fff",
                        borderRadius: 8,
                        padding: "10px 0",
                        margin: "6px 0",
                        textAlign: "center",
                        fontWeight: 700,
                        fontSize: 15,
                        textDecoration: "none",
                        outline: "none",
                        boxShadow: "0 1px 6px rgba(239,68,68,0.13)",
                        border: "none"
                      }}
                      tabIndex={0}
                      aria-label={`Call ${phone}`}
                    >{phone}</a>
                  ))}
                </div>
              ) : (
                <div
                  key={i}
                  className={`sgcb-bubble-row ${m.role === "user" ? "sgcb-bubble-user" : "sgcb-bubble-assistant"}`}
                  style={{
                    display: "flex",
                    justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                    margin: "10px 12px 0 12px"
                  }}
                >
                  {m.role === "assistant" && (
                    <span style={{
                      width: 32,
                      height: 32,
                      borderRadius: 999,
                      background: "#1e2a3a",
                      display: "grid",
                      placeItems: "center",
                      marginRight: 8,
                      marginTop: 2
                    }}>
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="9" fill="#00D4AA"/><path d="M9 3v7l4 2" stroke="#0A0F1E" strokeWidth="2" strokeLinecap="round"/></svg>
                    </span>
                  )}
                  <div
                    className="sgcb-bubble"
                    style={{
                      maxWidth: "80%",
                      padding: "12px 16px",
                      borderRadius: 14,
                      fontWeight: 500,
                      fontSize: 15,
                      background: m.role === "user" ? "#00D4AA" : "#0d1424",
                      color: m.role === "user" ? "#0A0F1E" : "#f4f7ff",
                      marginLeft: m.role === "user" ? 0 : 0,
                      marginRight: m.role === "user" ? 0 : 0,
                      boxShadow: m.role === "user" ? "0 2px 8px rgba(0,212,170,0.08)" : "0 2px 8px rgba(10,15,30,0.13)",
                      textAlign: m.role === "user" ? "right" : "left",
                      outline: "none"
                    }}
                    tabIndex={0}
                    aria-label={m.content}
                  >{m.content}</div>
                </div>
              )
            ))}
            {/* Typing indicator */}
            {typing && (
              <div style={{ display: "flex", alignItems: "center", margin: "10px 12px" }}>
                <span style={{ width: 32, height: 32, borderRadius: 999, background: "#1e2a3a", display: "grid", placeItems: "center", marginRight: 8 }}>
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="9" fill="#00D4AA"/><path d="M9 3v7l4 2" stroke="#0A0F1E" strokeWidth="2" strokeLinecap="round"/></svg>
                </span>
                <span className="sgcb-typing">
                  <span className="sgcb-dot"></span>
                  <span className="sgcb-dot"></span>
                  <span className="sgcb-dot"></span>
                </span>
              </div>
            )}
            {error && (
              <div style={{ color: "#EF4444", fontSize: 14, margin: "10px 18px" }}>{error}</div>
            )}
          </div>
          {/* Suggestions */}
          <div style={{ display: "flex", gap: 6, overflowX: "auto", padding: "8px 14px 0 14px", marginBottom: 2 }}>
            {suggestions.map((s, i) => (
              <button
                key={i}
                className="sgcb-chip"
                style={{
                  background: "#1e2a3a",
                  color: "#00D4AA",
                  border: "1px solid #00D4AA",
                  borderRadius: 999,
                  fontWeight: 500,
                  fontSize: 13,
                  padding: "7px 16px",
                  marginRight: 2,
                  marginBottom: 2,
                  cursor: "pointer",
                  outline: "none",
                  transition: "background 0.18s"
                }}
                onClick={() => sendMessage(s)}
                tabIndex={0}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") sendMessage(s); }}
              >{s}</button>
            ))}
          </div>
          {/* Input */}
          <form
            className="sgcb-input-row"
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 8,
              padding: "14px 14px 14px 14px",
              borderTop: "1px solid #1e2a3a",
              background: "#0A0F1E"
            }}
            onSubmit={e => { e.preventDefault(); handleSend(); }}
            autoComplete="off"
            role="search"
          >
            <textarea
              className="sgcb-input"
              style={{
                flex: 1,
                background: "#0d1424",
                color: "#fff",
                borderRadius: 12,
                border: "1.5px solid #1e2a3a",
                fontSize: 15,
                fontWeight: 500,
                padding: "12px 14px",
                minHeight: 38,
                maxHeight: 90,
                resize: "none",
                outline: "none",
                boxShadow: input.length > 0 ? "0 0 0 2px #00D4AA" : undefined,
                transition: "box-shadow 0.18s"
              }}
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={loading}
              aria-label="Type your message"
              autoFocus={open}
            />
            <button
              className="sgcb-send-btn"
              style={{
                background: input.trim() ? "#00D4AA" : "#1e2a3a",
                color: input.trim() ? "#0A0F1E" : "#7df0d7",
                border: "none",
                borderRadius: "50%",
                width: 44,
                height: 44,
                display: "grid",
                placeItems: "center",
                fontWeight: 700,
                fontSize: 20,
                marginLeft: 2,
                cursor: input.trim() ? "pointer" : "not-allowed",
                outline: "none",
                boxShadow: input.trim() ? "0 0 0 2px #00D4AA" : undefined,
                transition: "background 0.18s"
              }}
              onClick={handleSend}
              disabled={loading || !input.trim()}
              aria-label="Send message"
              tabIndex={0}
              type="submit"
            >
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><circle cx="11" cy="11" r="11" fill="currentColor"/><path d="M7 15l8-4-8-4v8z" fill="#0A0F1E"/></svg>
            </button>
          </form>
        </div>
      )}
      {/* Styles for widget */}
      <style jsx global>{`
        .sgcb-floating-btn:focus {
          outline: 2px solid #00D4AA;
          outline-offset: 2px;
        }
        .sgcb-widget-shell:focus {
          outline: 2px solid #00D4AA;
        }
        .sgcb-pill {
          display: inline-block;
          border-radius: 999px;
          font-size: 13px;
          font-weight: 700;
          padding: 6px 14px;
          background: #1e2a3a;
        }
        .sgcb-messages::-webkit-scrollbar {
          width: 4px;
        }
        .sgcb-messages::-webkit-scrollbar-thumb {
          background: #00D4AA;
          border-radius: 4px;
        }
        .sgcb-messages::-webkit-scrollbar-track {
          background: #1e2a3a;
        }
        @media (max-width: 600px) {
          .sgcb-widget-shell {
            max-width: 100vw !important;
            width: 100vw !important;
            left: 0;
            right: 0;
            border-radius: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
          }
        }
        @keyframes sgcb-scalein {
          from { opacity: 0; transform: scale(0.92); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes sgcb-pulse {
          0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.62); }
          100% { box-shadow: 0 0 0 10px rgba(239,68,68,0); }
        }
        .sgcb-typing {
          display: inline-flex;
          align-items: center;
          gap: 2px;
        }
        .sgcb-dot {
          width: 8px;
          height: 8px;
          background: #00D4AA;
          border-radius: 50%;
          margin: 0 2px;
          animation: sgcb-blink 1.4s infinite both;
        }
        .sgcb-dot:nth-child(2) { animation-delay: 0.2s; }
        .sgcb-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes sgcb-blink {
          0%, 80%, 100% { opacity: 0.2; }
          40% { opacity: 1; }
        }
        .sgcb-chip:focus, .sgcb-send-btn:focus, .sgcb-input:focus {
          outline: 2px solid #00D4AA !important;
          outline-offset: 2px;
        }
      `}</style>
    </>
  );
}
