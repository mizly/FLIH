"use client";
import { useState } from "react";
import { Crosshair, Minus, Plus, MapPin, Navigation } from "lucide-react";
import { places, type Robot, type PlaceId } from "@/lib/campus";
import { Fly } from "./fly";
import { Button } from "./ui/button";
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
  const point = places.find((p) => p.id === pickup)!;
  const target = places.find((p) => p.id === destination)!;
  const rx = robot?.x ?? 420,
    ry = robot?.y ?? 257;
  return (
    <div className="map-shell">
      <div className="map-top">
        <span className="map-campus">
          <MapPin size={17} /> University of Waterloo
        </span>
        <span className="map-demo">
          {robot?.demo === false ? "HARDWARE FEED" : "DEMO MODE"}
        </span>
      </div>
      <div className="map-art">
        <svg
          viewBox="0 0 800 540"
          className="campus-svg"
          role="img"
          aria-label="Illustrated Waterloo campus map. Use the pickup selector or click a labeled campus stop."
        >
          <defs>
            <pattern
              id="map-dots"
              width="18"
              height="18"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r=".8" fill="#d9dbce" />
            </pattern>
            <pattern
              id="building-lines"
              width="7"
              height="7"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(35)"
            >
              <line y2="7" stroke="#d4cfc3" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="800" height="540" fill="#eeeee3" />
          <rect width="800" height="540" fill="url(#map-dots)" />
          <g
            transform={`translate(${center ? 400 - rx * zoom : 400 - 400 * zoom},${center ? 270 - ry * zoom : 270 - 270 * zoom}) scale(${zoom})`}
            className="map-transform"
          >
            <path
              d="M0 375Q105 342 137 424T281 540H0ZM598 0q-80 77 0 120t202 23V0Z"
              fill="#dce4cd"
            />
            <path
              d="M20 0q82 120 57 210t82 183q74 27 82 147"
              fill="none"
              stroke="#b8d2d4"
              strokeWidth="22"
            />
            <path
              d="M20 0q82 120 57 210t82 183q74 27 82 147"
              fill="none"
              stroke="#eff5f2"
              strokeWidth="2"
              strokeDasharray="8 9"
            />
            <g
              fill="none"
              stroke="#d3d0c5"
              strokeWidth="24"
              strokeLinecap="round"
            >
              <path d="M-30 128L167 91 322 99 445 67 827 159" />
              <path d="M736 0L691 149 716 349 801 475" />
              <path d="M277 548L312 442 464 443 579 474 776 431" />
            </g>
            <g
              fill="none"
              stroke="#faf8ef"
              strokeWidth="19"
              strokeLinecap="round"
            >
              <path d="M-30 128L167 91 322 99 445 67 827 159" />
              <path d="M736 0L691 149 716 349 801 475" />
              <path d="M277 548L312 442 464 443 579 474 776 431" />
            </g>
            <g stroke="#faf8ef" strokeWidth="13" fill="none">
              <path d="M165 100L178 259 675 257M324 96L336 442M527 86L524 443M178 259L179 364 527 366M424 259V443M636 257V429" />
            </g>
            <g
              fill="#e3dfd3"
              stroke="#aaa699"
              strokeWidth="1.6"
              strokeLinejoin="round"
            >
              <path d="M207 139l99-4 3 52-23 1 1 35-83 2z" />
              <path d="M351 132l110-3 2 89-110 4z" />
              <path d="M477 151l104-2 3 81-55 2-1-28-51 2z" />
              <path d="M233 286l54-2 2 47-54 1z" />
              <path d="M353 295l51-1 2 62-52 2z" />
              <path d="M469 290l96-3 2 52-98 2z" />
              <path d="M588 297l82-4 3 64-85 4z" />
              <path d="M350 390l67-1 1 31-67 3z" />
              <path d="M446 389l108-2 1 32-107 2z" />
              <path d="M577 382l70-1 2 38-71 2z" />
              <path d="M111 145l48-5 4 60-50 5z" />
            </g>
            <g fill="url(#building-lines)" opacity=".6">
              <path d="M351 132l110-3 2 89-110 4zM353 295l51-1 2 62-52 2zM588 297l82-4 3 64-85 4z" />
            </g>
            <g fill="#d0dabc" stroke="#99aa83" strokeWidth="1.2">
              {[
                [128, 270],
                [146, 295],
                [109, 317],
                [151, 341],
                [266, 392],
                [290, 405],
                [580, 120],
                [610, 139],
                [655, 192],
                [657, 218],
                [455, 352],
                [462, 369],
                [572, 465],
                [597, 483],
                [189, 457],
                [168, 436],
                [376, 244],
                [395, 239],
              ].map(([x, y], i) => (
                <path
                  key={i}
                  d={`M${x} ${y - 9}q12-8 13 4q8 9-4 13q-9 6-16-2q-6-8 7-15Z`}
                />
              ))}
            </g>
            <g fill="#8e8c80" fontSize="14" letterSpacing="2">
              <text x="180" y="78" transform="rotate(2 180 78)">
                RING ROAD
              </text>
              <text x="563" y="91" transform="rotate(14 563 91)">
                RING ROAD
              </text>
              <text x="442" y="482">
                SOUTH CAMPUS
              </text>
              <text
                x="45"
                y="449"
                transform="rotate(24 45 449)"
                fill="#789096"
                letterSpacing="1"
              >
                Laurel Creek
              </text>
            </g>
            <g fill="#858274" fontSize="15" textAnchor="middle">
              <text x="406" y="168">
                Mathematics &
              </text>
              <text x="406" y="186">
                Computer
              </text>
              <text x="516" y="312">
                Science
              </text>
              <text x="516" y="329">
                Teaching
              </text>
              <text x="142" y="226">
                PAC
              </text>
              <text x="613" y="407">
                E5
              </text>
            </g>
            <path
              d={`M${rx} ${ry}L${point.x} 257L${point.x} ${point.y}`}
              stroke="#ff4d4d"
              strokeWidth="3.5"
              strokeDasharray="7 7"
              strokeLinecap="round"
              fill="none"
            />
            <path
              d={`M${point.x} ${point.y}L${point.x} 257L${target.x} 257L${target.x} ${target.y}`}
              stroke="#2d5da1"
              opacity=".45"
              strokeWidth="2"
              strokeDasharray="4 7"
              fill="none"
            />
            {places.map((p) => (
              <g
                key={p.id}
                role="button"
                tabIndex={0}
                aria-label={`Set pickup to ${p.name}`}
                onClick={() => onPickup(p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onPickup(p.id);
                  }
                }}
                className="map-stop"
              >
                <rect
                  x={p.x - 65}
                  y={p.y - 18}
                  width="130"
                  height="44"
                  fill="transparent"
                />
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={pickup === p.id ? 8 : 5}
                  fill={pickup === p.id ? "#ff4d4d" : "#fdfbf7"}
                  stroke={pickup === p.id ? "#ff4d4d" : "#77776c"}
                  strokeWidth="2"
                />
                <text
                  x={p.x}
                  y={p.y + 23}
                  textAnchor="middle"
                  fontSize="17"
                  fill="#44443e"
                  paintOrder="stroke"
                  stroke="#f4f3e9"
                  strokeWidth="5"
                >
                  {p.short}
                </text>
              </g>
            ))}
            <g transform={`translate(${rx},${ry})`} className="robot-marker">
              <circle r="35" fill="#ff4d4d" opacity=".10" />
              <circle
                r="24"
                fill="#fff9c4"
                stroke="#2d2d2d"
                strokeWidth="2.5"
              />
              <foreignObject x="-28" y="-29" width="56" height="49">
                <Fly small />
              </foreignObject>
              <path d="M-35-42q35-7 70 0v24h-30l-5 7-5-7h-30z" fill="#2d2d2d" />
              <text textAnchor="middle" y="-25" fill="white" fontSize="15">
                that’s me!
              </text>
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
            disabled={zoom >= 1.8}
            onClick={() => setZoom((z) => Math.min(1.8, z + 0.2))}
          >
            <Plus size={19} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Zoom out"
            disabled={zoom <= 1}
            onClick={() => {
              setZoom((z) => Math.max(1, z - 0.2));
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
        <span className="map-note">a little fly in a big world.</span>
      </div>
      <div className="map-legend">
        <span>
          <i className="legend-dot robot-dot" /> FLIH
        </span>
        <span>
          <i className="legend-dot pickup-dot" /> Your pickup
        </span>
        <span className="route-legend">┄┄ Suggested connection</span>
        <span className="schematic">Illustrated map · not to scale</span>
      </div>
    </div>
  );
}
