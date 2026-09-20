export type Point = { x: number; y: number };

/**
 * The drawing is the source of truth. Geometry is stored in source-image
 * pixels and converted through this single calibration. Update these two
 * reference values when a better field measurement is available.
 */
export const floorPlanCalibration = {
  referenceMeters: 2.5,
  referencePixels: 55,
  sourceOrigin: { x: 180, y: 120 },
  sourceSize: { width: 1590, height: 2500 },
} as const;

export const pixelsPerMeter =
  floorPlanCalibration.referencePixels /
  floorPlanCalibration.referenceMeters;

export const floorPlan = {
  ...floorPlanCalibration,
  worldWidth: floorPlanCalibration.sourceSize.width / pixelsPerMeter,
  worldHeight: floorPlanCalibration.sourceSize.height / pixelsPerMeter,
} as const;

export function sourceToWorld(point: Point): Point {
  return {
    x: (point.x - floorPlan.sourceOrigin.x) / pixelsPerMeter,
    y: (point.y - floorPlan.sourceOrigin.y) / pixelsPerMeter,
  };
}

export function worldToSource(point: Point): Point {
  return {
    x: floorPlan.sourceOrigin.x + point.x * pixelsPerMeter,
    y: floorPlan.sourceOrigin.y + point.y * pixelsPerMeter,
  };
}

// Corridor centrelines for the complete E5/E7 sixth-floor plan. The SVG is a
// crop of the source drawing, so keep the graph in SVG-local coordinates and
// apply the crop origin exactly once here. This also makes the values below
// directly comparable with the corridor geometry in floor-plan.svg.
function floorPoint(x: number, y: number): Point {
  return {
    x: floorPlan.sourceOrigin.x + x,
    y: floorPlan.sourceOrigin.y + y,
  };
}

export const routeNodes = {
  // Engineering 7: two long north/south halls, a central lobby, and a
  // southern return. Values are the geometric centres of the visible halls.
  e7NorthWest: floorPoint(183.5, 179.5),
  e7NorthEast: floorPoint(551, 179.5),
  e7UpperWest: floorPoint(183.5, 525.5),
  e7UpperEast: floorPoint(551, 525.5),
  e7MidWest: floorPoint(183.5, 1093.5),
  e7MidEast: floorPoint(551, 1093.5),
  e7LowerWest: floorPoint(183.5, 1979),
  e7LowerEast: floorPoint(551, 1979),
  e7SouthWest: floorPoint(183.5, 2126),
  e7SouthEast: floorPoint(551, 2126),

  // The three enclosed E7/E5 bridges.
  upperLinkCenter: floorPoint(813, 525.5),
  midLinkCenter: floorPoint(813, 1093.5),
  lowerLinkCenter: floorPoint(813, 1979),

  // Engineering 5 north loop and the passage around the west side of the
  // atrium that leads into the lower-floor spine.
  e5NorthWest: floorPoint(1076.5, 525.5),
  e5NorthEast: floorPoint(1436, 525.5),
  e5MidWest: floorPoint(1076.5, 1093.5),
  e5MidEast: floorPoint(1436, 1093.5),
  e5AtriumWest: floorPoint(1076.5, 1339),
  e5SpineNorth: floorPoint(1283.5, 1339),

  // Main lower E5 corridor. Room nodes sit at their corridor-side entrances,
  // not in the rooms themselves, so generated routes remain walkable.
  e5Room6003: floorPoint(1283.5, 1390),
  e5Room6002: floorPoint(1283.5, 1432),
  e5Room6004: floorPoint(1283.5, 1610),
  e5Room6005: floorPoint(1283.5, 1649),
  e5Room6007: floorPoint(1283.5, 1762),
  e5Room6006: floorPoint(1283.5, 1931),
  e5LowerJunction: floorPoint(1283.5, 1979),
  e5Room6008: floorPoint(1283.5, 2090),
  e5Room6009: floorPoint(1283.5, 2100),
  e5SouthLoopEast: floorPoint(1283.5, 2190),
  e5Room6011: floorPoint(1283.5, 2263),
  e5South: floorPoint(1283.5, 2338),

  // Loop serving the small south rooms and the lower bridge.
  e5SouthLoopWestTop: floorPoint(1039.5, 1979),
  e5Room6014: floorPoint(1039.5, 2073.5),
  e5SouthLoopWestBottom: floorPoint(1039.5, 2190),
  e5Room6013: floorPoint(1081.5, 2190),
  e5Room6012: floorPoint(1226.5, 2190),
} as const satisfies Record<string, Point>;

