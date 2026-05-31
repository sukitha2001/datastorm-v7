"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useMap } from "react-leaflet"
import L from "leaflet"
import "leaflet.markercluster"
import { SlidersHorizontal } from "lucide-react"
import type { LatLngExpression } from "leaflet"
import type { PlaceFeature } from "@/components/ui/place-autocomplete"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Map,
  MapControlContainer,
  MapTileLayer,
  MapZoomControl,
  MapLayers,
  MapLayersControl,
  MapLayerGroup,
  MapSearchControl,
} from "@/components/ui/map"

const TYPE_MAP: Record<string, string> = {
  Kiosk: "kade",
  Grocery: "grocery",
  Grocry: "grocery",
  Eatery: "eatery",
  " Eatery ": "eatery",
  Bakery: "eatery",
  Bakry: "eatery",
  Pharmacy: "pharmacy",
  Hotel: "other",
  SMMT: "other",
}

const TYPE_ORDER = ["kade", "grocery", "eatery", "pharmacy", "other"] as const
type OutletType = (typeof TYPE_ORDER)[number]
type VolumeFilter = "all" | "major" | "high" | "growth" | "small"
type HotspotFilter = "all" | "hotspot" | "standard"
type SpendFilter = "all" | "allocated" | "unallocated"
type CoolerFilter = "all" | "has-cooler" | "no-cooler"

interface MapFilters {
  volume: VolumeFilter
  hotspot: HotspotFilter
  spend: SpendFilter
  cooler: CoolerFilter
}

const TYPE_LABEL: Record<OutletType, string> = {
  kade: "Kiosk",
  grocery: "Grocery",
  eatery: "Eatery",
  pharmacy: "Pharmacy",
  other: "Other",
}

interface Outlet {
  Outlet_ID: string
  Maximum_Monthly_Liters: number
  Latitude: number
  Longitude: number
  Outlet_Type?: string
  Outlet_Size?: string
  Cooler_Count?: number
  historical_max_volume?: number
  incremental_volume?: number
  rd_demand_pressure?: number
  Trade_Spend_LKR?: number
}

interface Props {
  outlets: Outlet[]
}

function normalizeType(raw: string | undefined): OutletType {
  if (!raw) return "other"
  const t = TYPE_MAP[raw.trim()]
  return TYPE_ORDER.includes(t as OutletType) ? (t as OutletType) : "other"
}

function getLatentPotential(o: Outlet) {
  return (
    o.incremental_volume ??
    (o.historical_max_volume != null
      ? Math.max(o.Maximum_Monthly_Liters - o.historical_max_volume, 0)
      : o.Maximum_Monthly_Liters)
  )
}

function isHotspotOutlet(o: Outlet, hotspotThreshold: number) {
  return o.rd_demand_pressure != null
    ? o.rd_demand_pressure >= 0.7
    : getLatentPotential(o) >= hotspotThreshold
}

function matchesFilters(
  outlet: Outlet,
  filters: MapFilters,
  hotspotThreshold: number
) {
  const volume = outlet.Maximum_Monthly_Liters

  if (filters.volume === "major" && volume < 1500) return false
  if (filters.volume === "high" && (volume < 1000 || volume >= 1500)) {
    return false
  }
  if (filters.volume === "growth" && (volume < 500 || volume >= 1000)) {
    return false
  }
  if (filters.volume === "small" && volume >= 500) return false

  const isHotspot = isHotspotOutlet(outlet, hotspotThreshold)
  if (filters.hotspot === "hotspot" && !isHotspot) return false
  if (filters.hotspot === "standard" && isHotspot) return false

  const hasSpend = (outlet.Trade_Spend_LKR ?? 0) > 0
  if (filters.spend === "allocated" && !hasSpend) return false
  if (filters.spend === "unallocated" && hasSpend) return false

  const hasCooler = (outlet.Cooler_Count ?? 0) > 0
  if (filters.cooler === "has-cooler" && !hasCooler) return false
  if (filters.cooler === "no-cooler" && hasCooler) return false

  return true
}

function getColor(v: number): string {
  if (v > 20000) return "#dc2626"
  if (v > 10000) return "#ea580c"
  if (v > 5000) return "#ca8a04"
  if (v > 2000) return "#65a30d"
  return "#2563eb"
}

function BoundsUpdater({ outlets }: { outlets: Outlet[] }) {
  const map = useMap()
  useEffect(() => {
    if (outlets.length === 0) return
    const coords = outlets.map(
      (o) => [o.Latitude, o.Longitude] as [number, number]
    )
    map.fitBounds(L.latLngBounds(coords))
  }, [outlets, map])
  return null
}

function MapResizer() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      try {
        map.invalidateSize()
      } catch {}
    })
    const el = map.getContainer().parentElement
    if (el) observer.observe(el)
    return () => observer.disconnect()
  }, [map])
  return null
}

