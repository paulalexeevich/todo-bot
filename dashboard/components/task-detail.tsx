"use client";

import { useEffect, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ScoreBadge } from "@/components/score-badge";
import { StatusIcon } from "@/components/tasks-table";
import { getOffers, type Offer, type Task } from "@/lib/api";
import { cn } from "@/lib/utils";

const TYPE_COLOR: Record<string, string> = {
  idea: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  todo: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  note: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  shopping: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  learning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  architecture: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  question: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-2">
      {children}
    </p>
  );
}

interface Props {
  task: Task | null;
  onClose: () => void;
}

export function TaskDetail({ task, onClose }: Props) {
  const [offers, setOffers] = useState<Offer[]>([]);

  useEffect(() => {
    if (task?.type === "shopping" && task.id) {
      getOffers(task.id).then(setOffers);
    } else {
      setOffers([]);
    }
  }, [task]);

  return (
    <Sheet open={!!task} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        {task && (
          <>
            <SheetHeader className="mb-5">
              <SheetTitle className="text-left text-lg font-semibold leading-snug pr-6">
                {task.text}
              </SheetTitle>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <span className="text-xs text-muted-foreground">
                  #{task.id}
                </span>
                <span className="text-muted-foreground/40">·</span>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize",
                    TYPE_COLOR[task.type] ?? "bg-gray-100 text-gray-700"
                  )}
                >
                  {task.type}
                </span>
                <span className="text-muted-foreground/40">·</span>
                <span className="flex items-center gap-1">
                  <StatusIcon status={task.status} />
                  <span className="text-xs text-muted-foreground capitalize">
                    {task.status}
                  </span>
                </span>
                <span className="text-muted-foreground/40">·</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(task.created_at).toLocaleString()}
                </span>
              </div>
            </SheetHeader>

            <div className="h-px bg-border mb-5" />

            {task.type === "shopping" ? (
              <div className="space-y-4">
                <SectionLabel>Offers ({offers.length})</SectionLabel>
                {offers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {task.status === "processing"
                      ? "Searching for offers…"
                      : "No offers found yet."}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {offers.map((o) => (
                      <li
                        key={o.id}
                        className="flex items-start gap-2 text-sm border rounded-md p-3"
                      >
                        <div className="flex-1 min-w-0">
                          <a
                            href={o.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-blue-600 hover:underline line-clamp-2"
                          >
                            {o.title}
                          </a>
                          <div className="flex items-center gap-2 mt-1.5">
                            {o.price && (
                              <span className="text-xs font-semibold text-green-700 bg-green-50 dark:bg-green-900/20 dark:text-green-400 px-1.5 py-0.5 rounded">
                                {o.price}
                              </span>
                            )}
                            {o.store && (
                              <span className="text-xs text-muted-foreground">
                                {o.store}
                              </span>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : task.discovery ? (
              <div className="space-y-6">
                {/* Score */}
                <div>
                  <SectionLabel>Score</SectionLabel>
                  <div className="flex items-center gap-3">
                    <ScoreBadge score={task.discovery.score} />
                    {task.discovery.score !== null && (
                      <>
                        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all",
                              task.discovery.score >= 8
                                ? "bg-green-500"
                                : task.discovery.score >= 5
                                ? "bg-amber-500"
                                : "bg-red-500"
                            )}
                            style={{
                              width: `${(task.discovery.score / 10) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {task.discovery.score.toFixed(1)} / 10
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Verdict */}
                {task.discovery.verdict && (
                  <div>
                    <SectionLabel>Verdict</SectionLabel>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {task.discovery.verdict}
                    </p>
                  </div>
                )}

                {/* Market Size */}
                {task.discovery.market_size && (
                  <div>
                    <SectionLabel>Market Size</SectionLabel>
                    <p className="text-sm text-muted-foreground">
                      {task.discovery.market_size}
                    </p>
                  </div>
                )}

                {/* Competitors */}
                {task.discovery.full_report?.competitors?.length ? (
                  <div>
                    <SectionLabel>Competitors</SectionLabel>
                    <ul className="space-y-1.5">
                      {task.discovery.full_report.competitors.map((c) => (
                        <li
                          key={c}
                          className="text-sm text-muted-foreground flex items-center gap-2"
                        >
                          <span className="w-1 h-1 rounded-full bg-muted-foreground/50 shrink-0" />
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {/* Community Sentiment */}
                {(task.discovery.ih_summary ||
                  task.discovery.reddit_summary ||
                  task.discovery.hn_summary) && (
                  <div>
                    <SectionLabel>Community Sentiment</SectionLabel>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {task.discovery.ih_summary ||
                        task.discovery.reddit_summary ||
                        task.discovery.hn_summary}
                    </p>
                  </div>
                )}

                {/* Sources */}
                {task.discovery.full_report?.sources?.length ? (
                  <div>
                    <SectionLabel>Sources</SectionLabel>
                    <ul className="space-y-2">
                      {task.discovery.full_report.sources.map((s, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs">
                          <span className="inline-block bg-muted px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wide shrink-0 mt-0.5">
                            {s.platform}
                          </span>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline leading-relaxed"
                          >
                            {s.title}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
                <StatusIcon status={task.status} />
                <p className="text-sm mt-1">
                  {task.status === "pending"
                    ? "Discovery hasn't run yet. Runs nightly at 02:00 UTC."
                    : task.status === "processing"
                    ? "Discovery is currently running…"
                    : task.status === "error"
                    ? "Discovery failed for this task."
                    : "No discovery data available."}
                </p>
              </div>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
