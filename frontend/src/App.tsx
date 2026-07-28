import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { AuthMethodsPage } from "./pages/AuthMethodsPage";
import { ClientAppsPage } from "./pages/ClientAppsPage";
import { GrantsPage } from "./pages/GrantsPage";
import { IdentitiesPage } from "./pages/IdentitiesPage";
import { IdentityDetailPage } from "./pages/IdentityDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { LoginsPage } from "./pages/LoginsPage";
import { OauthProvidersPage } from "./pages/OauthProvidersPage";
import { SessionsPage } from "./pages/SessionsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/client-apps" replace />} />
        <Route path="/auth-methods" element={<AuthMethodsPage />} />
        <Route path="/client-apps" element={<ClientAppsPage />} />
        <Route path="/oauth-providers" element={<OauthProvidersPage />} />
        <Route path="/identities" element={<IdentitiesPage />} />
        <Route path="/identities/:id" element={<IdentityDetailPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/logins" element={<LoginsPage />} />
        <Route path="/grants" element={<GrantsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
