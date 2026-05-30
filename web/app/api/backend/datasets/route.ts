import { ANALYSIS_DATASETS, getDatasetSummary } from "@/lib/backend/datasets"

export const runtime = "nodejs"

export async function GET() {
  return Response.json({
    generatedAt: new Date().toISOString(),
    datasets: ANALYSIS_DATASETS.map(getDatasetSummary),
  })
}
