export const places = [
  { id: "slc", name: "Student Life Centre", short: "SLC", x: 300, y: 184 },
  { id: "dc", name: "Davis Centre", short: "Davis Centre", x: 520, y: 225 },
  {
    id: "dp",
    name: "Dana Porter Library",
    short: "Dana Porter",
    x: 340,
    y: 345,
  },
  { id: "e7", name: "Engineering 7", short: "Engineering 7", x: 636, y: 330 },
  {
    id: "ml",
    name: "Modern Languages",
    short: "Modern Languages",
    x: 220,
    y: 345,
  },
  { id: "hh", name: "Hagey Hall", short: "Hagey Hall", x: 390, y: 443 },
] as const;
export type PlaceId = (typeof places)[number]["id"];
export type QueueEntry = {
  id: string;
  username: string;
  pickup: PlaceId;
  destination: PlaceId;
  createdAt: number;
  lastSeenAt?: number;
};
export type Robot = {
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
