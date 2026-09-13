import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600"],
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Catalyst",
  description: "Autonomous Product Intelligence & Execution Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const bodyClass = [fraunces.variable, plexSans.variable, plexMono.variable].join(" ");
  return (
    <html lang="en">
      <body className={bodyClass}>
        {children}
      </body>
    </html>
  );
}