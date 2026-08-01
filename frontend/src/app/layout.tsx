import type { Metadata } from "next";
import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
