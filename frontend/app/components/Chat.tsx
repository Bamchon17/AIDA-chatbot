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
  onAISpeak?: (text: string) => void;
  onAIAudio?: (audioUrl: string | null) => void;
  isFirebaseReady?: boolean;
}

export default function Chat({ 
  userId,
  chatId, 
  onCreateNewChat,
  voiceInput,
  onAISpeak,
  onAIAudio,
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

  const requestAIResponse = useCallback(async (text: string) => {
    const response = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text })
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    return response.json() as Promise<{ answer?: string; audio_url?: string | null }>;
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
      const data = await requestAIResponse(userText);
      const aiText = data.answer ?? "";
      const aiAudioUrl = data.audio_url ?? null;

      if (aiText) {
        await persistMessage(activeChatId, aiText, "ai");
      }

      onAISpeak?.(aiText);
      onAIAudio?.(aiAudioUrl);
    } catch (error) {
      console.error("API Error:", error);
    }
  }, [ensureChatId, isFirebaseReady, messages.length, onAISpeak, onAIAudio, persistMessage, requestAIResponse, updateChatTitle]);

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
      {/* Browser Mockup Container - Draggable on desktop */}
      <div 
        ref={chatRef}
        className="absolute flex h-[95%] w-[95%] flex-col overflow-hidden rounded-2xl border-2 border-[#ac88c4] shadow-[0_25px_60px_-12px_rgba(0,0,0,0.5)] md:h-[90%] md:w-[60%]"
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
          className="flex items-center gap-2 bg-[#ac88c4] px-4 py-3 select-none cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
        >
          {/* Window Title */}
          <div className="flex-1 text-center">
            <span className="text-sm font-medium text-white">Chat with Aida</span>
          </div>
          {/* Close Button */}
          <button 
            className="text-white transition-colors hover:text-zinc-200"
            onClick={(e) => e.stopPropagation()}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="h-5 w-5"
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
        <div className="flex min-h-0 flex-1 flex-col bg-white/80 backdrop-blur-sm">
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {!isFirebaseReady || !userId || chatId === null ? (
              <div className="flex h-full items-center justify-center text-zinc-400">
                <p>
                  {!isFirebaseReady
                    ? "Firebase is not configured"
                    : userId
                      ? "Select a chat or start a new conversation"
                      : "Connecting to Firebase..."}
                </p>
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
                    <span className="mt-1 block text-xs opacity-70">
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

          <div className="border-t border-[#b57edc]/30 bg-white/50 p-4">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Type your message..."
                className="flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-zinc-800 placeholder-zinc-400 focus:border-[#b57edc] focus:outline-none focus:ring-1 focus:ring-[#b57edc]"
              />

              <button
                onClick={() => void handleSendMessage()}
                disabled={inputValue.trim() === ""}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-[#b57edc] text-white transition-colors hover:bg-[#a060c8] disabled:cursor-not-allowed disabled:opacity-50"
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
          </div>
        </div>
      </div>
    </div>
  );
}