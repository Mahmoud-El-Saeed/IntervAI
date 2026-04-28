import { createBrowserRouter, Navigate } from 'react-router-dom';

import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { AppShell } from '../components/layout/AppShell';
import { AnalysisReportPage } from '../pages/AnalysisReportPage';
import { DashboardPage } from '../pages/DashboardPage';
import { LiveInterviewPage } from '../pages/LiveInterviewPage';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { RegisterPage } from '../pages/RegisterPage';
import { SettingsPage } from '../pages/SettingsPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/dashboard', element: <DashboardPage /> },
          { path: '/dashboard/history', element: <DashboardPage /> },
          { path: '/dashboard/settings', element: <SettingsPage /> },
          { path: '/interview/:interviewId', element: <LiveInterviewPage /> },
          { path: '/analysis/:interviewId', element: <AnalysisReportPage /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);
