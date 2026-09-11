import { useState } from "react";
import { SubmitForm } from "./components/SubmitForm";
import { ReviewQueue } from "./components/ReviewQueue";

type Tab = "submit" | "review";

function App() {
  const [tab, setTab] = useState<Tab>("submit");
  // Remounting ReviewQueue on tab switch is a simple way to force a fresh
  // fetch after a submission, without threading extra refresh state around.
  const [reviewQueueKey, setReviewQueueKey] = useState(0);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">
          Protocol Deviation Triage Agent
        </h1>

        <div className="flex gap-1 mb-6 border-b border-slate-200">
          <TabButton active={tab === "submit"} onClick={() => setTab("submit")}>
            Submit New Deviation
          </TabButton>
          <TabButton
            active={tab === "review"}
            onClick={() => {
              setTab("review");
            }}
          >
            Review Queue
          </TabButton>
        </div>

        {tab === "submit" && (
          <SubmitForm
            onSubmitted={() => {
              setReviewQueueKey((k) => k + 1);
            }}
          />
        )}
        {tab === "review" && <ReviewQueue key={reviewQueueKey} />}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "px-4 py-2 text-sm font-medium border-b-2 -mb-px " +
        (active
          ? "border-sky-600 text-sky-700"
          : "border-transparent text-slate-500 hover:text-slate-700")
      }
    >
      {children}
    </button>
  );
}

export default App;
