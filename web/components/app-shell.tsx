"use client"

import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"
import dynamic from "next/dynamic"
import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Skeleton } from "@/components/ui/skeleton"

const LazyOutletMap = dynamic(() => import("@/components/outlet-map"), {
  ssr: false,
})

interface Outlet {
  Outlet_ID: string
  Maximum_Monthly_Liters: number
  Latitude: number
  Longitude: number
  Outlet_Type?: string
  Outlet_Size?: string
  Cooler_Count?: number
  Distributor_ID?: string
  Trade_Spend_LKR?: number
}

function isWesternProvince(lat: number, lng: number) {
  return lat >= 6.4 && lat <= 7.2 && lng >= 79.7 && lng <= 80.2
}

function useMapData() {
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        console.log("[useMapData] fetching outlets.json...")
        const res = await fetch("/data/outlets.json")
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const all: Outlet[] = await res.json()
        if (cancelled) return
        console.log("[useMapData] loaded", all.length, "outlets")

        const western = all.filter(
          (o) =>
            typeof o.Latitude === "number" &&
            typeof o.Longitude === "number" &&
            !isNaN(o.Latitude) &&
            !isNaN(o.Longitude) &&
            isWesternProvince(o.Latitude, o.Longitude)
        )
        console.log("[useMapData] western outlets:", western.length)

        setOutlets(western)
        setLoaded(true)
      } catch (err) {
        console.error("[useMapData] error:", err)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  return { outlets, loaded }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isMapPage = pathname === "/map"
  const { outlets, loaded } = useMapData()

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />

        {/* Page content — hidden on map page */}
        <div
          style={{
            display: isMapPage ? "none" : "flex",
            flexDirection: "column",
            flex: 1,
            minHeight: 0,
          }}
        >
          {children}
        </div>

        {/* Map — hidden off-screen on non-map pages, fills layout on map page */}
        <div
          style={
            isMapPage
              ? {
                  display: "flex",
                  flexDirection: "column",
                  flex: 1,
                  minHeight: 0,
                  padding: "12px 24px",
                }
              : {
                  position: "absolute",
                  left: "-9999px",
                  top: "-9999px",
                  width: "100vw",
                  height: "100vh",
                  display: "flex",
                  flexDirection: "column",
                }
          }
        >
          <div
            style={{
              border: "1px solid #e5e5e5",
              borderRadius: 8,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
              background: "#fff",
              flex: 1,
              minHeight: 0,
              fontFamily: "system-ui, sans-serif",
            }}
          >
            <div
              style={{
                padding: "10px 14px",
                borderBottom: "1px solid #e5e5e5",
                fontSize: 14,
                fontWeight: 600,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              {loaded ? (
                <>
                  <span>Western Province — Outlet Map</span>
                  <span style={{ color: "#666", fontWeight: 400, fontSize: 13 }}>
                    {outlets.length.toLocaleString()} outlets
                  </span>
                </>
              ) : (
                <>
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-20" />
                </>
              )}
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              {loaded ? (
                <LazyOutletMap outlets={outlets} />
              ) : (
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 12,
                    }}
                  >
                    <Skeleton className="size-12 rounded-full" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