function SearchHandler({
  onPlaceSelect,
}: {
  onPlaceSelect: (feature: PlaceFeature) => void
}) {
  const map = useMap()
  const handleSelect = useCallback(
    (feature: PlaceFeature) => {
      const [lng, lat] = feature.geometry.coordinates
      map.flyTo([lat, lng], 15, { duration: 1.5 })
      onPlaceSelect(feature)
    },
    [map, onPlaceSelect]
  )
  return <MapSearchControl onPlaceSelect={handleSelect} />
}

function ClusterIcon({ count }: { count: number }) {
  return `<div style="width:40px;height:40px;border-radius:50%;border:2px solid white;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:white;box-shadow:0 2px 6px rgba(0,0,0,.3)">${count}</div>`
}

const fmt = (v: number) =>
  v.toLocaleString(undefined, { maximumFractionDigits: 0 })

function quantile(values: number[], q: number) {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  return sorted[base + 1] !== undefined
    ? sorted[base] + rest * (sorted[base + 1] - sorted[base])
    : sorted[base]
}

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

function markerHtml(color: string) {
  return `<div style="width:28px;height:28px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.3)"><div style="width:7px;height:7px;border-radius:50%;background:white"></div></div>`
}

function popupHtml(
  o: Outlet,
  outletType: OutletType,
  hotspotThreshold: number
) {
  const isHotspot = isHotspotOutlet(o, hotspotThreshold)
  const hotspotText = isHotspot ? "Hot spot" : "Standard catchment"
  const hotspotColor = isHotspot ? "#dc2626" : "#2563eb"
  const hotspotBg = isHotspot ? "#fee2e2" : "#dbeafe"
  const coolerText =
    o.Cooler_Count != null
      ? ` &middot; ${fmt(o.Cooler_Count)} cooler${o.Cooler_Count === 1 ? "" : "s"}`
      : ""
  const spendText = o.Trade_Spend_LKR
    ? `<div style="display:flex;justify-content:space-between;gap:12px;padding:8px 0 0;border-top:1px solid #e5e7eb">
        <span style="color:#6b7280">Promo spend</span>
        <strong style="color:#16a34a">LKR ${fmt(o.Trade_Spend_LKR)}</strong>
      </div>`
    : ""

  return `<div style="font-family:system-ui,sans-serif;font-size:13px;line-height:1.4;min-width:220px;color:#111827;background:#f9fafb;padding:20px">
    <div style="display:flex;align-items:flex-start;gap:12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb">
      <div>
        <p style="font-weight:700;margin:0;font-size:14px">${escapeHtml(o.Outlet_ID)}</p>
        <p style="font-size:12px;color:#6b7280;margin:2px 0 0">${TYPE_LABEL[outletType]}</p>
      </div>
      <span style="white-space:nowrap;border-radius:999px;background:${hotspotBg};color:${hotspotColor};font-size:11px;font-weight:700;padding:3px 8px">${hotspotText}</span>
    </div>

    <div style="display:grid;grid-template-columns:1fr;gap:8px;margin:10px 0">
      <div style="border:1px solid #e5e7eb;border-radius:8px;padding:8px;background:#f9fafb">
        <div style="font-size:11px;color:#6b7280">Max monthly</div>
        <div style="font-weight:800;font-size:16px;color:#111827">${fmt(o.Maximum_Monthly_Liters)} L</div>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;gap:8px;color:#6b7280">
      <span>Profile</span>
      <strong style="color:#374151;font-weight:600">${escapeHtml(o.Outlet_Size || "Unknown")}${coolerText}</strong>
    </div>
    ${
      o.rd_demand_pressure != null
        ? `<div style="display:flex;justify-content:space-between;gap:12px;margin-top:4px;color:#6b7280"><span>RD pressure</span><strong style="color:#374151">${o.rd_demand_pressure.toFixed(2)}</strong></div>`
        : ""
    }
    ${spendText}
  </div>`
}

function OutletMarkers({
  outlets,
  hotspotThreshold,
}: {
  outlets: Outlet[]
  hotspotThreshold: number
}) {
  const map = useMap()

  useEffect(() => {
    if (outlets.length === 0) return

    let clusterGroup: L.MarkerClusterGroup | null = null
    const mountTimer = window.setTimeout(() => {
      clusterGroup = L.markerClusterGroup({
        showCoverageOnHover: false,
        chunkedLoading: true,
        iconCreateFunction(cluster) {
          return L.divIcon({
            html: ClusterIcon({ count: cluster.getChildCount() }),
            className: "outlet-cluster-icon",
            iconSize: [40, 40],
            iconAnchor: [20, 20],
          })
        },
      })

      for (const o of outlets) {
        const outletType = normalizeType(o.Outlet_Type)
        const marker = L.marker([o.Latitude, o.Longitude], {
          icon: L.divIcon({
            html: markerHtml(getColor(o.Maximum_Monthly_Liters)),
            className: "outlet-marker-icon",
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -14],
          }),
        }).bindPopup(popupHtml(o, outletType, hotspotThreshold))

        clusterGroup.addLayer(marker)
      }

      map.addLayer(clusterGroup)
    }, 0)

    return () => {
      window.clearTimeout(mountTimer)
      if (clusterGroup) {
        clusterGroup.clearLayers()
        if (map.hasLayer(clusterGroup)) {
          map.removeLayer(clusterGroup)
        }
      }
    }
  }, [hotspotThreshold, map, outlets])

  return null
}

