"use client";

import Image from "next/image";
import { useState, useRef, useEffect } from "react";

interface AvatarProps {
  avatarSrc?: string;
  onVoiceInput?: (text: string) => void;
}

export default function Avatar({ 
  avatarSrc = "/AIDA.png",
  onVoiceInput
}: AvatarProps) {
  const [isListening, setIsListening] = useState(false);
  const [isRecordingMode, setIsRecordingMode] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptRef = useRef<string>("");

  // Format recording time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Start recording timer
  const startTimer = () => {
    setRecordingTime(0);
    timerRef.current = setInterval(() => {
      setRecordingTime(prev => prev + 1);
    }, 1000);
  };

  // Stop recording timer
  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleMicrophoneClick = () => {
    if (isRecordingMode) {
      // Stop recording
      stopRecording();
    } else {
      // Start recording
      setIsRecordingMode(true);
      transcriptRef.current = "";
      startRecording();
    }
  };

  const startRecording = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in your browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'th-TH';

    recognition.onstart = () => {
      setIsListening(true);
      startTimer();
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interimTranscript = '';
      let finalTranscript = '';

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
      
      // Update with interim transcript if no final yet
      if (!finalTranscript && interimTranscript) {
        transcriptRef.current = interimTranscript;
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('Speech recognition error:', event.error);
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
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setIsListening(false);
    setIsRecordingMode(false);
    stopTimer();
    setRecordingTime(0);
    
    // Send transcribed text to parent component
    if (transcriptRef.current.trim() && onVoiceInput) {
      onVoiceInput(transcriptRef.current.trim());
    }
    transcriptRef.current = "";
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      stopTimer();
    };
  }, []);

  return (
    <div className="relative flex h-full w-full items-center justify-center md:justify-end overflow-hidden">
      {/* Avatar PNG */}
      <div className="relative z-10 flex items-center justify-center md:translate-x-35 translate-y-3">
        <Image
          src={avatarSrc}
          alt="Virtual AI Avatar"
          width={800}
          height={1000}
          
          className="object-contain max-h-[30vh] md:max-h-[80vh]"
          priority
          onError={(e) => {
            e.currentTarget.style.display = 'none';
          }}
        />
      </div>

      {/* Microphone Button - Bottom Left Corner */}
      <div className="absolute bottom-16 left-8 z-20">
        <button
          onClick={handleMicrophoneClick}
          className={`relative flex h-20 w-20 items-center justify-center rounded-full text-white shadow-2xl transition-all hover:scale-110 active:scale-95 ${
            isListening ? 'bg-red-500 animate-pulse' : 'bg-[#b57edc] hover:bg-[#a060c8]'
          }`}
          title={isListening ? "Stop recording" : "Start voice recording"}
        >
          {/* Pulsing rings when listening */}
          {isListening && (
            <>
              <div className="absolute w-28 h-28 rounded-full bg-[#b57edc]/20 animate-ping"></div>
              <div className="absolute w-24 h-24 rounded-full bg-[#b57edc]/30 animate-pulse"></div>
            </>
          )}
          
          {/* Microphone Icon */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="h-10 w-10 relative z-10"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
            />
          </svg>
        </button>

        {/* Recording Timer Display */}
        {isRecordingMode && (
          <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-lg shadow-lg">
            <div className="text-lg font-mono text-zinc-700 whitespace-nowrap">
              {formatTime(recordingTime)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
