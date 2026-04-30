import type { Metadata } from "next";

import "@/app/globals.css";
import { AppHeader } from "@/components/layout/AppHeader";

export const metadata: Metadata = {
  title: "AI Consulting Studio",
  description: "Dashboard for AI-powered management consulting workflows",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
