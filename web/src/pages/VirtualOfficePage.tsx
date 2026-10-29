import { useState, useEffect, useRef, useCallback } from "react";
import { FloatingCity3D } from "@/components/city3d/FloatingCity3D";
import { CityHUD } from "@/components/city3d/CityHUD";
import { BuildingDrawer } from "@/components/city3d/BuildingDrawer";
import { OfficeLiveChat } from "@/components/city3d/OfficeLiveChat";
import type { BuildingDef } from "@/components/city3d/cityConfig";
import { fetchJSON, buildWsUrl } from "@/lib/api";

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
  // 3D City State
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [hoveredBuilding, setHoveredBuilding] = useState<BuildingDef | null>(null);
  const [cameraResetTrigger, setCameraResetTrigger] = useState<number>(0);

  // Live Data State
  const [agents, setAgents] = useState<OfficeAgent[]>([]);
  const [tasks, setTasks] = useState<OfficeTask[]>([]);
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [museStatus, setMuseStatus] = useState<MuseStatus | null>(null);
  const [isOpenAiEnabled, setIsOpenAiEnabled] = useState<boolean>(false);

  // Action State
  const [isAssigning, setIsAssigning] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  const fetchOfficeData = useCallback(async () => {
    try {
      const [agentsRes, tasksRes, museRes, mediaRes, openaiRes] = await Promise.all([
        fetchJSON<any>("/api/office/agents"),
        fetchJSON<any>("/api/office/tasks"),
        fetchJSON<any>("/api/office/muse/status"),
        fetchJSON<any>("/api/office/media"),
        fetchJSON<any>("/api/office/openai/status").catch(() => null),
      ]);

      if (agentsRes?.ok && agentsRes.agents) setAgents(agentsRes.agents);
      if (tasksRes?.ok && tasksRes.tasks) setTasks([...tasksRes.tasks].reverse());
      if (museRes?.ok) setMuseStatus(museRes);
      if (mediaRes?.ok && mediaRes.media) setMediaList(mediaRes.media);
      if (openaiRes?.ok) setIsOpenAiEnabled(!!openaiRes.enabled);
    } catch (e) {
      console.error("Failed to fetch office data", e);
    }
  }, []);

  useEffect(() => {
    fetchOfficeData();

    let isSubscribed = true;
    const connectWs = async () => {
      try {
        const wsUrl = await buildWsUrl("/api/office/ws");
        if (!isSubscribed) return;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (
              msg.type === "agent_status" ||
              msg.type === "agent_updated" ||
              msg.type === "task_created" ||
              msg.type === "task_step" ||
              msg.type === "task_completed" ||
              msg.type === "task_failed"
            ) {
              fetchOfficeData();
            }
          } catch {
            // ignore parse error
          }
        };
      } catch (err) {
        console.warn("Office WS setup deferred:", err);
      }
    };

    connectWs();

    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 15000);

    return () => {
      isSubscribed = false;
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [fetchOfficeData]);

  // Handler: Assign Task via CEO
  const handleCeoAssign = async (instruction: string) => {
    if (!instruction.trim()) return;
    setIsAssigning(true);
    try {
      const data = await fetchJSON<any>("/api/office/tasks/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction }),
      });
      if (data?.ok) {
        fetchOfficeData();
      }
    } catch (e) {
      console.error("Assign error", e);
    } finally {
      setIsAssigning(false);
    }
  };

  // Handler: Generate Media via MuseAI
  const handleTestGenerateMedia = async (prompt: string, type: "video" | "image") => {
    if (!prompt.trim()) return;
    setIsGenerating(true);
    setGenMessage(null);
    try {
      const data = await fetchJSON<any>("/api/office/muse/test-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, media_type: type }),
      });
      if (data?.ok) {
        setGenMessage(`Thành công! Đã sinh ${data.media_files?.length || 1} tệp media.`);
        fetchOfficeData();
      } else {
        setGenMessage(`Lỗi: ${data?.error || "Không thể sinh media"}`);
      }
    } catch (e: any) {
      setGenMessage(`Lỗi kết nối: ${e.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // Handler: Save Agent Prompt & Permissions
  const handleSaveAgentPrompt = async (agentId: string, prompt: string, tools: string[]) => {
    try {
      await fetchJSON(`/api/office/agents/${agentId}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (agentId !== "ceo") {
        await fetchJSON(`/api/office/agents/${agentId}/permissions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allowed_tools: tools }),
        });
      }
      fetchOfficeData();
    } catch (e) {
      console.error("Failed to save agent", e);
    }
  };

  const handleToggleOpenAi = async () => {
    try {
      const res = await fetchJSON<any>("/api/office/openai/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !isOpenAiEnabled }),
      });
      if (res?.ok) {
        setIsOpenAiEnabled(!!res.enabled);
        fetchOfficeData();
      }
    } catch (e) {
      console.error("Failed to toggle OpenAI", e);
    }
  };

  const handleSelectBuilding = (buildingId: string) => {
    setSelectedBuildingId(buildingId);
  };

  const handleResetCamera = () => {
    setSelectedBuildingId(null);
    setCameraResetTrigger((prev) => prev + 1);
  };

  // Calculate live statistics
  const activeAgentsCount = agents.filter((a) => a.status === "working").length;
  const inProgressTasksCount = tasks.filter((t) => t.status === "in_progress").length;
  const isMuseOnline = !!museStatus?.muse_server?.online;
  const isGologinReady = !!museStatus?.gologin_and_cookies?.gologin_token_configured;

  return (
    <div className="relative w-full h-[calc(100dvh-5.5rem)] lg:h-[calc(100dvh-4.5rem)] overflow-hidden rounded-2xl border border-border/50 bg-[#0f131a] select-none shadow-2xl">
      {/* 3D WebGL Canvas */}
      <FloatingCity3D
        selectedBuildingId={selectedBuildingId}
        onSelectBuilding={handleSelectBuilding}
        hoveredBuilding={hoveredBuilding}
        setHoveredBuilding={setHoveredBuilding}
        cameraResetTrigger={cameraResetTrigger}
      />

      {/* Game HUD Bar (Header & Quick Navigation) */}
      <CityHUD
        agentsCount={{ active: activeAgentsCount, total: agents.length }}
        tasksCount={{ inProgress: inProgressTasksCount, total: tasks.length }}
        mediaCount={mediaList.length}
        isMuseOnline={isMuseOnline}
        isGologinReady={isGologinReady}
        isOpenAiEnabled={isOpenAiEnabled}
        selectedBuildingId={selectedBuildingId}
        onSelectBuilding={handleSelectBuilding}
        onResetCamera={handleResetCamera}
        onToggleChat={() => setIsChatOpen((prev) => !prev)}
      />

      {/* Slide-out Architectural Building Module Drawer */}
      <BuildingDrawer
        buildingId={selectedBuildingId}
        onClose={() => setSelectedBuildingId(null)}
        agents={agents}
        tasks={tasks}
        mediaList={mediaList}
        museStatus={museStatus}
        isOpenAiEnabled={isOpenAiEnabled}
        onCeoAssign={handleCeoAssign}
        isAssigning={isAssigning}
        onGenerateMedia={handleTestGenerateMedia}
        isGenerating={isGenerating}
        genMessage={genMessage}
        onSaveAgentPrompt={handleSaveAgentPrompt}
        onRefreshData={fetchOfficeData}
        onToggleOpenAi={handleToggleOpenAi}
        onOpenLiveChat={() => setIsChatOpen(true)}
      />

      {/* Live Assistant & Zalo Auto-Fix Chat System */}
      <OfficeLiveChat
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        onOpen={() => setIsChatOpen(true)}
      />
    </div>
  );
}
