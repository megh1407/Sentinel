import { AlertTriangle, ShieldAlert, ShieldCheck, Siren, Eye } from "lucide-react";
import { Status, statusColor, statusSoftColor } from "@/lib/viewModels";

const icons: Record<Status, React.ElementType> = {
  NORMAL: ShieldCheck,
  WATCH: Eye,
  WARNING: AlertTriangle,
  CRITICAL: ShieldAlert,
  EMERGENCY: Siren,
};

export default function StatusPill({
  status,
  size = "md",
  pulse = false,
}: {
  status: Status;
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
}) {
  const Icon = icons[status];
  const dims =
    size === "lg"
      ? { pad: "10px 18px", font: 15, icon: 18, gap: 8 }
      : size === "sm"
      ? { pad: "3px 9px", font: 11.5, icon: 12, gap: 5 }
      : { pad: "6px 12px", font: 13, icon: 14, gap: 6 };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: dims.gap,
        padding: dims.pad,
        borderRadius: 999,
        background: statusSoftColor[status],
        color: statusColor[status],
        fontWeight: 600,
        fontSize: dims.font,
        letterSpacing: "0.02em",
        position: "relative",
      }}
    >
      {pulse && (status === "CRITICAL" || status === "EMERGENCY") && (
        <span
          aria-hidden
          style={{
            position: "absolute",
            left: 8,
            top: "50%",
            width: 6,
            height: 6,
            marginTop: -3,
            borderRadius: "50%",
            background: statusColor[status],
            animation: "pulseDot 1.6s ease-in-out infinite",
          }}
        />
      )}
      <Icon size={dims.icon} strokeWidth={2.2} style={{ marginLeft: pulse ? 8 : 0 }} />
      {status}
      <style>{`
        @keyframes pulseDot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.35; transform: scale(1.8); }
        }
      `}</style>
    </span>
  );
}
