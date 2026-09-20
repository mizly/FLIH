"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { MeshSurfaceSampler } from "three/examples/jsm/math/MeshSurfaceSampler.js";
import type { TrainingSnapshot } from "@/lib/training-types";

type Activity = TrainingSnapshot["neural_activity"];
function mappedNeurons(activity: Activity) {
  if (
    activity?.coordinate_status === "unsupported_dataset" ||
    activity?.coordinate_status === "unavailable"
  )
    return [];
  return (activity?.neurons ?? []).filter(
    (neuron) =>
      neuron.position?.length === 3 &&
      neuron.position.every(Number.isFinite) &&
      Number.isFinite(neuron.activation),
  );
}

type AtlasRegion = { name: string; positions: number[]; indices: number[] };
type View = "Front" | "Side" | "Top";
type Viewer = {
  view: (view: View) => void;
  zoom: (factor: number) => void;
  surface: (enabled: boolean) => void;
  activity: (activity: Activity) => void;
};

type BrainViewerProps = {
  activity?: Activity;
  autoRotate?: boolean;
  compact?: boolean;
};

export default function BrainViewer({
  activity,
  autoRotate = false,
  compact = false,
}: BrainViewerProps) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [status, setStatus] = useState("Loading brain anatomy…");
  const [ready, setReady] = useState(false);
  const [surface, setSurface] = useState(false);
  const mapped = mappedNeurons(activity).length;

  useEffect(() => {
    const container = host.current!;
    const abort = new AbortController();
    let disposed = false;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        preserveDrawingBuffer: true,
      });
    } catch {
      setStatus(
        "3D rendering requires WebGL. Open the FAFB source in Explore.",
      );
      return;
    }
    renderer.setClearColor("#0b1418");
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute(
      "aria-label",
      "Interactive 3D bilateral FAFB fly-brain connectome anatomy. Drag to rotate; scroll to zoom. Arrow keys rotate; plus and minus zoom; Home resets.",
    );
    renderer.domElement.tabIndex = 0;
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.minDistance = 5;
    controls.maxDistance = 24;
    controls.rotateSpeed = 0.7;
    controls.zoomSpeed = 0.75;
    controls.autoRotate =
      autoRotate &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    controls.autoRotateSpeed = 0.45;
    const atlas = new THREE.Group();
    scene.add(atlas, new THREE.HemisphereLight(0xc5e8ed, 0x263a42, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2.5);
    light.position.set(-4, 5, 8);
    scene.add(light);
    const material = new THREE.MeshPhongMaterial({
      color: 0x789da8,
      transparent: true,
      opacity: 0.035,
      depthWrite: false,
      side: THREE.DoubleSide,
      shininess: 45,
    });
    const pointMaterial = new THREE.PointsMaterial({
      color: 0xc2d8dd,
      size: 0.009,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      sizeAttenuation: true,
    });
    const geometries: THREE.BufferGeometry[] = [];
    const activityGeometry = new THREE.BufferGeometry();
    activityGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute([], 3),
    );
    activityGeometry.setAttribute(
      "activation",
      new THREE.Float32BufferAttribute([], 1),
    );
    // Soft luminous markers at real annotation anchors. Magnitude controls size
    // and brightness directly: no synthetic firing or time-driven blinking.
    const activityMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.AdditiveBlending,
      uniforms: { pixelRatio: { value: Math.min(window.devicePixelRatio, 2) } },
      vertexShader: `
        attribute float activation;
        uniform float pixelRatio;
        varying float strength;
        varying vec3 tint;
        void main() {
          strength = clamp(abs(activation), 0.0, 1.0);
          tint = activation >= 0.0 ? vec3(0.27, 1.0, 0.73) : vec3(1.0, 0.40, 0.16);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = (8.0 + 22.0 * sqrt(strength)) * pixelRatio;
        }
      `,
      fragmentShader: `
        varying float strength;
        varying vec3 tint;
        void main() {
          float radius = length(gl_PointCoord - vec2(0.5)) * 2.0;
          if (radius > 1.0 || strength < 0.001) discard;
          float halo = exp(-5.0 * radius * radius) * (1.0 - smoothstep(0.75, 1.0, radius));
          float core = 1.0 - smoothstep(0.0, 0.24, radius);
          gl_FragColor = vec4(mix(tint, vec3(1.0), core * 0.7), halo * strength);
        }
      `,
    });
    const signals = new THREE.Points(activityGeometry, activityMaterial);
    signals.renderOrder = 10;
    signals.frustumCulled = false;
    scene.add(signals);
    const draw = () => {
      if (!disposed) renderer.render(scene, camera);
    };
    let fitDistance = 11;
    const view = (name: View) => {
      camera.up.set(0, 1, 0);
      if (name === "Top") {
        camera.up.set(0, 0, -1);
        camera.position.set(0, fitDistance, 0.001);
      } else if (name === "Side") camera.position.set(fitDistance, 0, 0);
      else camera.position.set(0, 0, fitDistance);
      controls.target.set(0, 0, 0);
      controls.update();
      draw();
    };
    const zoom = (factor: number) => {
      camera.position
        .multiplyScalar(factor)
        .clampLength(controls.minDistance, controls.maxDistance);
      controls.update();
      draw();
    };
    viewer.current = {
      view,
      zoom,
      activity: (sample) => {
        const neurons = mappedNeurons(sample);
        // Release previous GPU attributes before replacing a telemetry sample.
        activityGeometry.dispose();
        activityGeometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(
            neurons.flatMap((neuron) => neuron.position!),
            3,
          ),
        );
        activityGeometry.setAttribute(
          "activation",
          new THREE.Float32BufferAttribute(
            neurons.map((neuron) =>
              Math.max(-1, Math.min(1, neuron.activation)),
            ),
            1,
          ),
        );
        activityGeometry.setDrawRange(0, neurons.length);
        draw();
      },
      surface: (enabled) => {
        material.opacity = enabled ? 0.94 : 0.035;
        material.depthWrite = enabled;
        pointMaterial.opacity = enabled ? 0.12 : 0.55;
        draw();
      },
    };
    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      const previousFit = fitDistance;
      fitDistance = Math.max(
        8.5,
        3.6 / (Math.tan(THREE.MathUtils.degToRad(19)) * camera.aspect),
      );
      camera.position.multiplyScalar(fitDistance / previousFit);
      renderer.setSize(width, height);
      controls.update();
      draw();
    };
    view("Front");
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    controls.addEventListener("change", draw);
    let animationFrame = 0;
    const animate = () => {
      if (disposed || !controls.autoRotate) return;
      controls.update();
      animationFrame = requestAnimationFrame(animate);
    };
    if (controls.autoRotate) animationFrame = requestAnimationFrame(animate);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Home") view("Front");
      else if (event.key === "+" || event.key === "=") zoom(0.85);
      else if (event.key === "-") zoom(1.15);
      else if (event.key.startsWith("Arrow")) {
        const offset = new THREE.Spherical().setFromVector3(camera.position);
        if (event.key === "ArrowLeft") offset.theta -= 0.15;
        if (event.key === "ArrowRight") offset.theta += 0.15;
        if (event.key === "ArrowUp") offset.phi -= 0.15;
        if (event.key === "ArrowDown") offset.phi += 0.15;
        offset.makeSafe();
        camera.position.setFromSpherical(offset);
        controls.update();
        draw();
      } else return;
      event.preventDefault();
    };
    renderer.domElement.addEventListener("keydown", onKey);
    fetch("/brain/neuropils.json", { signal: abort.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Atlas unavailable");
        return response.json() as Promise<AtlasRegion[]>;
      })
      .then((regions) => {
        if (disposed) return;
        // Area-weighted samples retain the actual atlas surface, not invented neurons.
        let seed = 783;
        const random = () => {
          seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
          return seed / 4294967296;
        };
        const samples: number[] = [];
        const point = new THREE.Vector3();
        for (const region of regions) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute(
            "position",
            new THREE.Float32BufferAttribute(region.positions, 3),
          );
          geometry.setIndex(region.indices);
          geometry.computeVertexNormals();
          geometries.push(geometry);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = region.name;
          atlas.add(mesh);
          // Three r186 exposes this method; its DefinitelyTyped declaration lags.
          const sampler = new MeshSurfaceSampler(mesh) as MeshSurfaceSampler & {
            setRandomGenerator(random: () => number): MeshSurfaceSampler;
          };
          sampler.setRandomGenerator(random).build();
          const count = Math.max(150, Math.floor(region.indices.length / 6));
          for (let i = 0; i < count; i++) {
            sampler.sample(point);
            samples.push(point.x, point.y, point.z);
          }
        }
        const points = new THREE.BufferGeometry();
        points.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(samples, 3),
        );
        geometries.push(points);
        atlas.add(new THREE.Points(points, pointMaterial));
        setStatus("");
        setReady(true);
        draw();
      })
      .catch((error: unknown) => {
        if (
          !disposed &&
          !(error instanceof DOMException && error.name === "AbortError")
        )
          setStatus(
            "Brain anatomy could not load. Reload to try again, or open Explore.",
          );
      });
    const lost = (event: Event) => {
      event.preventDefault();
      setReady(false);
      setStatus("3D graphics interrupted. Reload to restore the brain view.");
    };
    renderer.domElement.addEventListener("webglcontextlost", lost);
    return () => {
      disposed = true;
      abort.abort();
      viewer.current = null;
      observer.disconnect();
      cancelAnimationFrame(animationFrame);
      controls.dispose();
      renderer.domElement.removeEventListener("keydown", onKey);
      renderer.domElement.removeEventListener("webglcontextlost", lost);
      geometries.forEach((geometry) => geometry.dispose());
      material.dispose();
      pointMaterial.dispose();
      activityGeometry.dispose();
      activityMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [autoRotate]);

  useEffect(() => {
    viewer.current?.activity(activity);
  }, [activity, ready]);

  return (
    <>
      <div
        ref={host}
        className="brain-viewport"
        data-ready={ready}
        data-mapped-neurons={mapped}
      />
      {status && (
        <div className="brain-load-message" role="note">
          {status}
        </div>
      )}
      {!compact && (
        <>
          <div
            className="brain-view-controls"
            aria-label="Brain camera controls"
          >
            {(["Front", "Side", "Top"] as const).map((name) => (
              <button
                key={name}
                disabled={!ready}
                onClick={() => viewer.current?.view(name)}
                aria-label={`${name} brain view`}
              >
                {name}
              </button>
            ))}
            <span />
            <button
              disabled={!ready}
              onClick={() => viewer.current?.zoom(0.85)}
              aria-label="Zoom in on brain"
            >
              +
            </button>
            <button
              disabled={!ready}
              onClick={() => viewer.current?.zoom(1.15)}
              aria-label="Zoom out of brain"
            >
              −
            </button>
            <button
              disabled={!ready}
              aria-pressed={surface}
              onClick={() => {
                viewer.current?.surface(!surface);
                setSurface(!surface);
              }}
            >
              Surface
            </button>
          </div>
          <div className="brain-interaction-hint">
            Drag to rotate · Scroll or pinch to zoom
          </div>
          <div className="brain-activity-coverage">
            {activity?.coordinate_status === "unavailable"
              ? "Neuron coordinates unavailable"
              : activity?.coordinate_status === "unsupported_dataset"
                ? "No coordinate map for this dataset"
                : activity?.neurons.length
                  ? `${mapped}/${activity.neurons.length} sampled neurons located`
                  : "Waiting for measured neuron activity"}
          </div>
        </>
      )}
    </>
  );
}
