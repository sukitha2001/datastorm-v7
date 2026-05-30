import { getDatasetConfig, readDataset } from "@/lib/backend/datasets"

export const runtime = "nodejs"

function toPositiveInt(value: string | null, fallback: number) {
  const parsed = Number(value)

  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback
  }

  return Math.floor(parsed)
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const datasetKey = searchParams.get("dataset") ?? "outlets"
  const dataset = getDatasetConfig(datasetKey)

  if (!dataset) {
    return Response.json(
      { error: `Unknown dataset: ${datasetKey}` },
      { status: 404 }
    )
  }

  const encoder = new TextEncoder()
  const rows = readDataset(dataset)
  const offset = toPositiveInt(searchParams.get("offset"), 0)
  const requestedLimit = toPositiveInt(searchParams.get("limit"), rows.length)
  const limit = Math.min(requestedLimit, 50_000)
  const slice = rows.slice(offset, offset + limit)

  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(
          JSON.stringify({
            type: "meta",
            dataset: dataset.key,
            label: dataset.label,
            totalRows: rows.length,
            offset,
            limit: slice.length,
          }) + "\n"
        )
      )

      for (const row of slice) {
        controller.enqueue(
          encoder.encode(JSON.stringify({ type: "row", data: row }) + "\n")
        )
      }

      controller.enqueue(
        encoder.encode(
          JSON.stringify({
            type: "done",
            nextOffset:
              offset + slice.length < rows.length ? offset + slice.length : null,
          }) + "\n"
        )
      )
      controller.close()
    },
  })

  return new Response(stream, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "X-Accel-Buffering": "no",
    },
  })
}
