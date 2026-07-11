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
  "aurora-blob aurora-blob-1 -top-[20%] max-lg:-top-[12%] -left-[20%] max-lg:-left-[30%]",
  "aurora-blob aurora-blob-2 -top-[15%] max-lg:-top-[8%] -right-[20%] max-lg:-right-[25%]",
  "aurora-blob aurora-blob-3 -bottom-[25%] max-lg:-bottom-[15%] left-[15%] max-lg:left-[10%]",
  "aurora-blob aurora-blob-4 bottom-[5%] max-lg:bottom-[0%] -right-[10%] max-lg:-right-[20%]",
  "aurora-blob aurora-blob-5 top-[35%] max-lg:top-[30%] -left-[10%] max-lg:-left-[20%]",
  "aurora-blob aurora-blob-6 top-[10%] max-lg:top-[2%] left-[35%] max-lg:left-[30%]",
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
