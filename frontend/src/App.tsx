import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ResourcePage } from "./components/ResourcePage";
import { useAuth } from "./lib/auth";
import { Academic } from "./pages/Academic";
import { Attendance } from "./pages/Attendance";
import { Audit } from "./pages/Audit";
import { Dashboard } from "./pages/Dashboard";
import { Fees } from "./pages/Fees";
import { Login } from "./pages/Login";
import { Masters } from "./pages/Masters";
import { ModulePage } from "./pages/ModulePage";
import { Promotion } from "./pages/Promotion";
import { Users } from "./pages/Users";

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <div className="flex h-full items-center justify-center text-slate-400">Loading…</div>;
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/academic" element={<Academic />} />
        <Route path="/attendance" element={<Attendance />} />
        <Route path="/fees" element={<Fees />} />
        <Route path="/promotion" element={<Promotion />} />
        <Route path="/masters" element={<Masters />} />
        <Route path="/users" element={<Users />} />
        <Route path="/audit" element={<Audit />} />
        <Route
          path="/students"
          element={<ResourcePage entitySlug="student" permPrefix="student_information_system" title="Students" />}
        />
        <Route
          path="/employees"
          element={<ResourcePage entitySlug="employee" permPrefix="employee_hrms" title="Employees / HR" />}
        />
        <Route
          path="/admissions"
          element={<ResourcePage entitySlug="admission-lead" permPrefix="admissions_crm" title="Admissions" />}
        />
        <Route path="/m/:slug" element={<ModulePage />} />
        <Route index element={<Navigate to="/dashboard" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
