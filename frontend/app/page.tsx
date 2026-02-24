"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import Avatar from "./components/Avatar";
import Chat from "./components/Chat";

interface Message {
  id: number;
  text: string;
  sender: "user" | "ai";
  timestamp: Date;
}

interface ChatHistory {
  id: number;
  title: string;
  messages: Message[];
  timestamp: Date;
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [voiceInput, setVoiceInput] = useState<string | null>(null);
  const [chatHistories, setChatHistories] = useState<ChatHistory[]>([
    { 
      id: 1, 
      title: "Previous Chat 1", 
      messages: [
        { id: 1, text: "Hello!", sender: "user", timestamp: new Date(Date.now() - 86400000) },
        { id: 2, text: "Hello! I'm your Virtual AI assistant. How can I help you today?", sender: "ai", timestamp: new Date(Date.now() - 86400000) },
      ],
      timestamp: new Date(Date.now() - 86400000) 
    },
    { 
      id: 2, 
      title: "Previous Chat 2", 
      messages: [
        { id: 1, text: "What can you do?", sender: "user", timestamp: new Date(Date.now() - 172800000) },
        { id: 2, text: "I can help you with many things! Feel free to ask me anything.", sender: "ai", timestamp: new Date(Date.now() - 172800000) },
      ],
      timestamp: new Date(Date.now() - 172800000) 
    },
  ]);
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Close sidebar when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (isSidebarOpen && sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        setIsSidebarOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSidebarOpen]);

  const handleNewChat = () => {
    const newChatId = Date.now();
    const newChat: ChatHistory = {
      id: newChatId,
      title: `New Chat`,
      messages: [],
      timestamp: new Date(),
    };
    setChatHistories(prev => [newChat, ...prev]);
    setCurrentChatId(newChatId);
    setIsSidebarOpen(false);
    return newChatId;
  };

  const createNewChatAndReturn = useCallback(() => {
    const newChatId = Date.now();
    const newChat: ChatHistory = {
      id: newChatId,
      title: `New Chat`,
      messages: [],
      timestamp: new Date(),
    };
    setChatHistories(prev => [newChat, ...prev]);
    setCurrentChatId(newChatId);
    return newChatId;
  }, []);

  const loadChat = (chatId: number) => {
    setCurrentChatId(chatId);
    setIsSidebarOpen(false);
  };

  const deleteChat = (chatId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setChatHistories(prev => prev.filter(chat => chat.id !== chatId));
    if (currentChatId === chatId) {
      setCurrentChatId(null);
    }
  };

  const updateChatMessages = useCallback((chatId: number, messages: Message[]) => {
    setChatHistories(prev => prev.map(chat => {
      if (chat.id === chatId) {
        return {
          ...chat,
          messages,
          title: messages.length > 0 ? messages[0].text.slice(0, 30) + (messages[0].text.length > 30 ? '...' : '') : 'New Chat',
        };
      }
      return chat;
    }));
  }, []);

  const currentChat = chatHistories.find(chat => chat.id === currentChatId);
  const getLastMessage = (chat: ChatHistory) => {
    if (chat.messages.length === 0) return "No messages yet";
    return chat.messages[chat.messages.length - 1].text;
  };

  // Handle voice input from Avatar
  const handleVoiceInput = useCallback((text: string) => {
    setVoiceInput(text);
    // Reset voice input after a short delay to allow Chat component to process it
    setTimeout(() => {
      setVoiceInput(null);
    }, 200);
  }, []);

  return (
    <div className="relative flex flex-col md:flex-row h-screen w-screen overflow-hidden">
      {/* Full Page Background */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/bg aida5.png"
          alt="Background"
          fill
          className="object-cover"
          priority
        />
      </div>

      {/* Sidebar Overlay */}
      {isSidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <div
        ref={sidebarRef}
        className={`fixed top-0 left-0 h-full w-72 bg-[#e0dbf4] z-50 transform transition-transform duration-300 ease-in-out rounded-r-2xl ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-zinc-700">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-zinc-600 text-black hover:bg-white transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto p-2">
          <p className="text-xs text-zinc-500 px-3 py-2">Recent Chats</p>
          {chatHistories.map((chat) => (
            <div
              key={chat.id}
              onClick={() => loadChat(chat.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left hover:bg-white transition-colors cursor-pointer ${
                currentChatId === chat.id ? 'bg-white/50' : ''
              }`}
            >
              {/* Avatar Icon */}
              <div className="w-8 h-8 rounded-full bg-[#b57edc] flex items-center justify-center shrink-0">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-4 h-4 text-white"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                  />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-black truncate">{chat.title}</p>
                <p className="text-xs text-zinc-500 truncate">{getLastMessage(chat)}</p>
              </div>
              {/* Delete Button */}
              <button
                onClick={(e) => deleteChat(chat.id, e)}
                className="p-1 rounded hover:bg-red-100 text-zinc-400 hover:text-red-500 transition-colors"
                title="Delete chat"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-4 h-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Hamburger Menu Button - Fixed on left side */}
      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className="fixed top-4 left-4 z-30 flex h-10 w-10 items-center justify-center rounded-full bg-[#b57edc] text-white hover:bg-[#a060c8] transition-colors shadow-lg"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className="w-5 h-5"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      {/* Left Side - Avatar Section */}
      <div className="relative z-10 w-full md:w-1/2 h-1/3 md:h-full">
        <Avatar onVoiceInput={handleVoiceInput} />
      </div>

      {/* Right Side - Chat Section */}
      <div className="relative z-10 w-full md:w-1/2 h-2/3 md:h-full p-2 md:p-6">
        <Chat 
          key={currentChatId}
          chatId={currentChatId}
          initialMessages={currentChat?.messages || []}
          onMessagesUpdate={(messages) => currentChatId && updateChatMessages(currentChatId, messages)}
          onCreateNewChat={createNewChatAndReturn}
          voiceInput={voiceInput}
        />
      </div>
    </div>
  );
}
