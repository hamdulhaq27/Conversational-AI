export type WebSocketCallback = {
    onSession: (sessionId: string) => void;
    onToken: (token: string) => void;
    onEnd: () => void;
    onError: (error: string) => void;
    onAudioResponse: (base64: string) => void;
    onTranscription: (text: string) => void;
    onTranscriptionPartial?: (text: string) => void;
};

export class WebSocketService {
    private ws: WebSocket | null = null;
    private url: string;
    private callbacks: WebSocketCallback;
    private reconnectTimer: NodeJS.Timeout | null = null;

    constructor(url: string, callbacks: WebSocketCallback) {
        this.url = url;
        this.callbacks = callbacks;
    }

    connect() {
        console.log("[CHATBOT] Connecting to WebSocket:", this.url);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log("[CHATBOT] WebSocket connection opened.");
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case "session":
                    this.callbacks.onSession(data.session_id);
                    break;
                case "token":
                    this.callbacks.onToken(data.token);
                    break;
                case "end":
                    this.callbacks.onEnd();
                    break;
                case "error":
                    this.callbacks.onError(data.error || data.message || "Unknown error");
                    break;
                case "audio_response":
                    this.callbacks.onAudioResponse(data.audio_base64);
                    break;
                case "transcription":
                    this.callbacks.onTranscription(data.text);
                    break;
                case "transcription_partial":
                    this.callbacks.onTranscriptionPartial?.(data.text);
                    break;
                default:
                    console.warn("[CHATBOT] Unknown message type:", data.type);
            }
        };

        this.ws.onclose = () => {
            console.log("[CHATBOT] WebSocket disconnected, reconnecting in 2s...");
            this.reconnectTimer = setTimeout(() => this.connect(), 2000);
        };

        this.ws.onerror = (err) => {
            console.error("[CHATBOT] WebSocket error event:", err);
        };
    }

    isOpen(): boolean {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }

    sendText(sessionId: string | null, message: string) {
        if (!this.isOpen()) return false;
        this.ws!.send(JSON.stringify({ type: "text", session_id: sessionId, message }));
        return true;
    }

    sendAudio(sessionId: string | null, base64Audio: string) {
        if (!this.isOpen()) return false;
        this.ws!.send(JSON.stringify({ type: "audio", session_id: sessionId, audio_base64: base64Audio }));
        return true;
    }

    sendAudioPartial(sessionId: string | null, base64Audio: string) {
        if (!this.isOpen()) return false;
        this.ws!.send(JSON.stringify({ type: "audio_partial", session_id: sessionId, audio_base64: base64Audio }));
        return true;
    }

    disconnect() {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        if (this.ws) {
            this.ws.onclose = null; // prevent auto-reconnect
            this.ws.close();
            this.ws = null;
        }
    }
}
