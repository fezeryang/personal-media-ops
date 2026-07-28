/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getSession,
  login as loginRequest,
  logout as logoutRequest,
  type Session,
} from "../../api/auth";

interface AuthState {
  session: Session | null;
  pending: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    void getSession(controller.signal)
      .then(setSession)
      .catch(() =>
        setSession({
          authenticated: false,
          user: null,
          csrf_token: null,
        }),
      )
      .finally(() => setPending(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const unauthenticated = () =>
      setSession({
        authenticated: false,
        user: null,
        csrf_token: null,
      });
    window.addEventListener("mediaops:unauthorized", unauthenticated);
    return () =>
      window.removeEventListener("mediaops:unauthorized", unauthenticated);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      pending,
      login: async (username, password) => {
        setSession(await loginRequest(username, password));
      },
      logout: async () => {
        await logoutRequest();
        setSession({
          authenticated: false,
          user: null,
          csrf_token: null,
        });
      },
    }),
    [pending, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
