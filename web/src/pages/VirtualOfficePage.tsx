import { useState, useEffect, useRef } from "react";
import {
  Building2,
  Palette,
  Clock,
  Shield,
  Send,
  Play,
  RefreshCw,
  Users,
  Lock,
  Edit3,
  Video,
  Image as ImageIcon,
  Download,
  Activity,
  Layers,
  Check,
  ChevronRight,
} from "lucide-react";

interface OfficeAgent {
  id: string;
  name: string;
  role: string;
  title: string;
  department: string;
  avatar: string;
  desk_id: string;
  level: number;
  allowed_tools: string[];
  system_prompt: string;
  status: "idle" | "working" | "awaiting_approval" | "offline";
  current_task?: string | null;
  last_active: number;
}

interface OfficeTask {
  id: string;
  creator: string;
  title: string;
  instruction: string;
  assigned_to: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  created_at: number;
  updated_at: number;
  steps: {
    agent: string;
    action: string;
    detail: string;
    timestamp: number;
  }[];
  result?: string | null;
  media_outputs?: string[];
}

interface MediaItem {
  name: string;
  type: "video" | "image";
  path: string;
  size_bytes: number;
  created_at: number;
  url: string;
}

interface MuseStatus {
  muse_server: {
    online: boolean;
    accounts_count?: number;
    active_accounts?: number;
    concurrency?: number;
    status?: string;
    error?: string;
    url?: string;
  };
  gologin_and_cookies: {
    gologin_available: boolean;
    gologin_token_configured: boolean;
    gologin_cli_installed: boolean;
    cookies_dir: string;
    cookies_count: number;
    cookies: { name: string; size_bytes: number; updated_at: number }[];
  };
}

