"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import { onAuthStateChanged, signInAnonymously } from "firebase/auth";
import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDocs,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
} from "firebase/firestore";
import Avatar from "./components/Avatar";
import Chat from "./components/Chat";
import { auth, db, isFirebaseConfigured } from "@/lib/firebase";

interface ChatHistory {
  id: string;
  title: string;
  timestamp: Date | null;
}

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [micTrigger, setMicTrigger] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSecs, setRecordingSecs] = useState(0);
  const [voiceInput, setVoiceInput] = useState<string | null>(null);

  const formatTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  const [aiAudioUrl, setAIAudioUrl] = useState<string | null>(null);
  const [currentEmotion, setCurrentEmotion] = useState<"Normal" | "Talking" | "Curious">("Normal");
  const [chatHistories, setChatHistories] = useState<ChatHistory[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const isSigningInRef = useRef(false);

  const formatChatTimestamp = (timestamp: Date | null) => {
    if (!timestamp) return "New chat";

    return timestamp.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

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

  useEffect(() => {
    const firebaseAuth = auth;

    if (!firebaseAuth) {
      setUserId(null);
      return;
    }

    const unsubscribe = onAuthStateChanged(firebaseAuth, async (currentUser) => {
      if (currentUser) {
        isSigningInRef.current = false;
        setUserId(currentUser.uid);
        return;
      }

      if (isSigningInRef.current) {
        return;
      }

      isSigningInRef.current = true;

      try {
        const credential = await signInAnonymously(firebaseAuth);
        setUserId(credential.user.uid);
      } catch (error) {
        console.error("Error signing in anonymously:", error);
      } finally {
        isSigningInRef.current = false;
      }
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const firestore = db;

    if (!firestore || !userId) return;

    const q = query(
      collection(firestore, "users", userId, "chats"),
      orderBy("timestamp", "desc")
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const histories: ChatHistory[] = snapshot.docs.map((chatDoc) => {
        const data = chatDoc.data();
        const rawTimestamp = data.timestamp;

        return {
          id: chatDoc.id,
          title: typeof data.title === "string" && data.title.trim().length > 0 ? data.title : "New Chat",
          timestamp: rawTimestamp && typeof rawTimestamp.toDate === "function" ? rawTimestamp.toDate() : null,
        };
      });

      setChatHistories(histories);
    });

    return () => unsubscribe();
  }, [userId]);

const handleNewChat = useCallback(async () => {
    const firestore = db;

    if (!firestore || !userId) return null;

    const docRef = await addDoc(collection(firestore, "users", userId, "chats"), {
      title: "New Chat",
      timestamp: serverTimestamp(),
    });

    // Reset memory ฝั่ง backend ทุกครั้งที่เปิด New Chat
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/reset`, {
        method: "POST",
      });
    } catch (err) {
      console.warn("[NewChat] ไม่สามารถ reset memory ได้:", err);
    }

    setCurrentChatId(docRef.id);
    setIsSidebarOpen(false);
    return docRef.id;
  }, [userId]);

  const loadChat = (chatId: string) => {
    setCurrentChatId(chatId);
    setIsSidebarOpen(false);
  };

  const deleteChat = async (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const firestore = db;

    if (!firestore || !userId) return;

    try {
      const messagesSnapshot = await getDocs(
        collection(firestore, "users", userId, "chats", chatId, "messages")
      );

      await Promise.all(messagesSnapshot.docs.map((messageDoc) => deleteDoc(messageDoc.ref)));
      await deleteDoc(doc(firestore, "users", userId, "chats", chatId));

      if (currentChatId === chatId) {
        setCurrentChatId(null);
      }
    } catch (error) {
      console.error("Error deleting chat:", error);
    }
  };

  const handleVoiceInput = useCallback((text: string) => {
    setVoiceInput(text);
    setTimeout(() => {
      setVoiceInput(null);
    }, 200);
  }, []);

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden md:flex-row">
      {/* Full Page Background */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/bg aida6.png"
          alt="Background"
          fill
          className="object-cover object-bottom"
          priority
        />
      </div>

      {/* Sidebar Overlay */}
      {isSidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* Sidebar — Dreamy Glass */}
      <div
        ref={sidebarRef}
        className={`fixed left-0 top-0 z-50 flex h-full w-72 flex-col transform backdrop-blur-2xl transition-transform duration-300 ease-in-out ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{
          background: "rgba(175, 145, 225, 0.72)",
          borderRight: "1px solid rgba(255,255,255,0.30)",
          boxShadow: "4px 0 32px rgba(100,60,180,0.25), inset -1px 0 0 rgba(255,255,255,0.15)",
        }}
      >
        {/* Sidebar header */}
        <div
          className="flex shrink-0 items-center gap-3 px-5 py-4"
          style={{
            background: "rgba(120, 80, 185, 0.65)",
            borderBottom: "1px solid rgba(255,255,255,0.18)",
          }}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
            className="h-4 w-4 text-pink-200">
            <path fillRule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clipRule="evenodd" />
          </svg>
          <span className="flex-1 text-sm font-semibold tracking-widest text-white/95"
            style={{ textShadow: "0 1px 8px rgba(100,50,160,0.5)" }}>
            Chat History
          </span>
        </div>

        {/* New Chat button */}
        <div className="shrink-0 px-4 py-3"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
          <button
            onClick={() => void handleNewChat()}
            disabled={!isFirebaseConfigured || !userId}
            className="flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-medium text-white transition-all hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: "rgba(155, 110, 215, 0.55)",
              border: "1px solid rgba(255,255,255,0.30)",
              boxShadow: "0 2px 16px rgba(120,70,200,0.30)",
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
              strokeWidth={2} stroke="currentColor" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto px-3 py-2 kawaii-scroll">
          <p className="px-2 py-2 text-xs tracking-widest text-white/50">
            {!isFirebaseConfigured
              ? "✦ firebase config missing"
              : userId ? "✦ recent chats" : "✦ connecting..."}
          </p>

          {chatHistories.map((chat) => (
            <div
              key={chat.id}
              onClick={() => loadChat(chat.id)}
              className="flex w-full cursor-pointer items-center gap-3 rounded-2xl px-3 py-2.5 mb-1 text-left transition-all hover:scale-[1.01]"
              style={
                currentChatId === chat.id
                  ? {
                      background: "rgba(255,255,255,0.55)",
                      border: "1px solid rgba(255,255,255,0.75)",
                      boxShadow: "0 4px 16px rgba(100,50,180,0.25)",
                    }
                  : {
                      background: "rgba(255,255,255,0.20)",
                      border: "1px solid rgba(255,255,255,0.35)",
                    }
              }
            >
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm text-white/80"
                style={{
                  background: "rgba(180, 140, 230, 0.50)",
                  border: "1px solid rgba(255,255,255,0.25)",
                }}
              >
                ✦
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-white/90">{chat.title}</p>
                <p className="truncate text-[11px] text-white/45">{formatChatTimestamp(chat.timestamp)}</p>
              </div>
              <button
                onClick={(e) => void deleteChat(chat.id, e)}
                className="shrink-0 rounded-lg p-1 text-white/30 transition-colors hover:text-red-300"
                title="Delete chat"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                  strokeWidth={1.5} stroke="currentColor" className="h-4 w-4">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className="fixed left-4 top-4 z-30 flex h-12 w-12 items-center justify-center rounded-2xl backdrop-blur-md transition-all hover:scale-110 hover:brightness-110 active:scale-95"
        style={{
          background: "linear-gradient(135deg, rgba(190,140,255,0.65), rgba(150,95,235,0.55))",
          border: "1.5px solid rgba(210,175,255,0.65)",
          boxShadow: "0 0 20px rgba(155,90,240,0.50), 0 4px 16px rgba(120,65,210,0.35), inset 0 1px 0 rgba(255,255,255,0.55)",
        }}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="#d8b4fe"
          className="h-7 w-7"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      {/* Mic overlay — bubble + clickable area */}
      <div className="absolute z-20" style={{ left: "59%", bottom: "8%", width: "7%", height: "32%" }}>
        <div
          className="absolute -top-20 left-[calc(25%+20px)] -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full whitespace-nowrap text-[11px] font-medium text-white backdrop-blur-md pointer-events-none bubble-breathe"
          style={{
            background: "rgba(255,255,255,0.18)",
            border: "1px solid rgba(255,255,255,0.40)",
          }}
        >
          {isRecording ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-pink-300 animate-pulse" />
              {formatTime(recordingSecs)}
            </>
          ) : (
            "Tap the mic to speak"
          )}
        </div>
        <button
          className="w-full h-full cursor-pointer rounded-2xl"
          style={{ background: "transparent" }}
          onClick={() => setMicTrigger((n) => n + 1)}
        />
      </div>

      <div className="relative z-10 h-1/3 w-full md:h-full md:w-[55%]">
        <Avatar
          onVoiceInput={handleVoiceInput}
          aiAudioUrl={aiAudioUrl}
          emotion={currentEmotion}
          triggerMic={micTrigger}
          onRecordingChange={(rec, secs) => { setIsRecording(rec); setRecordingSecs(secs); }}
        />
      </div>

      <div className="relative z-10 h-2/3 w-full p-2 md:h-full md:w-[45%] md:p-6">
        <Chat
          userId={userId}
          chatId={currentChatId}
          onCreateNewChat={handleNewChat}
          voiceInput={voiceInput}
          onAIAudio={setAIAudioUrl}
          onAIEmotion={setCurrentEmotion}
          isFirebaseReady={isFirebaseConfigured && Boolean(db)}
        />
      </div>
    </div>
  );
}