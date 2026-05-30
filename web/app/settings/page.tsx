"use client"

import { useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Brain,
  Cable,
  Check,
  Database,
  Plug,
  RadioTower,
  Settings2,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

const sections = [
  {
    id: "streaming",
    title: "Streaming",
    description: "Kafka topics and real-time event flow",
    icon: Cable,
  },
  {
    id: "warehouse",
    title: "Warehouse",
    description: "External analytics warehouse connection",
    icon: Database,
  },
  {
    id: "backend",
    title: "Backend",
    description: "Analysis datasets exposed through API streams",
    icon: RadioTower,
  },
  {
    id: "genai",
    title: "Gen AI",
    description: "LLM keys for outlet explainability",
    icon: Brain,
  },
  {
    id: "pipeline",
    title: "Pipeline",
    description: "Batch output and retry controls",
    icon: Settings2,
  },
] as const

type SectionId = (typeof sections)[number]["id"]

function SettingsRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-3 py-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,280px)] md:items-center">
      <div className="space-y-0.5">
        <Label className="text-sm font-medium">{label}</Label>
        {description ? (
          <p className="text-xs leading-5 text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <div className="flex min-w-0 items-center gap-2">{children}</div>
    </div>
  )
}

function SavedButton({
  saved,
  onClick,
  children,
}: {
  saved: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Button onClick={onClick}>
      {saved ? (
        <>
          <Check className="size-4" /> Saved
        </>
      ) : (
        children
      )}
    </Button>
  )
}