export type RouteNodeId = keyof typeof routeNodes;

export const routeEdges = [
  ["e7NorthWest", "e7NorthEast"],
  ["e7NorthWest", "e7UpperWest"],
  ["e7NorthEast", "e7UpperEast"],
  ["e7UpperWest", "e7UpperEast"],
  ["e7UpperWest", "e7MidWest"],
  ["e7UpperEast", "e7MidEast"],
  ["e7MidWest", "e7MidEast"],
  ["e7MidWest", "e7LowerWest"],
  ["e7MidEast", "e7LowerEast"],
  ["e7LowerWest", "e7LowerEast"],
  ["e7LowerWest", "e7SouthWest"],
  ["e7LowerEast", "e7SouthEast"],
  ["e7SouthWest", "e7SouthEast"],
  ["e7UpperEast", "upperLinkCenter"],
  ["upperLinkCenter", "e5NorthWest"],
  ["e7MidEast", "midLinkCenter"],
  ["midLinkCenter", "e5MidWest"],
  ["e7LowerEast", "lowerLinkCenter"],
  ["lowerLinkCenter", "e5LowerJunction"],
  ["e5NorthWest", "e5NorthEast"],
  ["e5NorthWest", "e5MidWest"],
  ["e5NorthEast", "e5MidEast"],
  ["e5MidWest", "e5MidEast"],
  ["e5MidWest", "e5AtriumWest"],
  ["e5AtriumWest", "e5SpineNorth"],
  ["e5SpineNorth", "e5Room6003"],
  ["e5Room6003", "e5Room6002"],
  ["e5Room6002", "e5Room6004"],
  ["e5Room6004", "e5Room6005"],
  ["e5Room6005", "e5Room6007"],
  ["e5Room6007", "e5Room6006"],
  ["e5Room6006", "e5LowerJunction"],
  ["e5LowerJunction", "e5Room6008"],
  ["e5Room6008", "e5Room6009"],
  ["e5Room6009", "e5SouthLoopEast"],
  ["e5SouthLoopEast", "e5Room6011"],
  ["e5Room6011", "e5South"],
  ["e5LowerJunction", "e5SouthLoopWestTop"],
  ["e5SouthLoopWestTop", "e5Room6014"],
  ["e5Room6014", "e5SouthLoopWestBottom"],
  ["e5SouthLoopWestBottom", "e5Room6013"],
  ["e5Room6013", "e5Room6012"],
  ["e5Room6012", "e5SouthLoopEast"],
] as const satisfies readonly (readonly [RouteNodeId, RouteNodeId])[];

