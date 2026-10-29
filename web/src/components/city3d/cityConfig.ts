export interface BuildingDef {
  id: string;
  name: string;
  subtitle: string;
  badge: string;
  color: string;
  roofColor: string;
  icon: string;
  islandIndex: number;
  position: [number, number, number]; // [x, y, z]
  size: [number, number, number]; // [width, height, depth]
  targetCamera: [number, number, number]; // Camera focus point
  description: string;
}

export interface IslandDef {
  id: string;
  name: string;
  position: [number, number, number]; // [x, y, z]
  size: [number, number, number]; // [width, height, depth]
  baseColor: string;
  topColor: string;
  elevation: number;
}

export const ISLANDS: IslandDef[] = [
  {
    id: "island-hq",
    name: "Đảo Trung Tâm - Bộ Chỉ Huy",
    position: [0, 0.4, 0],
    size: [9, 1.8, 9],
    baseColor: "#3a3028",
    topColor: "#4a7c59",
    elevation: 0.4,
  },
  {
    id: "island-agents",
    name: "Đảo Đông - Làng Trợ Lý AI",
    position: [11.5, 0.1, -1.5],
    size: [8, 1.6, 7.5],
    baseColor: "#322b26",
    topColor: "#568259",
    elevation: 0.1,
  },
  {
    id: "island-tasks",
    name: "Đảo Bắc - Trung Tâm Điều Phối",
    position: [-1.5, 0.2, -11.5],
    size: [8.5, 1.7, 7.5],
    baseColor: "#2d2824",
    topColor: "#4f7d61",
    elevation: 0.2,
  },
  {
    id: "island-media",
    name: "Đảo Tây - Xưởng Phim MuseAI",
    position: [-11.5, -0.1, 1],
    size: [8.5, 1.5, 8],
    baseColor: "#352c25",
    topColor: "#587f63",
    elevation: -0.1,
  },
  {
    id: "island-vault",
    name: "Đảo Nam - Kho Tài Khoản GoLogin",
    position: [-1, 0.3, 11],
    size: [7.5, 1.6, 7.5],
    baseColor: "#392f28",
    topColor: "#487352",
    elevation: 0.3,
  },
  {
    id: "island-observatory",
    name: "Đảo Đông Nam - Đài Quan Sát",
    position: [10, 0.6, 9.5],
    size: [7, 1.9, 7],
    baseColor: "#312822",
    topColor: "#3e664b",
    elevation: 0.6,
  },
];

export const BUILDINGS: BuildingDef[] = [
  {
    id: "hq",
    name: "Tòa Nhà Điều Hành",
    subtitle: "CEO Command & Master Control",
    badge: "BỘ CHỈ HUY",
    color: "#e8ecef",
    roofColor: "#2c3e50",
    icon: "Building2",
    islandIndex: 0,
    position: [0, 1.3, 0],
    size: [3.8, 4.8, 3.8],
    targetCamera: [0, 2.5, 0],
    description: "Trung tâm phát lệnh CEO, quản lý phân cấp trợ lý và điều hành toàn bộ văn phòng ảo.",
  },
  {
    id: "agents",
    name: "Làng Trợ Lý AI",
    subtitle: "AI Specialists & Workstations",
    badge: "TRỢ LÝ AI",
    color: "#f5ebe0",
    roofColor: "#d4a373",
    icon: "Users",
    islandIndex: 1,
    position: [11.5, 0.9, -1.5],
    size: [4.5, 3.2, 4],
    targetCamera: [11.5, 2, -1.5],
    description: "Khu vực làm việc chuyên trách của các Agent: phân quyền công cụ, sửa System Prompt và theo dõi trạng thái.",
  },
  {
    id: "tasks",
    name: "Trung Tâm Điều Phối",
    subtitle: "Kanban Queue & Workflow Dispatch",
    badge: "NHIỆM VỤ",
    color: "#e9ecef",
    roofColor: "#457b9d",
    icon: "Layers",
    islandIndex: 2,
    position: [-1.5, 1.05, -11.5],
    size: [4.4, 3.4, 4.2],
    targetCamera: [-1.5, 2.2, -11.5],
    description: "Điều phối tiến độ công việc, nhật ký thực thi từng bước và giao việc tự động cho các trợ lý.",
  },
  {
    id: "media",
    name: "Xưởng Phim MuseAI",
    subtitle: "Media Studio & Video Generator",
    badge: "KHO MEDIA",
    color: "#ede0d4",
    roofColor: "#9c6644",
    icon: "Video",
    islandIndex: 3,
    position: [-11.5, 0.75, 1],
    size: [4.8, 3.5, 4.4],
    targetCamera: [-11.5, 2, 1],
    description: "Trình tạo video và hình ảnh AI từ MuseAI Pool, lưu trữ thư viện thành phẩm và tải media về máy.",
  },
  {
    id: "vault",
    name: "Kho Tài Khoản & GoLogin",
    subtitle: "Cookie Pool & Security Vault",
    badge: "TÀI KHOẢN",
    color: "#e2e8f0",
    roofColor: "#b08968",
    icon: "Shield",
    islandIndex: 4,
    position: [-1, 1.1, 11],
    size: [3.8, 3.2, 3.8],
    targetCamera: [-1, 2.2, 11],
    description: "Quản lý Pool tài khoản Muse.ai, trạng thái cookie hoạt động và token GoLogin Orbita chống phát hiện.",
  },
  {
    id: "observatory",
    name: "Đài Quan Sát Hệ Thống",
    subtitle: "Telemetry & Performance Radar",
    badge: "QUAN SÁT",
    color: "#d8e2dc",
    roofColor: "#1d3557",
    icon: "Activity",
    islandIndex: 5,
    position: [10, 1.55, 9.5],
    size: [3.6, 3.6, 3.6],
    targetCamera: [10, 2.8, 9.5],
    description: "Quan sát sức khỏe máy chủ, thời gian phản hồi gateway, WebSocket thời gian thực và thông số tài nguyên.",
  },
];
