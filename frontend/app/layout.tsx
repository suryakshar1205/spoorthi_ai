import type { Metadata } from "next";
import { Newsreader, Space_Grotesk } from "next/font/google";

import "./globals.css";
import { ToastProvider } from "@/components/toast-provider";


const bodyFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-body"
});

const displayFont = Newsreader({
  subsets: ["latin"],
  variable: "--font-display"
});


export const metadata: Metadata = {
  title: "Spoorthi Chatbot",
  description: "Technical fest assistant for Spoorthi"
};


export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${bodyFont.variable} ${displayFont.variable} bg-cream text-ink antialiased`}>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
