import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Grid, Line } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import URDFLoader from "urdf-loader";
import type { URDFRobot } from "urdf-loader";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

export const JOINT_MAP: Record<string, string> = {
  shoulder_pan: "Rotation",
  shoulder_lift: "Pitch",
  elbow_flex: "Elbow",
  wrist_flex: "Wrist_Pitch",
  wrist_roll: "Wrist_Roll",
  gripper: "Jaw",
};

// Feetech STS3215 서보: 0~4095 범위, 2048 = 중립(0rad), 4096 steps = 2π rad
function servoToRad(value: number): number {
  if (Math.abs(value) <= Math.PI * 2) return value;
  return (value - 2048) * (2 * Math.PI / 4096);
}

interface RobotModelProps {
  jointPositions: Record<string, number>;
  showTrail: boolean;
  isPlaying: boolean;
  trailKey: number;
}

function RobotModel({ jointPositions, showTrail, isPlaying, trailKey }: RobotModelProps) {
  const { scene } = useThree();
  const robotRef = useRef<URDFRobot | null>(null);
  const [robotLoaded, setRobotLoaded] = useState(false);
  const [trailPoints, setTrailPoints] = useState<[number, number, number][]>([]);
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  useEffect(() => {
    const loader = new URDFLoader();
    loader.packages = { so_arm_description: "/robots" };
    loader.loadMeshCb = (path, manager, done) => {
      new STLLoader(manager).load(
        path,
        (geom) => {
          geom.computeVertexNormals();
          const mat = new THREE.MeshPhongMaterial({
            color: 0x9b59b6,
            specular: 0x444444,
            shininess: 60,
          });
          done(new THREE.Mesh(geom, mat));
        },
        undefined,
        () => done(new THREE.Object3D())
      );
    };

    loader.load("/robots/so_arm101.urdf", (robot) => {
      robot.rotation.x = -Math.PI / 2;
      scene.add(robot);
      robotRef.current = robot;
      setRobotLoaded(true);
    });

    return () => {
      if (robotRef.current) {
        scene.remove(robotRef.current);
        robotRef.current = null;
      }
      setRobotLoaded(false);
    };
  }, [scene]);

  useEffect(() => {
    setTrailPoints([]);
  }, [trailKey]);

  useEffect(() => {
    const robot = robotRef.current;
    if (!robot || !robotLoaded) return;

    Object.entries(jointPositions).forEach(([datasetName, angle]) => {
      const urdfJointName = JOINT_MAP[datasetName];
      if (urdfJointName && robot.joints[urdfJointName]) {
        robot.joints[urdfJointName].setJointValue(servoToRad(angle));
      }
    });

    if (showTrail && isPlayingRef.current) {
      const endLink = robot.links["jaw"] ?? robot.links["gripper"];
      if (endLink) {
        const pos = new THREE.Vector3();
        endLink.getWorldPosition(pos);
        setTrailPoints((prev) => {
          const next: [number, number, number][] = [...prev, [pos.x, pos.y, pos.z]];
          // 슬라이딩 윈도우: 최근 30프레임만 유지해 꼬리처럼 사라짐
          return next.length > 30 ? next.slice(-30) : next;
        });
      }
    }
  }, [jointPositions, showTrail, robotLoaded]);

  // CatmullRomCurve3 보간 + 그라데이션 버텍스 컬러 계산
  const trailData = useMemo(() => {
    if (trailPoints.length < 2) return null;
    const vectors = trailPoints.map(([x, y, z]) => new THREE.Vector3(x, y, z));
    const curve = new THREE.CatmullRomCurve3(vectors);
    const pts = curve.getPoints(Math.min(trailPoints.length * 6, 500));
    const n = pts.length;
    const points: [number, number, number][] = [];
    const colors: [number, number, number][] = [];
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const ease = t * t;
      points.push([pts[i].x, pts[i].y, pts[i].z]);
      colors.push([ease * 0.05, ease * 0.95, ease * 1.0]);
    }
    const tip = trailPoints[trailPoints.length - 1];
    return { points, colors, tip };
  }, [trailPoints]);

  return (
    <>
      {showTrail && trailData && (
        <>
          <Line
            points={trailData.points}
            vertexColors={trailData.colors}
            lineWidth={7.5}
            toneMapped={false}
          />
          {/* 현재 위치 발광 구체 */}
          <mesh position={trailData.tip}>
            <sphereGeometry args={[0.005, 10, 10]} />
            <meshBasicMaterial color="#aaf8ff" toneMapped={false} />
          </mesh>
        </>
      )}
    </>
  );
}

interface RobotViewerProps {
  jointPositions: Record<string, number>;
  showTrail: boolean;
  isPlaying: boolean;
  trailKey: number;
}

export default function RobotViewer({
  jointPositions,
  showTrail,
  isPlaying,
  trailKey,
}: RobotViewerProps) {
  return (
    <Canvas
      camera={{ position: [0.4, 0.4, 0.4], fov: 45, near: 0.001, far: 10 }}
      style={{ background: "#0d1117" }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[1, 2, 1]} intensity={1.2} />
      <Grid
        position={[0, -0.01, 0]}
        args={[2, 2]}
        cellSize={0.1}
        sectionSize={0.5}
        cellColor="#1e293b"
        sectionColor="#334155"
        fadeDistance={3}
      />
      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
      <RobotModel
        jointPositions={jointPositions}
        showTrail={showTrail}
        isPlaying={isPlaying}
        trailKey={trailKey}
      />
    </Canvas>
  );
}
