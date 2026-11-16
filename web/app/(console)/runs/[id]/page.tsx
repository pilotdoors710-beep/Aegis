import { Suspense } from "react";
import { SkeletonGroup, SkeletonCards } from "@/components/skeleton";
import { RunSession } from "./run-session";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ replay?: string; queue?: string }>;
};

async function Session({ params, searchParams }: Props) {
  const { id } = await params;
  const query = await searchParams;
  return <RunSession key={`${id}:${query.replay}`} runId={id} replay={query.replay === "1"} queue={Math.max(0, Number(query.queue) || 0)} />;
}

export default function RunPage(props: Props) {
  return <Suspense fallback={<SkeletonGroup label="Loading run…"><SkeletonCards n={2} /></SkeletonGroup>}><Session {...props} /></Suspense>;
}
