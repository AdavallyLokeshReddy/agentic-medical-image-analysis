import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { AppShell } from "@/components/shell/AppShell";
import { BackendProvider } from "@/components/shell/BackendContext";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Agentic Medical Image Analysis",
    template: "%s · Agentic Medical Image Analysis",
  },
  description:
    "Research prototype: governed agentic AI for medical imaging. Not for clinical diagnosis or treatment.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#060a11",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} h-full`}>
      <body className="min-h-full">
        <BackendProvider>
          <AppShell>{children}</AppShell>
        </BackendProvider>
      </body>
    </html>
  );
}
