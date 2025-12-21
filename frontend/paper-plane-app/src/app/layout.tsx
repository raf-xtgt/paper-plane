import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import LayoutClient from "./layoutClient";
import { UserProvider } from "./context/userContext";
import { StateControllerProvider } from "./context/stateController";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PaperPlane",
  description: "AI Powered B2B2C CRM",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <UserProvider>
          <StateControllerProvider>
            <LayoutClient>{children}</LayoutClient>
          </StateControllerProvider>
        </UserProvider>      
      </body>
    </html>
  );
}