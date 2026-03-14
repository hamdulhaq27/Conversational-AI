import { Send, RotateCcw, UtensilsCrossed, ChefHat, MessageSquare } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { WebSocketService } from "../services/websocket";
import { MessageBubble, TypingIndicator } from "./MessageBubble";
import { MicrophoneButton } from "./MicrophoneButton";

interface Message {
    role: "user" | "assistant";
    content: string;
    audioBase64?: string;
}

const BOT_GREETING: Message = {
    role: "assistant",
    content: "Hello! I'm the virtual assistant for La Bella Tavola 🍝.\nI can help you with reservations, opening hours, menu questions, and more.\nHow may I assist you today?",
};

export const ChatWindow = () => {
    const [messages, setMessages] = useState<Message[]>([BOT_GREETING]);
    const [input, setInput] = useState("");
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isReceiving, setIsReceiving] = useState(false);
    const [waitingLong, setWaitingLong] = useState(false);
    const [isRecording, setIsRecording] = useState(false);

    const wsService = useRef<WebSocketService | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const requestStartRef = useRef<number>(0);
    const longWaitTimerRef = useRef<NodeJS.Timeout | null>(null);

    const clearLongWaitTimer = () => {
        if (longWaitTimerRef.current) {
            clearTimeout(longWaitTimerRef.current);
            longWaitTimerRef.current = null;
        }
        setWaitingLong(false);
    };

    useEffect(() => {
        const wsUrl = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/chat";

        wsService.current = new WebSocketService(wsUrl, {
            onSession: (sid) => setSessionId(sid),
            onToken: (token) => {
                clearLongWaitTimer();
                setIsReceiving(true);
                setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMsg = newMessages[newMessages.length - 1];
                    if (lastMsg && lastMsg.role === "assistant" && lastMsg.content !== BOT_GREETING.content) {
                        lastMsg.content += token;
                    } else {
                        newMessages.push({ role: "assistant", content: token });
                    }
                    return newMessages;
                });
            },
            onEnd: () => {
                clearLongWaitTimer();
                setIsReceiving(false);
            },
            onError: (error) => {
                clearLongWaitTimer();
                setIsReceiving(false);
                setMessages((prev) => [...prev, { role: "assistant", content: `**Error:** ${error}` }]);
            },
            onAudioResponse: (base64) => {
                setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMsgIdx = newMessages.length - 1;
                    if (newMessages[lastMsgIdx]?.role === "assistant") {
                        newMessages[lastMsgIdx] = { ...newMessages[lastMsgIdx], audioBase64: base64 };
                    }
                    return newMessages;
                });

                try {
                    const byteCharacters = atob(base64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const blob = new Blob([new Uint8Array(byteNumbers)], { type: "audio/wav" });
                    const url = URL.createObjectURL(blob);
                    new Audio(url).play().catch(e => console.error("Audio playback error:", e));
                } catch (e) {
                    console.error("Audio decode error:", e);
                }
            },
            onTranscription: (text) => {
                setMessages((prev) => {
                    const newMessages = [...prev];
                    for (let i = newMessages.length - 1; i >= 0; i--) {
                        if (newMessages[i].role === "user" && newMessages[i].content.startsWith("🎙️")) {
                            newMessages[i] = { ...newMessages[i], content: `🎙️ ${text}` };
                            break;
                        }
                    }
                    return newMessages;
                });
            },
            onTranscriptionPartial: (text) => {
                setMessages((prev) => {
                    const newMessages = [...prev];
                    for (let i = newMessages.length - 1; i >= 0; i--) {
                        if (newMessages[i].role === "user" && newMessages[i].content.startsWith("🎙️")) {
                            newMessages[i] = { ...newMessages[i], content: `🎙️ ${text}...` };
                            break;
                        }
                    }
                    return newMessages;
                });
            }
        });

        wsService.current.connect();

        return () => {
            clearLongWaitTimer();
            wsService.current?.disconnect();
        };
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, waitingLong]);

    const handleSendText = () => {
        if (!input.trim() || !wsService.current?.isOpen()) return;

        const userMessage = input.trim();
        setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
        setInput("");
        setIsReceiving(true);

        requestStartRef.current = performance.now();
        clearLongWaitTimer();
        longWaitTimerRef.current = setTimeout(() => setWaitingLong(true), 5000);

        wsService.current.sendText(sessionId, userMessage);
    };

    const handleAudioReady = (base64Audio: string, isPartial?: boolean) => {
        if (!wsService.current?.isOpen()) return;

        setMessages((prev) => {
            const hasVoicePlaceholder = prev.some(m => m.role === "user" && m.content.startsWith("🎙️"));
            if (!hasVoicePlaceholder) {
                return [...prev, { role: "user", content: "🎙️ (Listening...)" }];
            }
            return prev;
        });

        if (!isPartial) {
            setIsReceiving(true);
            requestStartRef.current = performance.now();
            clearLongWaitTimer();
            longWaitTimerRef.current = setTimeout(() => setWaitingLong(true), 5000);
            wsService.current.sendAudio(sessionId, base64Audio);
        } else {
            wsService.current.sendAudioPartial(sessionId, base64Audio);
        }
    };

    const handleReset = () => {
        clearLongWaitTimer();
        setSessionId(null);
        setMessages([BOT_GREETING]);
        setInput("");
        setIsReceiving(false);

        // Disconnect and reconnect to force new session
        if (wsService.current) {
            wsService.current.disconnect();
            setTimeout(() => wsService.current?.connect(), 100);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendText();
        }
    };

    return (
        <div className="flex flex-1 flex-col h-screen bg-background relative selection:bg-primary/20">
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
                    New Chat
                </button>
            </header>

            <div className="flex-1 overflow-y-auto px-4 pb-32 pt-8 overflow-x-hidden">
                <div className="mx-auto max-w-3xl space-y-8">
                    {messages.map((msg, i) => (
                        <MessageBubble key={i} message={msg} />
                    ))}
                    {isReceiving && messages.length > 0 && messages[messages.length - 1].role === "user" && (
                        <TypingIndicator waitingLong={waitingLong} />
                    )}
                    <div ref={messagesEndRef} className="h-4" />
                </div>
            </div>

            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background/95 to-transparent pt-12 pb-8 px-4">
                <div className="mx-auto max-w-3xl">
                    <div className="relative flex items-center rounded-2xl border-2 border-border/80 bg-white px-3 py-2 shadow-soft focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10 transition-all duration-300">
                        <div className="p-2 ml-1 text-muted-foreground mr-1">
                            <MessageSquare className="h-5 w-5" strokeWidth={1.5} />
                        </div>
                        <input
                            type="text"
                            placeholder={isRecording ? "Listening... Speak now 🎙️" : "E.g., I want a table for 4 at 8 PM..."}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={isReceiving || isRecording}
                            className="flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground/70 outline-none disabled:opacity-50 py-2"
                            autoFocus
                        />
                        <div className="flex items-center gap-2 ml-2">
                            <MicrophoneButton
                                onAudioReady={handleAudioReady}
                                isReceiving={isReceiving}
                                onRecordingStateChange={setIsRecording}
                                onError={(err) => setMessages(prev => [...prev, { role: "assistant", content: err }])}
                            />
                            <button
                                onClick={handleSendText}
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
