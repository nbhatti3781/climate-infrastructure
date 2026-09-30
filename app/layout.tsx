import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "U.S. Climate Infrastructure Dashboard",
  description: "Explore county-level transportation exposure to climate hazards across the United States.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
