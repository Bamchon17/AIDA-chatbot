"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { EmotionType } from "@/lib/live2d/live2dmanager";

interface AvatarProps {
  onVoiceInput?: (text: string) => void;
  aiAudioUrl?: string | null;
  emotion?: EmotionType;
  triggerMic?: number;
  onRecordingChange?: (isRecording: boolean, seconds: number) => void;
}

export default function Avatar({
  onVoiceInput,
  aiAudioUrl,
  emotion,
  triggerMic,
  onRecordingChange,
}: AvatarProps) {
  // ─── Live2D ───────────────────────────────────────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const managerRef = useRef<import("@/lib/live2d/live2dmanager").Live2DManager | null>(null);
  const live2dLoadedRef = useRef(false);

  const latestEmotionRef = useRef<EmotionType | undefined>(emotion);
  useEffect(() => {
    latestEmotionRef.current = emotion;
  }, [emotion]);

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

  useEffect(() => {
    if (triggerMic === undefined || triggerMic === 0) return;
    handleMicrophoneClick();
  }, [triggerMic]);


  const [isRecordingMode, setIsRecordingMode] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const aiAudioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptRef = useRef<string>("");

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
      stopTimer();
    };

    recognition.onend = () => {
      stopTimer();
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const stopRecording = () => {
    if (recognitionRef.current) recognitionRef.current.stop();
    setIsRecordingMode(false);
    stopTimer();
    setRecordingTime(0);

    if (transcriptRef.current.trim() && onVoiceInput) {
      onVoiceInput(transcriptRef.current.trim());
    }
    transcriptRef.current = "";
  };

  useEffect(() => {
    onRecordingChange?.(isRecordingMode, recordingTime);
  }, [isRecordingMode, recordingTime, onRecordingChange]);

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

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const normalizedUrl = aiAudioUrl.startsWith("http")
      ? aiAudioUrl
      : `${apiUrl}${aiAudioUrl.startsWith("/") ? "" : "/"}${aiAudioUrl}`;

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

    audio.addEventListener("loadedmetadata", () => {
      const durationMs = (audio.duration || 5) * 1000 + 500;
      fallbackTimerRef.current = setTimeout(revertToIdle, durationMs);
    });

    audio.addEventListener("play", () => {
      const currentEm = latestEmotionRef.current;
      if (currentEm && currentEm !== "Normal") {
        managerRef.current?.setEmotion(currentEm);
      } else {
        managerRef.current?.setEmotion("Talking");
      }
    });

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
      <div
        className="relative z-10 flex items-center justify-center w-full h-full max-h-[60vh] md:max-h-[90vh]"
        style={{ transform: "translateX(140px) translateY(-95px)" }}
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{ display: "block" }}
        />
      </div>
    </div>
  );
}