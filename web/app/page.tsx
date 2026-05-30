import fs from "fs"
import path from "path"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { DataTable } from "@/components/data-table"
import { SectionCards, type CardData } from "@/components/section-cards"

const DATA_DIR = path.join(process.cwd(), "public", "data")

function readJSON(filename: string): any[] {
  const p = path.join(DATA_DIR, filename)
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : []
}

const fmt = (v: number) =>
  v.toLocaleString(undefined, { maximumFractionDigits: 0 })
const fmtMoney = (v: number) =>
  "LKR " + v.toLocaleString(undefined, { maximumFractionDigits: 0 })

export default function OverviewPage() {
  const coords = readJSON("outlet_coordinates.json")
  const preds = readJSON("predictions.json")
  const budget = readJSON("budget_allocations.json")

  const validCoords = coords.filter(
    (c: any) =>
      typeof c.Latitude === "number" && typeof c.Longitude === "number"
  )
  const wpCoords = validCoords.filter(
    (c: any) =>
      c.Latitude >= 6.4 &&
      c.Latitude <= 7.2 &&
      c.Longitude >= 79.7 &&
      c.Longitude <= 80.2
  )

  const totalVolume = preds.reduce(
    (s: number, p: any) => s + (p.Maximum_Monthly_Liters ?? 0),
    0
  )
  const avgVolume = preds.length ? totalVolume / preds.length : 0
  const totalBudget = budget.reduce(
    (s: number, b: any) => s + (b.Trade_Spend_LKR ?? 0),
    0
  )
  const wpShare =
    validCoords.length > 0
      ? ((wpCoords.length / validCoords.length) * 100).toFixed(1)
      : "0"

  const sorted = [...budget].sort(
    (a: any, b: any) => b.Trade_Spend_LKR - a.Trade_Spend_LKR
  )

  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <SectionCards
        cards={
          [
            // {
            //   label: "Total Outlets",
            //   value: fmt(coords.length),
            //   extra: "All provinces included",
            // },
            {
              label: "Western Province Outlets",
              value: fmt(wpCoords.length),
              sub: `${wpShare}% of total`,
            },
            // {
            //   label: "Avg Predicted Volume",
            //   value: `${fmt(Math.round(avgVolume))} L/mo`,
            // },
            {
              label: "Total Addressable Volume",
              value: `${fmt(Math.round(totalVolume))} L/mo`,
            },
            {
              label: "Budget Allocations",
              value: `${fmt(budget.length)} outlets`,
              extra: `${fmtMoney(Math.round(totalBudget))} total`,
            },
            // {
            //   label: "Promo Budget",
            //   value: fmtMoney(Math.round(totalBudget)),
            //   sub: "LKR 5M cap",
            //   extra: `${((totalBudget / 5_000_000) * 100).toFixed(1)}% utilized`,
            // },
          ] satisfies CardData[]
        }
      />

      {/*<div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">
              Strategy Summary
            </CardTitle>
            <CardDescription>
              Allocating <strong>{fmtMoney(Math.round(totalBudget))}</strong> in
              promotional trade spend across{" "}
              <strong>{fmt(budget.length)} Western Province outlets</strong> to
              maximize incremental volume. The latent demand model estimates a
              total addressable volume of{" "}
              <strong>{fmt(Math.round(totalVolume))} L/mo</strong> across all{" "}
              {fmt(coords.length)} outlets.
              <br /><br />
              <strong>Budget cap:</strong> LKR 5,000,000 &middot;{" "}
              <strong>Utilized:</strong> {fmtMoney(Math.round(totalBudget))} ({((totalBudget / 5_000_000) * 100).toFixed(1)}%)
            </CardDescription>
          </CardHeader>
        </Card>
      </div>*/}

      <div className="px-4 lg:px-6">
        <DataTable data={sorted} />
      </div>
    </div>
  )
}
