import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "SENTINEL — Industrial Safety Intelligence",
  description: "Industrial Safety Intelligence Platform for Zero-Harm Operations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="pageShell">
          <Nav />
          <main className="pageMain">{children}</main>
        </div>
      </body>
    </html>
  );
}
