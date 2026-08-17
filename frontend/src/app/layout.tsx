import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Capability",
  description: "Drop a CSV and a rubric screenshot. Get percentage-normalized contribution.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
