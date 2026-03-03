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
  voiceInput?: string | null;
  onAISpeak?: (text: string) => void; // เพิ่ม Prop สำหรับส่งข้อความไปให้ระบบเสียง
}

export default function Chat({ 
  chatId, 
  initialMessages = [], 
  onMessagesUpdate, 
  onCreateNewChat, 
  voiceInput,
  onAISpeak
}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 });
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const initialMessageCountRef = useRef(initialMessages.length);
  const processedVoiceInputRef = useRef<string>("");

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

  useEffect(() => {
    if (!voiceInput || !voiceInput.trim()) return;
    if (processedVoiceInputRef.current === voiceInput) return;
    
    processedVoiceInputRef.current = voiceInput;
    const userText = voiceInput.trim();
    
    let activeChatId = chatId;
    if (activeChatId === null && onCreateNewChat) {
      activeChatId = onCreateNewChat();
    }
    
    if (activeChatId === null) return;

    const newMessage: Message = {
      id: Date.now(),
      text: userText,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);

    // สร้างฟังก์ชันสำหรับยิง API เมื่อได้รับเสียง
    const fetchAIResponseForVoice = async () => {
      try {
        const response = await fetch("http://localhost:8000/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: userText })
        });
        
        const data = await response.json();
        const aiText = data.answer;
        
        const aiResponse: Message = {
          id: Date.now() + 1,
          text: aiText,
          sender: "ai",
          timestamp: new Date(),
        };
        
        setMessages((prev) => [...prev, aiResponse]);
        onAISpeak?.(aiText); // ส่งข้อความไปให้ไอด้าพูด

      } catch (error) {
        console.error("API Error:", error);
      }
    };

    fetchAIResponseForVoice();
  }, [voiceInput, chatId, onCreateNewChat, onAISpeak]);

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
    if (inputValue.trim() === "") return;

    let activeChatId = chatId;
    if (activeChatId === null && onCreateNewChat) {
      activeChatId = onCreateNewChat();
    }
    
    if (activeChatId === null) return;

    const userText = inputValue.trim();
    const newUserMessage: Message = {
      id: Date.now(),
      text: userText,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue("");

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userText })
      });
      
      const data = await response.json();
      const aiText = data.answer;
      
      const aiResponse: Message = {
        id: Date.now() + 1,
        text: aiText,
        sender: "ai",
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, aiResponse]);
      
      onAISpeak?.(aiText);
      
    } catch (error) {
      console.error("API Error:", error);
    }
  }, [inputValue, chatId, onCreateNewChat, onAISpeak]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSendMessage();
    }
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
            <div className="flex items-center gap-2">
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
          </div>
        </div>
      </div>
    </div>
  );
}
