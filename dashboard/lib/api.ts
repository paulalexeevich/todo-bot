const API_URL = process.env.DATA_API_URL!;
const API_KEY = process.env.DATA_API_KEY!;

function headers() {
  return { "X-API-Key": API_KEY };
}

export interface Task {
  id: number;
  text: string;
  type: string;
  status: string;
  created_at: string;
  discovery?: Discovery | null;
}

export interface Discovery {
  id: number;
  task_id: number;
  ran_at: string;
  reddit_summary: string | null;
  hn_summary: string | null;
  ph_summary: string | null;
  ih_summary: string | null;
  verdict: string | null;
  score: number | null;
  market_size: string | null;
  full_report: {
    competitors?: string[];
    sentiment_summary?: string;
    sources?: { platform: string; title: string; url: string }[];
  } | null;
}

export async function getTasks(params?: {
  status?: string;
  type?: string;
  limit?: number;
}): Promise<Task[]> {
  const url = new URL(`${API_URL}/tasks`);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.type) url.searchParams.set("type", params.type);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));

  const res = await fetch(url.toString(), {
    headers: headers(),
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function getTask(id: number): Promise<Task> {
  const res = await fetch(`${API_URL}/tasks/${id}`, {
    headers: headers(),
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export interface Offer {
  id: number;
  task_id: number;
  title: string;
  price: string | null;
  store: string | null;
  url: string;
  snippet: string | null;
  found_at: string;
}

export async function getOffers(taskId: number): Promise<Offer[]> {
  const res = await fetch(`${API_URL}/tasks/${taskId}/offers`, {
    headers: headers(),
    next: { revalidate: 30 },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getCounts(): Promise<Record<string, number>> {
  const res = await fetch(`${API_URL}/counts`, {
    headers: headers(),
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}
