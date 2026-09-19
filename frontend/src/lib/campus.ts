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

// Corridor centreline for the complete E5/E7 sixth-floor plan. Source-pixel
// coordinates keep the trace aligned even when the metre calibration changes.
export const routeNodes = {
  e7NorthWest: { x: 355, y: 285 },
  e7NorthEast: { x: 748, y: 285 },
  e7UpperWest: { x: 355, y: 645 },
  e7UpperEast: { x: 748, y: 645 },
  e7MidWest: { x: 355, y: 1165 },
  e7MidEast: { x: 748, y: 1165 },
  e7LowerWest: { x: 355, y: 1430 },
  e7LowerEast: { x: 748, y: 1430 },
  e7SouthWest: { x: 355, y: 2050 },
  e7SouthEast: { x: 748, y: 2050 },
  e7BottomWest: { x: 355, y: 2290 },
  e7BottomEast: { x: 748, y: 2290 },
  upperLinkWest: { x: 860, y: 645 },
  upperLinkEast: { x: 1115, y: 645 },
  midLinkWest: { x: 860, y: 1410 },
  midLinkCenter: { x: 985, y: 1410 },
  midLinkEast: { x: 1115, y: 1410 },
  e5MidTurn: { x: 1235, y: 1410 },
  e5MidLink: { x: 1485, y: 1410 },
  lowerLinkWest: { x: 860, y: 2050 },
  lowerLinkEast: { x: 1115, y: 2050 },
  e5UpperWest: { x: 1235, y: 645 },
  e5UpperEast: { x: 1655, y: 645 },
  e5NorthWest: { x: 1235, y: 645 },
  e5NorthEast: { x: 1655, y: 645 },
  e5MidWest: { x: 1235, y: 1210 },
  e5MidEast: { x: 1655, y: 1210 },
  e5Room6002: { x: 1485, y: 1510 },
  e5Room6004: { x: 1485, y: 1725 },
  e5Room6007: { x: 1485, y: 1955 },
  e5LowerJunction: { x: 1485, y: 2050 },
  e5Room6008: { x: 1485, y: 2215 },
  e5South: { x: 1485, y: 2445 },
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
  ["e7SouthWest", "e7BottomWest"],
  ["e7SouthEast", "e7BottomEast"],
  ["e7BottomWest", "e7BottomEast"],
  ["e7UpperEast", "upperLinkWest"],
  ["upperLinkWest", "upperLinkEast"],
  ["upperLinkEast", "e5UpperWest"],
  ["e7LowerEast", "midLinkWest"],
  ["midLinkWest", "midLinkCenter"],
  ["midLinkCenter", "midLinkEast"],
  ["midLinkEast", "e5MidTurn"],
  ["midLinkEast", "e5MidLink"],
  ["e5MidWest", "e5MidTurn"],
  ["e5MidTurn", "e5MidLink"],
  ["e7SouthEast", "lowerLinkWest"],
  ["lowerLinkWest", "lowerLinkEast"],
  ["lowerLinkEast", "e5LowerJunction"],
  ["e5NorthWest", "e5NorthEast"],
  ["e5NorthWest", "e5UpperWest"],
  ["e5NorthEast", "e5UpperEast"],
  ["e5UpperWest", "e5UpperEast"],
  ["e5UpperWest", "e5MidWest"],
  ["e5UpperEast", "e5MidEast"],
  ["e5MidWest", "e5MidEast"],
  ["e5MidLink", "e5Room6002"],
  ["e5Room6002", "e5Room6004"],
  ["e5Room6004", "e5Room6007"],
  ["e5Room6007", "e5LowerJunction"],
  ["e5LowerJunction", "e5Room6008"],
  ["e5Room6008", "e5South"],
] as const satisfies readonly (readonly [RouteNodeId, RouteNodeId])[];

export const places = [
  {
    id: "slc",
    name: "E7/E5 link — You Are Here",
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
    node: "e7BottomEast",
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
  { id: "r6007", name: "Room 6007", short: "6007", node: "e5Room6007" },
  { id: "r6008", name: "Room 6008", short: "6008", node: "e5Room6008" },
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
