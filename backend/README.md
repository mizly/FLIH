# Backend and bot services

This directory is reserved for the FLIH bot and hardware-facing backend code.

The web app currently exposes its HTTP API through `frontend/src/app/api/flih/route.ts`, because Next.js route handlers must live inside the frontend app's `app` directory. The robot service can be added here and send telemetry to that API using `ROBOT_API_KEY`.
