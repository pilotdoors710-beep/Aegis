import { SkeletonCards, SkeletonGroup, Skeleton } from "@/components/skeleton";

// Shown while a console route's code or server data is still arriving.
export default function Loading() {
  return <SkeletonGroup label="Loading page…"><Skeleton className="skeleton-line is-title" /><SkeletonCards n={3} /></SkeletonGroup>;
}
