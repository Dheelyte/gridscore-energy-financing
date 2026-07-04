import { Navigate, Route, Routes } from "react-router-dom";

import App from "@/app/App";
import { AppShell } from "@/app/AppShell";
import { RequireAuth } from "@/app/RequireAuth";
import { AdminPage } from "@/features/admin/AdminPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { OperatorConsolePage } from "@/features/console/OperatorConsolePage";
import { UploadPage } from "@/features/ingest/UploadPage";
import { LenderPage } from "@/features/lender/LenderPage";
import { PortfolioPage } from "@/features/portfolio/PortfolioPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/console" element={<OperatorConsolePage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/lender" element={<LenderPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
