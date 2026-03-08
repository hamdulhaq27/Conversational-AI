import { Send, RotateCcw, UtensilsCrossed, ChefHat, MessageSquare } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
}

// ─── Hardcoded greeting (no LLM call needed) ────────────────────────────────
const BOT_GREETING: Message = {
  role: "assistant",
  content:
    "Hello! I'm the virtual assistant for La Bella Tavola 🍝.\nI can help you with reservations, opening hours, menu questions, and more.\nHow may I assist you today?",
};

const ChatMain = () => {
  const [messages, setMessages] = useState<Message[]>([BOT_GREETING]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isReceiving, setIsReceiving] = useState(false);
  const [waitingLong, setWaitingLong] = useState(false); // Show "Generating..." after delay
  const ws = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const requestStartRef = useRef<number>(0);
  const longWaitTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Clear the long-wait timer helper
  const clearLongWaitTimer = () => {
    if (longWaitTimerRef.current) {
      clearTimeout(longWaitTimerRef.current);
      longWaitTimerRef.current = null;
    }
    setWaitingLong(false);
  };

  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout;

    const connectWebSocket = () => {
      const wsUrl = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/chat";
      console.log("[CHATBOT] Connecting to WebSocket:", wsUrl);
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onopen = () => {
        console.log("[CHATBOT] WebSocket connection opened.");
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("[CHATBOT] WebSocket frame received:", data);

        if (data.type === "session") {
          console.log("[CHATBOT] Session ID received:", data.session_id);
          setSessionId(data.session_id);

        } else if (data.type === "token") {
          // First token arrived — clear the "Generating..." indicator
          clearLongWaitTimer();
          setIsReceiving(true);
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg && lastMsg.role === "assistant" && lastMsg !== BOT_GREETING) {
              lastMsg.content += data.token;
            } else if (lastMsg && lastMsg.role === "assistant" && lastMsg.content === BOT_GREETING.content) {
              newMessages.push({ role: "assistant", content: data.token });
            } else if (lastMsg && lastMsg.role === "assistant") {
              lastMsg.content += data.token;
            } else {
              newMessages.push({ role: "assistant", content: data.token });
            }
            return newMessages;
          });

        } else if (data.type === "end") {
          clearLongWaitTimer();
          const elapsed = ((performance.now() - requestStartRef.current) / 1000).toFixed(2);
          console.log(`[CHATBOT] Backend response complete (${elapsed}s)`);
          console.log(`[PERFORMANCE] Total response time: ${elapsed} seconds`);
          console.log("[CHATBOT] Rendering bot response");
          setIsReceiving(false);

        } else if (data.type === "error") {
          clearLongWaitTimer();
          setIsReceiving(false);
          console.error("[CHATBOT] WebSocket Error:", data.error);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `**Error:** ${data.error}` },
          ]);
        }
      };

      socket.onclose = () => {
        console.log("[CHATBOT] WebSocket disconnected, reconnecting in 2s...");
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWebSocket, 2000);
      };

      socket.onerror = (err) => {
        console.error("[CHATBOT] WebSocket error event:", err);
      };
    };

    connectWebSocket();

    return () => {
      clearTimeout(reconnectTimer);
      clearLongWaitTimer();
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, waitingLong]);

  const handleSend = () => {
    if (!input.trim() || !ws.current) return;

    if (ws.current.readyState !== WebSocket.OPEN) {
      console.warn("[CHATBOT] WebSocket not open, cannot send.");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "**System:** Backend disconnected. Attempting to reconnect..." },
      ]);
      return;
    }

    const userMessage = input.trim();
    console.log(`[CHATBOT] User message sent: "${userMessage}"`);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    setIsReceiving(true);

    // Start timer
    requestStartRef.current = performance.now();
    console.log("[CHATBOT] Sending request to backend...");

    // Start long-wait indicator after 5 seconds
    clearLongWaitTimer();
    longWaitTimerRef.current = setTimeout(() => {
      console.log("[CHATBOT] Response taking long — showing generating indicator");
      setWaitingLong(true);
    }, 5000);

    ws.current.send(
      JSON.stringify({
        session_id: sessionId,
        message: userMessage,
      })
    );
  };

  const handleReset = () => {
    console.log("[CHATBOT] Session reset — inserting greeting.");
    clearLongWaitTimer();
    setSessionId(null);
    setMessages([BOT_GREETING]);
    setInput("");
    setIsReceiving(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-1 flex-col h-screen bg-background relative selection:bg-primary/20">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 glass-header z-10 sticky top-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary shadow-sm">
            <UtensilsCrossed className="h-5 w-5 text-white" strokeWidth={2} />
          </div>
          <div>
            <span className="font-heading text-lg font-bold text-foreground block leading-tight">La Bella Tavola</span>
            <span className="text-xs font-medium text-primary uppercase tracking-wider">Reservations</span>
          </div>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-secondary text-secondary-foreground hover:bg-zinc-200 transition-colors shadow-sm border border-black/5"
          title="Reset Conversation"
        >
          <RotateCcw className="h-4 w-4" />
          New Session
        </button>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-4 pb-32 pt-8 overflow-x-hidden">
        <div className="mx-auto max-w-3xl space-y-8">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex w-full animate-in fade-in slide-in-from-bottom-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mr-3 mt-1">
                  <ChefHat className="h-4 w-4 text-primary" />
                </div>
              )}

              <div
                className={`rounded-2xl px-5 py-3.5 max-w-[80%] shadow-sm overflow-hidden min-w-[3rem] ${msg.role === "user"
                  ? "bg-primary text-primary-foreground ml-12 rounded-tr-sm"
                  : "bg-white border border-border text-foreground mr-12 rounded-tl-sm"
                  }`}
              >
                {msg.role === "user" ? (
                  <div className="whitespace-pre-wrap font-medium break-words">{msg.content}</div>
                ) : (
                  <div className="prose prose-sm md:prose-base dark:prose-invert max-w-none text-foreground leading-relaxed break-words overflow-x-auto w-full max-w-full [&_pre]:max-w-full">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing indicator — bouncing dots while waiting for first token */}
          {isReceiving && messages.length > 0 && messages[messages.length - 1].role === "user" && (
            <div className="flex w-full animate-in fade-in slide-in-from-bottom-2 justify-start">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mr-3 mt-1">
                <ChefHat className="h-4 w-4 text-primary" />
              </div>
              <div className="rounded-2xl px-5 py-4 max-w-[80%] bg-white border border-border shadow-sm flex items-center gap-2 rounded-tl-sm">
                <span className="w-2 h-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: "0ms" }}></span>
                <span className="w-2 h-2 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: "150ms" }}></span>
                <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "300ms" }}></span>
                {waitingLong && (
                  <span className="ml-2 text-xs text-muted-foreground animate-pulse">
                    Generating response, please wait…
                  </span>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      {/* Input Form */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background/95 to-transparent pt-12 pb-8 px-4">
        <div className="mx-auto max-w-3xl">
          <div className="relative flex items-center rounded-2xl border-2 border-border/80 bg-white px-3 py-2 shadow-soft focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10 transition-all duration-300">
            <div className="p-2 ml-1 text-muted-foreground mr-1">
              <MessageSquare className="h-5 w-5" strokeWidth={1.5} />
            </div>
            <input
              type="text"
              placeholder="E.g., I want a table for 4 at 8 PM..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isReceiving}
              className="flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground/70 outline-none disabled:opacity-50 py-2"
              autoFocus
            />
            <div className="flex items-center gap-2 ml-2">
              <button
                onClick={handleSend}
                disabled={!input.trim() || isReceiving}
                className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-white transition-all duration-200 hover:opacity-90 disabled:opacity-50 disabled:bg-muted-foreground shadow-sm shadow-primary/30"
              >
                <Send className="h-5 w-5 ml-0.5" strokeWidth={2} />
              </button>
            </div>
          </div>
          <div className="text-center mt-3 text-xs text-muted-foreground font-medium flex items-center justify-center gap-1.5 opacity-80">
            <ChefHat className="h-3 w-3" />
            La Bella Tavola Virtual Host — Powered by Fully Local AI
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMain;
