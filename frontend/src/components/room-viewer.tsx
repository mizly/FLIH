"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { AlertTriangle, Box, LoaderCircle, RotateCcw } from "lucide-react";
import { Button } from "./ui/button";

type RoomViewerProps = {
  onExit: () => void;
};

export function RoomViewer({ onExit }: RoomViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const renderCanvas = canvas;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#dfe8e7");
    scene.fog = new THREE.Fog("#dfe8e7", 18, 38);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(7.2, 4.8, 8.4);

    const renderer = new THREE.WebGLRenderer({ canvas: renderCanvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;

    const hemiLight = new THREE.HemisphereLight("#fffaf0", "#71808b", 2.4);
    scene.add(hemiLight);
    const keyLight = new THREE.DirectionalLight("#fff6dc", 4.2);
    keyLight.position.set(5, 11, 5);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight("#b9d9e8", 1.8);
    fillLight.position.set(-8, 5, -5);
    scene.add(fillLight);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(16, 64),
      new THREE.MeshStandardMaterial({ color: "#c7d4d1", roughness: 0.96 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const grid = new THREE.GridHelper(30, 30, "#91a6a7", "#b5c4c1");
    grid.position.y = 0.01;
    grid.material.transparent = true;
    grid.material.opacity = 0.5;
    scene.add(grid);

    const controls = new OrbitControls(camera, renderCanvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 2.2;
    controls.maxDistance = 22;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.target.set(0, 1.6, 0);

    let animationFrame = 0;
    let disposed = false;
    let model: THREE.Object3D | null = null;

    function resize() {
      const width = renderCanvas.clientWidth || 1;
      const height = renderCanvas.clientHeight || 1;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(renderCanvas);
    resize();

    const loader = new GLTFLoader();
    loader.load(
      "/room.glb",
      (gltf) => {
        if (disposed) return;
        model = gltf.scene;
        const bounds = new THREE.Box3().setFromObject(model);
        const size = bounds.getSize(new THREE.Vector3());
        const maxDimension = Math.max(size.x, size.y, size.z) || 1;
        model.scale.setScalar(8 / maxDimension);

        const scaledBounds = new THREE.Box3().setFromObject(model);
        const scaledCenter = scaledBounds.getCenter(new THREE.Vector3());
        model.position.x -= scaledCenter.x;
        model.position.z -= scaledCenter.z;
        model.position.y -= scaledBounds.min.y;

        model.traverse((object) => {
          if (object instanceof THREE.Mesh) {
            object.castShadow = true;
            object.receiveShadow = true;
          }
        });
        scene.add(model);
        controls.target.set(0, Math.max(1.2, Math.min(2.5, size.y * 0.3)), 0);
        controls.update();
        setStatus("ready");
      },
      undefined,
      () => {
        if (!disposed) setStatus("error");
      },
    );

    function animate() {
      if (disposed) return;
      animationFrame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      ground.geometry.dispose();
      (ground.material as THREE.Material).dispose();
      if (model) {
        model.traverse((object) => {
          if (!(object instanceof THREE.Mesh)) return;
          object.geometry.dispose();
          if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
          else object.material.dispose();
        });
      }
    };
  }, []);

  return (
    <div className="room-viewer">
      <canvas ref={canvasRef} className="room-viewer-canvas" aria-label="Interactive 3D view of Room 6002" />
      <div className="room-viewer-heading">
        <div className="room-viewer-title"><Box size={18} /><div><strong>Room 6002</strong><span>3D street view · E5 sixth floor</span></div></div>
        <Button variant="outline" size="icon" aria-label="Return to floor plan" onClick={onExit}><RotateCcw size={18} /></Button>
      </div>
      <div className="room-viewer-anchor"><span className="room-anchor-dot" /> Model anchored to the highlighted area <small>Drag to look around · scroll to zoom</small></div>
      {status === "loading" && <div className="room-viewer-status"><LoaderCircle className="spin" size={22} /><span>Loading room.glb…</span></div>}
      {status === "error" && <div className="room-viewer-status room-viewer-error"><AlertTriangle size={22} /><span>Couldn’t load room.glb. Check that the model is available.</span></div>}
    </div>
  );
}
