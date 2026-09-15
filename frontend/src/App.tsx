import { useState } from "react";
import { Sidebar, type View } from "./components/Sidebar";
import { SubmitWizard } from "./components/wizard/SubmitWizard";
import { ReviewQueue } from "./components/ReviewQueue";
import { Analytics } from "./components/Analytics";

function App() {
  const [view, setView] = useState<View>("submit");
  // Remounting ReviewQueue on submit is a simple way to force a fresh
  // fetch after a submission, without threading extra refresh state around.
  const [reviewQueueKey, setReviewQueueKey] = useState(0);

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar active={view} onNavigate={setView} />

      <main className="flex-1 px-8 py-8 overflow-x-hidden">
        {view === "submit" && (
          <SubmitWizard
            onSubmitted={() => {
              setReviewQueueKey((k) => k + 1);
            }}
          />
        )}
        {view === "review" && <ReviewQueue key={reviewQueueKey} />}
        {view === "analytics" && <Analytics />}
      </main>
    </div>
  );
}

export default App;
