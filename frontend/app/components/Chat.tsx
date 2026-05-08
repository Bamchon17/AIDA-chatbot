"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { addDoc, collection, doc, onSnapshot, orderBy, query, serverTimestamp, updateDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";

interface Message {
  id: string;
  text: string;
  sender: "user" | "ai";
  timestamp: Date;
}

interface Position {
  x: number;
  y: number;
}

interface ChatProps {
  userId: string | null;
  chatId: string | null;
  onCreateNewChat?: () => Promise<string | null>;
  voiceInput?: string | null;
  onMicClick?: () => void;
  isRecording?: boolean;
  recordingSecs?: number;
  onAISpeak?: (text: string) => void;
  onAIAudio?: (audioUrl: string | null) => void;
  onAIEmotion?: (emotion: "Normal" | "Talking" | "Curious") => void;
  isFirebaseReady?: boolean;
}

export default function Chat({
  userId,
  chatId,
  onCreateNewChat,
  voiceInput,
  onMicClick,
  isRecording = false,
  recordingSecs = 0,
  onAISpeak,
  onAIAudio,
  onAIEmotion,
  isFirebaseReady = true,
}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 });
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const processedVoiceInputRef = useRef<string>("");
  const formatRecordingTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  useEffect(() => {
    setInputValue("");
  }, [chatId]);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const firestore = db;

    if (!isFirebaseReady || !firestore || !userId || !chatId) {
      setMessages([]);
      return;
    }

    const q = query(
      collection(firestore, "users", userId, "chats", chatId, "messages"),
      orderBy("timestamp", "asc")
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const nextMessages: Message[] = snapshot.docs.map((messageDoc) => {
        const data = messageDoc.data();
        const rawTimestamp = data.timestamp;

        return {
          id: messageDoc.id,
          text: typeof data.text === "string" ? data.text : "",
          sender: data.sender === "ai" ? "ai" : "user",
          timestamp: rawTimestamp && typeof rawTimestamp.toDate === "function" ? rawTimestamp.toDate() : new Date(),
        };
      });

      setMessages(nextMessages);
    });

    return () => unsubscribe();
  }, [chatId, isFirebaseReady, userId]);

  const ensureChatId = useCallback(async () => {
    if (chatId) {
      return chatId;
    }

    if (!onCreateNewChat) {
      return null;
    }

    return onCreateNewChat();
  }, [chatId, onCreateNewChat]);

  const updateChatTitle = useCallback(async (activeChatId: string, firstMessage: string) => {
    const firestore = db;

    if (!isFirebaseReady || !firestore || !userId) return;

    const title = firstMessage.slice(0, 30) + (firstMessage.length > 30 ? "..." : "");
    await updateDoc(doc(firestore, "users", userId, "chats", activeChatId), {
      title,
    });
  }, [isFirebaseReady, userId]);

  const persistMessage = useCallback(async (activeChatId: string, text: string, sender: "user" | "ai") => {
    const firestore = db;

    if (!isFirebaseReady || !firestore || !userId) return;

    await addDoc(collection(firestore, "users", userId, "chats", activeChatId, "messages"), {
      text,
      sender,
      timestamp: serverTimestamp(),
    });
  }, [isFirebaseReady, userId]);
  // --- MOCKUP: ลบออกหลัง screenshot เสร็จ ---
  const GREETING_PATTERNS = /สวัสดี|หวัดดี|ดีค่ะ|ดีครับ|hello|hi\b/i;
  const FOOD_PATTERNS = /ทานอะไร|กินอะไร|อาหาร|ข้าว|หิว/i;

  const getMockResponse = useCallback((text: string): { answer: string; audio_url: null; emotion: "Normal" | "Talking" | "Curious" } | null => {
    if (GREETING_PATTERNS.test(text)) {
      return {
        answer: "สวัสดีค่ะ Aida เป็นผู้ช่วยเสมือนซึ่งจะช่วยตอบคำถามเกี่ยวกับสาขาวิศวกรรมปัญญาประดิษฐ์และวิทยาการข้อมูล มีอะไรให้ช่วยไหมคะ",
        audio_url: null,
        emotion: "Talking",
      };
    }
    if (FOOD_PATTERNS.test(text)) {
      return {
        answer: "ขออภัยค่ะ ไม่สามารถตอบคำถามได้ เนื่องจากไม่เกี่ยวกับวิชาของสาขา กรุณาถามใหม่นะคะ",
        audio_url: null,
        emotion: "Curious",
      };
    }
    return null;
  }, []);
  // --- END MOCKUP ---

  //fetch ส่งไปให้ backend
  const requestAIResponse = useCallback(async (text: string) => {
    const response = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text })
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json() as Promise<{ answer?: string; audio_url?: string | null; emotion?: string }>;
  }, []);

  const sendMessage = useCallback(async (messageText: string) => {
    const userText = messageText.trim();

    if (userText === "") return;
    if (!isFirebaseReady) return;

    const activeChatId = await ensureChatId();
    if (!activeChatId) return;

    const shouldUpdateTitle = messages.length === 0;

    setInputValue("");
    await persistMessage(activeChatId, userText, "user");

    if (shouldUpdateTitle) {
      await updateChatTitle(activeChatId, userText);
    }

    try {
      const mock = getMockResponse(userText);
      const data = mock ?? await requestAIResponse(userText);
      const aiText = data.answer ?? "";
      const aiAudioUrl = data.audio_url ?? null;
      const aiEmotion = (data.emotion ?? "Normal") as "Normal" | "Talking" | "Curious";

      if (aiText) {
        await persistMessage(activeChatId, aiText, "ai");
      }

      onAISpeak?.(aiText);
      onAIAudio?.(aiAudioUrl);
      onAIEmotion?.(aiEmotion);
    } catch (error) {
      console.error("API Error:", error);
    }
  }, [ensureChatId, getMockResponse, isFirebaseReady, messages.length, onAISpeak, onAIAudio, onAIEmotion, persistMessage, requestAIResponse, updateChatTitle]);

  // Handle mouse move for dragging
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !containerRef.current || !chatRef.current) return;
    
    const containerRect = containerRef.current.getBoundingClientRect();
    const chatRect = chatRef.current.getBoundingClientRect();
    
    let newX = e.clientX - containerRect.left - dragOffset.x;
    let newY = e.clientY - containerRect.top - dragOffset.y;
    
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

  const handleSendMessage = useCallback(async () => {
    await sendMessage(inputValue);
  }, [inputValue, sendMessage]);

  useEffect(() => {
    if (!voiceInput || !voiceInput.trim()) return;
    if (processedVoiceInputRef.current === voiceInput) return;

    processedVoiceInputRef.current = voiceInput;
    void sendMessage(voiceInput);
  }, [voiceInput, sendMessage]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      void handleSendMessage();
    }
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {/* Chat Window — Dreamy Glass */}
      <div
        ref={chatRef}
        className="absolute flex h-[95%] w-[95%] flex-col overflow-hidden backdrop-blur-2xl md:h-[90%] md:w-[62%]"
        style={{
          ...(position === null
            ? { right: 0, top: "50%", transform: "translateY(-50%)" }
            : { left: position.x, top: position.y, cursor: isDragging ? "grabbing" : "default" }),
          background: "rgba(215, 190, 255, 0.45)",
          border: "1px solid rgba(220, 190, 255, 0.55)",
          boxShadow: "0 8px 48px rgba(120, 60, 220, 0.35), 0 0 0 1px rgba(200,160,255,0.25), inset 0 1px 0 rgba(255,255,255,0.65)",
          borderRadius: "24px",
        }}
      >
        {/* ── Title Bar ── */}
        <div
          className="flex shrink-0 items-center gap-3 px-5 py-3 select-none cursor-grab active:cursor-grabbing"
          style={{
            background: "linear-gradient(135deg, rgba(165, 105, 245, 0.80), rgba(125, 75, 210, 0.75))",
            borderBottom: "1px solid rgba(220,190,255,0.30)",
          }}
          onMouseDown={handleMouseDown}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
            className="h-4 w-4 text-pink-200">
            <path fillRule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clipRule="evenodd" />
          </svg>
          <span className="flex-1 text-sm font-semibold tracking-widest text-white/95"
            style={{ textShadow: "0 1px 8px rgba(120,60,180,0.5)" }}>
            Chat with Aida
          </span>
          {/* window dots */}
          <div className="flex gap-1.5">
            {[
              "rgba(255,200,200,0.7)",
              "rgba(255,230,150,0.7)",
              "rgba(180,255,180,0.7)",
            ].map((color, i) => (
              <button
                key={i}
                onClick={(e) => e.stopPropagation()}
                className="h-3 w-3 rounded-full transition-all hover:scale-110"
                style={{ background: color, border: "1px solid rgba(255,255,255,0.4)" }}
              />
            ))}
          </div>
        </div>

        {/* ── Messages area ── */}
        <div
          className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3 kawaii-scroll"
          style={{ background: "transparent" }}
        >
          {!isFirebaseReady || !userId || chatId === null ? (
            <div className="flex h-full items-center justify-center">
              <div className="rounded-2xl px-6 py-4 text-sm text-purple-200 text-center"
                style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)" }}>
                ✦{" "}
                {!isFirebaseReady
                  ? "Firebase is not configured"
                  : userId
                    ? "Select a chat or start a new conversation"
                    : "Connecting..."}
                {" "}✦
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="rounded-2xl px-6 py-4 text-sm text-purple-200 text-center"
                style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)" }}>
                ✦ Start a conversation... ✦
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex items-end gap-2 ${message.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                {message.sender === "ai" && (
                  <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-xs mb-0.5"
                    style={{ background: "rgba(200,160,255,0.45)", border: "1px solid rgba(255,255,255,0.3)" }}>
                    ✦
                  </div>
                )}
                <div
                  className="max-w-[75%] px-4 py-2.5"
                  style={
                    message.sender === "user"
                      ? {
                          background: "linear-gradient(135deg, rgba(155, 90, 240, 0.88), rgba(115, 55, 200, 0.82))",
                          border: "1px solid rgba(210,175,255,0.45)",
                          backdropFilter: "blur(16px)",
                          color: "#fff",
                          borderRadius: "18px 18px 4px 18px",
                          boxShadow: "0 4px 20px rgba(120,55,210,0.40)",
                        }
                      : {
                          background: "rgba(255, 255, 255, 0.82)",
                          border: "1px solid rgba(220,200,255,0.60)",
                          backdropFilter: "blur(16px)",
                          color: "#2d1555",
                          borderRadius: "18px 18px 18px 4px",
                          boxShadow: "0 4px 20px rgba(160,120,220,0.20)",
                        }
                  }
                >
                  <p className="text-sm leading-relaxed">{message.text}</p>
                  <span className="mt-1 block text-right text-[10px] opacity-50">
                    {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* ── Input area ── */}
        <div
          className="shrink-0 px-4 py-3"
          style={{
            background: "rgba(140, 100, 215, 0.42)",
            borderTop: "1px solid rgba(220,190,255,0.30)",
          }}
        >
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="✦  say something..."
              className="flex-1 rounded-2xl px-4 py-2.5 text-sm text-purple-900 focus:outline-none"
              style={{
                background: "rgba(255, 255, 255, 0.72)",
                border: "1px solid rgba(200,170,255,0.55)",
                backdropFilter: "blur(16px)",
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.8)",
              }}
              onFocus={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.90)";
                e.currentTarget.style.boxShadow = "0 0 0 2px rgba(170,110,255,0.45), inset 0 1px 0 rgba(255,255,255,0.9)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.72)";
                e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.8)";
              }}
            />
            <button
              onClick={onMicClick}
              disabled={!onMicClick}
              className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-white transition-all hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: isRecording
                  ? "linear-gradient(135deg, rgba(255, 115, 180, 0.95), rgba(190, 70, 220, 0.88))"
                  : "rgba(255,255,255,0.18)",
                border: "1px solid rgba(230,205,255,0.55)",
                boxShadow: isRecording
                  ? "0 4px 18px rgba(220,70,190,0.42)"
                  : "0 2px 14px rgba(120,70,200,0.24)",
              }}
              title={isRecording ? `Stop recording ${formatRecordingTime(recordingSecs)}` : "Start voice input"}
            >
              {isRecording && (
                <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-pink-200 animate-pulse" />
              )}
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                strokeWidth={2} stroke="currentColor" className="h-5 w-5">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M12 18.75a6 6 0 006-6v-1.5m-12 0v1.5a6 6 0 006 6m0 0v3m-3 0h6M12 15.75a3 3 0 003-3v-6a3 3 0 10-6 0v6a3 3 0 003 3z" />
              </svg>
            </button>
            <button
              onClick={() => void handleSendMessage()}
              disabled={inputValue.trim() === ""}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-white text-base transition-all hover:scale-105 active:scale-95 disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, rgba(175, 105, 255, 0.92), rgba(125, 60, 225, 0.88))",
                border: "1px solid rgba(210,175,255,0.50)",
                boxShadow: "0 4px 20px rgba(140,70,230,0.55)",
              }}
              title="Send message"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                strokeWidth={2} stroke="currentColor" className="h-5 w-5">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