export default function SettingsPage() {
  const [activeId, setActiveId] = useState<SectionId>("streaming")
  const [saved, setSaved] = useState<Record<string, boolean>>({})
  const [backendStatus, setBackendStatus] = useState("Ready")
  const [warehouseStatus, setWarehouseStatus] = useState("Not tested")

  const activeIndex = sections.findIndex((section) => section.id === activeId)
  const active = sections[activeIndex]

  const progress = useMemo(
    () => `${activeIndex + 1} of ${sections.length}`,
    [activeIndex]
  )

  const handleSave = (key: string) => {
    setSaved((prev) => ({ ...prev, [key]: true }))
    window.setTimeout(
      () => setSaved((prev) => ({ ...prev, [key]: false })),
      2000
    )
  }

  const goTo = (direction: -1 | 1) => {
    const nextIndex =
      (activeIndex + direction + sections.length) % sections.length
    setActiveId(sections[nextIndex].id)
  }

  const testBackendStream = async () => {
    setBackendStatus("Streaming sample...")
    const response = await fetch("/api/backend/stream?dataset=outlets&limit=5")
    const text = await response.text()
    const rows = text
      .split("\n")
      .filter((line) => line.includes('"type":"row"')).length
    setBackendStatus(`Streamed ${rows} sample rows`)
  }

  const testWarehouse = async () => {
    setWarehouseStatus("Checking settings...")
    const response = await fetch("/api/backend/warehouse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "snowflake",
        host: "analytics.example.com",
        database: "datastorm",
        user: "service_user",
      }),
    })
    const payload = await response.json()
    setWarehouseStatus(payload.ok ? payload.message : payload.error)
  }

  return (
    <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
      <div className="px-4 lg:px-6">
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure live data streams, backend datasets, warehouse export, and
          explainability providers.
        </p>
      </div>

      <div className="grid gap-4 px-4 lg:grid-cols-[220px_minmax(0,1fr)] lg:px-6">
        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader className="space-y-1 pb-3">
            <CardTitle className="text-sm font-medium">Sections</CardTitle>
            <CardDescription>{progress}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {sections.map((section) => {
              const Icon = section.icon
              const selected = section.id === activeId

              return (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveId(section.id)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                    selected
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Icon className="mt-0.5 size-4 shrink-0" />
                  <span className="min-w-0">
                    <span className="block font-medium">{section.title}</span>
                    <span className="block truncate text-xs opacity-80">
                      {section.description}
                    </span>
                  </span>
                </button>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base font-medium">
                  {active.title}
                </CardTitle>
                <CardDescription>{active.description}</CardDescription>
              </div>
              <Badge variant="outline" className="shrink-0">
                {progress}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {activeId === "streaming" ? (
              <div className="space-y-1">
                <SettingsRow
                  label="Bootstrap Servers"
                  description="Kafka brokers used by real-time ingestion."
                >
                  <Input defaultValue="localhost:9092" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Consumer Group ID"
                  description="Unique consumer group for raw transaction events."
                >
                  <Input defaultValue="datastorm-consumer" />
                </SettingsRow>
                <Separator />
                <SettingsRow label="Input Topic" description="Raw event source.">
                  <Input defaultValue="raw.transactions" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Output Topic"
                  description="Processed demand prediction events."
                >
                  <Input defaultValue="predictions.output" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Security Protocol"
                  description="Use SASL_SSL for hosted clusters."
                >
                  <Select defaultValue="SASL_SSL">
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="SASL_SSL">SASL_SSL</SelectItem>
                      <SelectItem value="PLAINTEXT">PLAINTEXT</SelectItem>
                    </SelectContent>
                  </Select>
                </SettingsRow>
                <Separator />
                <SettingsRow label="SASL Username" description="Kafka identity.">
                  <div className="flex w-full items-center gap-2">
                    <Input type="password" defaultValue="admin" />
                    <Badge variant="outline" className="text-xs">
                      stored
                    </Badge>
                  </div>
                </SettingsRow>
                <div className="flex flex-wrap items-center gap-2 pt-4">
                  <SavedButton
                    saved={Boolean(saved.streaming)}
                    onClick={() => handleSave("streaming")}
                  >
                    Save Streaming Settings
                  </SavedButton>
                  <Button variant="outline">
                    <Plug className="size-4" /> Test Connection
                  </Button>
                </div>
              </div>
            ) : null}

            {activeId === "warehouse" ? (
              <div className="space-y-1">
                <SettingsRow
                  label="Provider"
                  description="Destination warehouse for curated analysis tables."
                >
                  <Select defaultValue="snowflake">
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="snowflake">Snowflake</SelectItem>
                      <SelectItem value="bigquery">BigQuery</SelectItem>
                      <SelectItem value="redshift">Redshift</SelectItem>
                      <SelectItem value="postgres">Postgres</SelectItem>
                    </SelectContent>
                  </Select>
                </SettingsRow>
                <Separator />
                <SettingsRow label="Host" description="Warehouse host or account.">
                  <Input defaultValue="analytics.example.com" />
                </SettingsRow>
                <Separator />
                <SettingsRow label="Database" description="Target database name.">
                  <Input defaultValue="datastorm" />
                </SettingsRow>
                <Separator />
                <SettingsRow label="Schema" description="Tables are written here.">
                  <Input defaultValue="public" />
                </SettingsRow>
                <Separator />
                <SettingsRow label="User" description="Service account username.">
                  <Input defaultValue="service_user" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Password or Token"
                  description="Keep the real secret in DATA_WAREHOUSE_* env vars."
                >
                  <Input type="password" placeholder="Stored outside the app" />
                </SettingsRow>
                <div className="flex flex-wrap items-center gap-2 pt-4">
                  <SavedButton
                    saved={Boolean(saved.warehouse)}
                    onClick={() => handleSave("warehouse")}
                  >
                    Save Warehouse Settings
                  </SavedButton>
                  <Button variant="outline" onClick={testWarehouse}>
                    <Plug className="size-4" /> Test Warehouse
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    {warehouseStatus}
                  </span>
                </div>
              </div>
            ) : null}

            {activeId === "backend" ? (
              <div className="space-y-1">
                <SettingsRow
                  label="Dataset Metadata"
                  description="Lists row counts, file sizes, and stream URLs."
                >
                  <Input readOnly value="/api/backend/datasets" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Outlet Stream"
                  description="Streams analysis rows as NDJSON instead of one large payload."
                >
                  <Input readOnly value="/api/backend/stream?dataset=outlets" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Default Page Size"
                  description="Use limit and offset to page large datasets."
                >
                  <Input type="number" defaultValue="1000" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Cache Policy"
                  description="Keep dynamic streams fresh while static assets stay cacheable."
                >
                  <Select defaultValue="no-store">
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="no-store">No store</SelectItem>
                      <SelectItem value="short">Short cache</SelectItem>
                    </SelectContent>
                  </Select>
                </SettingsRow>
                <div className="flex flex-wrap items-center gap-2 pt-4">
                  <Button variant="outline" onClick={testBackendStream}>
                    <RadioTower className="size-4" /> Test Stream
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    {backendStatus}
                  </span>
                </div>
              </div>
            ) : null}

            {activeId === "genai" ? (
              <div className="space-y-1">
                <SettingsRow
                  label="OpenAI API Key"
                  description="Used for outlet-level explanations."
                >
                  <div className="flex w-full items-center gap-2">
                    <Input type="password" placeholder="sk-..." />
                    <Badge variant="outline" className="text-xs text-amber-600">
                      <AlertCircle className="size-3" /> not set
                    </Badge>
                  </div>
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="OpenAI Model"
                  description="Default explanation model."
                >
                  <Input defaultValue="gpt-4o-mini" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Gemini API Key"
                  description="Optional alternative provider."
                >
                  <div className="flex w-full items-center gap-2">
                    <Input type="password" placeholder="Stored outside the app" />
                    <Badge variant="outline" className="text-xs text-amber-600">
                      <AlertCircle className="size-3" /> not set
                    </Badge>
                  </div>
                </SettingsRow>
                <Separator />
                <SettingsRow label="Max Tokens" description="Per explanation.">
                  <Input type="number" defaultValue="512" />
                </SettingsRow>
                <Separator />
                <SettingsRow label="Temperature" description="0.0 to 1.0.">
                  <Input type="number" step="0.1" min="0" max="1" defaultValue="0.3" />
                </SettingsRow>
                <div className="flex flex-wrap items-center gap-2 pt-4">
                  <SavedButton
                    saved={Boolean(saved.genai)}
                    onClick={() => handleSave("genai")}
                  >
                    Save API Settings
                  </SavedButton>
                  <Button variant="outline">Validate Keys</Button>
                </div>
              </div>
            ) : null}

            {activeId === "pipeline" ? (
              <div className="space-y-1">
                <SettingsRow
                  label="Output Directory"
                  description="Final predictions and allocations."
                >
                  <Input defaultValue="data/output/" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Web Data Directory"
                  description="Backend streams from this generated folder."
                >
                  <Input defaultValue="web/public/data/" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Batch Size"
                  description="Rows per processing batch."
                >
                  <Input type="number" defaultValue="10000" />
                </SettingsRow>
                <Separator />
                <SettingsRow
                  label="Retry Limit"
                  description="Max retries on API failure."
                >
                  <Input type="number" defaultValue="3" />
                </SettingsRow>
                <div className="flex flex-wrap items-center gap-2 pt-4">
                  <SavedButton
                    saved={Boolean(saved.pipeline)}
                    onClick={() => handleSave("pipeline")}
                  >
                    Save Pipeline Settings
                  </SavedButton>
                </div>
              </div>
            ) : null}

            <Separator className="my-5" />
            <div className="flex items-center justify-between gap-3">
              <Button variant="outline" onClick={() => goTo(-1)}>
                <ArrowLeft className="size-4" /> Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                {active.title} settings
              </span>
              <Button variant="outline" onClick={() => goTo(1)}>
                Next <ArrowRight className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
