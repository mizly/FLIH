import type { Metadata } from "next";
import "@fontsource/kalam/700.css";
import "@fontsource/patrick-hand/400.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "FLIH — Tiny brain. Big campus.",
  description:
    "Meet your four-wheeled campus companion. Find FLIH, join the queue, and explore Waterloo together.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
