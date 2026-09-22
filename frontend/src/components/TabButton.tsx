interface TabButtonProps {
  active: boolean;
  icon: React.ReactNode;
  onClick: () => void;
  children: React.ReactNode;
}

export function TabButton({ active, icon, onClick, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={
        "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px " +
        (active ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:text-slate-700")
      }
    >
      {icon}
      {children}
    </button>
  );
}
