import { useMemo } from "react";
import { useTheme } from "../hooks/useTheme";

const LIGHT_BLOBS = [
  { bg: "radial-gradient(ellipse at center, rgba(108,200,182,0.15) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(125,200,165,0.12) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(165,153,142,0.1) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(148,220,206,0.12) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(178,230,219,0.08) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(200,192,184,0.06) 0%, transparent 65%)" },
];

const DARK_BLOBS = [
  { bg: "radial-gradient(ellipse at center, rgba(94,234,212,0.2) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(167,139,250,0.18) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(251,191,36,0.12) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(52,211,153,0.15) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(236,72,153,0.1) 0%, transparent 65%)" },
  { bg: "radial-gradient(ellipse at center, rgba(96,165,250,0.1) 0%, transparent 65%)" },
];

const BLOB_CLASSES = [
  "aurora-blob aurora-blob-1 -top-[15%] -left-[10%]",
  "aurora-blob aurora-blob-2 -top-[10%] -right-[15%]",
  "aurora-blob aurora-blob-3 -bottom-[20%] left-[20%]",
  "aurora-blob aurora-blob-4 bottom-[10%] -right-[5%]",
  "aurora-blob aurora-blob-5 top-[40%] -left-[5%]",
  "aurora-blob aurora-blob-6 top-[5%] left-[40%]",
];

export default function AuroraBackground({ children, className = "" }) {
  const [isDark] = useTheme();
  const blobs = useMemo(() => isDark ? DARK_BLOBS : LIGHT_BLOBS, [isDark]);

  return (
    <div className={`relative min-h-screen ${className}`}>
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        {blobs.map((blob, i) => (
          <div key={i} className={BLOB_CLASSES[i]} style={{ background: blob.bg }} />
        ))}
      </div>
      {children}
    </div>
  );
}
