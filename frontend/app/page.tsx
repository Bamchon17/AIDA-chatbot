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
  const [voiceInput, setVoiceInput] = useState<string | null>(null);
  const [aiAudioUrl, setAIAudioUrl] = useState<string | null>(null);
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
          src="/bg aida5.png"
          alt="Background"
          fill
          className="object-cover"
          priority
        />
      </div>

      {/* Sidebar Overlay */}
      {isSidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <div
        ref={sidebarRef}
        className={`fixed left-0 top-0 z-50 h-full w-72 transform rounded-r-2xl bg-[#e0dbf4] transition-transform duration-300 ease-in-out ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="border-b border-zinc-700 p-4">
          <button
            onClick={() => void handleNewChat()}
            disabled={!isFirebaseConfigured || !userId}
            className="flex w-full items-center gap-3 rounded-lg border border-zinc-600 px-4 py-3 text-black transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="h-5 w-5"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <p className="px-3 py-2 text-xs text-zinc-500">
            {!isFirebaseConfigured
              ? "Firebase config missing or invalid"
              : userId
                ? "Recent Chats"
                : "Connecting to Firebase..."}
          </p>
          {chatHistories.map((chat) => (
            <div
              key={chat.id}
              onClick={() => loadChat(chat.id)}
              className={`flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors hover:bg-white ${
                currentChatId === chat.id ? "bg-white/50" : ""
              }`}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#b57edc]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="h-4 w-4 text-white"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                  />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-black">{chat.title}</p>
                <p className="truncate text-xs text-zinc-500">{formatChatTimestamp(chat.timestamp)}</p>
              </div>
              <button
                onClick={(e) => void deleteChat(chat.id, e)}
                className="rounded p-1 text-zinc-400 transition-colors hover:bg-red-100 hover:text-red-500"
                title="Delete chat"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="h-4 w-4"
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

      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className="fixed left-4 top-4 z-30 flex h-10 w-10 items-center justify-center rounded-full bg-[#b57edc] text-white shadow-lg transition-colors hover:bg-[#a060c8]"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className="h-5 w-5"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      <div className="relative z-10 h-1/3 w-full md:h-full md:w-1/2">
        <Avatar onVoiceInput={handleVoiceInput} aiAudioUrl={aiAudioUrl} />
      </div>

      <div className="relative z-10 h-2/3 w-full p-2 md:h-full md:w-1/2 md:p-6">
        <Chat
          userId={userId}
          chatId={currentChatId}
          onCreateNewChat={handleNewChat}
          voiceInput={voiceInput}
          onAIAudio={setAIAudioUrl}
          isFirebaseReady={isFirebaseConfigured && Boolean(db)}
        />
      </div>
    </div>
  );
}