import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/** Inline loading indicator for buttons and busy affordances. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <>
      <Loader2 className={cn("h-4 w-4 shrink-0 animate-spin", className)} aria-hidden="true" />
      {label ? <span className="sr-only">{label}</span> : null}
    </>
  );
}
