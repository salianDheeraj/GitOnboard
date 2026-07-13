import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/Header";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GitOnboard - Repository Intelligence",
  description: "Repository Intelligence Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full bg-slate-50">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-full flex flex-col overflow-hidden text-slate-900`}>
        <Header />
        <div className="flex-1 flex overflow-hidden">
          {children}
        </div>
      </body>
    </html>
  );
}
