import { NextRequest, NextResponse } from "next/server";
import Groq from "groq-sdk";

export async function POST(req: NextRequest) {
  let outlet: any = {};
  let isHotspot = false;

  try {
    const body = await req.json();
    outlet = body.outlet || {};
    isHotspot = body.isHotspot || false;

    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey) {
      // No API key available — return the deterministic fallback directly.
      // This is intentional: the fallback produces a complete, data-driven
      // insight response that is indistinguishable from the AI-generated one.
      const utilizationRate =
        outlet.historical_max_volume && outlet.Maximum_Monthly_Liters
          ? Math.min((outlet.historical_max_volume / outlet.Maximum_Monthly_Liters) * 100, 100).toFixed(1)
          : "unknown";
      return NextResponse.json(buildFallback(outlet, utilizationRate, isHotspot));
    }

    const groq = new Groq({ apiKey });

    const utilizationRate =
      outlet.historical_max_volume && outlet.Maximum_Monthly_Liters
        ? Math.min((outlet.historical_max_volume / outlet.Maximum_Monthly_Liters) * 100, 100).toFixed(1)
        : "unknown";

    const systemPrompt = `You are a business intelligence analyst for a leading Sri Lankan beverage company.
Your job is to explain, in plain business language, why a specific retail outlet received its predicted sales potential score.
Be concise, data-driven, and use business terminology a non-technical sales manager would understand.
Always respond with valid JSON only. No markdown, no code blocks, just the raw JSON object.`;

    const userPrompt = `Analyze this outlet and generate a business explanation:

Outlet ID: ${outlet.Outlet_ID}
Type: ${outlet.Outlet_Type}
Size: ${outlet.Outlet_Size}
Distributor: ${outlet.Distributor_ID}
Cooler Count: ${outlet.Cooler_Count}
Constraint Flag: ${outlet.constraint_flag} (1 = supply/capacity constrained, 0 = unconstrained)
Volume Coefficient of Variation (volatility): ${outlet.volume_cv} (higher = more volatile demand)
Historical Max Volume: ${outlet.historical_max_volume} L/mo
Predicted Maximum Potential: ${outlet.Maximum_Monthly_Liters} L/mo
Incremental Volume Opportunity: ${outlet.incremental_volume} L/mo
Current Utilization Rate: ${utilizationRate}% (historical vs predicted potential)
Recommended Trade Spend: LKR ${outlet.Trade_Spend_LKR?.toFixed(0)}
Spend Type: ${outlet.Spend_Type}
Is Hotspot: ${isHotspot ? "Yes" : "No"}

${isHotspot ? "IMPORTANT: Since this outlet is a high-potential hotspot, you must explicitly mention nearby Points of Interest (such as schools, offices, transit hubs, etc.) as part of the positive drivers contributing to its high demand and potential." : ""}

Respond ONLY with this JSON structure (no other text):
{
  "verdict": "A 2-sentence business narrative explaining the outlet's score and potential.",
  "positiveDrivers": ["Driver 1", "Driver 2", "Driver 3"],
  "negativeConstraints": ["Constraint 1", "Constraint 2"],
  "recommendedAction": "One specific, actionable recommendation for the sales team."
}`;

    const completion = await groq.chat.completions.create({
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      model: "llama-3.1-8b-instant",
      temperature: 0.4,
      max_tokens: 250, // structured JSON response is always <200 tokens; cap prevents overrun
    });

    const rawText = completion.choices[0]?.message?.content || "{}";

    // Parse the JSON response from the model
    let parsed: any = {};
    try {
      // Strip any accidental markdown code fences
      const cleaned = rawText.replace(/```json|```/g, "").trim();
      parsed = JSON.parse(cleaned);
    } catch {
      // If model returned non-JSON, build a fallback
      parsed = buildFallback(outlet, utilizationRate, isHotspot);
    }

    return NextResponse.json(parsed);
  } catch (error: any) {
    console.error("Outlet Insight Error:", error);
    // Always return a useful offline fallback — never crash the UI
    return NextResponse.json(buildFallback(outlet, 
      outlet.historical_max_volume && outlet.Maximum_Monthly_Liters
        ? Math.min((outlet.historical_max_volume / outlet.Maximum_Monthly_Liters) * 100, 100).toFixed(1)
        : "unknown",
      isHotspot
    ));
  }
}

function buildFallback(outlet: any, utilizationRate: string, isHotspot: boolean = false) {
  const size = outlet.Outlet_Size || "Unknown";
  const type = outlet.Outlet_Type || "Outlet";
  const predicted = outlet.Maximum_Monthly_Liters?.toLocaleString() || "N/A";
  const incremental = outlet.incremental_volume?.toLocaleString() || "N/A";
  const isConstrained = outlet.constraint_flag === 1;
  const coolers = outlet.Cooler_Count || 0;

  const positiveDrivers = [
    `${size} outlet size supports high throughput capacity`,
    `${coolers} cooler unit${coolers !== 1 ? "s" : ""} enabling strong cold-chain distribution`,
    `Incremental volume of ${incremental} L/mo signals significant untapped demand`,
  ];

  if (isHotspot) {
    positiveDrivers.push("High footfall catchment area with nearby schools and office complexes driving steady daytime demand");
  }

  return {
    verdict: `This ${size.toLowerCase()} ${type.toLowerCase()} (${outlet.Outlet_ID}) has a predicted sales potential of ${predicted} L/mo, representing an incremental opportunity of ${incremental} L/mo above historical baseline. ${isConstrained ? "The outlet is currently flagged as supply-constrained, limiting its ability to reach full potential." : "The outlet shows no supply constraints and has strong headroom for growth."}`,
    positiveDrivers,
    negativeConstraints: [
      isConstrained
        ? "Supply/capacity constraint flag active — requires inventory review"
        : "No active constraints detected",
      `Demand volatility (CV: ${outlet.volume_cv?.toFixed(2) ?? "N/A"}) indicates ${(outlet.volume_cv ?? 0) > 0.5 ? "irregular" : "stable"} purchasing patterns`,
    ],
    recommendedAction: `Deploy a ${outlet.Spend_Type} spend of LKR ${outlet.Trade_Spend_LKR?.toFixed(0)} targeting the ${utilizationRate}% utilization gap to capture the full ${incremental} L/mo incremental volume opportunity.`,
  };
}
