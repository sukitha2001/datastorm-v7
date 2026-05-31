"use client"

import dynamic from "next/dynamic"

type Outlet = {
  Outlet_ID: string
  Latitude: number
  Longitude: number
  Maximum_Monthly_Liters: number
  Trade_Spend_LKR?: number
}

const OutletMap = dynamic(() => import("@/components/outlet-map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[calc(100vh-13rem)] min-h-[560px] items-center justify-center rounded-md border bg-card text-sm text-muted-foreground">
      Loading outlet map...
    </div>
  ),
})

export default function MapCard({ outlets }: { outlets: Outlet[] }) {
  return <OutletMap outlets={outlets} />
}
