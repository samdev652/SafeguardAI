"use client";
import { useEffect, useRef, useState } from "react";

const EMERGENCY_WORDS = [
  "help", "sos", "emergency", "stuck", "trapped", "niokoe", "msaada", "nimezingirwa", "nimeumia"
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
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [welcome, setWelcome] = useState(true);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionId = getSessionId();

  useEffect(() => {
    if (open && messages.length === 0 && welcome) {
      setMessages([
        {
          role: "assistant",
          content:
            "Hello I am your Safeguard AI disaster assistant. I can tell you about current risks in your area, guide you to safety, and connect you with rescue services. Ask me anything in English or Swahili."
        }
      ]);
      setWelcome(false);
    }
  }, [open, messages.length, welcome]);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open]);

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
    setError("");
    try {
      const res = await fetch("/api/chatbot/message/", {
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
        setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
      } else {
        setError("No response from assistant.");
      }
    } catch (e) {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
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
          className="fixed bottom-6 right-6 z-50 bg-navy rounded-full shadow-lg p-4 flex items-center justify-center hover:bg-teal-600 transition-colors"
          style={{ width: 64, height: 64 }}
          onClick={() => setOpen(true)}
        >
          <span className="relative">
            <svg width="32" height="32" fill="none" viewBox="0 0 32 32">
              <circle cx="16" cy="16" r="16" fill="#0f172a" />
              <path d="M10 22l12-6-12-6v12z" fill="#14b8a6" />
            </svg>
            {threatCount > 0 && (
              <span className="absolute -top-2 -right-2 bg-red-600 animate-pulse text-xs text-white rounded-full px-2 py-0.5 font-bold">
                {threatCount}
              </span>
            )}
          </span>
        </button>
      )}
      {/* Expanded chat */}
      {open && (
        <div
          className="fixed z-50 bottom-0 right-0 w-full max-w-[380px] md:rounded-t-lg md:rounded-b-lg md:bottom-6 md:right-6 bg-navy text-white shadow-2xl flex flex-col"
          style={{ height: "min(90vh, 600px)", maxHeight: 600 }}
        >
          <div className="flex items-center justify-between px-4 py-3 bg-navy border-b border-teal-600">
            <span className="font-bold text-lg">Safeguard AI Assistant</span>
            <button
              aria-label="Close chatbot"
              className="text-teal-400 hover:text-teal-200"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 py-2 space-y-3 bg-navy"
            style={{ minHeight: 200 }}
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] px-4 py-2 rounded-lg shadow-md fade-in ${
                    m.role === "user"
                      ? "bg-teal-700 text-right ml-auto"
                      : "bg-gray-800 text-left mr-auto"
                  }`}
                  style={{ animation: "fadeIn 0.4s" }}
                  dangerouslySetInnerHTML={{ __html: m.content }}
                />
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 px-4 py-2 rounded-lg shadow-md flex items-center space-x-2">
                  <span className="dot-typing">
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </span>
                </div>
              </div>
            )}
            {error && (
              <div className="text-red-400 text-sm mt-2">{error}</div>
            )}
          </div>
          {/* Suggestions */}
          <div className="flex flex-wrap gap-2 px-4 pb-2">
            {suggestions.map((s, i) => (
              <button
                key={i}
                className="bg-gray-700 hover:bg-teal-700 text-white text-xs rounded-full px-3 py-1 transition-colors"
                onClick={() => sendMessage(s)}
              >
                {s}
              </button>
            ))}
          </div>
          {/* Input */}
          <div className="flex items-center px-4 py-3 border-t border-teal-600 bg-navy">
            <textarea
              className="flex-1 bg-gray-900 text-white rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-teal-500"
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={loading}
              style={{ minHeight: 36, maxHeight: 80 }}
            />
            <button
              className="ml-2 bg-teal-600 hover:bg-teal-500 text-white rounded-full px-4 py-2 font-bold transition-colors"
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </div>
        </div>
      )}
      <style jsx>{`
        @media (max-width: 600px) {
          div.fixed.z-50.bottom-0.right-0 {
            max-width: 100vw !important;
            width: 100vw !important;
            left: 0;
            right: 0;
            border-radius: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
          }
        }
        .fade-in {
          animation: fadeIn 0.4s;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: none; }
        }
        .dot-typing {
          display: inline-block;
        }
        .dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          margin: 0 2px;
          background: #14b8a6;
          border-radius: 50%;
          animation: blink 1.4s infinite both;
        }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes blink {
          0%, 80%, 100% { opacity: 0.2; }
          40% { opacity: 1; }
        }
      `}</style>
    </>
  );
}
