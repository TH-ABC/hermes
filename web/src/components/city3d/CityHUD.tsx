import React from "react";
import {
  Building2,
  Users,
  Layers,
  Video,
  Shield,
  Activity,
  RotateCcw,
  Sparkles,
  Compass,
  KeyRound,
} from "lucide-react";
import { BUILDINGS } from "./cityConfig";

interface CityHUDProps {
  agentsCount: { active: number; total: number };
  tasksCount: { inProgress: number; total: number };
  mediaCount: number;
  isMuseOnline: boolean;
  isGologinReady: boolean;
  isOpenAiEnabled: boolean;
  selectedBuildingId: string | null;
  onSelectBuilding: (buildingId: string) => void;
  onResetCamera: () => void;
  onToggleChat?: () => void;
}

export const CityHUD: React.FC<CityHUDProps> = ({
  agentsCount,
  tasksCount,
  mediaCount,
  isMuseOnline,
  isGologinReady,
  isOpenAiEnabled,
  selectedBuildingId,
  onSelectBuilding,
  onResetCamera,
  onToggleChat,
}) => {
  const getIcon = (iconName: string) => {
    switch (iconName) {
      case "Building2":
        return <Building2 className="h-4 w-4" />;
      case "Users":
        return <Users className="h-4 w-4" />;
      case "Layers":
        return <Layers className="h-4 w-4" />;
      case "Video":
        return <Video className="h-4 w-4" />;
      case "Shield":
        return <Shield className="h-4 w-4" />;
      case "Activity":
        return <Activity className="h-4 w-4" />;
      default:
        return <Sparkles className="h-4 w-4" />;
    }
  };

  return (
    <>
      {/* Top Header & HUD Stats Strip */}
      <div className="absolute top-4 inset-x-4 pointer-events-none z-10 flex flex-wrap items-center justify-between gap-3">
        {/* City Title Banner */}
        <div className="pointer-events-auto flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-card/80 border border-border/50 backdrop-blur-xl shadow-xl">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 text-white shadow-md shadow-orange-500/20">
            <Compass className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm tracking-wider uppercase text-foreground bg-clip-text">
                HERMES FLOATING CITY
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                3D DIORAMA
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Văn phòng điều hành trợ lý ảo đa tác vụ • Góc nhìn Isometric 3D
            </p>
          </div>
        </div>

        {/* Real-time KPI Stats Badges */}
        <div className="pointer-events-auto flex flex-wrap items-center gap-2">
          {/* Active Agents */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-card/85 border border-border/50 backdrop-blur-md shadow-sm text-xs">
            <Users className="h-3.5 w-3.5 text-sky-400" />
            <span className="text-muted-foreground">Trợ lý:</span>
            <span className="font-bold text-foreground font-mono">
              {agentsCount.active}/{agentsCount.total}
            </span>
          </div>

          {/* Running Tasks */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-card/85 border border-border/50 backdrop-blur-md shadow-sm text-xs">
            <Layers className="h-3.5 w-3.5 text-emerald-400" />
            <span className="text-muted-foreground">Nhiệm vụ:</span>
            <span className="font-bold text-foreground font-mono">
              {tasksCount.inProgress} đang chạy
            </span>
          </div>

          {/* Media Created */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-card/85 border border-border/50 backdrop-blur-md shadow-sm text-xs">
            <Video className="h-3.5 w-3.5 text-purple-400" />
            <span className="text-muted-foreground">Media:</span>
            <span className="font-bold text-foreground font-mono">
              {mediaCount} files
            </span>
          </div>

          {/* Muse Server Status */}
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border backdrop-blur-md text-xs font-medium ${
              isMuseOnline
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : "border-rose-500/40 bg-rose-500/10 text-rose-400"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${isMuseOnline ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`} />
            <span>Muse:8770 {isMuseOnline ? "ONLINE" : "OFFLINE"}</span>
          </div>

          {/* GoLogin Token Status */}
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border backdrop-blur-md text-xs font-medium ${
              isGologinReady
                ? "border-sky-500/40 bg-sky-500/10 text-sky-400"
                : "border-amber-500/40 bg-amber-500/10 text-amber-400"
            }`}
          >
            <Shield className="h-3 w-3" />
            <span>GoLogin: {isGologinReady ? "Sẵn sàng" : "Chưa token"}</span>
          </div>

          {/* OpenAI Key Status */}
          <button
            onClick={() => onSelectBuilding("vault")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border backdrop-blur-md text-xs font-bold transition hover:scale-105 cursor-pointer ${
              isOpenAiEnabled
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : "border-rose-500/40 bg-rose-500/15 text-rose-400 shadow-sm"
            }`}
            title="Nhấp để cấu hình và bật/tắt OpenAI Key"
          >
            <KeyRound className="h-3 w-3" />
            <span>OpenAI: {isOpenAiEnabled ? "BẬT" : "ĐÃ TẮT"}</span>
          </button>

          {/* Live Assistant & Zalo Fix Chat Button */}
          {onToggleChat && (
            <button
              onClick={onToggleChat}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-sky-500/40 bg-gradient-to-r from-sky-500/20 to-indigo-500/20 text-sky-300 font-bold text-xs backdrop-blur-md shadow-md transition hover:scale-105 active:scale-95 cursor-pointer"
              title="Mở kênh trò chuyện trực tuyến với Trợ lý và Fix lỗi Zalo"
            >
              <span className="text-sm">🤖</span>
              <span>Chat Trợ Lý (Fix Zalo)</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </button>
          )}
        </div>
      </div>

      {/* Bottom Fast-Travel Building Dock */}
      <div className="absolute bottom-6 inset-x-0 pointer-events-none z-10 flex flex-col items-center gap-2">
        {/* Navigation Dock */}
        <div className="pointer-events-auto flex items-center gap-1.5 p-2 rounded-2xl bg-card/90 border border-border/60 backdrop-blur-2xl shadow-2xl">
          {BUILDINGS.map((b) => {
            const isSelected = selectedBuildingId === b.id;
            return (
              <button
                key={b.id}
                onClick={() => onSelectBuilding(b.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  isSelected
                    ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30 scale-105"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                }`}
                title={b.description}
              >
                {getIcon(b.icon)}
                <span className="hidden md:inline">{b.name}</span>
              </button>
            );
          })}

          <div className="h-5 w-px bg-border/80 mx-1" />

          {/* Reset Camera button */}
          <button
            onClick={onResetCamera}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition"
            title="Đưa camera về góc nhìn toàn cảnh thành phố"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Toàn Cảnh</span>
          </button>
        </div>

        {/* Camera Hints Pill */}
        <div className="text-[11px] font-medium text-muted-foreground/75 px-3 py-1 rounded-full bg-background/50 backdrop-blur-sm border border-border/30">
          🎮 Chuột trái xoay góc nhìn • Chuột phải/Shift kéo map • Cuộn chuột phóng to/thu nhỏ
        </div>
      </div>
    </>
  );
};
