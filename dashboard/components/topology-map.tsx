"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Grid, Line, Html, OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { useRef, useMemo } from "react";
import type { Group, Mesh } from "three";
import * as THREE from "three";
import { SystemHealth, HealthStatus } from "@/lib/types";

// ─────────────────────────────────────────────────────────────────────────────
// Types & Data
// ─────────────────────────────────────────────────────────────────────────────

interface ServiceNode {
  id: keyof SystemHealth;
  label: string;
  position: [number, number, number];
  baseColor: string;
}

const SERVICES: ServiceNode[] = [
  { id: "auth", label: "AUTH", position: [0, 1.2, 0], baseColor: "#10b981" },
  { id: "gateway", label: "GATEWAY", position: [0, 0, 0], baseColor: "#06b6d4" },
  { id: "db", label: "DB", position: [0.9, -0.9, 0], baseColor: "#f59e0b" },
];

const HEALTH_COLORS: Record<HealthStatus, string> = {
  healthy: "#10b981",
  degraded: "#f59e0b",
  critical: "#ef4444",
};

const CONNECTIONS: [from: keyof SystemHealth, to: keyof SystemHealth][] = [
  ["auth", "gateway"],
  ["gateway", "db"],
];

// ─────────────────────────────────────────────────────────────────────────────
// Animated Data Packet
// ─────────────────────────────────────────────────────────────────────────────

function DataPacket({
  from,
  to,
  color,
  initialProgress,
}: {
  from: THREE.Vector3;
  to: THREE.Vector3;
  color: string;
  initialProgress: number;
}) {
  const meshRef = useRef<Mesh>(null);
  const progress = useRef(initialProgress);

  useFrame((_, delta) => {
    if (meshRef.current) {
      progress.current += delta * 0.5;
      if (progress.current > 1) progress.current = 0;

      const pos = new THREE.Vector3().lerpVectors(from, to, progress.current);
      meshRef.current.position.copy(pos);
    }
  });

  return (
    <mesh ref={meshRef} position={from.clone()}>
      <sphereGeometry args={[0.03, 8, 8]} />
      <meshStandardMaterial
        color="#ffffff"
        emissive={color}
        emissiveIntensity={3}
        toneMapped={false}
      />
    </mesh>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Floating Ring Node with Core
// ─────────────────────────────────────────────────────────────────────────────

function RingNode({
  position,
  node,
  health,
}: {
  position: [number, number, number];
  node: ServiceNode;
  health: HealthStatus;
}) {
  const coreRef = useRef<Mesh>(null);
  const ringRef = useRef<Group>(null);

  const color = HEALTH_COLORS[health];

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (coreRef.current) {
      coreRef.current.scale.setScalar(1 + Math.sin(t * 3) * 0.1);
    }
    if (ringRef.current) {
      ringRef.current.rotation.x = Math.sin(t * 0.5) * 0.05;
      ringRef.current.rotation.z = Math.sin(t * 0.7) * 0.03;
    }
  });

  return (
    <group position={position}>
      {/* Outer floating ring */}
      <group ref={ringRef}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.22, 0.015, 12, 48]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={0.8}
            metalness={0.9}
            roughness={0.1}
          />
        </mesh>

        {/* Inner glow ring */}
        <mesh rotation={[Math.PI / 2, 0.2, 0]}>
          <torusGeometry args={[0.15, 0.008, 12, 32]} />
          <meshStandardMaterial
            color="#ffffff"
            emissive={color}
            emissiveIntensity={1.5}
            toneMapped={false}
          />
        </mesh>
      </group>

      {/* Pulsing core */}
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.08, 1]} />
        <meshStandardMaterial
          color="#ffffff"
          emissive={color}
          emissiveIntensity={2}
          toneMapped={false}
        />
      </mesh>

      {/* Wireframe cage */}
      <mesh>
        <icosahedronGeometry args={[0.14, 0]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.25} />
      </mesh>

      {/* Compact HTML Label */}
      <Html position={[0.28, 0.18, 0]} center style={{ pointerEvents: "none" }}>
        <div
          className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm"
          style={{
            background: "rgba(0, 0, 0, 0.85)",
            border: `1px solid ${color}40`,
            boxShadow: `0 0 6px ${color}30`,
          }}
        >
          <div className="w-1 h-1 rounded-full" style={{ background: color }} />
          <span
            className="text-[8px] font-mono font-bold tracking-wide"
            style={{ color }}
          >
            {node.label}
          </span>
        </div>
      </Html>
    </group>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Connection Lines with Packets
