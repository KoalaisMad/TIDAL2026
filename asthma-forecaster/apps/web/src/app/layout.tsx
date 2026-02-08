import type { Metadata, Viewport } from "next"
import "./globals.css"
import SessionProvider from "@/components/providers/SessionProvider"
import FloatingMascot from "@/components/FloatingMascot"

export const metadata: Metadata = {
  title: "Asthma Monitor",
  description: "Mobile-first asthma risk dashboard",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-w-0 overflow-x-hidden">
        <SessionProvider>{children}</SessionProvider>
        <FloatingMascot />
      </body>
    </html>
  )
}
