import Anthropic from "@anthropic-ai/sdk";
import { Business, ConversationRecord } from "../businesses/types";
import { toolsForBusiness, executeTool } from "./tools";
import { systemPromptFor } from "./prompts";
import * as store from "../businesses/store";

const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5";
const MAX_TOOL_ROUNDS = 6;

let client: Anthropic | null = null;
function getClient(): Anthropic {
  if (!client) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY manquant. Ajoute-le dans .env pour activer l'agent.");
    }
    client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return client;
}

export async function handleMessage(
  channel: string,
  externalUserId: string,
  businessId: string,
  userMessage: string
): Promise<string> {
  const business = store.getBusiness(businessId);
  if (!business) throw new Error(`Commerce inconnu: ${businessId}`);

  const conversation = store.getOrCreateConversation(channel, externalUserId, businessId);
  conversation.history.push({ role: "user", content: userMessage });

  const reply = await runAgent(business, conversation);

  conversation.history.push({ role: "assistant", content: reply });
  store.saveConversation(conversation);
  return reply;
}

async function runAgent(business: Business, conversation: ConversationRecord): Promise<string> {
  const anthropic = getClient();
  const tools = toolsForBusiness(business);
  const system = systemPromptFor(business);

  const messages: Anthropic.MessageParam[] = conversation.history.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
    const response = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 1024,
      system,
      tools,
      messages,
    });

    const toolUses = response.content.filter((b): b is Anthropic.ToolUseBlock => b.type === "tool_use");

    if (toolUses.length === 0) {
      const textBlocks = response.content.filter((b): b is Anthropic.TextBlock => b.type === "text");
      return textBlocks.map((b) => b.text).join("\n").trim() || "Desole, je n'ai pas de reponse.";
    }

    messages.push({ role: "assistant", content: response.content });

    const toolResults: Anthropic.ToolResultBlockParam[] = toolUses.map((tu) => ({
      type: "tool_result",
      tool_use_id: tu.id,
      content: executeTool(business, tu.name, tu.input),
    }));
    messages.push({ role: "user", content: toolResults });
  }

  return "Desole, je n'arrive pas a finaliser ta demande pour le moment. Un membre de l'equipe va te recontacter.";
}
