"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Minus, Plus, MapPin, Navigation } from "lucide-react";
import {
  floorPlan,
  nearestRouteNode,
  places,
  routeEdges,
  routeLengthMeters,
  routeNodes,
  routePoints,
  worldToSource,
  type Robot,
  type PlaceId,
  type Point,
} from "@/lib/campus";
import { Fly } from "./fly";
import { Button } from "./ui/button";

const MIN_ZOOM = 0.8;
const MAX_ZOOM = 5;
const DESKTOP_ZOOM = 2.35;
const MOBILE_ZOOM = 1.45;
const DETAIL_ZOOM = 2.15;

function pathData(points: Point[]) {
  return points.map((point, index) => `${index ? "L" : "M"}${point.x} ${point.y}`).join(" ");
}

export function CampusMap({ robot, pickup, destination, onPickup }: { robot: Robot | null; pickup: PlaceId; destination: PlaceId; onPickup: (id: PlaceId) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ distance?: number; midpoint?: Point; moved: boolean }>({ moved: false });
  const [zoom, setZoom] = useState(DESKTOP_ZOOM);
  const [pan, setPan] = useState<Point>({ x: 180, y: 0 });
  const point = places.find((place) => place.id === pickup)!;
  const target = places.find((place) => place.id === destination)!;
  const robotPoint = worldToSource(robot ?? { x: 32.7, y: 58.6 });
  const robotNode = nearestRouteNode(robotPoint);
  const pickupRoute = useMemo(() => routePoints(robotNode, point.node), [robotNode, point.node]);
  const destinationRoute = useMemo(() => routePoints(point.node, target.node), [point.node, target.node]);
  const tripDistance = routeLengthMeters(destinationRoute);
  const viewCenter = useMemo(() => ({
    x: floorPlan.sourceOrigin.x + floorPlan.sourceSize.width / 2,
    y: floorPlan.sourceOrigin.y + floorPlan.sourceSize.height / 2,
  }), []);

  useEffect(() => {
    if (window.matchMedia("(max-width: 760px)").matches) {
      setZoom(MOBILE_ZOOM);
      setPan({ x: 0, y: 0 });
    }
  }, []);

  const tx = viewCenter.x * (1 - zoom) + pan.x;
  const ty = viewCenter.y * (1 - zoom) + pan.y;
  const transform = `translate(${tx} ${ty}) scale(${zoom})`;

  function clientToSvg(clientX: number, clientY: number): Point {
    const rect = svgRef.current!.getBoundingClientRect();
    const viewRatio = floorPlan.sourceSize.width / floorPlan.sourceSize.height;
    const rectRatio = rect.width / rect.height;
    const drawnWidth = rectRatio > viewRatio ? rect.height * viewRatio : rect.width;
    const drawnHeight = rectRatio > viewRatio ? rect.height : rect.width / viewRatio;
    const offsetX = (rect.width - drawnWidth) / 2;
    const offsetY = (rect.height - drawnHeight) / 2;
    return {
      x: floorPlan.sourceOrigin.x + ((clientX - rect.left - offsetX) / drawnWidth) * floorPlan.sourceSize.width,
      y: floorPlan.sourceOrigin.y + ((clientY - rect.top - offsetY) / drawnHeight) * floorPlan.sourceSize.height,
    };
  }

  function zoomAt(nextZoom: number, anchor: Point) {
    const bounded = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, nextZoom));
    const worldX = (anchor.x - tx) / zoom;
    const worldY = (anchor.y - ty) / zoom;
    setPan({
      x: anchor.x - worldX * bounded - viewCenter.x * (1 - bounded),
      y: anchor.y - worldY * bounded - viewCenter.y * (1 - bounded),
    });
    setZoom(bounded);
  }

  function stepZoom(direction: number) {
    zoomAt(zoom * (direction > 0 ? 1.25 : 0.8), viewCenter);
  }

  function onWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    zoomAt(zoom * Math.exp(-event.deltaY * 0.0015), clientToSvg(event.clientX, event.clientY));
  }

  function onPointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    gesture.current.moved = false;
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      gesture.current.distance = Math.hypot(a.x - b.x, a.y - b.y);
      gesture.current.midpoint = clientToSvg((a.x + b.x) / 2, (a.y + b.y) / 2);
    }
  }

  function onPointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const previous = pointers.current.get(event.pointerId);
    if (!previous) return;
    const current = { x: event.clientX, y: event.clientY };
    pointers.current.set(event.pointerId, current);
    gesture.current.moved = true;
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (gesture.current.distance && gesture.current.midpoint) zoomAt(zoom * (distance / gesture.current.distance), gesture.current.midpoint);
      gesture.current.distance = distance;
      gesture.current.midpoint = clientToSvg((a.x + b.x) / 2, (a.y + b.y) / 2);
      return;
    }
    const before = clientToSvg(previous.x, previous.y);
    const after = clientToSvg(current.x, current.y);
    setPan((value) => ({ x: value.x + after.x - before.x, y: value.y + after.y - before.y }));
  }

  function endPointer(event: React.PointerEvent<SVGSVGElement>) {
    pointers.current.delete(event.pointerId);
    gesture.current.distance = undefined;
    gesture.current.midpoint = undefined;
  }

  function resetView() {
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    setZoom(mobile ? MOBILE_ZOOM : DESKTOP_ZOOM);
    setPan(mobile ? { x: 0, y: 0 } : { x: 180, y: 0 });
  }

  return (
    <div className="map-shell">
      <div className="map-top">
        <span className="map-campus"><MapPin size={17} /> E5 + E7 · sixth floor</span>
        <span className="map-demo">{robot?.demo === false ? "HARDWARE FEED" : "CALIBRATED PLAN"}</span>
      </div>
      <div className="map-art indoor-map-art">
        <svg
          ref={svgRef}
          viewBox={`${floorPlan.sourceOrigin.x} ${floorPlan.sourceOrigin.y} ${floorPlan.sourceSize.width} ${floorPlan.sourceSize.height}`}
          className={pointers.current.size ? "campus-svg indoor-map-svg is-dragging" : "campus-svg indoor-map-svg"}
          role="img"
          aria-label="Interactive route map of Engineering 5 and Engineering 7. Scroll or pinch to zoom and drag to move."
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endPointer}
          onPointerCancel={endPointer}
        >
          <g transform={transform} className="map-transform">
            <image href={zoom >= DETAIL_ZOOM ? "/floor-plan.svg#detail" : "/floor-plan.svg#overview"} x={floorPlan.sourceOrigin.x} y={floorPlan.sourceOrigin.y} width={floorPlan.sourceSize.width} height={floorPlan.sourceSize.height} />
            <g className="route-network" aria-hidden="true">
              {routeEdges.map(([from, to]) => <line key={`${from}-${to}`} x1={routeNodes[from].x} y1={routeNodes[from].y} x2={routeNodes[to].x} y2={routeNodes[to].y} />)}
            </g>
            <path d={pathData([robotPoint, routeNodes[robotNode], ...pickupRoute.slice(1)])} className="active-route pickup-route" />
            <path d={pathData(destinationRoute)} className="active-route destination-route" />
            {places.map((place) => {
              const location = routeNodes[place.node];
              const important = place.id === pickup || place.id === destination;
              return (
                <g key={place.id} role="button" tabIndex={0} aria-label={`Set starting point to ${place.name}`} onClick={() => { if (!gesture.current.moved) onPickup(place.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPickup(place.id); } }} className={important ? "map-stop important" : "map-stop"}>
                  <circle cx={location.x} cy={location.y} r={important ? 18 : 13} fill={place.id === pickup ? "#285c9e" : place.id === destination ? "#ed4d4d" : "#fffdf7"} stroke={place.id === pickup ? "#285c9e" : place.id === destination ? "#ed4d4d" : "#7f8a95"} strokeWidth="5" />
                  {(important || zoom >= DETAIL_ZOOM) && <text className="place-label" x={location.x} y={location.y - 32}>{place.short}</text>}
                </g>
              );
            })}
            <g transform={`translate(${robotPoint.x},${robotPoint.y})`} className="robot-marker">
              <circle r="56" fill="#ff4d4d" opacity=".13" /><circle r="37" fill="#fff9c4" stroke="#2d2d2d" strokeWidth="5" />
              <foreignObject x="-43" y="-43" width="86" height="76"><Fly small /></foreignObject>
            </g>
          </g>
        </svg>
        <div className="map-compass"><Navigation size={23} /><span>N</span></div>
        <div className="map-controls">
          <Button variant="outline" size="icon" aria-label="Zoom in" disabled={zoom >= MAX_ZOOM} onClick={() => stepZoom(1)}><Plus size={19} /></Button>
          <Button variant="outline" size="icon" aria-label="Zoom out" disabled={zoom <= MIN_ZOOM} onClick={() => stepZoom(-1)}><Minus size={19} /></Button>
          <Button variant="outline" size="icon" aria-label="Reset map view" onClick={resetView}><Crosshair size={20} /></Button>
        </div>
        <span className="map-note">{tripDistance.toFixed(1)} m · scroll to zoom</span>
      </div>
    </div>
  );
}
