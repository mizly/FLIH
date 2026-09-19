# Backend and bot services

This directory contains the FLIH bot and hardware-facing backend code. The web
app's route handlers remain under `frontend/src/app/api` as required by Next.js.

## OMNI surroundings classification

The `classification` module sends a camera image and optional LiDAR scan to
Huawei OMNI, then returns a structured description of the robot's surroundings.

```powershell
python -m pip install -r backend/classification/requirements.txt
Copy-Item .env.example .env
# Add your private YIBU_API_KEY to .env, then run from the repository root:
python backend/classification/classify_surroundings.py
```

The bundled `images.jpg` is used by default. To fuse a LiDAR scan:

```powershell
python backend/classification/classify_surroundings.py `
  --image backend/classification/images.jpg `
  --lidar backend/classification/lidar_example.json
```

The LiDAR JSON may be an array of distances (evenly distributed around 360
degrees), or an object with a `ranges` array and optional sensor metadata such
as `angle_min`, `angle_increment`, `unit`, and `max_range`.

API call metadata and token counts are appended to the git-ignored
`.data/yibu_api_calls.jsonl` ledger. Prompts, media, responses, and full API keys
are not logged.
