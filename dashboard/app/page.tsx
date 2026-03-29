import { getTasks } from "@/lib/api";
import { TasksTable } from "@/components/tasks-table";
import { RefreshButton } from "@/components/refresh-button";
import { ThemeToggle } from "@/components/theme-toggle";

export const revalidate = 30;

export default async function Home() {
  let tasks = [];
  let error = null;

  try {
    tasks = await getTasks({ limit: 100 });
    const withDiscovery = await Promise.all(
      tasks.map(async (task) => {
        if (task.status !== "done") return task;
        try {
          const res = await fetch(
            `${process.env.DATA_API_URL}/tasks/${task.id}`,
            {
              headers: { "X-API-Key": process.env.DATA_API_KEY! },
              next: { revalidate: 30 },
            }
          );
          return res.ok ? res.json() : task;
        } catch {
          return task;
        }
      })
    );
    tasks = withDiscovery;
  } catch (e) {
    error = "Could not connect to data API.";
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Tasks</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              All tasks from your Telegram bot
            </p>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <RefreshButton />
          </div>
        </div>

        {error ? (
          <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <TasksTable tasks={tasks} />
        )}
      </div>
    </div>
  );
}
