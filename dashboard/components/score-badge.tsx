export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span className="text-muted-foreground text-sm">—</span>;

  const color =
    score >= 8 ? "bg-green-100 text-green-800" :
    score >= 5 ? "bg-amber-100 text-amber-800" :
                 "bg-red-100 text-red-800";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}
