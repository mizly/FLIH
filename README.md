# FLIH — tiny brain, big campus

A Next.js campus pickup app for a fly-inspired, four-wheeled robot. Built with TypeScript, Tailwind CSS, shadcn-style Radix UI components, Lucide icons, and locally bundled Kalam and Patrick Hand fonts. The hand-drawn design follows `frontend/design_prompt.xml`.

## Repository layout

- `frontend/` contains the Next.js app, its route handlers, UI components, and browser tests.
- `backend/` is reserved for the bot and hardware service code that will run alongside the web app.
- The root `package.json` keeps the development, build, typecheck, test, and format commands convenient from the repository root.

## Run locally

```sh
npm install
npm run dev
```

Open http://127.0.0.1:3000. For a production build, run `npm run build` followed by `npm start`.

## What works

- Calibrated E5/E7 sixth-floor plan with selectable indoor stops, shortest-path routing, zoom, and robot centering.
- Shared first-in, first-out queue with custom usernames and no accounts.
- Server-validated, single-use math captchas with five-minute expiry.
- Anonymous HTTP-only session cookie, reservation recovery on refresh, and cancellation.
- Five-second updates, connection errors, queue limits, and duplicate-name checks.
- Authenticated robot telemetry and queue completion endpoint.

The default robot position is **simulated and labeled demo**. The queue is real and persists to `.data/flih.json`. Demo reservations do not dispatch a robot. The corridor graph is a planning trace over the supplied floor plan; it must be field-verified and paired with localization, obstacle avoidance, and a low-level controller before autonomous operation.

## Floor-map calibration

The complete Engineering 5/7 sixth-floor drawing is shown under a routable corridor graph. The supplied 2.5 m reference is represented by `referenceMeters` and `referencePixels` in `frontend/src/lib/campus.ts`. Change those two values after a better survey and all metre conversion, distance labels, telemetry bounds, and the scale bar update from one place. Graph nodes remain in source-image pixels so recalibration does not require moving every waypoint.

## Hardware connection

Copy `.env.example` to `.env.local`, set `ROBOT_API_KEY` to a long random secret, then restart the server. Send telemetry from the hardware service to `PATCH /api/flih`:

```http
Authorization: Bearer YOUR_ROBOT_API_KEY
Content-Type: application/json
```

```json
{
  "x": 420,
  "y": 257,
  "battery": 86,
  "status": "available"
}
```

Coordinates are indoor floor coordinates in metres from the displayed plan's top-left origin, with +x to the right and +y down the drawing. The current calibrated bounds are derived from the floor-map calibration rather than hard-coded in the API. Status is `available`, `guiding`, or `offline`. Updates older than 30 seconds display as offline. Send `completedId` with a queue entry ID to remove that completed trip. `GET /api/flih` provides the ordered queue and current robot state; session identifiers are never returned.

## Storage and deployment

Run as **one Node.js server process with a persistent writable `.data` directory**. File updates are serialized in that process and written with an atomic rename. Use a shared transactional database before deploying multiple instances, workers, or ephemeral/serverless storage. Reservations expire after 90 seconds without a browser check-in. The page checks in while it is open, so refreshing keeps your spot while closing or losing the page eventually releases it automatically. The playful math check is basic friction, not a hardened anti-bot service; use a provider such as Turnstile if abuse becomes a concern.

Usernames and selected stops are visible to everyone. Session cookies last seven days; there is no cross-device identity recovery.

## Verification

```sh
npm run build
npm run typecheck
npm test
```

Browser tests expect the local server on port 3000 and Microsoft Edge installed. They cover captcha rejection, successful reservations, another browser seeing the shared queue, refresh persistence, cancellation, mobile layout, map controls, invalid destinations, and unauthorized API requests.
