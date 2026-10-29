import { useState, useEffect, useRef, useCallback } from "react";
import {
  Send,
  RefreshCw,
  Activity,
  Trash2,
  X,
  Minimize2,
  Maximize2,
  Sparkles,
  Radio,
  Image as ImageIcon,
  Video as VideoIcon,
} from "lucide-react";
import { fetchJSON } from "@/lib/api";

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: number;
  media?: string[];
  action_status?: {
    type: "zalo_diagnostic" | "zalo_restart" | "media_generation" | null;
    diagnostic?: {
      bridge?: {
        online?: boolean;
        status?: string;
        own_id?: string;
        queue_len?: number;
      };
      gateway?: {
        running?: boolean;
        pid?: number;
      };
      muse?: {
        online?: boolean;
        accounts_ready?: number;
      };
    };
  } | null;
}

interface OfficeLiveChatProps {
  isOpen: boolean;
  onClose: () => void;
  onOpen: () => void;
}

export function OfficeLiveChat({ isOpen, onClose, onOpen }: OfficeLiveChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isActionRunning, setIsActionRunning] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetchJSON<{ ok: boolean; history: ChatMessage[] }>("/api/office/chat/history");
      if (res?.ok && Array.isArray(res.history)) {
        setMessages(res.history);
      }
    } catch (e) {
      console.error("Failed to load office chat history", e);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, loadHistory]);

  useEffect(() => {
    if (isOpen && !isMinimized) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [messages, isOpen, isMinimized]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isLoading) return;

    if (!textToSend) {
      setInputText("");
    }

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp_${Date.now()}`,
      sender: "user",
      text,
      timestamp: Date.now() / 1000,
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsLoading(true);

    try {
      const res = await fetchJSON<{ ok: boolean; message: ChatMessage; history?: ChatMessage[] }>(
        "/api/office/chat/send",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        }
      );
      if (res?.ok && res.message) {
        setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, res.message]);
      }
    } catch (e) {
      console.error("Failed to send message", e);
      const errMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: "assistant",
        text: "❌ Dạ sếp, có lỗi kết nối khi gửi tin nhắn. Sếp bấm nút chẩn đoán Zalo hoặc thử lại nhé!",
        timestamp: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAction = async (action: string) => {
    if (isActionRunning) return;
    setIsActionRunning(true);
    setIsLoading(true);
    try {
      const res = await fetchJSON<{ ok: boolean; message: ChatMessage; history?: ChatMessage[] }>(
        "/api/office/chat/action",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        }
      );
      if (res?.ok) {
        if (action === "clear_history" && res.history) {
          setMessages(res.history);
        } else if (res.message) {
          setMessages((prev) => [...prev, res.message]);
        }
      }
    } catch (e) {
      console.error("Failed to execute action", e);
    } finally {
      setIsActionRunning(false);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={onOpen}
        className="fixed bottom-6 right-6 z-40 group flex items-center gap-3 px-4 py-3 rounded-2xl bg-gradient-to-r from-sky-600/90 to-indigo-600/90 hover:from-sky-500 hover:to-indigo-500 text-white font-medium text-sm shadow-[0_4px_24px_rgba(14,165,233,0.4)] backdrop-blur-md border border-sky-400/30 transition-all duration-300 hover:scale-105 active:scale-95 cursor-pointer"
      >
        <div className="relative">
          <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center text-lg">🤖</div>
          <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#0f141f] animate-pulse" />
        </div>
        <div className="text-left">
          <div className="flex items-center gap-1.5 leading-none">
            <span className="font-semibold tracking-wide">Trợ Lý Điều Hành</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Online
            </span>
          </div>
          <div className="text-[11px] text-sky-200/80 mt-1 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-amber-300" />
            <span>Chat trực tuyến & Báo lỗi Zalo</span>
          </div>
        </div>
      </button>
    );
  }

  return (
    <div
      className={`fixed right-6 z-50 flex flex-col rounded-2xl border border-sky-500/30 bg-[#0d121d]/95 backdrop-blur-2xl shadow-[0_16px_50px_rgba(0,0,0,0.85),0_0_30px_rgba(56,189,248,0.2)] transition-all duration-300 overflow-hidden ${
        isMinimized
          ? "bottom-6 w-80 h-16"
          : "bottom-6 w-[430px] max-w-[94vw] h-[620px] max-h-[85vh]"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#131b2b] border-b border-sky-500/20 select-none">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-lg shadow-md">
              🤖
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border border-[#0d121d] animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-slate-100">Trợ Lý Điều Hành</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30 font-mono">
                24/7
              </span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              <span>Sẵn sàng xử lý & Fix lỗi Zalo</span>
            </div>
          </div>
        </div>

        {/* Window controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleAction("diagnose_zalo")}
            title="Chẩn đoán Zalo & Muse AI"
            disabled={isLoading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-sky-300 hover:bg-sky-500/10 transition-colors cursor-pointer"
          >
            <Activity className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleAction("restart_zalo")}
            title="Khởi động lại & Khắc phục Zalo"
            disabled={isLoading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-300 hover:bg-emerald-500/10 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${isActionRunning ? "animate-spin text-emerald-400" : ""}`} />
          </button>
          <button
            onClick={() => handleAction("clear_history")}
            title="Xóa lịch sử chat"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            title={isMinimized ? "Phóng to" : "Thu nhỏ"}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
          </button>
          <button
            onClick={onClose}
            title="Đóng chat"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Quick Action Chips */}
          <div className="px-3 py-2 bg-[#0a0e17]/60 border-b border-slate-800/80 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            <button
              onClick={() => handleAction("diagnose_zalo")}
              disabled={isLoading}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 flex items-center gap-1 transition-all cursor-pointer"
            >
              <Activity className="w-3 h-3 text-sky-400" />
              <span>Chẩn đoán Zalo</span>
            </button>
            <button
              onClick={() => handleAction("restart_zalo")}
              disabled={isLoading}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 transition-all cursor-pointer"
            >
              <RefreshCw className="w-3 h-3 text-emerald-400" />
              <span>Sửa & Restart Zalo</span>
            </button>
            <button
              onClick={() => handleAction("test_ping_zalo")}
              disabled={isLoading}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1 transition-all cursor-pointer"
            >
              <Radio className="w-3 h-3 text-purple-400" />
              <span>Test Ping Zalo</span>
            </button>
            <button
              onClick={() => handleSendMessage("Tạo một hình ảnh chú mèo thần tài phong cách 3D isometric")}
              disabled={isLoading}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 transition-all cursor-pointer"
            >
              <ImageIcon className="w-3 h-3 text-amber-400" />
              <span>Tạo ảnh Muse</span>
            </button>
            <button
              onClick={() => handleSendMessage("Tạo một video clip ly cà phê bốc khói buổi sáng")}
              disabled={isLoading}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1 transition-all cursor-pointer"
            >
              <VideoIcon className="w-3 h-3 text-rose-400" />
              <span>Tạo video TVC</span>
            </button>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3 font-sans text-xs">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              return (
                <div key={msg.id} className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
                  {/* Avatar */}
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs shadow-sm ${
                      isUser
                        ? "bg-gradient-to-tr from-blue-600 to-indigo-600 text-white"
                        : "bg-gradient-to-tr from-sky-500 to-emerald-600 text-white"
                    }`}
                  >
                    {isUser ? "👔" : "🤖"}
                  </div>

                  {/* Message Bubble */}
                  <div
                    className={`max-w-[84%] px-3.5 py-2.5 rounded-2xl shadow-md ${
                      isUser
                        ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-tr-xs"
                        : "bg-[#161f30] border border-slate-700/60 text-slate-100 rounded-tl-xs"
                    }`}
                  >
                    {/* Message Header */}
                    <div className="flex items-center justify-between gap-2 mb-1 opacity-70 text-[10px]">
                      <span className="font-semibold">{isUser ? "Chủ Tịch (CEO)" : "Trợ Lý Điều Hành"}</span>
                      <span>
                        {new Date(msg.timestamp * 1000).toLocaleTimeString("vi-VN", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    {/* Text Body */}
                    <div className="whitespace-pre-wrap leading-relaxed select-text text-slate-200">
                      {msg.text}
                    </div>

                    {/* Diagnostic Summary Card if present */}
                    {msg.action_status?.diagnostic && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/50 space-y-1.5 text-[11px]">
                        <div className="flex items-center justify-between text-slate-300">
                          <span>Zalo Bridge (Cổng 3050):</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              msg.action_status.diagnostic.bridge?.online
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            }`}
                          >
                            {msg.action_status.diagnostic.bridge?.status || "OFFLINE"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-slate-300">
                          <span>Hermes Gateway:</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              msg.action_status.diagnostic.gateway?.running
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            }`}
                          >
                            {msg.action_status.diagnostic.gateway?.running ? `PID ${msg.action_status.diagnostic.gateway.pid}` : "OFFLINE"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-slate-300">
                          <span>Máy chủ Muse 24/24:</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              msg.action_status.diagnostic.muse?.online
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            }`}
                          >
                            {msg.action_status.diagnostic.muse?.online ? `${msg.action_status.diagnostic.muse.accounts_ready} Acc Online` : "OFFLINE"}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Media attachments */}
                    {msg.media && msg.media.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/50 space-y-2">
                        {msg.media.map((url, idx) => {
                          const isVid = url.endsWith(".mp4") || url.endsWith(".mov") || url.endsWith(".webm");
                          return isVid ? (
                            <video
                              key={idx}
                              src={url}
                              controls
                              className="rounded-lg max-h-48 w-full bg-black/50 border border-slate-700/40"
                            />
                          ) : (
                            <img
                              key={idx}
                              src={url}
                              alt="Generated preview"
                              className="rounded-lg max-h-48 w-full object-cover bg-black/50 border border-slate-700/40"
                            />
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className="flex items-center gap-2.5 text-slate-400">
                <div className="w-7 h-7 rounded-lg bg-sky-500/20 flex items-center justify-center text-xs">🤖</div>
                <div className="px-3 py-2 rounded-2xl bg-[#161f30] border border-slate-700/40 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:0.4s]" />
                  <span className="text-[11px] text-slate-400 ml-1">Trợ lý đang phân tích & thực thi...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-[#111724] border-t border-slate-800 flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhắn cho trợ lý (ví dụ: 'Zalo bị lỗi', 'Fix Zalo', 'Tạo ảnh con mèo', 'Báo cáo')..."
              rows={2}
              className="flex-1 bg-[#182030] text-slate-100 placeholder-slate-500 text-xs rounded-xl px-3 py-2 border border-slate-700/60 focus:outline-none focus:border-sky-500/60 resize-none leading-relaxed"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={!inputText.trim() || isLoading}
              className="p-2.5 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white shadow-md disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
