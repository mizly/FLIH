"use client";

import { useMemo, useState } from "react";
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

function pathData(points: Point[]) {
  return points
    .map((point, index) => `${index ? "L" : "M"}${point.x} ${point.y}`)
    .join(" ");
}

export function CampusMap({
  robot,
  pickup,
  destination,
  onPickup,
}: {
  robot: Robot | null;
  pickup: PlaceId;
  destination: PlaceId;
  onPickup: (id: PlaceId) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState(false);
  const point = places.find((place) => place.id === pickup)!;
  const target = places.find((place) => place.id === destination)!;
  const robotPoint = worldToSource(robot ?? { x: 32.7, y: 58.6 });
  const robotNode = nearestRouteNode(robotPoint);
  const pickupRoute = useMemo(
    () => routePoints(robotNode, point.node),
    [robotNode, point.node],
  );
  const destinationRoute = useMemo(
    () => routePoints(point.node, target.node),
    [point.node, target.node],
  );
  const tripDistance = routeLengthMeters(destinationRoute);
  const viewCenter = {
    x: floorPlan.sourceOrigin.x + floorPlan.sourceSize.width / 2,
    y: floorPlan.sourceOrigin.y + floorPlan.sourceSize.height / 2,
  };
  const focus = center ? robotPoint : viewCenter;
  const tx = viewCenter.x - focus.x * zoom;
  const ty = viewCenter.y - focus.y * zoom;
  const transform = `translate(${tx},${ty}) scale(${zoom})`;

  return (
    <div className="map-shell">
      <div className="map-top">
        <span className="map-campus">
          <MapPin size={17} /> E5 + E7 · sixth floor
        </span>
        <span className="map-demo">
          {robot?.demo === false ? "HARDWARE FEED" : "CALIBRATED PLAN"}
        </span>
      </div>
      <div className="map-art indoor-map-art">
        <svg
          viewBox={`${floorPlan.sourceOrigin.x} ${floorPlan.sourceOrigin.y} ${floorPlan.sourceSize.width} ${floorPlan.sourceSize.height}`}
          className="campus-svg indoor-map-svg"
          role="img"
          aria-label="Routable vector floor plan of Engineering 5 and Engineering 7. Use the pickup selector or click a stop marker."
        >
          <g transform={transform} className="map-transform">
            <image
              href="/floor-plan.svg"
              x={floorPlan.sourceOrigin.x}
              y={floorPlan.sourceOrigin.y}
              width={floorPlan.sourceSize.width}
              height={floorPlan.sourceSize.height}
            />
            <g
              className="map-scale-mark"
              transform={`translate(${floorPlan.sourceOrigin.x + 35},${floorPlan.sourceOrigin.y + 55})`}
            >
              <text x="0" y="0">
                {floorPlan.referenceMeters} m
              </text>
              <path
                d={`M0 16v14h${floorPlan.referencePixels}V16`}
              />
            </g>
            <g className="route-network" aria-hidden="true">
              {routeEdges.map(([from, to]) => (
                <line
                  key={`${from}-${to}`}
                  x1={routeNodes[from].x}
                  y1={routeNodes[from].y}
                  x2={routeNodes[to].x}
                  y2={routeNodes[to].y}
                />
              ))}
            </g>
            <path
              d={pathData([
                robotPoint,
                routeNodes[robotNode],
                ...pickupRoute.slice(1),
              ])}
              className="active-route pickup-route"
            />
            <path
              d={pathData(destinationRoute)}
              className="active-route destination-route"
            />
            {places.map((place) => {
              const location = routeNodes[place.node];
              return (
                <g
                  key={place.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Set pickup to ${place.name}`}
                  onClick={() => onPickup(place.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onPickup(place.id);
                    }
                  }}
                  className="map-stop"
                >
                  <circle
                    cx={location.x}
                    cy={location.y}
                    r={pickup === place.id ? 18 : 13}
                    fill={pickup === place.id ? "#ff4d4d" : "#fffdf7"}
                    stroke={pickup === place.id ? "#ff4d4d" : "#2d5da1"}
                    strokeWidth="5"
                  />
                </g>
              );
            })}
            <g
              transform={`translate(${robotPoint.x},${robotPoint.y})`}
              className="robot-marker"
            >
              <circle r="56" fill="#ff4d4d" opacity=".13" />
              <circle
                r="37"
                fill="#fff9c4"
                stroke="#2d2d2d"
                strokeWidth="5"
              />
              <foreignObject x="-43" y="-43" width="86" height="76">
                <Fly small />
              </foreignObject>
            </g>
          </g>
        </svg>
        <div className="map-compass">
          <Navigation size={23} />
          <span>N</span>
        </div>
        <div className="map-controls">
          <Button
            variant="outline"
            size="icon"
            aria-label="Zoom in"
            disabled={zoom >= 2.2}
            onClick={() => setZoom((value) => Math.min(2.2, value + 0.2))}
          >
            <Plus size={19} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Zoom out"
            disabled={zoom <= 1}
            onClick={() => {
              setZoom((value) => Math.max(1, value - 0.2));
              setCenter(false);
            }}
          >
            <Minus size={19} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Center map on FLIH"
            onClick={() => {
              setZoom(1.3);
              setCenter(true);
            }}
          >
            <Crosshair size={20} />
          </Button>
        </div>
        <span className="map-note">route: {tripDistance.toFixed(1)} m</span>
      </div>
    </div>
  );
}
