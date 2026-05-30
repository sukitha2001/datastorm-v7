const PROVIDERS = ["snowflake", "bigquery", "redshift", "postgres"] as const

type WarehouseProvider = (typeof PROVIDERS)[number]

function redact(value: string | undefined) {
  if (!value) {
    return ""
  }

  if (value.length <= 6) {
    return "***"
  }

  return `${value.slice(0, 3)}***${value.slice(-3)}`
}

function isProvider(value: string): value is WarehouseProvider {
  return PROVIDERS.includes(value as WarehouseProvider)
}

export const runtime = "nodejs"

export async function GET() {
  return Response.json({
    providers: PROVIDERS,
    activeProvider: process.env.DATA_WAREHOUSE_PROVIDER ?? null,
    configured: Boolean(process.env.DATA_WAREHOUSE_URL),
    connection: {
      host: redact(process.env.DATA_WAREHOUSE_HOST),
      database: process.env.DATA_WAREHOUSE_DATABASE ?? "",
      schema: process.env.DATA_WAREHOUSE_SCHEMA ?? "",
      user: redact(process.env.DATA_WAREHOUSE_USER),
    },
  })
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => null)

  if (!body || typeof body !== "object") {
    return Response.json({ ok: false, error: "Invalid request body" }, { status: 400 })
  }

  const provider = String(body.provider ?? "")
  const host = String(body.host ?? "")
  const database = String(body.database ?? "")
  const user = String(body.user ?? "")

  if (!isProvider(provider)) {
    return Response.json(
      { ok: false, error: "Choose a supported warehouse provider." },
      { status: 400 }
    )
  }

  const missing = [
    ["host", host],
    ["database", database],
    ["user", user],
  ]
    .filter(([, value]) => !value)
    .map(([key]) => key)

  if (missing.length > 0) {
    return Response.json(
      {
        ok: false,
        error: `Missing required warehouse fields: ${missing.join(", ")}`,
      },
      { status: 400 }
    )
  }

  return Response.json({
    ok: true,
    provider,
    message:
      "Warehouse settings are valid. Add the matching DATA_WAREHOUSE_* environment variables to enable a live connector.",
  })
}
