import { Mic, Square } from "lucide-react";
import { useState, useRef } from "react";

interface MicrophoneButtonProps {
    onAudioReady: (base64Audio: string, isPartial?: boolean) => void;
    isReceiving: boolean;
    onRecordingStateChange: (isRecording: boolean) => void;
    onError: (msg: string) => void;
}

export const MicrophoneButton = ({ onAudioReady, isReceiving, onRecordingStateChange, onError }: MicrophoneButtonProps) => {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);

    const handleStartRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);

                    // Progressive transcription emit
                    if (mediaRecorder.state === "recording") {
                        const partialBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
                        const reader = new FileReader();
                        reader.readAsDataURL(partialBlob);
                        reader.onloadend = () => {
                            const base64data = reader.result as string;
                            const base64Audio = base64data.split(",")[1];
                            onAudioReady(base64Audio, true); // true = partial
                        };
                    }
                }
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64data = reader.result as string;
                    const base64Audio = base64data.split(",")[1];
                    onAudioReady(base64Audio, false); // false = definitive
                };

                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start(1000); // Capture chunks every 1000ms
            setIsRecording(true);
            onRecordingStateChange(true);
            console.log("[CHATBOT] Started recording audio...");
        } catch (err) {
            console.error("[CHATBOT] Microphone access denied or unavailable", err);
            onError("🚨 **System Error:** Microphone access denied or unavailable. Please check your browser permissions.");
        }
    };

    const handleStopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
            onRecordingStateChange(false);
            console.log("[CHATBOT] Stopped recording audio.");
        }
    };

    return (
        <button
            onClick={isRecording ? handleStopRecording : handleStartRecording}
            disabled={isReceiving}
            className={`flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200 shadow-sm ${isRecording
                ? "bg-red-500 text-white hover:bg-red-600 animate-pulse"
                : "bg-secondary text-secondary-foreground hover:bg-zinc-200"
                } disabled:opacity-50`}
            title={isRecording ? "Stop Recording" : "Record Voice"}
            type="button"
        >
            {isRecording ? <Square className="h-4 w-4 fill-current" /> : <Mic className="h-5 w-5" />}
        </button>
    );
};
