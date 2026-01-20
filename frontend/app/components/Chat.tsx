"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface Message {
  id: number;
  text: string;
  sender: "user" | "ai";
  timestamp: Date;
}

interface Position {
  x: number;
  y: number;
}

interface ChatProps {
  chatId: number | null;
  initialMessages?: Message[];
  onMessagesUpdate?: (messages: Message[]) => void;
  onCreateNewChat?: () => number;
}

export default function Chat({ chatId, initialMessages = [], onMessagesUpdate, onCreateNewChat }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isRecordingMode, setIsRecordingMode] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const initialMessageCountRef = useRef(initialMessages.length);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Notify parent only when NEW messages are added (not on initial load)
  useEffect(() => {
    if (messages.length > initialMessageCountRef.current) {
      onMessagesUpdate?.(messages);
      initialMessageCountRef.current = messages.length;
    }
  }, [messages, onMessagesUpdate]);

  // Handle mouse move for dragging
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !containerRef.current || !chatRef.current) return;
    
    const containerRect = containerRef.current.getBoundingClientRect();
    const chatRect = chatRef.current.getBoundingClientRect();
    
    // Calculate new position relative to container
    let newX = e.clientX - containerRect.left - dragOffset.x;
    let newY = e.clientY - containerRect.top - dragOffset.y;
    
    // Limit to container bounds
    newX = Math.max(0, Math.min(newX, containerRect.width - chatRect.width));
    newY = Math.max(0, Math.min(newY, containerRect.height - chatRect.height));
    
    setPosition({ x: newX, y: newY });
  }, [isDragging, dragOffset]);

  // Handle mouse up to stop dragging
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add and remove event listeners for dragging
  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }
    
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Handle mouse down on title bar to start dragging
  const handleMouseDown = (e: React.MouseEvent) => {
    if (chatRef.current) {
      const rect = chatRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
      
      // If first drag, set initial position from current location
      if (position === null && containerRef.current) {
        const containerRect = containerRef.current.getBoundingClientRect();
        setPosition({
          x: rect.left - containerRect.left,
          y: rect.top - containerRect.top,
        });
      }
      
      setIsDragging(true);
    }
  };

  // AI Response templates
  const AI_RESPONSES = {
    greeting: "สวัสดีค่า ไอด้านะคะ ยินดีที่ได้รู้จัก ไอด้าเป็นผู้ช่วยตอบคำถามสำหรับคณะวิศวกรรมศาสตร์ สาขาปัญญาประดิษฐ์และวิทยาการข้อมูลค่ะ มีอะไรอยากสอบถามไหมคะ?",
    aboutMajor: "สาขาเราคือ AI และ Data Science ย่อมาจาก Artificial Intelligence and Data Science ค่ะ",
    cannotAnswer: "เรื่องนี้ไอด้าไม่สามารถให้ข้อมูลได้จริงๆค่ะ ขอโทษนะคะ",
  };

  // Simple keyword matching for responses
  const getAIResponse = (userMessage: string): string => {
    const lowerMessage = userMessage.toLowerCase();
    
    // Check for greetings
    if (lowerMessage.includes("สวัสดี") || lowerMessage.includes("hello") || lowerMessage.includes("hi") || lowerMessage.includes("หวัดดี")) {
      return AI_RESPONSES.greeting;
    }
    
    // Check for questions about the major
    if (lowerMessage.includes("สาขา") || lowerMessage.includes("ai") || lowerMessage.includes("data science") || lowerMessage.includes("เรียน")) {
      return AI_RESPONSES.aboutMajor;
    }
    
    // Default greeting for first message
    return AI_RESPONSES.greeting;
  };

  const handleSendMessage = () => {
    if (inputValue.trim() === "") return;

    // Create new chat if none exists
    let activeChatId = chatId;
    if (activeChatId === null && onCreateNewChat) {
      activeChatId = onCreateNewChat();
    }
    
    if (activeChatId === null) return;

    const newMessage: Message = {
      id: Date.now(),
      text: inputValue.trim(),
      sender: "user",
      timestamp: new Date(),
    };

    const userText = inputValue.trim();
    setMessages((prev) => [...prev, newMessage]);
    setInputValue("");

    // AI response based on user message
    setTimeout(() => {
      const aiResponse: Message = {
        id: Date.now() + 1,
        text: getAIResponse(userText),
        sender: "ai",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiResponse]);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSendMessage();
    }
  };

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
    // Enter recording mode but don't start recording yet
    setIsRecordingMode(true);
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
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
      startTimer();
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      setInputValue(prev => prev + finalTranscript);
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
  };

  const cancelRecording = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setIsListening(false);
    setIsRecordingMode(false);
    stopTimer();
    setRecordingTime(0);
    setInputValue("");
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {/* Browser Mockup Container - Draggable on desktop */}
      <div 
        ref={chatRef}
        className="absolute flex h-[95%] md:h-[90%] w-[95%] md:w-[60%] flex-col rounded-2xl border-2 border-[#ac88c4] overflow-hidden shadow-[0_25px_60px_-12px_rgba(0,0,0,0.5)]"
        style={position === null ? {
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
        } : {
          left: position.x,
          top: position.y,
          cursor: isDragging ? 'grabbing' : 'default',
        }}
      >
        {/* Browser Top Bar - Drag Handle */}
        <div 
          className="bg-[#ac88c4] px-4 py-3 flex items-center gap-2 cursor-grab active:cursor-grabbing select-none"
          onMouseDown={handleMouseDown}
        >
          {/* Window Title */}
          <div className="flex-1 text-center">
            <span className="text-white text-sm font-medium">Chat with Aida</span>
          </div>
          {/* Close Button */}
          <button 
            className="text-white hover:text-zinc-200 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Chat Content Area - Glass Effect */}
        <div className="flex-1 flex flex-col bg-white/80 backdrop-blur-sm">
          
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatId === null ? (
              <div className="flex h-full items-center justify-center text-zinc-400">
                <p>Select a chat or start a new conversation</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full items-center justify-center text-zinc-400">
                <p>Start a conversation...</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 ${
                      message.sender === "user"
                        ? "bg-[#b57edc] text-white"
                        : "bg-zinc-100 text-zinc-800"
                    }`}
                  >
                    <p className="text-sm">{message.text}</p>
                    <span className="text-xs opacity-70 mt-1 block">
                      {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Container */}
          <div className="border-t border-[#b57edc]/30 p-4 bg-white/50">
            {isRecordingMode ? (
              /* Voice Recording Interface */
              <div className="flex flex-col items-center justify-center py-4 space-y-4">
                {/* Recording Timer */}
                <div className="text-2xl font-mono text-zinc-700">
                  {formatTime(recordingTime)}
                </div>

                {/* Animated Circle / Waveform Visual */}
                <div className="relative flex items-center justify-center">
                  {/* Outer pulsing rings */}
                  <div className={`absolute w-32 h-32 rounded-full bg-[#b57edc]/20 ${isListening ? 'animate-ping' : ''}`}></div>
                  <div className={`absolute w-24 h-24 rounded-full bg-[#b57edc]/30 ${isListening ? 'animate-pulse' : ''}`}></div>
                  
                  {/* Large Mic Button - Click to start/stop recording */}
                  <button
                    onClick={isListening ? stopRecording : startRecording}
                    className={`relative z-10 flex h-20 w-20 items-center justify-center rounded-full text-white shadow-lg transition-transform hover:scale-105 active:scale-95 ${
                      isListening ? 'bg-red-500' : 'bg-[#b57edc]'
                    }`}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      className="h-10 w-10"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
                      />
                    </svg>
                  </button>
                </div>

                {/* Status Text */}
                <p className="text-sm text-zinc-500">
                  {isListening ? "Listening... Tap to stop" : "Tap the mic to start recording"}
                </p>

                {/* Transcribed Text Preview */}
                {inputValue && (
                  <div className="w-full max-w-xs px-4 py-2 bg-zinc-100 rounded-lg text-sm text-zinc-700 text-center truncate">
                    {inputValue}
                  </div>
                )}
              </div>
            ) : (
              /* Normal Text Input Interface */
              <div className="flex items-center gap-2">
                {/* Microphone Button */}
                <button
                  onClick={handleMicrophoneClick}
                  className="relative flex h-10 w-10 items-center justify-center rounded-full bg-[#b57edc] text-white transition-all hover:bg-[#a060c8]"
                  title="Start voice recording"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
                    />
                  </svg>
                </button>

                {/* Text Input */}
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  className="flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-zinc-800 placeholder-zinc-400 focus:border-[#b57edc] focus:outline-none focus:ring-1 focus:ring-[#b57edc]"
                />

                {/* Send Button */}
                <button
                  onClick={handleSendMessage}
                  disabled={inputValue.trim() === ""}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-[#b57edc] text-white transition-colors hover:bg-[#a060c8] disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Send message"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                    />
                  </svg>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
