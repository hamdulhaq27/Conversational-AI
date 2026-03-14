import { ChefHat, Volume2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface Message {
    role: "user" | "assistant";
    content: string;
    audioBase64?: string;
}

export const MessageBubble = ({ message, isReceiving, isLastAssistanceMsg, waitingLong }: {
    message: Message,
    isReceiving?: boolean,
    isLastAssistanceMsg?: boolean,
    waitingLong?: boolean
}) => {
    const isUser = message.role === "user";

    const playAudio = () => {
        if (!message.audioBase64) return;
        try {
            const byteCharacters = atob(message.audioBase64);
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
    };

    return (
        <div className={`flex w-full animate-in fade-in slide-in-from-bottom-2 ${isUser ? "justify-end" : "justify-start"}`}>
            {!isUser && (
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mr-3 mt-1">
                    <ChefHat className="h-4 w-4 text-primary" />
                </div>
            )}

            <div
                className={`rounded-2xl px-5 py-3.5 max-w-[80%] shadow-sm overflow-hidden min-w-[3rem] flex flex-col gap-2 ${isUser
                    ? "bg-primary text-primary-foreground ml-12 rounded-tr-sm"
                    : "bg-white border border-border text-foreground mr-12 rounded-tl-sm"
                    }`}
            >
                {isUser ? (
                    <div className="whitespace-pre-wrap font-medium break-words">{message.content}</div>
                ) : (
                    <div className="prose prose-sm md:prose-base dark:prose-invert max-w-none text-foreground leading-relaxed break-words overflow-x-auto w-full max-w-full [&_pre]:max-w-full">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                )}
                {!isUser && message.audioBase64 && (
                    <button
                        onClick={playAudio}
                        className="self-start flex items-center gap-1.5 text-xs font-medium text-primary bg-primary/10 hover:bg-primary/20 px-2.5 py-1.5 rounded-md transition-colors w-fit border border-primary/20 mt-1"
                        title="Play audio response"
                        type="button"
                    >
                        <Volume2 className="h-3.5 w-3.5" />
                        Play Audio
                    </button>
                )}
            </div>
        </div>
    );
};

export const TypingIndicator = ({ waitingLong }: { waitingLong: boolean }) => (
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
);
