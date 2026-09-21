import { useState } from "react";
import { Sidebar, type View } from "./components/Sidebar";
import { SubmitWizard } from "./components/wizard/SubmitWizard";
import { ReviewQueue } from "./components/ReviewQueue";
import { Analytics } from "./components/Analytics";
import { CorrectQueue } from "./components/CorrectQueue";
import { SafetyTracker } from "./components/SafetyTracker";
import { RuleCatalog } from "./components/RuleCatalog";
import { Subjects } from "./components/Subjects";

function App() {
  const [view, setView] = useState<View>("submit");
  // Remounting a view on key bump is a simple way to force a fresh fetch
  // after a submission/review, without threading extra refresh state around.
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
        {view === "correct" && <CorrectQueue key={reviewQueueKey} />}
        {view === "analytics" && <Analytics />}
        {view === "safety" && <SafetyTracker />}
        {view === "rules" && <RuleCatalog />}
        {view === "subjects" && <Subjects />}
      </main>
    </div>
  );
}

export default App;
