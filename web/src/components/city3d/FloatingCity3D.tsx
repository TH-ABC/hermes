import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { BUILDINGS, ISLANDS } from "./cityConfig";
import type { BuildingDef } from "./cityConfig";

interface FloatingCity3DProps {
  selectedBuildingId: string | null;
  onSelectBuilding: (buildingId: string) => void;
  hoveredBuilding: BuildingDef | null;
  setHoveredBuilding: (building: BuildingDef | null) => void;
  cameraResetTrigger: number;
}

export const FloatingCity3D: React.FC<FloatingCity3DProps> = ({
  selectedBuildingId,
  onSelectBuilding,
  hoveredBuilding,
  setHoveredBuilding,
  cameraResetTrigger,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const buildingMeshesRef = useRef<Map<string, THREE.Group>>(new Map());
  const animatedObjectsRef = useRef<{ obj: THREE.Object3D; speed: number; axis: "x" | "y" | "z"; type?: string }[]>([]);

  // Camera animation target state
  const cameraTargetRef = useRef<{
    pos: THREE.Vector3;
    lookAt: THREE.Vector3;
    active: boolean;
  }>({
    pos: new THREE.Vector3(25, 26, 25),
    lookAt: new THREE.Vector3(0, 1.5, 0),
    active: false,
  });

  const isDraggingRef = useRef(false);
  const isRightDragRef = useRef(false);
  const prevMouseRef = useRef({ x: 0, y: 0 });
  const sphericalRef = useRef({ radius: 40, theta: Math.PI / 4, phi: Math.PI / 3.4 });
  const centerTargetRef = useRef(new THREE.Vector3(0, 1.5, 0));

  // Initialize Scene
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene & Atmosphere
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color("#0f131a");
    scene.fog = new THREE.FogExp2("#0f131a", 0.013);

    // 2. Camera: Isometric 3/4 angle
    const camera = new THREE.PerspectiveCamera(34, width / height, 0.5, 250);
    cameraRef.current = camera;
    updateCameraFromSpherical();

    // 3. Renderer with high-end soft lighting
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    rendererRef.current = renderer;
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    // 4. Lighting System
    const ambientLight = new THREE.AmbientLight("#a2c2e8", 0.85);
    scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight("#fdfbf7", "#2c3e50", 0.7);
    hemiLight.position.set(0, 50, 0);
    scene.add(hemiLight);

    const sunLight = new THREE.DirectionalLight("#fff4e0", 2.2);
    sunLight.position.set(30, 45, 20);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 10;
    sunLight.shadow.camera.far = 120;
    const d = 26;
    sunLight.shadow.camera.left = -d;
    sunLight.shadow.camera.right = d;
    sunLight.shadow.camera.top = d;
    sunLight.shadow.camera.bottom = -d;
    sunLight.shadow.bias = -0.0005;
    scene.add(sunLight);

    const rimLight = new THREE.DirectionalLight("#60a5fa", 0.8);
    rimLight.position.set(-25, 20, -20);
    scene.add(rimLight);

    // 5. Build Floating Islands & Props
    const islandGroups = new THREE.Group();
    scene.add(islandGroups);

    ISLANDS.forEach((isl) => {
      const islGroup = new THREE.Group();
      islGroup.position.set(...isl.position);

      // Top grass / terrace platform (chamfered)
      const topGeo = new THREE.BoxGeometry(isl.size[0], 0.6, isl.size[2]);
      const topMat = new THREE.MeshStandardMaterial({
        color: isl.topColor,
        roughness: 0.75,
        metalness: 0.05,
        flatShading: true,
      });
      const topMesh = new THREE.Mesh(topGeo, topMat);
      topMesh.position.y = isl.size[1] / 2;
      topMesh.receiveShadow = true;
      topMesh.castShadow = true;
      islGroup.add(topMesh);

      // Floating bedrock cone/pyramid below island
      const rockHeight = isl.size[1] * 2.2;
      const rockGeo = new THREE.ConeGeometry(Math.min(isl.size[0], isl.size[2]) * 0.7, rockHeight, 6);
      rockGeo.rotateX(Math.PI);
      const rockMat = new THREE.MeshStandardMaterial({
        color: isl.baseColor,
        roughness: 0.9,
        metalness: 0.1,
        flatShading: true,
      });
      const rockMesh = new THREE.Mesh(rockGeo, rockMat);
      rockMesh.position.y = -rockHeight / 2 + 0.3;
      rockMesh.receiveShadow = true;
      rockMesh.castShadow = true;
      islGroup.add(rockMesh);

      // Island border stones / retaining wall
      const curbGeo = new THREE.BoxGeometry(isl.size[0] + 0.2, 0.25, isl.size[2] + 0.2);
      const curbMat = new THREE.MeshStandardMaterial({ color: "#7a6e65", roughness: 0.85, flatShading: true });
      const curb = new THREE.Mesh(curbGeo, curbMat);
      curb.position.y = isl.size[1] / 2 - 0.15;
      curb.receiveShadow = true;
      islGroup.add(curb);

      // Add cute decorative props (potted trees, streetlamps)
      addIslandDecorations(islGroup, isl);
      islandGroups.add(islGroup);
    });

    // 6. Connecting Bridges & Stepping Stones
    createBridges(islandGroups);

    // 7. Build Stylized Diorama Buildings
    buildingMeshesRef.current.clear();
    BUILDINGS.forEach((b) => {
      const bGroup = createBuildingGroup(b);
      scene.add(bGroup);
      buildingMeshesRef.current.set(b.id, bGroup);
    });

    // 8. Low-altitude Drifting Clouds
    const cloudsGroup = new THREE.Group();
    scene.add(cloudsGroup);
    for (let i = 0; i < 18; i++) {
      const cloud = createLowPolyCloud();
      cloud.position.set(
        (Math.random() - 0.5) * 70,
        -4.5 - Math.random() * 3.5,
        (Math.random() - 0.5) * 70
      );
      cloud.scale.setScalar(0.7 + Math.random() * 0.8);
      cloudsGroup.add(cloud);
      animatedObjectsRef.current.push({
        obj: cloud,
        speed: 0.01 + Math.random() * 0.015,
        axis: "x",
        type: "cloud",
      });
    }

    // 9. Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Smooth camera transition if active
      if (cameraTargetRef.current.active && cameraRef.current) {
        camera.position.lerp(cameraTargetRef.current.pos, 0.06);
        centerTargetRef.current.lerp(cameraTargetRef.current.lookAt, 0.06);
        camera.lookAt(centerTargetRef.current);

        if (camera.position.distanceTo(cameraTargetRef.current.pos) < 0.15) {
          cameraTargetRef.current.active = false;
        }
      }

      // Animate drifting clouds & rotating elements (radar, beacons)
      animatedObjectsRef.current.forEach((item) => {
        if (item.type === "cloud") {
          item.obj.position.x += item.speed;
          if (item.obj.position.x > 38) item.obj.position.x = -38;
        } else if (item.axis === "y") {
          item.obj.rotation.y += item.speed;
        } else if (item.axis === "z") {
          item.obj.rotation.z += item.speed;
        }
      });

      // Gentle floating bob on islands
      islandGroups.position.y = Math.sin(elapsed * 0.8) * 0.08;

      renderer.render(scene, camera);
    };
    animate();

    // 10. Resize handler
    const handleResize = () => {
      if (!containerRef.current || !cameraRef.current || !rendererRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      renderer.dispose();
      if (renderer.domElement.parentElement) {
        renderer.domElement.parentElement.removeChild(renderer.domElement);
      }
    };
  }, []);

  function updateCameraFromSpherical() {
    if (!cameraRef.current) return;
    const { radius, theta, phi } = sphericalRef.current;
    const x = radius * Math.sin(phi) * Math.sin(theta) + centerTargetRef.current.x;
    const y = radius * Math.cos(phi) + centerTargetRef.current.y;
    const z = radius * Math.sin(phi) * Math.cos(theta) + centerTargetRef.current.z;
    cameraRef.current.position.set(x, y, z);
    cameraRef.current.lookAt(centerTargetRef.current);
  }

  // Create Island Decorations (Trees, Lamps, Benches)
  const addIslandDecorations = (group: THREE.Group, isl: (typeof ISLANDS)[0]) => {
    const halfW = isl.size[0] / 2 - 0.7;
    const halfD = isl.size[2] / 2 - 0.7;
    const posY = isl.size[1] / 2;

    // Corner trees
    const treeCoords = [
      [-halfW, halfD],
      [halfW, -halfD],
      [-halfW, -halfD + 1],
    ];

    treeCoords.forEach(([tx, tz]) => {
      const tree = createStylizedTree();
      tree.position.set(tx, posY, tz);
      group.add(tree);
    });

    // Warm street lamppost
    const lamp = createStreetLamp();
    lamp.position.set(halfW, posY, halfD);
    group.add(lamp);
  };

  // Create Stylized Low-Poly Tree
  const createStylizedTree = () => {
    const tree = new THREE.Group();
    // Trunk
    const trunkGeo = new THREE.CylinderGeometry(0.12, 0.16, 0.9, 5);
    const trunkMat = new THREE.MeshStandardMaterial({ color: "#6b4226", roughness: 0.9, flatShading: true });
    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
    trunk.position.y = 0.45;
    trunk.castShadow = true;
    tree.add(trunk);

    // Leaves layers
    const leafMat = new THREE.MeshStandardMaterial({ color: "#2d6a4f", roughness: 0.8, flatShading: true });
    const leafGeo1 = new THREE.ConeGeometry(0.8, 1.1, 6);
    const leaves1 = new THREE.Mesh(leafGeo1, leafMat);
    leaves1.position.y = 1.1;
    leaves1.castShadow = true;
    tree.add(leaves1);

    const leafGeo2 = new THREE.ConeGeometry(0.65, 0.9, 6);
    const leaves2 = new THREE.Mesh(leafGeo2, leafMat);
    leaves2.position.y = 1.6;
    leaves2.castShadow = true;
    tree.add(leaves2);

    return tree;
  };

  // Create Cozy Street Lamp
  const createStreetLamp = () => {
    const lamp = new THREE.Group();
    const poleGeo = new THREE.CylinderGeometry(0.04, 0.05, 1.4, 5);
    const poleMat = new THREE.MeshStandardMaterial({ color: "#2b2d42", metalness: 0.8, roughness: 0.3 });
    const pole = new THREE.Mesh(poleGeo, poleMat);
    pole.position.y = 0.7;
    lamp.add(pole);

    const headGeo = new THREE.BoxGeometry(0.2, 0.25, 0.2);
    const headMat = new THREE.MeshStandardMaterial({
      color: "#ffdd80",
      emissive: "#ffb703",
      emissiveIntensity: 0.9,
    });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.y = 1.4;
    lamp.add(head);

    const pLight = new THREE.PointLight("#ffb703", 0.6, 6, 2);
    pLight.position.y = 1.4;
    lamp.add(pLight);

    return lamp;
  };

  // Create Stylized Low-Poly Cloud
  const createLowPolyCloud = () => {
    const cloud = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({
      color: "#ffffff",
      roughness: 0.95,
      metalness: 0.0,
      flatShading: true,
      transparent: true,
      opacity: 0.82,
    });

    const puffGeo = new THREE.DodecahedronGeometry(1.2, 0);
    const puff1 = new THREE.Mesh(puffGeo, mat);
    cloud.add(puff1);

    const puff2 = new THREE.Mesh(puffGeo, mat);
    puff2.position.set(1.1, -0.2, 0.2);
    puff2.scale.setScalar(0.75);
    cloud.add(puff2);

    const puff3 = new THREE.Mesh(puffGeo, mat);
    puff3.position.set(-1.0, -0.15, -0.1);
    puff3.scale.setScalar(0.7);
    cloud.add(puff3);

    return cloud;
  };

  // Connecting Wooden Bridges Between Islands
  const createBridges = (parent: THREE.Group) => {
    const connections = [
      { from: ISLANDS[0], to: ISLANDS[1] },
      { from: ISLANDS[0], to: ISLANDS[2] },
      { from: ISLANDS[0], to: ISLANDS[3] },
      { from: ISLANDS[0], to: ISLANDS[4] },
      { from: ISLANDS[0], to: ISLANDS[5] },
    ];

    connections.forEach(({ from, to }) => {
      const vFrom = new THREE.Vector3(...from.position);
      const vTo = new THREE.Vector3(...to.position);

      // Create 3 floating stone pads along the path
      for (let i = 1; i <= 3; i++) {
        const t = i / 4;
        const padPos = vFrom.clone().lerp(vTo, t);
        padPos.y -= 0.15 + Math.sin(t * Math.PI) * 0.15;

        const padGeo = new THREE.BoxGeometry(1.2, 0.35, 1.2);
        const padMat = new THREE.MeshStandardMaterial({ color: "#8d99ae", roughness: 0.85, flatShading: true });
        const pad = new THREE.Mesh(padGeo, padMat);
        pad.position.copy(padPos);
        pad.rotation.y = (i * Math.PI) / 6;
        pad.castShadow = true;
        pad.receiveShadow = true;
        parent.add(pad);
      }
    });
  };

  // Architectural Diorama Buildings (Cutaway interior details)
  const createBuildingGroup = (b: BuildingDef) => {
    const group = new THREE.Group();
    group.position.set(...b.position);
    group.name = `building-${b.id}`;

    // Base main walls
    const wallGeo = new THREE.BoxGeometry(b.size[0], b.size[1], b.size[2]);
    const wallMat = new THREE.MeshStandardMaterial({
      color: b.color,
      roughness: 0.65,
      metalness: 0.15,
      flatShading: true,
    });
    const walls = new THREE.Mesh(wallGeo, wallMat);
    walls.castShadow = true;
    walls.receiveShadow = true;
    walls.position.y = b.size[1] / 2;
    group.add(walls);

    // Architectural Roof
    const roofHeight = 0.9;
    const roofGeo = new THREE.BoxGeometry(b.size[0] + 0.3, roofHeight, b.size[2] + 0.3);
    const roofMat = new THREE.MeshStandardMaterial({
      color: b.roofColor,
      roughness: 0.45,
      metalness: 0.3,
      flatShading: true,
    });
    const roof = new THREE.Mesh(roofGeo, roofMat);
    roof.position.y = b.size[1] + roofHeight / 2 - 0.1;
    roof.castShadow = true;
    roof.receiveShadow = true;
    group.add(roof);

    // Cutaway Glass Windows (Glowing interior room)
    const windowGeo = new THREE.BoxGeometry(b.size[0] * 0.65, b.size[1] * 0.55, 0.15);
    const windowMat = new THREE.MeshStandardMaterial({
      color: "#90e0ef",
      emissive: "#0077b6",
      emissiveIntensity: 0.35,
      roughness: 0.2,
      metalness: 0.8,
      transparent: true,
      opacity: 0.88,
    });
    const winFront = new THREE.Mesh(windowGeo, windowMat);
    winFront.position.set(0, b.size[1] * 0.45, b.size[2] / 2 + 0.05);
    group.add(winFront);

    // Warm Interior Point Light
    const roomLight = new THREE.PointLight("#ffeedd", 0.9, 8);
    roomLight.position.set(0, b.size[1] * 0.5, b.size[2] * 0.2);
    group.add(roomLight);

    // Specific features by building type
    if (b.id === "hq") {
      // Antenna & Holographic Diamond
      const antGeo = new THREE.CylinderGeometry(0.04, 0.08, 1.8, 6);
      const antMat = new THREE.MeshStandardMaterial({ color: "#2b2d42", metalness: 0.9 });
      const ant = new THREE.Mesh(antGeo, antMat);
      ant.position.y = b.size[1] + roofHeight + 0.8;
      group.add(ant);

      const beaconGeo = new THREE.OctahedronGeometry(0.35, 0);
      const beaconMat = new THREE.MeshStandardMaterial({
        color: "#38bdf8",
        emissive: "#0284c7",
        emissiveIntensity: 1.2,
      });
      const beacon = new THREE.Mesh(beaconGeo, beaconMat);
      beacon.position.y = b.size[1] + roofHeight + 1.8;
      group.add(beacon);
      animatedObjectsRef.current.push({ obj: beacon, speed: 0.03, axis: "y" });
    } else if (b.id === "observatory") {
      // Rotating Radar Dome Dish
      const dishGeo = new THREE.CylinderGeometry(0.8, 0.4, 0.3, 8);
      const dishMat = new THREE.MeshStandardMaterial({ color: "#cbd5e1", metalness: 0.8, roughness: 0.2 });
      const dish = new THREE.Mesh(dishGeo, dishMat);
      dish.position.y = b.size[1] + roofHeight + 0.5;
      dish.rotation.x = Math.PI / 4;
      group.add(dish);
      animatedObjectsRef.current.push({ obj: dish, speed: 0.02, axis: "y" });
    } else if (b.id === "media") {
      // Media billboard screen
      const screenGeo = new THREE.BoxGeometry(2.4, 1.4, 0.2);
      const screenMat = new THREE.MeshStandardMaterial({
        color: "#fbbf24",
        emissive: "#d97706",
        emissiveIntensity: 0.85,
        roughness: 0.2,
      });
      const screen = new THREE.Mesh(screenGeo, screenMat);
      screen.position.set(0, b.size[1] + 1.2, 0);
      group.add(screen);

      // Camera tripod prop outside
      const tripGeo = new THREE.CylinderGeometry(0.08, 0.08, 1.2, 4);
      const tripMat = new THREE.MeshStandardMaterial({ color: "#1e293b", metalness: 0.7 });
      const trip = new THREE.Mesh(tripGeo, tripMat);
      trip.position.set(b.size[0] / 2 + 0.6, 0.6, b.size[2] / 2 + 0.6);
      group.add(trip);
    } else if (b.id === "tasks") {
      // Server rack glow
      const rackGeo = new THREE.BoxGeometry(0.6, 1.2, 0.4);
      const rackMat = new THREE.MeshStandardMaterial({
        color: "#10b981",
        emissive: "#059669",
        emissiveIntensity: 0.7,
      });
      const rack = new THREE.Mesh(rackGeo, rackMat);
      rack.position.set(b.size[0] / 2 + 0.5, 0.6, -b.size[2] / 2 + 0.6);
      group.add(rack);
    } else if (b.id === "vault") {
      // Golden vault crest
      const crestGeo = new THREE.TorusGeometry(0.4, 0.1, 6, 12);
      const crestMat = new THREE.MeshStandardMaterial({ color: "#eab308", metalness: 0.9, roughness: 0.2 });
      const crest = new THREE.Mesh(crestGeo, crestMat);
      crest.position.set(0, b.size[1] * 0.7, b.size[2] / 2 + 0.12);
      group.add(crest);
    }

    // Interactive Invisible Hitbox for precise raycasting
    const hitGeo = new THREE.BoxGeometry(b.size[0] * 1.3, b.size[1] * 1.4, b.size[2] * 1.3);
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    const hitMesh = new THREE.Mesh(hitGeo, hitMat);
    hitMesh.position.y = b.size[1] / 2;
    (hitMesh as any).buildingId = b.id;
    group.add(hitMesh);

    return group;
  };

  // Raycasting for Mouse Hover & Click
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    isDraggingRef.current = true;
    isRightDragRef.current = e.button === 2 || e.shiftKey;
    prevMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDraggingRef.current) {
      const dx = e.clientX - prevMouseRef.current.x;
      const dy = e.clientY - prevMouseRef.current.y;
      prevMouseRef.current = { x: e.clientX, y: e.clientY };

      if (isRightDragRef.current) {
        // Pan
        const panSpeed = 0.04;
        const forward = new THREE.Vector3();
        cameraRef.current?.getWorldDirection(forward);
        forward.y = 0;
        forward.normalize();
        const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();

        centerTargetRef.current.addScaledVector(right, -dx * panSpeed);
        centerTargetRef.current.addScaledVector(forward, dy * panSpeed);
      } else {
        // Orbit
        const rotSpeed = 0.005;
        sphericalRef.current.theta -= dx * rotSpeed;
        sphericalRef.current.phi = THREE.MathUtils.clamp(
          sphericalRef.current.phi - dy * rotSpeed,
          0.15,
          Math.PI / 2 - 0.08
        );
      }
      updateCameraFromSpherical();
      return;
    }

    // Hover raycast check
    if (!containerRef.current || !cameraRef.current || !sceneRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, cameraRef.current);
    const intersects = raycaster.intersectObjects(sceneRef.current.children, true);

    let foundBuilding: BuildingDef | null = null;
    for (const hit of intersects) {
      const bId = (hit.object as any).buildingId;
      if (bId) {
        foundBuilding = BUILDINGS.find((b) => b.id === bId) || null;
        break;
      }
    }

    if (foundBuilding?.id !== hoveredBuilding?.id) {
      setHoveredBuilding(foundBuilding);

      // Visual highlight lift on mesh
      buildingMeshesRef.current.forEach((grp, id) => {
        if (id === foundBuilding?.id) {
          grp.position.y = THREE.MathUtils.lerp(grp.position.y, grp.position.y + 0.35, 0.5);
          grp.scale.set(1.05, 1.05, 1.05);
        } else {
          const original = BUILDINGS.find((b) => b.id === id);
          if (original) grp.position.y = original.position[1];
          grp.scale.set(1, 1, 1);
        }
      });
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    isDraggingRef.current = false;

    // Check click detection (if barely moved)
    if (!containerRef.current || !cameraRef.current || !sceneRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, cameraRef.current);
    const intersects = raycaster.intersectObjects(sceneRef.current.children, true);

    for (const hit of intersects) {
      const bId = (hit.object as any).buildingId;
      if (bId) {
        onSelectBuilding(bId);
        break;
      }
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    sphericalRef.current.radius = THREE.MathUtils.clamp(
      sphericalRef.current.radius + e.deltaY * 0.04,
      12,
      75
    );
    updateCameraFromSpherical();
  };

  // Focus Camera smoothly on selected building
  useEffect(() => {
    if (!selectedBuildingId) return;
    const b = BUILDINGS.find((item) => item.id === selectedBuildingId);
    if (!b || !cameraRef.current) return;

    const targetPos = new THREE.Vector3(...b.targetCamera);
    const offset = new THREE.Vector3(12, 11, 12);

    cameraTargetRef.current = {
      pos: targetPos.clone().add(offset),
      lookAt: targetPos,
      active: true,
    };
  }, [selectedBuildingId]);

  // Reset Camera to Default
  useEffect(() => {
    if (cameraResetTrigger === 0) return;
    cameraTargetRef.current = {
      pos: new THREE.Vector3(26, 28, 26),
      lookAt: new THREE.Vector3(0, 1.5, 0),
      active: true,
    };
    sphericalRef.current = { radius: 42, theta: Math.PI / 4, phi: Math.PI / 3.4 };
    centerTargetRef.current.set(0, 1.5, 0);
  }, [cameraResetTrigger]);

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onWheel={handleWheel}
      onContextMenu={(e) => e.preventDefault()}
      className="relative w-full h-full select-none cursor-grab active:cursor-grabbing overflow-hidden"
    >
      {/* 3D Floating Building Hover Badge / Tooltip */}
      {hoveredBuilding && (
        <div className="absolute top-24 left-1/2 -translate-x-1/2 pointer-events-none transition-all duration-200 z-20">
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-card/90 border border-primary/40 backdrop-blur-xl shadow-2xl text-foreground animate-in fade-in zoom-in-95">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-foreground">{hoveredBuilding.name}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-mono bg-primary/20 text-primary border border-primary/30 uppercase">
                  {hoveredBuilding.badge}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{hoveredBuilding.subtitle}</p>
            </div>
            <span className="text-xs font-medium text-primary pl-2 border-l border-border/60">
              Nhấp để mở ➔
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
