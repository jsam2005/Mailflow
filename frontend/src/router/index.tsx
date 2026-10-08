import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { AccountsPage } from "@/pages/AccountsPage";
import { CampaignDetailPage } from "@/pages/CampaignDetailPage";
import { CampaignsPage } from "@/pages/CampaignsPage";
import { CampaignWizardPage } from "@/pages/CampaignWizardPage";
import { ContactsPage } from "@/pages/ContactsPage";
import { ImportContactsPage } from "@/pages/ImportContactsPage";
import { InboxPage } from "@/pages/InboxPage";
import { LoginPage } from "@/pages/LoginPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TemplateEditorPage } from "@/pages/TemplateEditorPage";
import { TemplatesPage } from "@/pages/TemplatesPage";
import { UnsubscribePage } from "@/pages/UnsubscribePage";
import { ProtectedRoute } from "@/router/ProtectedRoute";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unsubscribe/:token" element={<UnsubscribePage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="contacts" element={<ContactsPage />} />
            <Route path="contacts/import" element={<ImportContactsPage />} />
            <Route path="campaigns" element={<CampaignsPage />} />
            <Route path="campaigns/new" element={<CampaignWizardPage mode="new" />} />
            <Route path="campaigns/:id" element={<CampaignDetailPage />} />
            <Route path="campaigns/:id/edit" element={<CampaignWizardPage mode="edit" />} />
            <Route path="templates" element={<TemplatesPage />} />
            <Route path="templates/new" element={<TemplateEditorPage />} />
            <Route path="templates/:id/edit" element={<TemplateEditorPage />} />
            <Route path="email-accounts" element={<AccountsPage />} />
            <Route path="accounts" element={<Navigate to="/email-accounts" replace />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
