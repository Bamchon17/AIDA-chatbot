"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { EmotionType } from "@/lib/live2d/live2dmanager";

interface AvatarProps {
  onVoiceInput?: (text: string) => void;
  aiAudioUrl?: string | null;
  emotion?: EmotionType;
}

export default function Avatar({
  onVoiceInput,
  aiAudioUrl,
  emotion,
}: AvatarProps) {
  // ─── Live2D ───────────────────────────────────────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const managerRef = useRef<import("@/lib/live2d/live2dmanager").Live2DManager | null>(null);
  const live2dLoadedRef = useRef(false);

  const initLive2D = useCallback(async () => {
    if (live2dLoadedRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const { Live2DManager } = await import("@/lib/live2d/live2dmanager");
    const manager = new Live2DManager();
    managerRef.current = manager;
    live2dLoadedRef.current = true;

    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;

    const ok = await manager.initialize(canvas);
    if (!ok) console.error("[Avatar] Failed to initialize Live2D");
  }, []);

  useEffect(() => {
    initLive2D();
    return () => {
      managerRef.current?.release();
      managerRef.current = null;
      live2dLoadedRef.current = false;
    };
  }, [initLive2D]);

  // Curious ให้ backend control, Talking/Normal ให้ audio control
  useEffect(() => {
    if (emotion === "Curious") {
      managerRef.current?.setEmotion("Curious");
      const t = setTimeout(() => managerRef.current?.stopMotion(), 4000);
      return () => clearTimeout(t);
    }
  }, [emotion]);

  // ─── Voice input ──────────────────────────────────────────────────────────
  const [isListening, setIsListening] = useState(false);
  const [isRecordingMode, setIsRecordingMode] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const aiAudioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptRef = useRef<string>("");

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const startTimer = () => {
    setRecordingTime(0);
    timerRef.current = setInterval(() => {
      setRecordingTime((prev) => prev + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleMicrophoneClick = () => {
    if (isRecordingMode) {
      stopRecording();
    } else {
      setIsRecordingMode(true);
      transcriptRef.current = "";
      startRecording();
    }
  };

  const startRecording = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in your browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "th-TH";

    recognition.onstart = () => {
      setIsListening(true);
      startTimer();
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interimTranscript = "";
      let finalTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        transcriptRef.current += finalTranscript;
      }
      if (!finalTranscript && interimTranscript) {
        transcriptRef.current = interimTranscript;
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error("Speech recognition error:", event.error);
      setIsListening(false);
      stopTimer();
    };

    recognition.onend = () => {
      setIsListening(false);
      stopTimer();
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const stopRecording = () => {
    if (recognitionRef.current) recognitionRef.current.stop();
    setIsListening(false);
    setIsRecordingMode(false);
    stopTimer();
    setRecordingTime(0);

    if (transcriptRef.current.trim() && onVoiceInput) {
      onVoiceInput(transcriptRef.current.trim());
    }
    transcriptRef.current = "";
  };

  // ─── AI audio — sync animation กับเสียง ──────────────────────────────────
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const revertToIdle = useCallback(() => {
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    managerRef.current?.stopMotion();
  }, []);

  useEffect(() => {
    if (!aiAudioUrl) return;

    const normalizedUrl = aiAudioUrl.startsWith("http")
      ? aiAudioUrl
      : `http://localhost:8000${aiAudioUrl}`;

    if (aiAudioRef.current) {
      aiAudioRef.current.pause();
      aiAudioRef.current.currentTime = 0;
      aiAudioRef.current = null;
    }
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }

    const audio = new Audio(normalizedUrl);
    aiAudioRef.current = audio;

    // รู้ duration แล้ว → ตั้ง fallback timer เผื่อ onended ไม่ fire
    audio.addEventListener("loadedmetadata", () => {
      const durationMs = (audio.duration || 5) * 1000 + 500;
      fallbackTimerRef.current = setTimeout(revertToIdle, durationMs);
    });

    // เสียงเริ่มเล่น → Talking
    audio.addEventListener("play", () => {
      managerRef.current?.setEmotion("Talking");
    });

    // เสียงจบ → Normal (primary handler)
    audio.addEventListener("ended", revertToIdle);
    audio.addEventListener("error", revertToIdle);

    audio.play().catch((err) => {
      console.error("Failed to play AI audio:", err);
      revertToIdle();
    });

    return () => {
      audio.pause();
      audio.currentTime = 0;
      revertToIdle();
    };
  }, [aiAudioUrl, revertToIdle]);

  // ─── Cleanup ──────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      aiAudioRef.current?.pause();
      aiAudioRef.current = null;
      if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
      recognitionRef.current?.stop();
      stopTimer();
    };
  }, []);

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="relative flex h-full w-full items-center justify-center md:justify-end overflow-hidden">
      {/* Live2D Canvas */}
      <div className="relative z-10 flex items-center justify-center md:translate-x-35 translate-y-3 w-full h-full max-h-[30vh] md:max-h-[80vh]">
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{ display: "block" }}
        />
      </div>

      {/* Microphone Button */}
      <div className="absolute bottom-16 left-8 z-20">
        {isRecordingMode && (
          <div
            className="absolute -top-11 left-1/2 -translate-x-1/2 px-3 py-1 rounded-lg whitespace-nowrap text-xs font-semibold text-white backdrop-blur-md"
            style={{
              background: "rgba(255,255,255,0.2)",
              border: "1px solid rgba(255,255,255,0.4)",
              boxShadow: "0 2px 12px rgba(160,100,220,0.3)",
            }}
          >
            ● {formatTime(recordingTime)}
          </div>
        )}

        <button
          onClick={handleMicrophoneClick}
          className="relative flex h-20 w-20 items-center justify-center rounded-3xl backdrop-blur-md transition-all hover:scale-105 active:scale-95"
          style={
            isListening
              ? {
                  background: "rgba(255,160,200,0.35)",
                  border: "1.5px solid rgba(255,200,230,0.6)",
                  boxShadow: "0 0 32px rgba(255,120,180,0.65), 0 4px 20px rgba(200,80,140,0.3), inset 0 1px 0 rgba(255,255,255,0.5)",
                }
              : {
                  background: "rgba(220,180,255,0.28)",
                  border: "1.5px solid rgba(200,160,240,0.55)",
                  boxShadow: "0 4px 24px rgba(160,100,220,0.4), inset 0 1px 0 rgba(255,255,255,0.45)",
                }
          }
          title={isListening ? "Stop recording" : "Start voice recording"}
        >
          {isListening && (
            <div className="absolute inset-0 rounded-3xl animate-pulse" style={{ background: "rgba(255,150,200,0.2)" }} />
          )}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="#d8b4fe"
            className="h-10 w-10 relative z-10"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
