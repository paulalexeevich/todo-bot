"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Search,
  ChevronUp,
  ChevronDown,
  ChevronRight,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScoreBadge } from "@/components/score-badge";
import { TaskDetail } from "@/components/task-detail";
import { cn } from "@/lib/utils";
import type { Task } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  idea: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  todo: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  note: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  shopping: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  learning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  architecture: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  question: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
};

export function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "pending":
      return <Clock size={13} className="text-amber-500 shrink-0" />;
    case "processing":
      return <Loader2 size={13} className="text-blue-500 animate-spin shrink-0" />;
    case "done":
      return <CheckCircle2 size={13} className="text-green-500 shrink-0" />;
    case "error":
      return <XCircle size={13} className="text-red-500 shrink-0" />;
    default:
      return <span className="w-3 h-3 rounded-full bg-muted-foreground/30 shrink-0" />;
  }
}

const TASK_TYPES = [
  "idea",
  "todo",
  "note",
  "shopping",
  "learning",
  "architecture",
  "question",
];

type SortField = "id" | "type" | "status" | "score" | "date";
type SortDir = "asc" | "desc";

const STATUS_ORDER = ["pending", "processing", "done", "error"];

export function TasksTable({ tasks }: { tasks: Task[] }) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ field: SortField; dir: SortDir } | null>(null);
  const [selected, setSelected] = useState<Task | null>(null);
  const [groupByStatus, setGroupByStatus] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const filtered = tasks.filter((t) => {
    if (statusFilter === "pending" && t.status !== "pending") return false;
    if (statusFilter === "done" && t.status !== "done") return false;
    if (typeFilter !== "all" && t.type !== typeFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!t.text.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const sorted = sort
    ? [...filtered].sort((a, b) => {
        let av: string | number, bv: string | number;
        switch (sort.field) {
          case "id":
            av = a.id;
            bv = b.id;
            break;
          case "type":
            av = a.type;
            bv = b.type;
            break;
          case "status":
            av = a.status;
            bv = b.status;
            break;
          case "score":
            av = a.discovery?.score ?? -1;
            bv = b.discovery?.score ?? -1;
            break;
          case "date":
            av = a.created_at;
            bv = b.created_at;
            break;
          default:
            av = 0;
            bv = 0;
        }
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sort.dir === "asc" ? cmp : -cmp;
      })
    : filtered;

  function toggleSort(field: SortField) {
    setSort((prev) =>
      prev?.field === field
        ? { field, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { field, dir: "asc" }
    );
  }

  function toggleGroup(group: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      next.has(group) ? next.delete(group) : next.add(group);
      return next;
    });
  }

  function SortIndicator({ field }: { field: SortField }) {
    if (sort?.field !== field)
      return <ChevronUp size={11} className="opacity-0 group-hover:opacity-40 transition-opacity" />;
    return sort.dir === "asc" ? (
      <ChevronUp size={11} className="text-foreground" />
    ) : (
      <ChevronDown size={11} className="text-foreground" />
    );
  }

  const grouped = groupByStatus
    ? STATUS_ORDER.map((status) => ({
        status,
        rows: sorted.filter((t) => t.status === status),
      })).filter((g) => g.rows.length > 0)
    : null;

  const pendingCount = tasks.filter((t) => t.status === "pending").length;
  const doneCount = tasks.filter((t) => t.status === "done").length;

  return (
    <>
      <div className="flex flex-col gap-3 mb-4">
        {/* Row 1: status tabs + search + group toggle */}
        <div className="flex items-center gap-2 flex-wrap">
          <Tabs value={statusFilter} onValueChange={setStatusFilter}>
            <TabsList>
              <TabsTrigger value="all">
                All
                <span className="ml-1 text-[11px] text-muted-foreground">
                  ({tasks.length})
                </span>
              </TabsTrigger>
              <TabsTrigger value="pending">
                Pending
                <span className="ml-1 text-[11px] text-muted-foreground">
                  ({pendingCount})
                </span>
              </TabsTrigger>
              <TabsTrigger value="done">
                Done
                <span className="ml-1 text-[11px] text-muted-foreground">
                  ({doneCount})
                </span>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="relative flex-1 min-w-44">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search… (⌘K)"
              className="w-full pl-8 pr-7 py-1.5 text-sm rounded-md border bg-background focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/60"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={13} />
              </button>
            )}
          </div>

          <button
            onClick={() => setGroupByStatus((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md border transition-colors whitespace-nowrap",
              groupByStatus
                ? "bg-foreground text-background border-foreground"
                : "bg-background text-muted-foreground hover:text-foreground border-border"
            )}
          >
            <SlidersHorizontal size={12} />
            Group
          </button>
        </div>

        {/* Row 2: type filter pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setTypeFilter("all")}
            className={cn(
              "px-2.5 py-0.5 rounded-full text-xs border transition-colors",
              typeFilter === "all"
                ? "bg-foreground text-background border-foreground"
                : "text-muted-foreground hover:text-foreground border-transparent hover:border-border"
            )}
          >
            All types
          </button>
          {TASK_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setTypeFilter((t) => (t === type ? "all" : type))}
              className={cn(
                "px-2.5 py-0.5 rounded-full text-xs border transition-colors capitalize",
                typeFilter === type
                  ? cn(TYPE_COLOR[type], "border-transparent")
                  : "text-muted-foreground hover:text-foreground border-transparent hover:border-border"
              )}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40">
              {(
                [
                  { label: "#", field: "id" as SortField, className: "w-10" },
                  { label: "Task", field: null, className: "" },
                  { label: "Type", field: "type" as SortField, className: "w-20" },
                  { label: "Status", field: "status" as SortField, className: "w-28" },
                  { label: "Score", field: "score" as SortField, className: "w-16" },
                  {
                    label: "Date",
                    field: "date" as SortField,
                    className: "w-28 hidden sm:table-cell",
                  },
                ] as const
              ).map(({ label, field, className }) => (
                <th
                  key={label}
                  onClick={field ? () => toggleSort(field) : undefined}
                  className={cn(
                    "py-2.5 px-3 text-left select-none",
                    className,
                    field
                      ? "cursor-pointer group hover:text-foreground"
                      : "cursor-default"
                  )}
                >
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {label}
                    {field && <SortIndicator field={field} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grouped ? (
              grouped.map(({ status, rows }) => {
                const collapsed = collapsedGroups.has(status);
                return (
                  <React.Fragment key={status}>
                    <tr
                      onClick={() => toggleGroup(status)}
                      className="border-b bg-muted/20 cursor-pointer hover:bg-muted/40 transition-colors"
                    >
                      <td colSpan={6} className="py-1.5 px-3">
                        <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
                          <ChevronRight
                            size={12}
                            className={cn(
                              "transition-transform",
                              !collapsed && "rotate-90"
                            )}
                          />
                          <StatusIcon status={status} />
                          <span className="capitalize">{status}</span>
                          <span className="text-muted-foreground/50">
                            ({rows.length})
                          </span>
                        </span>
                      </td>
                    </tr>
                    {!collapsed &&
                      rows.map((task) => (
                        <TaskRow
                          key={task.id}
                          task={task}
                          onClick={() => setSelected(task)}
                        />
                      ))}
                  </React.Fragment>
                );
              })
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Search size={28} strokeWidth={1.5} />
                    <p className="text-sm font-medium text-foreground">
                      No tasks found
                    </p>
                    <p className="text-xs">
                      {search
                        ? `No results for "${search}"`
                        : "Try adjusting your filters"}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              sorted.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onClick={() => setSelected(task)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <TaskDetail task={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function TaskRow({ task, onClick }: { task: Task; onClick: () => void }) {
  return (
    <tr
      onClick={onClick}
      className="border-b last:border-0 hover:bg-muted/30 cursor-pointer transition-colors"
    >
      <td className="py-2.5 px-3 text-xs text-muted-foreground tabular-nums">
        {task.id}
      </td>
      <td className="py-2.5 px-3 max-w-xs">
        <span className="line-clamp-2 text-sm font-medium leading-snug">
          {task.text}
        </span>
      </td>
      <td className="py-2.5 px-3">
        <span
          className={cn(
            "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize",
            TYPE_COLOR[task.type] ?? "bg-gray-100 text-gray-700"
          )}
        >
          {task.type}
        </span>
      </td>
      <td className="py-2.5 px-3">
        <span className="flex items-center gap-1.5">
          <StatusIcon status={task.status} />
          <span className="text-xs text-muted-foreground capitalize">
            {task.status}
          </span>
        </span>
      </td>
      <td className="py-2.5 px-3">
        <ScoreBadge score={task.discovery?.score ?? null} />
      </td>
      <td className="py-2.5 px-3 text-xs text-muted-foreground tabular-nums hidden sm:table-cell">
        {new Date(task.created_at).toLocaleDateString()}
      </td>
    </tr>
  );
}
