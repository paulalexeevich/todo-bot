export default function Loading() {
  const rows = [60, 85, 45, 70, 90, 55, 75, 65];
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="h-6 w-14 rounded-md bg-muted animate-pulse mb-1.5" />
            <div className="h-4 w-52 rounded-md bg-muted animate-pulse" />
          </div>
          <div className="h-8 w-8 rounded-md bg-muted animate-pulse" />
        </div>

        {/* Tabs + search skeleton */}
        <div className="flex items-center gap-3 mb-3">
          <div className="h-9 w-64 rounded-md bg-muted animate-pulse" />
          <div className="h-9 flex-1 rounded-md bg-muted animate-pulse" />
          <div className="h-9 w-20 rounded-md bg-muted animate-pulse" />
        </div>
        {/* Type pills skeleton */}
        <div className="flex gap-1.5 mb-4">
          {[48, 36, 32, 52, 44, 60, 52, 44].map((w, i) => (
            <div key={i} className="h-5 rounded-full bg-muted animate-pulse" style={{ width: w }} />
          ))}
        </div>

        <div className="rounded-md border overflow-hidden">
          <div className="h-9 bg-muted/40 border-b" />
          {rows.map((pct, i) => (
            <div
              key={i}
              className="h-12 border-b last:border-0 px-3 flex items-center gap-3"
            >
              <div className="h-3 w-5 rounded bg-muted animate-pulse" />
              <div className="h-3 rounded bg-muted animate-pulse flex-1" style={{ maxWidth: `${pct}%` }} />
              <div className="h-5 w-14 rounded bg-muted animate-pulse" />
              <div className="h-3 w-16 rounded bg-muted animate-pulse" />
              <div className="h-5 w-8 rounded bg-muted animate-pulse" />
              <div className="h-3 w-20 rounded bg-muted animate-pulse hidden sm:block" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
