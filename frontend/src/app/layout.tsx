import type { Metadata } from "next";
import "./globals.css";

import { ThemeEffect } from "@/components/features/settings/ThemeEffect";

export const metadata: Metadata = {
  title: "AcademicOS",
  description: "The Academic Operating System — Object-Centric Knowledge Graph",
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
        {children}
      </body>
    </html>
  );
}
