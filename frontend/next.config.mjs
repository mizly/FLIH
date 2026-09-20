/** @type {import('next').NextConfig} */

// Extra hostnames allowed to reach dev-only assets, as ALLOWED_DEV_ORIGINS=a,b.
const extraDevOrigins = (process.env.ALLOWED_DEV_ORIGINS || '')
  .split(',')
  .map((entry) => entry.trim())
  .filter(Boolean);

const nextConfig = {
  // Vercel runs from the repository root and expects the Next build manifest
  // at <repo>/.next, while this app's project directory is frontend/.
  distDir: '../.next',

  // `next dev` blocks cross-origin requests to dev assets, trusting only localhost
  // and the hostname it was started with. Teleop starts the server on 0.0.0.0 and
  // the control page is opened from another machine by IP, so without these entries
  // /_next/hmr is refused, the page never hydrates, and the control socket is never
  // opened - the UI simply sits on "connecting". Matching is on hostname alone, so
  // no scheme and no port; `*` stands for exactly one label, which for an IPv4
  // address is one octet. Development only; `npm run start` ignores this.
  allowedDevOrigins: [
    '127.0.0.1',
    '10.*.*.*', // LAN
    '192.168.*.*', // LAN
    '100.*.*.*', // Tailscale
    ...extraDevOrigins,
  ],
};

export default nextConfig;
