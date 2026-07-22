import { FeedItem } from "@/lib/contracts";
import { timeAgo } from "@/lib/viewModels";
import SourceTag from "./SourceTag";
import { Circle } from "lucide-react";

const severityColor: Record<string, string> = {
  CRITICAL: "var(--risk-critical)",
  HIGH: "var(--risk-warning)",
  MEDIUM: "var(--risk-watch)",
  LOW: "var(--text-tertiary)",
  INFO: "var(--text-tertiary)",
};

export default function LiveFeed({ items }: { items: FeedItem[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {items.map((item, i) => (
        <div
          key={item.id}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            padding: "11px 2px",
            borderTop: i === 0 ? "none" : "1px solid var(--border)",
          }}
        >
          <Circle
            size={7}
            fill={severityColor[item.severity]}
            color={severityColor[item.severity]}
            style={{ marginTop: 6, flexShrink: 0 }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5 }}>{item.message}</div>
            <div style={{ fontSize: 11.5, color: "var(--text-tertiary)", marginTop: 2 }}>
              {timeAgo(item.timestamp)}
            </div>
          </div>
          <SourceTag source={item.source} />
        </div>
      ))}
    </div>
  );
}