export const places = [
  {
    id: "slc",
    name: "E7/E5 middle link — You Are Here",
    short: "You are here",
    node: "midLinkCenter",
  },
  {
    id: "dc",
    name: "E7 north corridor",
    short: "E7 north",
    node: "e7NorthWest",
  },
  {
    id: "dp",
    name: "E7 south corridor",
    short: "E7 south",
    node: "e7LowerEast",
  },
  {
    id: "ml",
    name: "E5 north corridor",
    short: "E5 north",
    node: "e5NorthEast",
  },
  {
    id: "hh",
    name: "E5 south corridor",
    short: "E5 south",
    node: "e5South",
  },
  { id: "e7", name: "Room 6004", short: "6004", node: "e5Room6004" },
  { id: "r6002", name: "Room 6002", short: "6002", node: "e5Room6002" },
  { id: "r6003", name: "Room 6003", short: "6003", node: "e5Room6003" },
  { id: "r6005", name: "Room 6005", short: "6005", node: "e5Room6005" },
  { id: "r6006", name: "Room 6006", short: "6006", node: "e5Room6006" },
  { id: "r6007", name: "Room 6007", short: "6007", node: "e5Room6007" },
  { id: "r6008", name: "Room 6008", short: "6008", node: "e5Room6008" },
  { id: "r6009", name: "Room 6009", short: "6009", node: "e5Room6009" },
  { id: "r6011", name: "Room 6011", short: "6011", node: "e5Room6011" },
  { id: "r6012", name: "Room 6012", short: "6012", node: "e5Room6012" },
  { id: "r6013", name: "Room 6013", short: "6013", node: "e5Room6013" },
  { id: "r6014", name: "Room 6014", short: "6014", node: "e5Room6014" },
] as const satisfies readonly {
  id: string;
  name: string;
  short: string;
  node: RouteNodeId;
}[];

export type PlaceId = (typeof places)[number]["id"];

function distance(a: Point, b: Point) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function nearestRouteNode(point: Point): RouteNodeId {
  return (Object.entries(routeNodes) as [RouteNodeId, Point][]).reduce(
    (nearest, [id, node]) =>
      distance(point, node) < distance(point, routeNodes[nearest])
        ? id
        : nearest,
    "midLinkCenter" as RouteNodeId,
  );
}

export function findRoute(
  from: RouteNodeId,
  to: RouteNodeId,
): RouteNodeId[] {
  const unvisited = new Set<RouteNodeId>(
    Object.keys(routeNodes) as RouteNodeId[],
  );
  const costs = new Map<RouteNodeId, number>([[from, 0]]);
  const previous = new Map<RouteNodeId, RouteNodeId>();

  while (unvisited.size) {
    const current = [...unvisited].reduce<RouteNodeId | null>((best, id) => {
      if (best === null) return id;
      return (costs.get(id) ?? Infinity) < (costs.get(best) ?? Infinity)
        ? id
        : best;
    }, null);
    if (current === null || (costs.get(current) ?? Infinity) === Infinity) break;
    unvisited.delete(current);
    if (current === to) break;

    for (const [a, b] of routeEdges) {
      const neighbor = a === current ? b : b === current ? a : null;
      if (!neighbor || !unvisited.has(neighbor)) continue;
      const candidate =
        costs.get(current)! + distance(routeNodes[current], routeNodes[neighbor]);
      if (candidate < (costs.get(neighbor) ?? Infinity)) {
        costs.set(neighbor, candidate);
        previous.set(neighbor, current);
      }
    }
  }

  const result: RouteNodeId[] = [to];
  while (result[0] !== from) {
    const parent = previous.get(result[0]);
    if (!parent) return [from];
    result.unshift(parent);
  }
  return result;
}

export function routePoints(from: RouteNodeId, to: RouteNodeId): Point[] {
  return findRoute(from, to).map((id) => routeNodes[id]);
}

export function routeLengthMeters(points: Point[]) {
  return (
    points.reduce(
      (total, point, index) =>
        index === 0 ? total : total + distance(points[index - 1], point),
      0,
    ) / pixelsPerMeter
  );
}

export type QueueEntry = {
  id: string;
  username: string;
  pickup: PlaceId;
  destination: PlaceId;
  createdAt: number;
  lastSeenAt?: number;
};
export type Robot = {
  /** Calibrated floor coordinates in metres from the plan's top-left origin. */
  x: number;
  y: number;
  battery: number;
  status: "available" | "guiding" | "offline";
  updatedAt: number;
  demo: boolean;
};
export type Dashboard = {
  queue: QueueEntry[];
  robot: Robot;
  mine: string | null;
};
export function placeName(id: string) {
  return places.find((p) => p.id === id)?.name ?? id;
}
