import { NextRequest, NextResponse } from "next/server";
import { getTasks } from "@/lib/api";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const tasks = await getTasks({
    status: searchParams.get("status") ?? undefined,
    type: searchParams.get("type") ?? undefined,
    limit: 100,
  });
  return NextResponse.json(tasks);
}
