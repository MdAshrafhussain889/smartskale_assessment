import { Suspense } from "react";
import AttemptView from "./AttemptView";

export default function AttemptPage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading session...</p>}>
      <AttemptView />
    </Suspense>
  );
}
