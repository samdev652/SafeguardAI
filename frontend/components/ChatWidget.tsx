"use client";
import React, { useState, useRef, useEffect } from "react";

const TEAL = "#00D4AA";
const DARK_BG = "#0d1424";
const BORDER = "#1e2a3a";
const LIGHT_TEXT = "#c8d8f0";
const HEADER_BG = "#0A0F1E";

function isMobile() {
  if (typeof window === "undefined") return false;
  return window.innerWidth < 640;
}

function generateSessionId() {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

interface Message {
  role: "user" | "assistant";
  content: string;
  is_emergency?: boolean;
  risk_level?: string;
  relevant_ward?: string;
  suggestions?: string[];
  is_proactive_alert?: boolean;
  action_query?: string;
}

const WELCOME: Message = {
  role: "assistant",
  content: "Habari! I am Rafiki, your Safeguard AI disaster assistant. Ask me anything about current disaster risks in Kenya in English, Swahili, or Sheng.",
};

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionRef = useRef<string>("");
  const openRef = useRef(open);

  useEffect(() => {
    openRef.current = open;
  }, [open]);

  useEffect(() => {
    sessionRef.current = generateSessionId();
  }, []);

  useEffect(() => {
    const handleNewAlert = (e: Event) => {
      // Must appear automatically without the user asking anything if chat is open
      if (!openRef.current) return;
      
      const risk = (e as CustomEvent).detail;
      const levelStr = risk.risk_level.charAt(0).toUpperCase() + risk.risk_level.slice(1);
      const text = `New alert — ${risk.ward_name} ${risk.hazard_type} risk just upgraded to ${levelStr}. Tap to ask me about it.`;
      const actionQuery = `Tell me about the ${risk.ward_name} ${risk.hazard_type} alert`;
      
      setMessages(prev => {
        if (prev.some(m => m.content === text)) return prev;
        return [...prev, {
          role: 'assistant',
          content: text,
          is_proactive_alert: true,
          action_query: actionQuery
        }];
      });
    };
    
    window.addEventListener('safeguard:new_alert', handleNewAlert);
    return () => window.removeEventListener('safeguard:new_alert', handleNewAlert);
  }, []);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, typing]);

  const triggerSOS = async () => {
    try {
      const token = localStorage.getItem("safeguard_token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      // Attempt to hit the SOS endpoint
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/alerts/sos/`, { 
        method: "POST",
        headers 
      });
      alert("🚨 SOS DISPATCHED: Rescue teams have been notified of your location.");
    } catch (e) {
      alert("SOS connection failed. PLEASE CALL 0800 721 211 IMMEDIATELY.");
    }
  };

  const sendMessage = async (overrideText?: string) => {
    const text = overrideText || input;
    if (!text.trim() || loading) return;
    
    const userMsg: Message = { role: "user", content: text };
    setMessages((msgs) => [...msgs, userMsg]);
    if (!overrideText) setInput("");
    
    setTyping(true);
    setLoading(true);
    
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionRef.current }),
      });
      const data = await res.json();
      
      const assistantMsg: Message = {
        role: "assistant",
        content: data.reply || data.error || "Sorry, I am unable to connect to the safety network right now.",
        is_emergency: data.is_emergency,
        risk_level: data.risk_level,
        relevant_ward: data.relevant_ward,
        suggestions: data.suggestions
      };
      
      setMessages((msgs) => [...msgs, assistantMsg]);
    } catch {
      setMessages((msgs) => [
        ...msgs,
        { role: "assistant", content: "Connection lost. Please try again." },
      ]);
    } finally {
      setTyping(false);
      setLoading(false);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      <button
        aria-label="Open chat"
        onClick={() => setOpen(true)}
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          width: 60,
          height: 60,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #00D4AA, #0088ff)",
          border: "none",
          boxShadow: "0 8px 32px rgba(0, 212, 170, 0.4)",
          zIndex: 9999,
          display: open ? "none" : "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transition: "transform 0.2s",
        }}
        onMouseOver={e => (e.currentTarget.style.transform = "scale(1.08)")}
        onMouseOut={e => (e.currentTarget.style.transform = "scale(1)")}
      >
        <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="14" fill="#fff" />
          <path d="M8.5 19.5L19.5 14L8.5 8.5V19.5Z" fill="#00D4AA" />
        </svg>
      </button>

      {open && (
        <div
          style={{
            position: "fixed",
            bottom: isMobile() ? 0 : 90,
            right: isMobile() ? 0 : 24,
            width: isMobile() ? "100vw" : 400,
            height: isMobile() ? "100vh" : 560,
            maxWidth: "100vw",
            maxHeight: "100vh",
            background: DARK_BG,
            border: isMobile() ? 'none' : `1px solid rgba(0, 212, 170, 0.3)`,
            borderRadius: isMobile() ? 0 : 20,
            boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden"
          }}
        >
          {/* Header */}
          <div
            style={{
              background: "linear-gradient(to right, #0A0F1E, #0a1f2e)",
              color: TEAL,
              fontWeight: 700,
              fontSize: 18,
              padding: "16px 20px",
              borderBottom: `1px solid ${BORDER}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 10px #10b981" }} />
              Rafiki Intelligence
            </div>
            <button
              aria-label="Close chat"
              onClick={() => setOpen(false)}
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "none",
                color: "#c8d8f0",
                width: 32,
                height: 32,
                borderRadius: "50%",
                fontSize: 20,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "background 0.2s"
              }}
              onMouseOver={e => (e.currentTarget.style.background = "rgba(255,255,255,0.1)")}
              onMouseOut={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
            >
              &times;
            </button>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "20px 16px",
              background: DARK_BG,
              color: LIGHT_TEXT,
              fontSize: 15,
              display: "flex",
              flexDirection: "column",
              gap: 16,
              scrollBehavior: "smooth"
            }}
          >
            {messages.map((m, i) => {
              const isLast = i === messages.length - 1;
              const isAssistant = m.role === "assistant";
              
              let riskColor = "#22c55e";
              if (m.risk_level === "critical") riskColor = "#ef4444";
              if (m.risk_level === "high") riskColor = "#f97316";
              if (m.risk_level === "medium") riskColor = "#f59e0b";
              
              return (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div
                    style={{
                      alignSelf: isAssistant ? "flex-start" : "flex-end",
                      background: isAssistant ? HEADER_BG : "linear-gradient(135deg, #00D4AA, #00a888)",
                      color: isAssistant ? LIGHT_TEXT : "#fff",
                      borderRadius: isAssistant ? "4px 18px 18px 18px" : "18px 4px 18px 18px",
                      padding: "12px 18px",
                      maxWidth: "85%",
                      fontWeight: 500,
                      lineHeight: 1.5,
                      border: isAssistant && m.is_emergency ? "2px solid #ef4444" : isAssistant ? `1px solid ${BORDER}` : "none",
                      boxShadow: isAssistant && m.is_emergency 
                        ? "0 0 16px rgba(239, 68, 68, 0.3)" 
                        : "0 4px 12px rgba(0,0,0,0.15)",
                      wordBreak: "break-word",
                    }}
                  >
                    {m.is_proactive_alert ? (
                      <div 
                        onClick={() => sendMessage(m.action_query)}
                        style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: 6 }}
                      >
                        <div style={{ fontWeight: 700, color: "#ef4444", fontSize: "0.85rem", letterSpacing: "0.05em", textTransform: "uppercase" }}>🚨 Proactive Alert</div>
                        <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                        <div style={{ color: "#00D4AA", fontSize: "0.85rem", marginTop: 4, fontWeight: "bold" }}>» Tap to Auto-Send: "{m.action_query}"</div>
                      </div>
                    ) : (
                      <>
                        {isAssistant && (m.relevant_ward || m.risk_level) && (
                          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "#6b7280" }}>
                            {m.relevant_ward && <span>📍 {m.relevant_ward}</span>}
                            {m.risk_level && m.risk_level !== 'safe' && (
                              <span style={{ background: `${riskColor}22`, color: riskColor, padding: "2px 6px", borderRadius: 4, fontWeight: 700 }}>
                                {m.risk_level} Risk
                              </span>
                            )}
                          </div>
                        )}
                        
                        <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                        
                        {isAssistant && m.is_emergency && (
                          <button 
                            onClick={triggerSOS}
                            style={{
                              marginTop: 16,
                              width: "100%",
                              background: "#ef4444",
                              color: "#fff",
                              border: "none",
                              padding: "12px",
                              borderRadius: 8,
                              fontWeight: 700,
                              fontSize: "1rem",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: 8,
                              boxShadow: "0 4px 12px rgba(239, 68, 68, 0.4)",
                              transition: "background 0.2s"
                            }}
                            onMouseOver={e => (e.currentTarget.style.background = "#dc2626")}
                            onMouseOut={e => (e.currentTarget.style.background = "#ef4444")}
                          >
                            🚨 DISPATCH SOS RESCUE
                          </button>
                        )}
                      </>
                    )}
                  </div>
                  
                  {isAssistant && isLast && m.suggestions && m.suggestions.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
                      {m.suggestions.map((suggestion, idx) => (
                        <button
                          key={idx}
                          onClick={() => sendMessage(suggestion)}
                          disabled={loading}
                          style={{
                            background: "rgba(0, 212, 170, 0.1)",
                            color: TEAL,
                            border: `1px solid rgba(0, 212, 170, 0.3)`,
                            padding: "6px 14px",
                            borderRadius: 20,
                            fontSize: "0.85rem",
                            cursor: loading ? "not-allowed" : "pointer",
                            transition: "all 0.2s"
                          }}
                          onMouseOver={e => !loading && (e.currentTarget.style.background = "rgba(0, 212, 170, 0.2)")}
                          onMouseOut={e => !loading && (e.currentTarget.style.background = "rgba(0, 212, 170, 0.1)")}
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
            
            {typing && (
              <div
                style={{
                  alignSelf: "flex-start",
                  background: HEADER_BG,
                  color: LIGHT_TEXT,
                  borderRadius: "14px 14px 14px 4px",
                  padding: "12px 18px",
                  border: `1px solid ${BORDER}`,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <div style={{ width: 24, height: 24, borderRadius: "50%", background: "#0a1f2e", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={TEAL} strokeWidth="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                </div>
                <span style={{ display: "inline-flex", gap: 4 }}>
                  <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: TEAL, animation: "blink 1.4s infinite both" }} />
                  <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: TEAL, animation: "blink 1.4s 0.2s infinite both" }} />
                  <span className="dot" style={{ width: 6, height: 6, borderRadius: "50%", background: TEAL, animation: "blink 1.4s 0.4s infinite both" }} />
                </span>
              </div>
            )}
          </div>

          {/* Input */}
          <form
            onSubmit={e => { e.preventDefault(); sendMessage(); }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "16px",
              borderTop: `1px solid ${BORDER}`,
              background: HEADER_BG,
            }}
            autoComplete="off"
          >
            <textarea
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              rows={1}
              style={{
                flex: 1,
                resize: "none",
                minHeight: 44,
                maxHeight: 120,
                borderRadius: 24,
                border: `1px solid ${BORDER}`,
                fontSize: 15,
                padding: "12px 16px",
                background: "#0d1424",
                color: "#fff",
                outline: "none",
                boxShadow: input.length > 0 ? `0 0 0 1px ${TEAL}` : "inset 0 2px 4px rgba(0,0,0,0.2)",
                transition: "all 0.2s",
              }}
              placeholder="Ask Rafiki a question..."
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                background: input.trim() ? TEAL : "#1e2a3a",
                color: input.trim() ? "#0A0F1E" : "#6b7280",
                border: "none",
                borderRadius: "50%",
                width: 48,
                height: 48,
                display: "grid",
                placeItems: "center",
                flexShrink: 0,
                cursor: input.trim() ? "pointer" : "not-allowed",
                transition: "all 0.2s",
                boxShadow: input.trim() ? "0 4px 12px rgba(0, 212, 170, 0.3)" : "none",
              }}
            >
              <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                <circle cx="11" cy="11" r="11" fill="currentColor" />
                <path d="M7 15l8-4-8-4v8z" fill={input.trim() ? "#0A0F1E" : "#0d1424"} />
              </svg>
            </button>
          </form>
        </div>
      )}
      <style jsx global>{`
        @keyframes blink {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </>
  );
}
