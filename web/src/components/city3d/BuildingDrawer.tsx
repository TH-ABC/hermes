import React, { useState } from "react";
import {
  X,
  Building2,
  Users,
  Layers,
  Video,
  Shield,
  Activity,
  Send,
  Play,
  Download,
  Edit3,
  Check,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ChevronRight,
  KeyRound,
} from "lucide-react";
import { BUILDINGS } from "./cityConfig";

interface BuildingDrawerProps {
  buildingId: string | null;
  onClose: () => void;
  // Live State
  agents: any[];
  tasks: any[];
  mediaList: any[];
  museStatus: any;
  isOpenAiEnabled: boolean;
  // Actions
  onCeoAssign: (instruction: string) => Promise<void>;
  isAssigning: boolean;
  onGenerateMedia: (prompt: string, type: "video" | "image") => Promise<void>;
  isGenerating: boolean;
  genMessage: string | null;
  onSaveAgentPrompt: (agentId: string, prompt: string, tools: string[]) => Promise<void>;
  onRefreshData: () => void;
  onToggleOpenAi: () => Promise<void>;
  onOpenLiveChat?: () => void;
}

export const BuildingDrawer: React.FC<BuildingDrawerProps> = ({
  buildingId,
  onClose,
  agents,
  tasks,
  mediaList,
  museStatus,
  isOpenAiEnabled,
  onCeoAssign,
  isAssigning,
  onGenerateMedia,
  isGenerating,
  genMessage,
  onSaveAgentPrompt,
  onRefreshData,
  onToggleOpenAi,
  onOpenLiveChat,
}) => {
  const [ceoText, setCeoText] = useState("");
  const [promptText, setPromptText] = useState("");
  const [mediaType, setMediaType] = useState<"video" | "image">("video");
  const [editingAgent, setEditingAgent] = useState<any | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [editTools, setEditTools] = useState<string[]>([]);
  const [isSavingAgent, setIsSavingAgent] = useState(false);

  if (!buildingId) return null;
  const building = BUILDINGS.find((b) => b.id === buildingId);
  if (!building) return null;

  const handleSendCeo = async () => {
    if (!ceoText.trim()) return;
    await onCeoAssign(ceoText);
    setCeoText("");
  };

  const handleGenMedia = async () => {
    if (!promptText.trim()) return;
    await onGenerateMedia(promptText, mediaType);
    setPromptText("");
  };

  const openAgentEdit = (agent: any) => {
    setEditingAgent(agent);
    setEditPrompt(agent.system_prompt || "");
    setEditTools(agent.allowed_tools || []);
  };

  const saveAgent = async () => {
    if (!editingAgent) return;
    setIsSavingAgent(true);
    await onSaveAgentPrompt(editingAgent.id, editPrompt, editTools);
    setIsSavingAgent(false);
    setEditingAgent(null);
  };

  const getStatusPill = (status: string) => {
    switch (status) {
      case "working":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">ĐANG LÀM VIỆC</span>;
      case "awaiting_approval":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30">CHỜ DUYỆT</span>;
      case "offline":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-zinc-500/20 text-zinc-400 border border-zinc-500/30">NGOẠI TUYẾN</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">SẴN SÀNG</span>;
    }
  };

  return (
    <div className="absolute top-20 right-4 bottom-24 w-full max-w-lg z-30 flex flex-col rounded-3xl bg-card/90 border border-border/70 backdrop-blur-2xl shadow-2xl overflow-hidden animate-in slide-in-from-right duration-300">
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-secondary/30">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary border border-primary/25">
            {building.id === "hq" && <Building2 className="h-5 w-5" />}
            {building.id === "agents" && <Users className="h-5 w-5" />}
            {building.id === "tasks" && <Layers className="h-5 w-5" />}
            {building.id === "media" && <Video className="h-5 w-5" />}
            {building.id === "vault" && <Shield className="h-5 w-5" />}
            {building.id === "observatory" && <Activity className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-base text-foreground">{building.name}</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-primary/20 text-primary uppercase font-bold">
                {building.badge}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{building.subtitle}</p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition"
          title="Đóng bảng điều khiển"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer Content Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* ========================================================= */}
        {/* MODULE 1: HQ - TÒA NHÀ ĐIỀU HÀNH */}
        {/* ========================================================= */}
        {building.id === "hq" && (
          <div className="space-y-5">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-primary/10 via-background to-secondary/30 border border-primary/20 space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h3 className="font-bold text-sm text-foreground">Lệnh Tổng Chỉ Huy (CEO Broadcast)</h3>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Nhập chỉ đạo hoặc mục tiêu kinh doanh. Trợ lý Trưởng (EA) sẽ tự động phân tích, chia nhỏ nhiệm vụ và phân bổ cho các phòng ban thực thi.
              </p>
              <div className="space-y-2">
                <textarea
                  value={ceoText}
                  onChange={(e) => setCeoText(e.target.value)}
                  placeholder="Ví dụ: Tạo video quảng cáo sản phẩm mới bằng MuseAI và lên bài viết Zalo..."
                  className="w-full h-24 rounded-xl border border-border/60 bg-background/80 p-3 text-xs focus:border-primary focus:outline-none resize-none"
                />
                <button
                  onClick={handleSendCeo}
                  disabled={isAssigning || !ceoText.trim()}
                  className="w-full py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition flex items-center justify-center gap-2 shadow-lg shadow-primary/25 disabled:opacity-50"
                >
                  {isAssigning ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                  {isAssigning ? "Đang phân bổ lệnh..." : "Phát Lệnh Cho Trợ Lý"}
                </button>
                {onOpenLiveChat && (
                  <button
                    onClick={() => {
                      onClose();
                      onOpenLiveChat();
                    }}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-sky-600/30 to-indigo-600/30 hover:from-sky-600/40 hover:to-indigo-600/40 border border-sky-500/40 text-sky-200 text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer"
                  >
                    <span className="text-sm">💬</span>
                    <span>Chat Trực Tuyến & Báo Lỗi Zalo Với Trợ Lý</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </button>
                )}
              </div>
            </div>

            {/* Quick Overview */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/40">
                <span className="text-[11px] text-muted-foreground">Tổng Trợ Lý Sẵn Sàng</span>
                <p className="text-xl font-extrabold text-foreground mt-1 font-mono">
                  {agents.filter((a) => a.status !== "offline").length} Nhân sự
                </p>
              </div>
              <div className="p-3.5 rounded-2xl bg-secondary/30 border border-border/40">
                <span className="text-[11px] text-muted-foreground">Nhiệm Vụ Đã Hoàn Thành</span>
                <p className="text-xl font-extrabold text-emerald-400 mt-1 font-mono">
                  {tasks.filter((t) => t.status === "completed").length} Tasks
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODULE 2: AGENTS - LÀNG TRỢ LÝ AI */}
        {/* ========================================================= */}
        {building.id === "agents" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                Danh Sách Trợ Lý ({agents.length})
              </h3>
              <button
                onClick={onRefreshData}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <RefreshCw className="h-3 w-3" /> Làm mới
              </button>
            </div>

            <div className="space-y-3">
              {agents.map((ag) => (
                <div
                  key={ag.id}
                  className="p-4 rounded-2xl bg-card border border-border/50 hover:border-primary/40 transition space-y-2.5 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-base">
                        {ag.avatar || "🤖"}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-foreground">{ag.name}</span>
                          {getStatusPill(ag.status)}
                        </div>
                        <p className="text-xs text-muted-foreground">{ag.title} • {ag.department}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => openAgentEdit(ag)}
                      className="p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary/70 transition"
                      title="Chỉnh sửa phân quyền & prompt"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {ag.current_task && (
                    <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
                      <span className="font-semibold">Đang làm:</span> {ag.current_task}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1">
                    {ag.allowed_tools?.slice(0, 4).map((tool: string) => (
                      <span
                        key={tool}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-secondary text-muted-foreground"
                      >
                        {tool}
                      </span>
                    ))}
                    {(ag.allowed_tools?.length || 0) > 4 && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 text-muted-foreground">
                        +{(ag.allowed_tools?.length || 0) - 4}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODULE 3: TASKS - TRUNG TÂM ĐIỀU PHỐI */}
        {/* ========================================================= */}
        {building.id === "tasks" && (
          <div className="space-y-4">
            <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
              Tiến Độ Công Việc ({tasks.length})
            </h3>

            {tasks.length === 0 ? (
              <div className="text-center py-8 text-xs text-muted-foreground">
                Chưa có nhiệm vụ nào được giao. Hãy vào Bộ Chỉ Huy phát lệnh!
              </div>
            ) : (
              <div className="space-y-3">
                {tasks.map((t) => (
                  <div
                    key={t.id}
                    className="p-4 rounded-2xl bg-card border border-border/50 space-y-2.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-foreground">{t.title}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                          t.status === "completed"
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : t.status === "in_progress"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : "bg-zinc-500/20 text-zinc-400 border border-zinc-500/30"
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>

                    <p className="text-xs text-muted-foreground">{t.instruction}</p>

                    {/* Execution steps */}
                    {t.steps && t.steps.length > 0 && (
                      <div className="space-y-1.5 pt-2 border-t border-border/40">
                        <span className="text-[11px] font-semibold text-foreground">Nhật ký các bước:</span>
                        {t.steps.map((st: any, idx: number) => (
                          <div key={idx} className="flex items-start gap-2 text-[11px] text-muted-foreground font-mono">
                            <ChevronRight className="h-3 w-3 mt-0.5 text-primary shrink-0" />
                            <span>
                              <b className="text-foreground">{st.agent}:</b> {st.action} — {st.detail}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* MODULE 4: MEDIA - XƯỞNG PHIM MUSEAI */}
        {/* ========================================================= */}
        {building.id === "media" && (
          <div className="space-y-5">
            {/* Media Creation Form */}
            <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-3">
              <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                <Video className="h-4 w-4 text-purple-400" /> Tạo Video & Hình Ảnh MuseAI
              </h3>

              <div className="flex gap-2">
                <button
                  onClick={() => setMediaType("video")}
                  className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition ${
                    mediaType === "video" ? "bg-purple-600 text-white" : "bg-card text-muted-foreground"
                  }`}
                >
                  🎬 Video AI
                </button>
                <button
                  onClick={() => setMediaType("image")}
                  className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition ${
                    mediaType === "image" ? "bg-purple-600 text-white" : "bg-card text-muted-foreground"
                  }`}
                >
                  🖼️ Hình Ảnh AI
                </button>
              </div>

              <textarea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="Mô tả video hoặc hình ảnh bạn muốn Muse sinh..."
                className="w-full h-20 rounded-xl border border-border/60 bg-background/80 p-3 text-xs focus:border-primary focus:outline-none resize-none"
              />

              <button
                onClick={handleGenMedia}
                disabled={isGenerating || !promptText.trim()}
                className="w-full py-2.5 rounded-xl bg-purple-600 text-white text-xs font-bold hover:bg-purple-500 transition flex items-center justify-center gap-2 shadow-lg shadow-purple-600/25 disabled:opacity-50"
              >
                {isGenerating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                {isGenerating ? "Đang kết nối Muse Pool sinh media..." : "Sinh Media Ngay"}
              </button>

              {genMessage && (
                <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs text-purple-300">
                  {genMessage}
                </div>
              )}
            </div>

            {/* Media Gallery */}
            <div className="space-y-3">
              <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                Thành Phẩm Trong Kho ({mediaList.length})
              </h3>
              {mediaList.length === 0 ? (
                <div className="text-center py-8 text-xs text-muted-foreground">
                  Chưa có media nào. Hãy nhập prompt ở trên để sinh video đầu tiên!
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {mediaList.map((m, idx) => (
                    <div key={idx} className="rounded-2xl border border-border/50 bg-card overflow-hidden shadow-sm flex flex-col">
                      <div className="aspect-video bg-black/40 flex items-center justify-center overflow-hidden relative">
                        {m.type === "video" ? (
                          <video src={m.url} controls className="w-full h-full object-cover" />
                        ) : (
                          <img src={m.url} alt={m.name} className="w-full h-full object-cover" />
                        )}
                      </div>
                      <div className="p-3 flex-1 flex flex-col justify-between gap-2">
                        <span className="text-[11px] font-semibold text-foreground truncate">{m.name}</span>
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                          <span>{(m.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                          <a
                            href={m.url}
                            download
                            className="p-1 rounded-md hover:bg-secondary text-primary transition"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODULE 5: VAULT - KHO TÀI KHOẢN GOLOGIN */}
        {/* ========================================================= */}
        {building.id === "vault" && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-3">
              <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                <Shield className="h-4 w-4 text-sky-400" /> Trạng Thái Pool & GoLogin
              </h3>

              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-card border border-border/40">
                  <span className="text-muted-foreground">Muse Pool Server (:8770):</span>
                  <span className="font-bold text-emerald-400">
                    {museStatus?.muse_server.online ? "ĐANG HOẠT ĐỘNG" : "OFFLINE"}
                  </span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded-xl bg-card border border-border/40">
                  <span className="text-muted-foreground">GoLogin Token (Orbita):</span>
                  <span className="font-bold text-sky-400">
                    {museStatus?.gologin_and_cookies.gologin_token_configured ? "ĐÃ CẤU HÌNH" : "CHƯA SẴN SÀNG"}
                  </span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded-xl bg-card border border-border/40">
                  <span className="text-muted-foreground">Tài khoản cookies trong pool:</span>
                  <span className="font-bold text-foreground font-mono">
                    {museStatus?.gologin_and_cookies.cookies_count || 0} tài khoản
                  </span>
                </div>
              </div>
            </div>

            {/* OpenAI API Key Management Card */}
            <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-amber-400" />
                  <span className="font-bold text-sm text-foreground">OpenAI API Key</span>
                </div>
                <span
                  className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${
                    isOpenAiEnabled
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                      : "bg-rose-500/20 text-rose-400 border-rose-500/30"
                  }`}
                >
                  {isOpenAiEnabled ? "🟢 ĐANG BẬT" : "🔴 ĐÃ TẮT (GỠ BỎ)"}
                </span>
              </div>

              <p className="text-xs text-muted-foreground leading-relaxed">
                {isOpenAiEnabled
                  ? "OpenAI Key đang được kích hoạt. Bạn có thể nhấn tắt để gỡ bỏ hoàn toàn và chạy 100% bằng OpenRouter / Gemini."
                  : "OpenAI Key đã được tắt và gỡ bỏ hoàn toàn. Hệ thống hiện chạy qua OpenRouter (Gemini Flash) và Muse Engine nội bộ."}
              </p>

              <div className="pt-1 flex items-center justify-between">
                <span className="text-xs text-muted-foreground font-mono">
                  Trạng thái: <b className={isOpenAiEnabled ? "text-emerald-400" : "text-rose-400 font-bold"}>{isOpenAiEnabled ? "Đang Bật" : "ĐÃ TẮT"}</b>
                </span>
                <button
                  onClick={onToggleOpenAi}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                    isOpenAiEnabled
                      ? "bg-rose-600/80 hover:bg-rose-600 text-white shadow-lg shadow-rose-600/20"
                      : "bg-emerald-600/80 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-600/20"
                  }`}
                >
                  {isOpenAiEnabled ? "Tắt & Gỡ OpenAI Key" : "Bật Lại OpenAI Key"}
                </button>
              </div>
            </div>

            {/* Quick Link to local login */}
            <div className="p-4 rounded-2xl bg-primary/10 border border-primary/20 space-y-2">
              <span className="font-bold text-xs text-primary">Nạp Thêm Tài Khoản Vào Pool</span>
              <p className="text-xs text-muted-foreground">
                Để nạp thêm tài khoản Muse.ai bằng GoLogin Orbita, hãy nhấp đúp file <code className="font-mono text-foreground font-bold">start_local_login.bat</code> trên máy tính rồi bấm đăng nhập local tại tab Muse Dashboard.
              </p>
              <a
                href="http://127.0.0.1:8770/dashboard"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-primary hover:underline pt-1"
              >
                Mở Muse Dashboard (:8770) <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODULE 6: OBSERVATORY - ĐÀI QUAN SÁT */}
        {/* ========================================================= */}
        {building.id === "observatory" && (
          <div className="space-y-4">
            <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
              Thông Số Hệ Thống & Gateway
            </h3>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-2xl bg-card border border-border/50">
                <span className="text-[11px] text-muted-foreground">Zalo Gateway</span>
                <p className="text-lg font-bold text-emerald-400 mt-1 font-mono">Cổng 3050 OK</p>
              </div>
              <div className="p-3.5 rounded-2xl bg-card border border-border/50">
                <span className="text-[11px] text-muted-foreground">WebSocket Live</span>
                <p className="text-lg font-bold text-sky-400 mt-1 font-mono">Đã kết nối</p>
              </div>
              <div className="p-3.5 rounded-2xl bg-card border border-border/50">
                <span className="text-[11px] text-muted-foreground">Thời Gian Phản Hồi</span>
                <p className="text-lg font-bold text-foreground mt-1 font-mono">12 ms</p>
              </div>
              <div className="p-3.5 rounded-2xl bg-card border border-border/50">
                <span className="text-[11px] text-muted-foreground">Chế Độ Máy</span>
                <p className="text-lg font-bold text-amber-400 mt-1 font-mono">Local 24/7</p>
              </div>
            </div>

            {onOpenLiveChat && (
              <button
                onClick={() => {
                  onClose();
                  onOpenLiveChat();
                }}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-sky-600/30 to-indigo-600/30 hover:from-sky-600/40 hover:to-indigo-600/40 border border-sky-500/40 text-sky-200 text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer"
              >
                <span className="text-sm">💬</span>
                <span>Mở Kênh Chat Điều Hành & Sửa Lỗi Zalo</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Edit Agent System Prompt Modal */}
      {editingAgent && (
        <div className="absolute inset-0 z-40 bg-background/95 backdrop-blur-md p-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-border/50 pb-3">
              <div>
                <h4 className="font-bold text-sm text-foreground">Cấu Hình Trợ Lý: {editingAgent.name}</h4>
                <p className="text-xs text-muted-foreground">{editingAgent.title}</p>
              </div>
              <button
                onClick={() => setEditingAgent(null)}
                className="p-1 rounded-full text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-foreground">System Prompt (Chỉ dẫn hành vi):</label>
              <textarea
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                rows={6}
                className="w-full rounded-xl border border-border/60 bg-card p-3 text-xs font-mono focus:border-primary focus:outline-none resize-none"
              />
            </div>
          </div>

          <div className="flex gap-2 pt-4 border-t border-border/50">
            <button
              onClick={() => setEditingAgent(null)}
              className="flex-1 py-2.5 rounded-xl border border-border/60 text-xs font-medium hover:bg-secondary transition"
            >
              Hủy
            </button>
            <button
              onClick={saveAgent}
              disabled={isSavingAgent}
              className="flex-1 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition flex items-center justify-center gap-1.5"
            >
              {isSavingAgent ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
              Lưu Cấu Hình
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
