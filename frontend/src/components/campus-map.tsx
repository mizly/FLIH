"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Box, Crosshair, Map as MapIcon, Minus, Plus, MapPin, Navigation } from "lucide-react";
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
import { RoomViewer } from "./room-viewer";
import { Button } from "./ui/button";

const MIN_ZOOM = 0.8;
const MAX_ZOOM = 5;
const DESKTOP_ZOOM = 2.35;
const MOBILE_ZOOM = 1.45;
const STANDARD_LABEL_ZOOM = 1.45;
const DETAIL_ZOOM = 2.65;
const ENDPOINT_MARKER_SCALE = 3;
type EndpointKind = "start" | "end";

function pathData(points: Point[]) {
  return points.map((point, index) => `${index ? "L" : "M"}${point.x} ${point.y}`).join(" ");
}

export function CampusMap({ robot, pickup, destination, onPickup, onDestination }: { robot: Robot | null; pickup: PlaceId | null; destination: PlaceId | null; onPickup: (id: PlaceId) => void; onDestination: (id: PlaceId) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ distance?: number; midpoint?: Point; moved: boolean }>({ moved: false });
  const endpointDrag = useRef<{ kind: EndpointKind; pointerId: number } | null>(null);
  const [zoom, setZoom] = useState(DESKTOP_ZOOM);
  const [pan, setPan] = useState<Point>({ x: 180, y: 0 });
  const [floorPlanMarkup, setFloorPlanMarkup] = useState("");
  const [draggingEndpoint, setDraggingEndpoint] = useState<EndpointKind | null>(null);
  const [dragPosition, setDragPosition] = useState<Point | null>(null);
  const [dropTarget, setDropTarget] = useState<PlaceId | null>(null);
  const [viewMode, setViewMode] = useState<"plan" | "street">("plan");
  const point = places.find((place) => place.id === pickup);
  const target = places.find((place) => place.id === destination);
  const robotPoint = worldToSource(robot ?? { x: 32.7, y: 58.6 });
  const robotNode = nearestRouteNode(robotPoint);
  const pickupRoute = useMemo(() => point ? routePoints(robotNode, point.node) : [], [robotNode, point]);
  const destinationRoute = useMemo(() => point && target ? routePoints(point.node, target.node) : [], [point, target]);
  const tripDistance = destinationRoute.length ? routeLengthMeters(destinationRoute) : null;
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

  useEffect(() => {
    let active = true;
    void fetch("/floor-plan.svg")
      .then((response) => response.text())
      .then((markup) => {
        if (active) setFloorPlanMarkup(markup.replace(/<title[\s\S]*?<\/title>/i, "").replace(/<desc[\s\S]*?<\/desc>/i, ""));
      });
    return () => { active = false; };
  }, []);

  const tx = viewCenter.x * (1 - zoom) + pan.x;
  const ty = viewCenter.y * (1 - zoom) + pan.y;
  const transform = `translate(${tx} ${ty}) scale(${zoom})`;
  const floorPlanDetailClass =
    zoom >= DETAIL_ZOOM
      ? "floor-plan-layer show-standard show-detail"
      : zoom >= STANDARD_LABEL_ZOOM
        ? "floor-plan-layer show-standard"
        : "floor-plan-layer";

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
    const activeEndpoint = endpointDrag.current;
    if (activeEndpoint?.pointerId === event.pointerId) {
      event.preventDefault();
      updateEndpointDrag(event.clientX, event.clientY);
      return;
    }
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
    const activeEndpoint = endpointDrag.current;
    if (activeEndpoint?.pointerId === event.pointerId) {
      const nearest = nearestPlaceAt(event.clientX, event.clientY, activeEndpoint.kind);
      if (activeEndpoint.kind === "start") onPickup(nearest.id);
      else onDestination(nearest.id);
      finishEndpointDrag();
      return;
    }
    pointers.current.delete(event.pointerId);
    gesture.current.distance = undefined;
    gesture.current.midpoint = undefined;
  }

  function mapPointAt(clientX: number, clientY: number) {
    const viewportPoint = clientToSvg(clientX, clientY);
    return { x: (viewportPoint.x - tx) / zoom, y: (viewportPoint.y - ty) / zoom };
  }

  function nearestPlaceAt(clientX: number, clientY: number, endpoint: EndpointKind) {
    const mapPoint = mapPointAt(clientX, clientY);
    const otherEndpoint = endpoint === "start" ? destination : pickup;
    return places.filter((place) => place.id !== otherEndpoint).reduce((best, candidate) => {
      const candidatePoint = routeNodes[candidate.node];
      const bestPoint = routeNodes[best.node];
      return Math.hypot(mapPoint.x - candidatePoint.x, mapPoint.y - candidatePoint.y) < Math.hypot(mapPoint.x - bestPoint.x, mapPoint.y - bestPoint.y) ? candidate : best;
    });
  }

  function updateEndpointDrag(clientX: number, clientY: number) {
    const activeEndpoint = endpointDrag.current;
    if (!activeEndpoint) return;
    const mapPoint = mapPointAt(clientX, clientY);
    setDragPosition(mapPoint);
    setDropTarget(nearestPlaceAt(clientX, clientY, activeEndpoint.kind).id);
  }

  function finishEndpointDrag() {
    endpointDrag.current = null;
    setDraggingEndpoint(null);
    setDragPosition(null);
    setDropTarget(null);
  }

  function cancelEndpointDrag(event: React.PointerEvent<SVGSVGElement>) {
    if (endpointDrag.current?.pointerId === event.pointerId) finishEndpointDrag();
    pointers.current.delete(event.pointerId);
  }

  function endpointPointerDown(event: React.PointerEvent<SVGGElement>, endpoint: EndpointKind) {
    event.stopPropagation();
    endpointDrag.current = { kind: endpoint, pointerId: event.pointerId };
    svgRef.current?.setPointerCapture(event.pointerId);
    setDraggingEndpoint(endpoint);
    const endpointPlace = endpoint === "start" ? point : target;
    if (!endpointPlace) return;
    setDragPosition(routeNodes[endpointPlace.node]);
    setDropTarget(endpointPlace.id);
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
        <div className="map-view-toggle" role="group" aria-label="Map view">
          <button type="button" className={viewMode === "plan" ? "active" : ""} onClick={() => setViewMode("plan")} aria-pressed={viewMode === "plan"}><MapIcon size={15} /> Plan</button>
          <button type="button" className={viewMode === "street" ? "active" : ""} onClick={() => setViewMode("street")} aria-pressed={viewMode === "street"}><Box size={15} /> 3D street view</button>
        </div>
        <span className="map-demo">{viewMode === "street" ? "ROOM 6002 MODEL" : robot?.demo === false ? "HARDWARE FEED" : "CALIBRATED PLAN"}</span>
      </div>
      <div className="map-art indoor-map-art">
        {viewMode === "street" ? <RoomViewer onExit={() => setViewMode("plan")} /> : <svg
          ref={svgRef}
          viewBox={`${floorPlan.sourceOrigin.x} ${floorPlan.sourceOrigin.y} ${floorPlan.sourceSize.width} ${floorPlan.sourceSize.height}`}
          className={draggingEndpoint ? "campus-svg indoor-map-svg endpoint-drag-active" : "campus-svg indoor-map-svg"}
          role="img"
          aria-label="Interactive route map of Engineering 5 and Engineering 7. Scroll or pinch to zoom and drag to move."
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endPointer}
          onPointerCancel={cancelEndpointDrag}
        >
          <defs>
            <marker id="route-arrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="13" markerHeight="13" orient="auto" markerUnits="userSpaceOnUse">
              <path d="M1 1l10 5-10 5 2.5-5z" fill="#285c9e" stroke="#fffefa" strokeWidth="1.5" />
            </marker>
            <filter id="endpoint-shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="4" stdDeviation="4" floodOpacity=".24" /></filter>
          </defs>
          <g transform={transform} className="map-transform">
            {floorPlanMarkup ? (
              <g
                className={floorPlanDetailClass}
                transform={`translate(${floorPlan.sourceOrigin.x} ${floorPlan.sourceOrigin.y})`}
                style={{ "--map-zoom": zoom } as React.CSSProperties}
                dangerouslySetInnerHTML={{ __html: floorPlanMarkup }}
              />
            ) : (
              <image href="/floor-plan.svg#overview" x={floorPlan.sourceOrigin.x} y={floorPlan.sourceOrigin.y} width={floorPlan.sourceSize.width} height={floorPlan.sourceSize.height} />
            )}
            <g className="route-network" aria-hidden="true">
              {routeEdges.map(([from, to]) => <line key={`${from}-${to}`} x1={routeNodes[from].x} y1={routeNodes[from].y} x2={routeNodes[to].x} y2={routeNodes[to].y} />)}
            </g>
            {point && <path d={pathData([robotPoint, routeNodes[robotNode], ...pickupRoute.slice(1)])} className="active-route pickup-route" markerEnd="url(#route-arrow)" />}
            {point && target && <path d={pathData(destinationRoute)} className="active-route destination-route" markerMid="url(#route-arrow)" markerEnd="url(#route-arrow)" />}
            <g
              className="room-model-anchor"
              transform={`translate(${routeNodes.e5Room6002.x} ${routeNodes.e5Room6002.y})`}
              role="button"
              tabIndex={0}
              aria-label="Open 3D street view for Room 6002"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={() => setViewMode("street")}
              onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setViewMode("street"); } }}
            >
              <circle className="room-model-anchor-ring" r="29" />
              <circle className="room-model-anchor-dot" r="20" />
              <text className="room-model-anchor-label" y="1">3D</text>
            </g>
            {places.map((place) => {
              const location = routeNodes[place.node];
              const unavailable = draggingEndpoint === "start" ? place.id === destination : draggingEndpoint === "end" ? place.id === pickup : false;
              return (
                <g key={place.id} role="button" tabIndex={0} aria-label={`Set starting point to ${place.name}`} onClick={() => { if (!gesture.current.moved) onPickup(place.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPickup(place.id); } }} className={`map-stop${place.id === pickup || place.id === destination ? " important" : ""}${place.id === dropTarget ? " is-nearest" : ""}${unavailable ? " is-unavailable" : ""}`}>
                  <circle className="drop-target-halo" cx={location.x} cy={location.y} r={30 / zoom} />
                  <circle cx={location.x} cy={location.y} r="11" fill="#fffdf7" stroke="#7f8a95" strokeWidth="4" />
                  <text
                    className={place.id === pickup || place.id === destination || zoom >= STANDARD_LABEL_ZOOM ? "place-label is-visible" : "place-label"}
                    style={{ fontSize: `${44 / zoom}px`, strokeWidth: 12 / zoom }}
                    x={location.x}
                    y={location.y - 42 / zoom}
                  >
                    {place.short}
                  </text>
                </g>
              );
            })}
            {([
              point ? { kind: "start" as const, place: point, color: "#285c9e", label: "START" } : null,
              target ? { kind: "end" as const, place: target, color: "#ed4d4d", label: "END" } : null,
            ].filter((endpoint): endpoint is NonNullable<typeof endpoint> => endpoint !== null)).map((endpoint) => {
              const isDragging = draggingEndpoint === endpoint.kind;
              const location = isDragging && dragPosition ? dragPosition : routeNodes[endpoint.place.node];
              const inverseZoom = ENDPOINT_MARKER_SCALE / zoom;
              return (
                <g
                  key={endpoint.kind}
                  className={isDragging ? "endpoint-marker is-dragging" : "endpoint-marker"}
                  transform={`translate(${location.x} ${location.y}) scale(${inverseZoom})`}
                  role="button"
                  tabIndex={0}
                  aria-label={`Drag ${endpoint.kind} point. Currently ${endpoint.place.name}`}
                  onPointerDown={(event) => endpointPointerDown(event, endpoint.kind)}
                >
                  {isDragging && <ellipse className="endpoint-pickup-shadow" cy="21" rx="13" ry="5" />}
                  <g className="endpoint-marker-body">
                    <path d="M0 20C-5 12-18-1-18-14a18 18 0 1 1 36 0C18-1 5 12 0 20Z" fill={endpoint.color} stroke="white" strokeWidth="4" filter="url(#endpoint-shadow)" />
                    <circle cy="-14" r="6" fill="white" />
                    <g className="endpoint-label" transform="translate(0 37)">
                      <rect x="-31" y="-12" width="62" height="24" rx="12" fill={endpoint.color} />
                      <text y="1">{endpoint.label}</text>
                    </g>
                  </g>
                </g>
              );
            })}
            <g transform={`translate(${robotPoint.x},${robotPoint.y})`} className="robot-marker">
              <circle r="56" fill="#ff4d4d" opacity=".13" /><circle r="37" fill="#fff9c4" stroke="#2d2d2d" strokeWidth="5" />
              <foreignObject x="-43" y="-43" width="86" height="76"><Fly small /></foreignObject>
            </g>
          </g>
        </svg>}
        {viewMode === "plan" && draggingEndpoint && dropTarget && (
          <div className="endpoint-drag-hint" role="status">
            Drop {draggingEndpoint === "start" ? "START" : "END"} at {places.find((place) => place.id === dropTarget)?.short}
          </div>
        )}
        {viewMode === "plan" && <>
          <div className="map-compass"><Navigation size={23} /><span>N</span></div>
          <div className="map-controls">
            <Button variant="outline" size="icon" aria-label="Zoom in" disabled={zoom >= MAX_ZOOM} onClick={() => stepZoom(1)}><Plus size={19} /></Button>
            <Button variant="outline" size="icon" aria-label="Zoom out" disabled={zoom <= MIN_ZOOM} onClick={() => stepZoom(-1)}><Minus size={19} /></Button>
            <Button variant="outline" size="icon" aria-label="Reset map view" onClick={resetView}><Crosshair size={20} /></Button>
          </div>
          <span className="map-note">{tripDistance === null ? "Select start and end" : `${tripDistance.toFixed(1)} m`} · scroll to zoom</span>
        </>}
      </div>
    </div>
  );
}
