import { AiWorkspace } from "@/components/features/ai/AiWorkspace";

/** Legacy deep link — consolidated into the unified AI workspace (M26). */
export default function ChatPage() {
  return <AiWorkspace initialMode="general" />;
}
