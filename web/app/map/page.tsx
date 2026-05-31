import fs from "fs"
import path from "path"
import MapCard from "@/components/map-card"

const DATA_DIR = path.join(process.cwd(), "public", "data")

type JsonRecord = Record<string, unknown>

function readJSON(filename: string): JsonRecord[] {
  const filePath = path.join(DATA_DIR, filename)

  if (!fs.existsSync(filePath)) {
    return []
  }

  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as JsonRecord[]
}

function asNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

export default function MapPage() {
  const outletRows = readJSON("outlets.json")
  const coordinates = outletRows.length > 0 ? outletRows : readJSON("outlet_coordinates.json")
  const predictions = outletRows.length > 0 ? [] : readJSON("predictions.json")
  const budgetAllocations = outletRows.length > 0 ? [] : readJSON("budget_allocations.json")

  const predictionByOutlet = new Map(
    predictions.map((row) => [
      String(row.Outlet_ID),
      asNumber(row.Maximum_Monthly_Liters),
    ])
  )
  const spendByOutlet = new Map(
    budgetAllocations.map((row) => [
      String(row.Outlet_ID),
      asNumber(row.Trade_Spend_LKR),
    ])
  )

  const outlets = coordinates
    .map((row) => {
      const outletId = String(row.Outlet_ID)

      return {
        Outlet_ID: outletId,
        Latitude: asNumber(row.Latitude),
        Longitude: asNumber(row.Longitude),
        Maximum_Monthly_Liters:
          asNumber(row.Maximum_Monthly_Liters) ||
          predictionByOutlet.get(outletId) ||
          0,
        Trade_Spend_LKR:
          asNumber(row.Trade_Spend_LKR) || spendByOutlet.get(outletId) || 0,
      }
    })
    .filter(
      (row) =>
        Number.isFinite(row.Latitude) &&
        Number.isFinite(row.Longitude) &&
        !(row.Latitude === 0 && row.Longitude === 0)
    )

  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <div className="px-4 lg:px-6">
        <h1 className="text-lg font-semibold">Outlet Map</h1>
        <p className="text-sm text-muted-foreground">
          All mapped outlets with clustered hotspot coloring and demand hotspot
          regions.
        </p>
      </div>

      <div className="px-4 lg:px-6">
        <MapCard outlets={outlets} />
      </div>
    </div>
  )
}
