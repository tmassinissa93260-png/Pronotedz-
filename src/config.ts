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
  nodeEnv: process.env.NODE_ENV || "development",
  isProduction: process.env.NODE_ENV === "production",
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
  anthropicModel: process.env.ANTHROPIC_MODEL || "claude-sonnet-5",
  // URL publique HTTPS de ce service (necessaire pour reconstruire l'URL exacte
  // utilisee par Twilio lors de la validation de signature X-Twilio-Signature).
  publicBaseUrl: process.env.PUBLIC_BASE_URL || "",

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

  // Secret d'application Meta, partage par WhatsApp et Messenger/Instagram,
  // utilise pour verifier l'entete X-Hub-Signature-256 des webhooks entrants.
  metaAppSecret: process.env.META_APP_SECRET || "",

  voice: {
    // numero Twilio (To) -> business_id
    businessMap: parseJsonMap(process.env.VOICE_BUSINESS_MAP),
  },
  twilioAuthToken: process.env.TWILIO_AUTH_TOKEN || "",
};
