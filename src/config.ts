function parseJsonMap(raw: string | undefined): Record<string, string> {
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    console.warn("Impossible de parser une variable d'environnement JSON, valeur ignoree:", raw);
    return {};
  }
}

export const config = {
  port: Number(process.env.PORT || 3000),
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
  anthropicModel: process.env.ANTHROPIC_MODEL || "claude-sonnet-5",

  whatsapp: {
    verifyToken: process.env.WHATSAPP_VERIFY_TOKEN || "",
    accessToken: process.env.WHATSAPP_ACCESS_TOKEN || "",
    apiVersion: process.env.WHATSAPP_API_VERSION || "v21.0",
    // phone_number_id (cote Meta) -> business_id (cote agent)
    businessMap: parseJsonMap(process.env.WHATSAPP_BUSINESS_MAP),
  },

  messenger: {
    verifyToken: process.env.MESSENGER_VERIFY_TOKEN || "",
    pageAccessToken: process.env.MESSENGER_PAGE_ACCESS_TOKEN || "",
    apiVersion: process.env.MESSENGER_API_VERSION || "v21.0",
    // page_id (Facebook/Instagram) -> business_id
    businessMap: parseJsonMap(process.env.MESSENGER_BUSINESS_MAP),
  },

  voice: {
    // numero Twilio (To) -> business_id
    businessMap: parseJsonMap(process.env.VOICE_BUSINESS_MAP),
  },
};
