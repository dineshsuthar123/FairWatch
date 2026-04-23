import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "../api/client";

const DEFAULT_MESSAGE = {
  role: "bot",
  content: "Hi. I can explain the model, the data, affected groups, and whether this model is safe to deploy.",
};

function ChatPanel({ selectedModelId }) {
  const [messages, setMessages] = useState([DEFAULT_MESSAGE]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    setMessages([DEFAULT_MESSAGE]);
  }, [selectedModelId]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!input.trim() || !selectedModelId) {
      return;
    }

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsTyping(true);

    try {
      const response = await sendChatMessage(selectedModelId, userMessage);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: response.answer,
          data: {
            risk_level: response.risk_level,
            affected_groups: response.affected_groups,
            recommended_action: response.recommended_action,
          },
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Sorry, I could not connect to the fairness engine." },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-[600px] w-full flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl">
      <div className="flex shrink-0 items-center justify-between bg-gradient-to-r from-blue-600 to-indigo-600 p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 text-sm font-bold shadow-inner backdrop-blur-md text-white">
            FW
          </span>
          <div>
            <h3 className="font-heading text-lg font-bold text-white">Fairness Copilot</h3>
            <p className="text-[11px] font-medium text-blue-100">AI Fairness Assistant</p>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto bg-slate-50/50 p-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex max-w-[85%] flex-col ${msg.role === "user" ? "ml-auto" : "mr-auto"}`}>
            <div
              className={`p-3.5 shadow-sm ${
                msg.role === "user"
                  ? "rounded-2xl rounded-tr-sm bg-gradient-to-br from-blue-500 to-blue-600 text-white"
                  : "rounded-2xl rounded-tl-sm border border-slate-200/60 bg-white text-slate-700 backdrop-blur-sm"
              }`}
            >
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{msg.content}</p>

              {msg.data?.risk_level && (
                <div className="mt-4 space-y-2 border-t border-slate-100/10 pt-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold ${msg.role === "user" ? "text-blue-100" : "text-slate-500"}`}>
                      Risk Level:
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                        String(msg.data.risk_level).toLowerCase() === "unsafe"
                          ? "bg-rose-100 text-rose-800"
                          : String(msg.data.risk_level).toLowerCase() === "safe"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {msg.data.risk_level}
                    </span>
                  </div>

                  {msg.data.affected_groups?.length > 0 && (
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className={`text-xs font-semibold ${msg.role === "user" ? "text-blue-100" : "text-slate-500"}`}>
                        Affected:
                      </span>
                      {msg.data.affected_groups.map((group) => (
                        <span
                          key={group}
                          className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${
                            msg.role === "user" ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {group}
                        </span>
                      ))}
                    </div>
                  )}

                  {msg.data.recommended_action && (
                    <div className="mt-2 rounded-lg bg-black/5 p-2">
                      <span className={`text-[12px] font-medium leading-snug ${msg.role === "user" ? "text-white" : "text-slate-700"}`}>
                        {msg.data.recommended_action}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="mr-auto flex max-w-[85%]">
            <div className="flex gap-1.5 rounded-2xl rounded-tl-sm border border-slate-200/60 bg-white p-4 text-slate-400 shadow-sm backdrop-blur-sm">
              <span className="h-2 w-2 animate-bounce rounded-full bg-current" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-current" style={{ animationDelay: "0.15s" }} />
              <span className="h-2 w-2 animate-bounce rounded-full bg-current" style={{ animationDelay: "0.3s" }} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="shrink-0 border-t border-slate-100 bg-white p-4 pt-3">
        <form onSubmit={handleSubmit} className="relative flex gap-2">
          <input
            type="text"
            className="flex-1 rounded-full border border-slate-200 bg-slate-50 py-3 pl-5 pr-12 text-sm text-slate-700 shadow-sm transition-all focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:opacity-50"
            placeholder={selectedModelId ? "Ask about data, bias, or deployment safety..." : "Select a model first..."}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={!selectedModelId || isTyping}
          />
          <button
            type="submit"
            className="absolute right-1.5 top-1.5 flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white shadow-md transition-transform hover:scale-105 hover:bg-blue-700 disabled:scale-100 disabled:opacity-50"
            disabled={!selectedModelId || isTyping || !input.trim()}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="ml-0.5 h-4 w-4">
              <path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatPanel;
