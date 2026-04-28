import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import { useEffect, useRef, useState } from "react";
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

interface RobotModelProps {
  jointPositions: Record<string, number>;
  onEndEffectorPos?: (pos: [number, number, number]) => void;
  trailPositions: [number, number, number][];
  showTrail: boolean;
}

function RobotModel({ jointPositions, onEndEffectorPos, trailPositions, showTrail }: RobotModelProps) {
  const { scene } = useThree();
  const robotRef = useRef<URDFRobot | null>(null);
  const [robotLoaded, setRobotLoaded] = useState(false);

  useEffect(() => {
    const loader = new URDFLoader();
    loader.packages = { so_arm_description: "/robots" };
    loader.loadMeshCb = (path, manager, done) => {
      new STLLoader(manager).load(
        path,
        (geom) => {
          geom.computeVertexNormals();
          const mat = new THREE.MeshPhongMaterial({
            color: 0xffd124,
            specular: 0x333333,
            shininess: 40,
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
    const robot = robotRef.current;
    if (!robot) return;

    Object.entries(jointPositions).forEach(([datasetName, angle]) => {
      const urdfJointName = JOINT_MAP[datasetName];
      if (urdfJointName && robot.joints[urdfJointName]) {
        robot.joints[urdfJointName].setJointValue(angle);
      }
    });

    if (onEndEffectorPos) {
      const endLink = robot.links["jaw"] ?? robot.links["gripper"];
      if (endLink) {
        const pos = new THREE.Vector3();
        endLink.getWorldPosition(pos);
        onEndEffectorPos([pos.x, pos.y, pos.z]);
      }
    }
  }, [jointPositions, onEndEffectorPos, robotLoaded]);

  return (
    <>
      {showTrail && trailPositions.length > 1 && (
        <line>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array(trailPositions.flat()), 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#f97316" linewidth={2} />
        </line>
      )}
    </>
  );
}

interface RobotViewerProps {
  jointPositions: Record<string, number>;
  trailPositions: [number, number, number][];
  showTrail: boolean;
  onEndEffectorPos?: (pos: [number, number, number]) => void;
}

export default function RobotViewer({
  jointPositions,
  trailPositions,
  showTrail,
  onEndEffectorPos,
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
        trailPositions={trailPositions}
        showTrail={showTrail}
        onEndEffectorPos={onEndEffectorPos}
      />
    </Canvas>
  );
}
