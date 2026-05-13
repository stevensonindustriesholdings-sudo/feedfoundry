import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/AppNav";
import { Footer } from "@/components/Footer";

const inter = Inter({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "FeedFoundry — Creator archive, preserved and enriched",
  description:
    "Annual hosted archive access and processing credits for transcripts, chapters, show notes, metadata, CTAs, fact sheets, FAQs, and hosted manifests.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} app-shell min-h-screen font-sans antialiased text-zinc-100`}>
        <AppNav />
        <main className="mx-auto max-w-6xl px-4 py-10 md:py-12">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
