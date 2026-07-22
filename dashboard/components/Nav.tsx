"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, MapPin, Siren, History, Terminal, ShieldHalf } from "lucide-react";

const items = [
  { href: "/", label: "Command Center", icon: LayoutGrid },
  { href: "/zones/ZONE-A", label: "Plant / Zones", icon: MapPin, match: "/zones" },
  { href: "/emergency", label: "Emergency Center", icon: Siren },
  { href: "/history", label: "Event History", icon: History },
  { href: "/trace", label: "System Trace", icon: Terminal, secondary: true },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        width: 232,
        flexShrink: 0,
        borderRight: "1px solid var(--border)",
        background: "var(--surface)",
        padding: "24px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "4px 10px 22px" }}>
        <ShieldHalf size={22} color="var(--accent)" strokeWidth={2.2} />
        <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.01em" }}>SENTINEL</span>
      </div>
      {items.map((item) => {
        const active = item.match
          ? pathname.startsWith(item.match)
          : pathname === item.href;
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 12px",
              borderRadius: "var(--radius-sm)",
              fontSize: 13.5,
              fontWeight: 500,
              color: active ? "var(--accent-strong)" : "var(--text-secondary)",
              background: active ? "var(--accent-soft)" : "transparent",
              marginTop: item.secondary ? 16 : 0,
              borderTop: item.secondary ? "1px solid var(--border)" : "none",
              paddingTop: item.secondary ? 18 : 9,
            }}
          >
            <Icon size={16} strokeWidth={2} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
