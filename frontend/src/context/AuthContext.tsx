import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { DemoUser, ManagedUser } from "../types";

const STORAGE_KEY = "demo-auth-user";

interface AuthContextValue {
  user: DemoUser | null;
  login: (managedUser: ManagedUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredUser(): DemoUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DemoUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoUser | null>(() => loadStoredUser());

  useEffect(() => {
    try {
      if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Demo convenience only -- a viewer with storage blocked just won't
      // persist their session across a refresh.
    }
  }, [user]);

  function login(managedUser: ManagedUser) {
    setUser({
      name: managedUser.name,
      role: managedUser.role,
      siteId: managedUser.site_id ?? undefined,
    });
  }

  function logout() {
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
