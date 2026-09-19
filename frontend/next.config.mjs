/** @type {import('next').NextConfig} */
const nextConfig = {
  // Vercel runs from the repository root and expects the Next build manifest
  // at <repo>/.next, while this app's project directory is frontend/.
  distDir: '../.next',
};

export default nextConfig;