// ─────────────────────────────────────────────────────────────────────────────

function NetworkConnections({ systemHealth}: { systemHealth: SystemHealth }) {
  const packets = useMemo(() => {
    return CONNECTIONS.map(([fromId, toId], index) => {
      const fromNode = SERVICES.find((s) => s.id === fromId)!;
      const toNode = SERVICES.find((s) => s.id === toId)!;
      return {
        id: `${fromId}-${toId}`,
        from: new THREE.Vector3(...fromNode.position),
        to: new THREE.Vector3(...toNode.position),
        color: HEALTH_COLORS[systemHealth[fromId]] || "#10b981",
        initialProgress: ((index + 1) * 0.17) % 0.5,
      };
    });
  }, [systemHealth]);

  return (
    <>
      {packets.map((packet) => (
        <group key={packet.id}>
          {/* Glow line */}
          <Line
            points={[packet.from, packet.to]}
            color={packet.color}
            lineWidth={1.5}
            opacity={0.6}
            transparent
          />
          {/* Core line */}
          <Line
            points={[packet.from, packet.to]}
            color="#ffffff"
            lineWidth={0.3}
            opacity={0.2}
            transparent
          />
          {/* Animated data packet */}
          <DataPacket
            from={packet.from}
            to={packet.to}
            color={packet.color}
            initialProgress={packet.initialProgress}
          />
        </group>
      ))}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Cyber Grid Floor
// ─────────────────────────────────────────────────────────────────────────────

function CyberGrid() {
  return (
    <group rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.8, 0]}>
      <Grid
        position={[0, 0, 0]}
        args={[10, 10]}
        cellSize={0.4}
        cellThickness={0.3}
        cellColor="#10b981"
        sectionSize={1.5}
        sectionThickness={0.6}
        sectionColor="#064e3b"
        fadeDistance={6}
        fadeStrength={1}
        infiniteGrid
      />
    </group>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Scene Content
// ─────────────────────────────────────────────────────────────────────────────

function SceneContent({ systemHealth }: { systemHealth: SystemHealth }) {
  const groupRef = useRef<Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08;
    }
  });

  return (
    <group ref={groupRef} position={[0, -0.2, 0]}>
      {SERVICES.map((service) => (
        <RingNode
          key={service.id}
          position={service.position}
          node={service}
          health={systemHealth[service.id]}
        />
      ))}
      <NetworkConnections systemHealth={systemHealth} />
    </group>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Export Component
// ─────────────────────────────────────────────────────────────────────────────

interface TopologyMapProps {
  systemHealth: SystemHealth;
}

export function TopologyMap({ systemHealth }: TopologyMapProps) {
  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg isolate">
      {/* Header overlay */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-3 py-2 bg-gradient-to-b from-zinc-950 via-zinc-950/80 to-transparent">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
            Topology Map
          </h2>
        </div>
        <div className="flex items-center gap-2 text-[8px] font-mono text-zinc-600">
          {SERVICES.map((s) => (
            <span key={s.id} className="flex items-center gap-1">
              <span
                className="w-1 h-1 rounded-full"
                style={{ background: HEALTH_COLORS[systemHealth[s.id]] }}
              />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* Three.js Canvas */}
      <Canvas
        className="!h-full !w-full"
        camera={{ fov: 75, position: [0, 0, 4.5] }}
        gl={{ antialias: true, alpha: false }}
        style={{ background: "#000000" }}
      >
        <EffectComposer>
          <Bloom
            intensity={1.2}
            luminanceThreshold={0.1}
            luminanceSmoothing={0.9}
            mipmapBlur
          />
        </EffectComposer>

        <ambientLight intensity={0.15} />
        <pointLight position={[3, 3, 3]} intensity={0.4} color="#10b981" />
        <pointLight position={[-3, 2, -2]} intensity={0.3} color="#06b6d4" />

        <SceneContent systemHealth={systemHealth} />
        <CyberGrid />

        <OrbitControls
          enableZoom={false}
          enablePan={false}
          minPolarAngle={Math.PI / 3}
          maxPolarAngle={Math.PI / 2}
          minAzimuthAngle={-Math.PI / 6}
          maxAzimuthAngle={Math.PI / 6}
          rotateSpeed={0.2}
        />
      </Canvas>
    </div>
  );
}
