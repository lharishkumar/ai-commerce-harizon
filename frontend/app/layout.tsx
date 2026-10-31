import type { Metadata } from "next";
import "./globals.css";
import "./live-voice.css";
import "./product-detail.css";
import "@livekit/components-styles";

export const metadata: Metadata = {
  title: "HARIZON — Thoughtful tech for everyday life",
  description: "Discover beautifully considered electronics, smart home essentials and connected living.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