export default function VirtualOfficePage() {
  const [activeTab, setActiveTab] = useState<"office" | "media" | "agents" | "tasks">("office");
  const [agents, setAgents] = useState<OfficeAgent[]>([]);
  const [tasks, setTasks] = useState<OfficeTask[]>([]);
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [museStatus, setMuseStatus] = useState<MuseStatus | null>(null);
  const [serverUrl, setServerUrl] = useState("http://127.0.0.1:8770");
  const [isSavingServerUrl, setIsSavingServerUrl] = useState(false);
  const [saveUrlSuccess, setSaveUrlSuccess] = useState(false);

  // CEO Command Bar State
  const [ceoInstruction, setCeoInstruction] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);

  // Media Generator State
  const [mediaPrompt, setMediaPrompt] = useState("");
  const [mediaType, setMediaType] = useState<"video" | "image">("video");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);

  // Agent Prompt Editing Modal
  const [selectedAgent, setSelectedAgent] = useState<OfficeAgent | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [editTools, setEditTools] = useState<string[]>([]);
  const [isSavingAgent, setIsSavingAgent] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  // Available tools for role selection
  const ALL_TOOLS = [
    "muse_generate_media",
    "muse_check_status",
    "delegate_task",
    "web_search",
    "web_extract",
    "read_file",
    "terminal",
    "cron",
  ];

  const fetchOfficeData = async () => {
    try {
      const [agentsRes, tasksRes, museRes, mediaRes] = await Promise.all([
        fetch("/api/office/agents").then((r) => r.json()),
        fetch("/api/office/tasks").then((r) => r.json()),
        fetch("/api/office/muse/status").then((r) => r.json()),
        fetch("/api/office/media").then((r) => r.json()),
      ]);

      if (agentsRes.ok) setAgents(agentsRes.agents);
      if (tasksRes.ok) setTasks(tasksRes.tasks.reverse());
      if (museRes.ok) {
        setMuseStatus(museRes);
        if (museRes.active_base_url) setServerUrl(museRes.active_base_url);
      }
      if (mediaRes.ok) setMediaList(mediaRes.media);
    } catch (e) {
      console.error("Failed to fetch office data", e);
    }
  };

  useEffect(() => {
    fetchOfficeData();

    // Connect WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/office/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "agent_status" || msg.type === "agent_updated") {
          fetchOfficeData();
        } else if (msg.type === "task_created" || msg.type === "task_step" || msg.type === "task_completed" || msg.type === "task_failed") {
          fetchOfficeData();
        }
      } catch (err) {
        // ignore parse error
      }
    };

    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 15000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, []);

  const handleCeoAssign = async () => {
    if (!ceoInstruction.trim()) return;
    setIsAssigning(true);
    try {
      const res = await fetch("/api/office/tasks/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: ceoInstruction }),
      });
      const data = await res.json();
      if (data.ok) {
        setCeoInstruction("");
        fetchOfficeData();
      }
    } catch (e) {
      console.error("Assign error", e);
    } finally {
      setIsAssigning(false);
    }
  };

  const handleTestGenerateMedia = async () => {
    if (!mediaPrompt.trim()) return;
    setIsGenerating(true);
    setGenMessage(null);
    try {
      const res = await fetch("/api/office/muse/test-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: mediaPrompt, media_type: mediaType }),
      });
      const data = await res.json();
      if (data.ok) {
        setGenMessage(`Thành công! Đã sinh ${data.media_files?.length || 1} tệp media.`);
        setMediaPrompt("");
        fetchOfficeData();
      } else {
        setGenMessage(`Lỗi: ${data.error || "Không thể sinh media"}`);
      }
    } catch (e: any) {
      setGenMessage(`Lỗi kết nối: ${e.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveServerUrl = async () => {
    setIsSavingServerUrl(true);
    try {
      await fetch("/api/office/muse/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ server_url: serverUrl }),
      });
      setSaveUrlSuccess(true);
      fetchOfficeData();
      setTimeout(() => setSaveUrlSuccess(false), 2000);
    } catch (e) {
      console.error("Save server URL error", e);
    } finally {
      setIsSavingServerUrl(false);
    }
  };

  const openAgentModal = (agent: OfficeAgent) => {
    setSelectedAgent(agent);
    setEditPrompt(agent.system_prompt);
    setEditTools([...agent.allowed_tools]);
    setSaveSuccess(false);
  };

  const handleSaveAgent = async () => {
    if (!selectedAgent) return;
    setIsSavingAgent(true);
    try {
      await fetch(`/api/office/agents/${selectedAgent.id}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: editPrompt }),
      });

      if (selectedAgent.id !== "ceo") {
        await fetch(`/api/office/agents/${selectedAgent.id}/permissions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allowed_tools: editTools }),
        });
      }

      setSaveSuccess(true);
      fetchOfficeData();
      setTimeout(() => {
        setSelectedAgent(null);
        setSaveSuccess(false);
      }, 1000);
    } catch (e) {
      console.error("Failed to save agent", e);
    } finally {
      setIsSavingAgent(false);
    }
  };

  const getAgentBadgeColor = (status: string) => {
    switch (status) {
      case "working":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40 animate-pulse";
      case "awaiting_approval":
        return "bg-rose-500/20 text-rose-400 border-rose-500/40";
      case "offline":
        return "bg-zinc-500/20 text-zinc-400 border-zinc-500/40";
      default:
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "working":
        return "Đang làm việc";
      case "awaiting_approval":
        return "Chờ duyệt";
      case "offline":
        return "Ngoại tuyến";
      default:
        return "Sẵn sàng (Rảnh)";
    }
  };

  return (
    <div className="flex flex-col gap-6 text-foreground">
      {/* Top Header & System Overview */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border/40 bg-card/60 p-5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
            <Building2 className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Hệ Thống Văn Phòng Ảo Đa Agent & Muse Hub</h1>
            <p className="text-xs text-muted-foreground">
              Mô hình phân cấp CEO &rarr; Trợ lý Muse (EA) &rarr; Nhân viên chuyên môn • Zalo Assistant • Phân quyền nghiêm ngặt
            </p>
          </div>
        </div>

        {/* Server & GoLogin Status Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <div
            className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
              museStatus?.muse_server.online
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-rose-500/30 bg-rose-500/10 text-rose-400"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Muse Server (:8770): {museStatus?.muse_server.online ? "ONLINE" : "OFFLINE"}</span>
          </div>

          <div
            className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
              museStatus?.gologin_and_cookies.gologin_token_configured
                ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
                : "border-amber-500/30 bg-amber-500/10 text-amber-400"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            <span>GoLogin Token: {museStatus?.gologin_and_cookies.gologin_token_configured ? "Đã sẵn sàng" : "Chưa cấu hình"}</span>
          </div>

          <button
            onClick={fetchOfficeData}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-secondary/50 px-3 py-1.5 text-xs font-medium hover:bg-secondary transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Làm mới
          </button>
        </div>
      </div>

      {/* 24/7 Dedicated Machine URL Config (100% No VPS) */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-base">🖥️</span>
          <div>
            <span className="font-bold text-foreground">Máy Riêng 24/24 (Muse Server Local / LAN):</span>
            <span className="ml-2 text-muted-foreground">
              Hoạt động hoàn toàn trên máy riêng nội bộ, 100% không kết nối hay phụ thuộc bất kỳ VPS nào.
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            placeholder="http://127.0.0.1:8770 hoặc http://192.168.x.x:8770"
            className="w-64 rounded-lg border border-border/60 bg-background px-3 py-1.5 text-xs font-mono focus:border-primary focus:outline-none"
          />
          <button
            onClick={handleSaveServerUrl}
            disabled={isSavingServerUrl}
            className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition flex items-center gap-1"
          >
            {isSavingServerUrl ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            {saveUrlSuccess ? "Đã lưu!" : "Lưu Địa Chỉ"}
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border/40">
        <button
          onClick={() => setActiveTab("office")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "office"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Building2 className="h-4 w-4" />
          Sơ Đồ Văn Phòng Ảo
        </button>

        <button
          onClick={() => setActiveTab("media")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "media"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Palette className="h-4 w-4" />
          Media Lab & Muse Hub ({mediaList.length})
        </button>

        <button
          onClick={() => setActiveTab("agents")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "agents"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Users className="h-4 w-4" />
          Quản Lý Prompt & Phân Quyền
        </button>

        <button
          onClick={() => setActiveTab("tasks")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
            activeTab === "tasks"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Clock className="h-4 w-4" />
          Nhật Ký Chỉ Đạo CEO ({tasks.length})
        </button>
      </div>

      {/* TAB 1: SƠ ĐỒ VĂN PHÒNG ẢO (FLOOR PLAN) */}
      {activeTab === "office" && (
        <div className="flex flex-col gap-6">
          {/* CEO Command Bar */}
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 shadow-sm backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xl">👔</span>
              <span className="text-sm font-bold text-primary">PHÒNG CHỈ HUY CEO (Quản Trị Viên)</span>
              <span className="text-xs text-muted-foreground">| Giao chỉ đạo chiến lược cho Trợ lý Muse</span>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={ceoInstruction}
                onChange={(e) => setCeoInstruction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCeoAssign()}
                placeholder="Ví dụ: 'Tạo video TVC 5s ly cà phê bốc khói để đăng Zalo' hoặc 'Nghiên cứu thị trường AI tuần này'..."
                className="flex-1 rounded-lg border border-border/50 bg-background/80 px-4 py-2 text-sm focus:border-primary focus:outline-none"
              />
              <button
                onClick={handleCeoAssign}
                disabled={isAssigning || !ceoInstruction.trim()}
                className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition"
              >
                {isAssigning ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Giao Việc Cho Muse
              </button>
            </div>
          </div>

          {/* Visual Floor Plan Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* 1. Executive Suite (CEO & Muse EA) */}
            <div className="md:col-span-1 flex flex-col gap-4 rounded-xl border border-border/50 bg-card/40 p-4">
              <div className="flex items-center justify-between border-b border-border/30 pb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5 text-primary" /> Ban Giám Đốc & Điều Hành
                </span>
                <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded font-mono">Level 3 & 2</span>
              </div>

              {/* CEO Card */}
              {agents.filter((a) => a.role === "ceo").map((agent) => (
                <div
                  key={agent.id}
                  onClick={() => openAgentModal(agent)}
                  className="cursor-pointer rounded-lg border border-border/40 bg-card p-3 hover:border-primary/50 transition shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="text-2xl">{agent.avatar}</span>
                      <div>
                        <div className="text-sm font-bold">{agent.name}</div>
                        <div className="text-xs text-muted-foreground">{agent.title}</div>
                      </div>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${getAgentBadgeColor(agent.status)}`}>
                      {getStatusLabel(agent.status)}
                    </span>
                  </div>
                </div>
              ))}

              {/* Arrow Connector */}
              <div className="flex justify-center text-primary/60">
                <span className="text-xs flex items-center gap-1 font-mono">↓ Chỉ đạo & Giám sát ↓</span>
              </div>

              {/* Muse EA Card */}
              {agents.filter((a) => a.role === "muse_ea").map((agent) => (
                <div
                  key={agent.id}
                  onClick={() => openAgentModal(agent)}
                  className="cursor-pointer rounded-lg border border-sky-500/40 bg-sky-500/5 p-3 hover:border-sky-500 transition shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="text-2xl">{agent.avatar}</span>
                      <div>
                        <div className="text-sm font-bold text-sky-400">{agent.name}</div>
                        <div className="text-xs text-muted-foreground">{agent.title}</div>
                      </div>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${getAgentBadgeColor(agent.status)}`}>
                      {getStatusLabel(agent.status)}
                    </span>
                  </div>
                  {agent.current_task && (
                    <div className="mt-2 text-xs bg-background/80 p-2 rounded border border-border/40 text-sky-300">
                      ⚡ {agent.current_task}
                    </div>
                  )}
                  <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Quyền: Điều phối & Zalo Gateway</span>
                    <Edit3 className="h-3 w-3" />
                  </div>
                </div>
              ))}
            </div>

            {/* 2. Specialized Department Workstations */}
            <div className="md:col-span-2 flex flex-col gap-4 rounded-xl border border-border/50 bg-card/40 p-4">
              <div className="flex items-center justify-between border-b border-border/30 pb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-primary" /> Các Phòng Ban Nhân Viên Chuyên Môn
                </span>
                <span className="text-[10px] bg-secondary text-muted-foreground px-2 py-0.5 rounded font-mono">
                  Level 1 • Không Vượt Quyền
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {agents
                  .filter((a) => a.level === 1)
                  .map((agent) => (
                    <div
                      key={agent.id}
                      onClick={() => openAgentModal(agent)}
                      className="cursor-pointer rounded-lg border border-border/40 bg-card p-3 hover:border-primary/50 transition flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-2xl">{agent.avatar}</span>
                            <div>
                              <div className="text-sm font-bold">{agent.name}</div>
                              <div className="text-[11px] text-muted-foreground">{agent.department}</div>
                            </div>
                          </div>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${getAgentBadgeColor(agent.status)}`}>
                            {getStatusLabel(agent.status)}
                          </span>
                        </div>

                        {agent.current_task && (
                          <div className="mt-2 text-xs bg-amber-500/10 border border-amber-500/20 p-2 rounded text-amber-300">
                            ⏳ {agent.current_task}
                          </div>
                        )}
                      </div>

                      <div className="mt-3 pt-2 border-t border-border/30 flex items-center justify-between text-[10px] text-muted-foreground">
                        <span className="flex items-center gap-1 font-mono">
                          <Lock className="h-3 w-3 text-emerald-400" />
                          {agent.allowed_tools.join(", ") || "Không có tool"}
                        </span>
                        <ChevronRight className="h-3 w-3" />
                      </div>
                    </div>
                  ))}
              </div>

              {/* Live Task Stream Preview */}
              <div className="mt-2 rounded-lg border border-border/30 bg-background/50 p-3">
                <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground mb-2">
                  <span className="flex items-center gap-1.5">
                    <Activity className="h-3.5 w-3.5 text-primary" /> Tiến Độ Xử Lý Trực Tuyến
                  </span>
                  <span className="text-[10px]">{tasks.length} nhiệm vụ đã ghi nhận</span>
                </div>

                {tasks.length > 0 ? (
                  <div className="flex flex-col gap-2 max-h-40 overflow-y-auto text-xs">
                    {tasks.slice(0, 3).map((t) => (
                      <div key={t.id} className="rounded border border-border/30 bg-card/60 p-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">{t.title}</span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded ${
                              t.status === "completed"
                                ? "bg-emerald-500/20 text-emerald-400"
                                : t.status === "in_progress"
                                ? "bg-amber-500/20 text-amber-400 animate-pulse"
                                : "bg-zinc-500/20 text-zinc-400"
                            }`}
                          >
                            {t.status}
                          </span>
                        </div>
                        {t.steps.length > 0 && (
                          <div className="mt-1 text-[11px] text-muted-foreground">
                            Bước cuối: {t.steps[t.steps.length - 1].action} - {t.steps[t.steps.length - 1].detail}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-xs text-muted-foreground">
                    Chưa có nhiệm vụ nào được giao. Hãy gõ chỉ đạo ở thanh trên để thử nghiệm!
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MEDIA LAB & MUSE HUB */}
      {activeTab === "media" && (
        <div className="flex flex-col gap-6">
          {/* Quick Generator Box */}
          <div className="rounded-xl border border-border/40 bg-card p-5">
            <h2 className="text-base font-bold flex items-center gap-2 mb-3">
              <Palette className="h-5 w-5 text-primary" /> Trình Tạo Ảnh & Video Muse AI
            </h2>

            <div className="flex flex-col gap-3">
              <textarea
                value={mediaPrompt}
                onChange={(e) => setMediaPrompt(e.target.value)}
                placeholder="Nhập prompt mô tả ảnh hoặc video (ví dụ: 'Video TVC 5s ly cà phê bốc khói trên bàn gỗ, ánh sáng ấm áp')..."
                rows={3}
                className="w-full rounded-lg border border-border/50 bg-background/80 p-3 text-sm focus:border-primary focus:outline-none"
              />

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer font-medium">
                    <input
                      type="radio"
                      name="mtype"
                      checked={mediaType === "video"}
                      onChange={() => setMediaType("video")}
                      className="text-primary"
                    />
                    <Video className="h-4 w-4 text-primary" /> Video TVC / Clip (.mp4)
                  </label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer font-medium">
                    <input
                      type="radio"
                      name="mtype"
                      checked={mediaType === "image"}
                      onChange={() => setMediaType("image")}
                      className="text-primary"
                    />
                    <ImageIcon className="h-4 w-4 text-primary" /> Ảnh tĩnh nghệ thuật (.jpg/.png)
                  </label>
                </div>

                <button
                  onClick={handleTestGenerateMedia}
                  disabled={isGenerating || !mediaPrompt.trim()}
                  className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition"
                >
                  {isGenerating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {isGenerating ? "Đang sinh media qua Muse..." : "Bắt Đầu Tạo"}
                </button>
              </div>

              {genMessage && (
                <div
                  className={`p-3 rounded-lg text-xs border ${
                    genMessage.startsWith("Thành công")
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : "bg-rose-500/10 border-rose-500/30 text-rose-400"
                  }`}
                >
                  {genMessage}
                </div>
              )}
            </div>
          </div>

          {/* Media Gallery */}
          <div className="rounded-xl border border-border/40 bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold flex items-center gap-2">
                <Video className="h-5 w-5 text-primary" /> Kho Lưu Trữ Media & Video TVC ({mediaList.length})
              </h2>
              <span className="text-xs text-muted-foreground">Tự động gắn thẻ MEDIA: để gửi Zalo đính kèm gốc</span>
            </div>

            {mediaList.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {mediaList.map((item, idx) => (
                  <div key={idx} className="rounded-lg border border-border/40 bg-background/60 overflow-hidden flex flex-col">
                    <div className="aspect-video bg-black/40 flex items-center justify-center relative">
                      {item.type === "video" ? (
                        <video src={item.url} controls className="w-full h-full object-contain" />
                      ) : (
                        <img src={item.url} alt={item.name} className="w-full h-full object-contain" />
                      )}
                    </div>
                    <div className="p-3 flex flex-col gap-1 flex-1 justify-between">
                      <div>
                        <div className="text-xs font-semibold truncate" title={item.name}>
                          {item.name}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {new Date(item.created_at * 1000).toLocaleString("vi-VN")} • {(item.size_bytes / (1024 * 1024)).toFixed(2)} MB
                        </div>
                      </div>
                      <div className="mt-2 flex items-center justify-between pt-2 border-t border-border/30">
                        <span className="text-[10px] text-primary uppercase font-mono">{item.type}</span>
                        <a
                          href={item.url}
                          download={item.name}
                          className="flex items-center gap-1 text-[11px] text-primary hover:underline"
                        >
                          <Download className="h-3 w-3" /> Tải về
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-10 text-sm text-muted-foreground">
                Chưa có ảnh hoặc video nào được tạo. Hãy dùng trình tạo ở trên để sinh video đầu tiên!
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: QUẢN LÝ PROMPT & PHÂN QUYỀN (RBAC) */}
      {activeTab === "agents" && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" /> Danh Sách Agent & Cấu Hình Prompt Chuyên Môn
            </h2>
            <span className="text-xs text-muted-foreground">Nhấp vào Agent để cập nhật prompt hoặc quyền hạn</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="rounded-xl border border-border/40 bg-card p-4 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-border/30 pb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-3xl">{agent.avatar}</span>
                      <div>
                        <h3 className="text-sm font-bold">{agent.name}</h3>
                        <p className="text-xs text-muted-foreground">{agent.title} • {agent.department}</p>
                      </div>
                    </div>
                    <span className="text-xs font-mono bg-secondary px-2 py-0.5 rounded">Level {agent.level}</span>
                  </div>

                  <div className="my-3">
                    <div className="text-xs font-semibold text-muted-foreground mb-1">System Prompt:</div>
                    <div className="text-xs bg-background/80 border border-border/30 rounded p-2.5 max-h-24 overflow-y-auto leading-relaxed">
                      {agent.system_prompt}
                    </div>
                  </div>

                  <div className="mb-3">
                    <div className="text-xs font-semibold text-muted-foreground mb-1">Công Cụ Được Cấp Phép (Allowed Tools):</div>
                    <div className="flex flex-wrap gap-1.5">
                      {agent.allowed_tools.map((t) => (
                        <span key={t} className="text-[10px] font-mono bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/30 flex justify-end">
                  <button
                    onClick={() => openAgentModal(agent)}
                    className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                  >
                    <Edit3 className="h-3.5 w-3.5" /> Chỉnh Sửa Prompt & Quyền
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: NHẬT KÝ CHỈ ĐẠO CEO (TASK LOGS) */}
      {activeTab === "tasks" && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" /> Nhật Ký Thực Thi & Luồng Công Việc
            </h2>
            <span className="text-xs text-muted-foreground">Theo dõi quy trình CEO &rarr; Muse EA &rarr; Specialist</span>
          </div>

          <div className="flex flex-col gap-3">
            {tasks.map((task) => (
              <div key={task.id} className="rounded-xl border border-border/40 bg-card p-4">
                <div className="flex items-center justify-between border-b border-border/30 pb-2">
                  <div>
                    <h3 className="text-sm font-bold">{task.title}</h3>
                    <p className="text-xs text-muted-foreground">
                      Chỉ thị: "{task.instruction}" • {new Date(task.created_at * 1000).toLocaleString("vi-VN")}
                    </p>
                  </div>
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full border ${
                      task.status === "completed"
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                        : task.status === "in_progress"
                        ? "border-amber-500/40 bg-amber-500/10 text-amber-400 animate-pulse"
                        : "border-rose-500/40 bg-rose-500/10 text-rose-400"
                    }`}
                  >
                    {task.status.toUpperCase()}
                  </span>
                </div>

                {/* Task Steps */}
                <div className="mt-3 flex flex-col gap-2">
                  <div className="text-xs font-semibold text-muted-foreground">Các bước ủy quyền & thực thi:</div>
                  {task.steps.map((st, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs bg-background/60 p-2 rounded border border-border/20">
                      <span className="font-mono text-primary font-bold">[{st.agent}]</span>
                      <div className="flex-1">
                        <span className="font-medium">{st.action}</span>: <span className="text-muted-foreground">{st.detail}</span>
                      </div>
                      <span className="text-[10px] text-muted-foreground">{new Date(st.timestamp * 1000).toLocaleTimeString("vi-VN")}</span>
                    </div>
                  ))}
                </div>

                {task.result && (
                  <div className="mt-3 p-3 rounded-lg bg-primary/5 border border-primary/20 text-xs">
                    <span className="font-bold text-primary">Kết quả báo cáo CEO:</span> {task.result}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AGENT EDIT MODAL */}
      {selectedAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-xl rounded-xl border border-border bg-card p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">{selectedAgent.avatar}</span>
                <div>
                  <h3 className="text-base font-bold">Chỉnh Sửa Agent: {selectedAgent.name}</h3>
                  <p className="text-xs text-muted-foreground">{selectedAgent.title}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedAgent(null)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                ✕
              </button>
            </div>

            {/* Edit Prompt */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold">System Prompt (Tính cách & Nhiệm vụ):</label>
              <textarea
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                rows={5}
                className="w-full rounded-lg border border-border/50 bg-background p-3 text-xs focus:border-primary focus:outline-none leading-relaxed"
              />
            </div>

            {/* Edit Allowed Tools (If not CEO) */}
            {selectedAgent.id !== "ceo" && (
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold">Phân Quyền Công Cụ (Whitelisted Tools - Không Vượt Quyền):</label>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {ALL_TOOLS.map((t) => {
                    const checked = editTools.includes(t);
                    return (
                      <label key={t} className="flex items-center gap-2 cursor-pointer rounded border border-border/30 p-2 hover:bg-secondary/40">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setEditTools([...editTools, t]);
                            } else {
                              setEditTools(editTools.filter((x) => x !== t));
                            }
                          }}
                        />
                        <span className="font-mono text-[11px]">{t}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {saveSuccess && (
              <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs text-center font-medium">
                ✅ Đã lưu cấu hình Agent thành công!
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-border/30">
              <button
                onClick={() => setSelectedAgent(null)}
                className="px-4 py-2 rounded-lg border border-border/50 text-xs hover:bg-secondary transition"
              >
                Hủy
              </button>
              <button
                onClick={handleSaveAgent}
                disabled={isSavingAgent}
                className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition"
              >
                {isSavingAgent ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Lưu Thay Đổi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
