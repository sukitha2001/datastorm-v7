import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"

function SettingsCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Skeleton className="size-9 rounded-lg" />
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i}>
            <div className="flex items-center justify-between gap-4 py-3">
              <div className="space-y-1">
                <Skeleton className="h-3 w-28" />
                <Skeleton className="h-2 w-36" />
              </div>
              <Skeleton className="h-8 w-44" />
            </div>
            <Separator />
          </div>
        ))}
        <div className="pt-4">
          <Skeleton className="h-9 w-36" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function SettingsLoading() {
  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <div className="space-y-1 px-4 lg:px-6">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-3 w-64" />
      </div>

      <div className="space-y-4 px-4 lg:px-6">
        <SettingsCardSkeleton />
        <SettingsCardSkeleton />
        <SettingsCardSkeleton />
      </div>
    </div>
  )
}
