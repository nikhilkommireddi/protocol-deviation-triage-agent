import { useState } from "react";
import { Sidebar, type View } from "./components/Sidebar";
import { Dashboard } from "./components/Dashboard";
import { SubmitWizard } from "./components/wizard/SubmitWizard";
import { ReviewQueue } from "./components/ReviewQueue";
import { Analytics } from "./components/Analytics";
import { CorrectQueue } from "./components/CorrectQueue";
import { SafetyTracker } from "./components/SafetyTracker";
import { Sites } from "./components/Sites";
import { RuleCatalog } from "./components/RuleCatalog";
import { Subjects } from "./components/Subjects";
import { Administration } from "./components/Administration";
import { Login } from "./components/Login";
import { AuthProvider, useAuth } from "./context/AuthContext";

function AppContent() {
  const { user } = useAuth();
  const [view, setView] = useState<View>("dashboard");
  // Remounting a view on key bump is a simple way to force a fresh fetch
  // after a submission/review, without threading extra refresh state around.
  const [reviewQueueKey, setReviewQueueKey] = useState(0);

  if (!user) return <Login />;

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar active={view} onNavigate={setView} />

      <main className="flex-1 px-8 py-8 overflow-x-hidden">
        {view === "dashboard" && <Dashboard />}
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
        {view === "sites" && <Sites />}
        {view === "rules" && <RuleCatalog />}
        {view === "subjects" && <Subjects />}
        {view === "admin" && <Administration />}
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
