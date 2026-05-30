import { Skeleton } from "@/components/ui/skeleton"

export default function MapLoading() {
  return (
    <div className="flex flex-col gap-2 p-4 lg:p-6" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="flex items-center justify-between px-1 pb-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="relative flex-1 rounded-lg border overflow-hidden" style={{ minHeight: 400 }}>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Skeleton className="size-12 rounded-full" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
      </div>
    </div>
  )
}
