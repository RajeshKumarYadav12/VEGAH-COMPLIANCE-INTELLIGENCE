import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VEGAH Compliance Intelligence | RFP Intake & Analysis",
  description:
    "AI-powered multi-agent system for automated RFP intake, compliance gap analysis, and executive proposal generation by VEGAH.",
  keywords: ["RFP", "compliance", "AI", "VEGAH", "proposal", "intelligence"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#070b14" />
      </head>
      <body>{children}</body>
    </html>
  );
}
