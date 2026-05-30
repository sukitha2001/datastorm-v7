import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function CardSkeleton() {
  return (
    <Card className="flex-1 min-w-[180px]">
      <CardHeader>
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-32 mt-1" />
        <Skeleton className="h-5 w-20 mt-1" />
      </CardHeader>
      <CardFooter>
        <Skeleton className="h-3 w-36" />
      </CardFooter>
    </Card>
  )
}

function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-8 w-32 ml-auto" />
      </div>
      <div className="rounded-md border">
        <div className="border-b p-3">
          <div className="flex gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-4 flex-1" />
            ))}
          </div>
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="border-b p-3">
            <div className="flex gap-4">
              {Array.from({ length: 5 }).map((_, j) => (
                <Skeleton key={j} className="h-4 flex-1" />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <div className="flex gap-1">
          <Skeleton className="size-8" />
          <Skeleton className="size-8" />
        </div>
      </div>
    </div>
  )
}

export default function OverviewLoading() {
  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <div className="flex flex-row flex-wrap gap-4 px-4 lg:px-6">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>

      <div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
          </CardHeader>
          <CardContent>
            <TableSkeleton />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
