import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ReactQueryProvider } from "@/providers/react-query-provider";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "@/components/layout/navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Spoon Rebalancer",
  description: "Portfolio rebalancing UI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <ReactQueryProvider>
          <div className="min-h-dvh grid grid-cols-[240px_1fr] bg-background text-foreground">
            <Sidebar />
            <main className="px-6 py-6">{children}</main>
          </div>
          <Toaster richColors closeButton theme="dark" />
        </ReactQueryProvider>
      </body>
    </html>
  );
}
