import type { Metadata } from "next";
import "./globals.css";

import { ThemeEffect } from "@/components/features/settings/ThemeEffect";
import { AuthProvider } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "AcademicOS",
  description: "The Academic Operating System — Object-Centric Knowledge Graph",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThemeEffect />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