function MapFilterControl({
  filters,
  filteredCount,
  totalCount,
  onFiltersChange,
}: {
  filters: MapFilters
  filteredCount: number
  totalCount: number
  onFiltersChange: (filters: MapFilters) => void
}) {
  const activeCount = [
    filters.volume !== "all",
    filters.hotspot !== "all",
    filters.spend !== "all",
    filters.cooler !== "all",
  ].filter(Boolean).length

  return (
    <MapControlContainer className="top-1 right-12">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="secondary"
            size="icon-sm"
            aria-label="Filter outlets"
            title="Filter outlets"
            className="border"
          >
            <SlidersHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="z-1000 w-56">
          <DropdownMenuLabel>
            {fmt(filteredCount)} of {fmt(totalCount)} outlets
            {activeCount > 0 ? ` · ${activeCount} active` : ""}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Volume</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={filters.volume}
            onValueChange={(volume) =>
              onFiltersChange({ ...filters, volume: volume as VolumeFilter })
            }
          >
            <DropdownMenuRadioItem value="all">All volumes</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="major">1,500+ L</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="high">1,000-1,500 L</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="growth">500-1,000 L</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="small">Below 500 L</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Demand Signal</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={filters.hotspot}
            onValueChange={(hotspot) =>
              onFiltersChange({ ...filters, hotspot: hotspot as HotspotFilter })
            }
          >
            <DropdownMenuRadioItem value="all">All signals</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="hotspot">Hot spots</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="standard">
              Standard catchments
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Promo Spend</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={filters.spend}
            onValueChange={(spend) =>
              onFiltersChange({ ...filters, spend: spend as SpendFilter })
            }
          >
            <DropdownMenuRadioItem value="all">All outlets</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="allocated">Allocated</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="unallocated">
              Unallocated
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Coolers</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={filters.cooler}
            onValueChange={(cooler) =>
              onFiltersChange({ ...filters, cooler: cooler as CoolerFilter })
            }
          >
            <DropdownMenuRadioItem value="all">All cooler states</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="has-cooler">Has cooler</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="no-cooler">No cooler</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </MapControlContainer>
  )
}

export default function OutletMap({ outlets }: Props) {
  const COLOMBO_COORDINATES = [6.920575, 79.859823] satisfies LatLngExpression
  const [filters, setFilters] = useState<MapFilters>({
    volume: "all",
    hotspot: "all",
    spend: "all",
    cooler: "all",
  })
  const hotspotThreshold = useMemo(
    () =>
      quantile(
        outlets.map((o) => o.incremental_volume ?? o.Maximum_Monthly_Liters),
        0.75
      ),
    [outlets]
  )
  const filteredOutlets = useMemo(
    () =>
      outlets.filter((outlet) =>
        matchesFilters(outlet, filters, hotspotThreshold)
      ),
    [filters, hotspotThreshold, outlets]
  )
  const outletsByType = useMemo(() => {
    const groups: Record<OutletType, Outlet[]> = {
      kade: [],
      grocery: [],
      eatery: [],
      pharmacy: [],
      other: [],
    }
    for (const outlet of filteredOutlets) {
      groups[normalizeType(outlet.Outlet_Type)].push(outlet)
    }
    return groups
  }, [filteredOutlets])

  return (
    <Map center={COLOMBO_COORDINATES} zoom={8} className="h-full w-full">
      <MapLayers
        defaultTileLayer="Default"
        defaultLayerGroups={["Kiosk", "Grocery", "Eatery", "Pharmacy", "Other"]}
      >
        <MapTileLayer name="Default" />
        <MapTileLayer
          name="OSM"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />
        <MapTileLayer
          name="Satellite"
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="&copy; Esri"
        />

        <MapZoomControl position="bottom-1 left-1" />
        <MapLayersControl position="top-1 right-1" />
        <MapFilterControl
          filters={filters}
          filteredCount={filteredOutlets.length}
          totalCount={outlets.length}
          onFiltersChange={setFilters}
        />
        <SearchHandler onPlaceSelect={() => {}} />

        <BoundsUpdater outlets={filteredOutlets} />
        <MapResizer />
        {TYPE_ORDER.map((type) => (
          <MapLayerGroup key={type} name={TYPE_LABEL[type]}>
            <OutletMarkers
              outlets={outletsByType[type]}
              hotspotThreshold={hotspotThreshold}
            />
          </MapLayerGroup>
        ))}
      </MapLayers>
    </Map>
  )
}
