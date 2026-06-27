import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ResourcePage } from "./components/ResourcePage";
import { PORTAL_BASE, useAuth } from "./lib/auth";
import { Academic } from "./pages/Academic";
import { ActivitiesPage } from "./pages/ActivitiesPage";
import { Admissions } from "./pages/Admissions";
import { Attendance } from "./pages/Attendance";
import { AssetTracking } from "./pages/AssetTracking";
import { Audit } from "./pages/Audit";
import { Branding } from "./pages/Branding";
import { CMS } from "./pages/CMS";
import { Communication } from "./pages/Communication";
import { Curriculum } from "./pages/Curriculum";
import { Dashboard } from "./pages/Dashboard";
import { EmployeeProfile } from "./pages/EmployeeProfile";
import { Exams } from "./pages/Exams";
import { Fees } from "./pages/Fees";
import { FieldCustomizer } from "./pages/FieldCustomizer";
import { Finance } from "./pages/Finance";
import { HomeworkPage } from "./pages/HomeworkPage";
import { Hostel } from "./pages/Hostel";
import { HR } from "./pages/HR";
import { Integrations } from "./pages/Integrations";
import { KnowledgeBase } from "./pages/KnowledgeBase";
import { Library } from "./pages/Library";
import { Login } from "./pages/Login";
import { Masters } from "./pages/Masters";
import { Meals } from "./pages/Meals";
import { ModulePage } from "./pages/ModulePage";
import { ParentPortal as ParentPortalAdmin } from "./pages/ParentPortal";
import { ParentPortal, StudentPortal, TeacherPortal } from "./pages/Portals";
import { PublicAdmission } from "./pages/PublicAdmission";
import { Promotion } from "./pages/Promotion";
import { QuestionBank } from "./pages/QuestionBank";
import { Reports } from "./pages/Reports";
import { Store } from "./pages/Store";
import { StudentProfile } from "./pages/StudentProfile";
import { TeacherAllocation } from "./pages/TeacherAllocation";
import { Timetable } from "./pages/Timetable";
import { Transport } from "./pages/Transport";
import { Users } from "./pages/Users";

/** Auth + portal guard: redirects users to their own portal's base URL. */
function Guard({ need, children }: { need: string; children: React.ReactNode }) {
  const { me, portal, loading } = useAuth();
  if (loading) return <div className="flex h-full items-center justify-center text-slate-400">Loading…</div>;
  if (!me) return <Navigate to="/login" replace />;
  if (portal && portal.portal !== need) return <Navigate to={PORTAL_BASE[portal.portal] ?? "/"} replace />;
  return <>{children}</>;
}

/** The full admin/staff ERP (RBAC-filtered navigation). */
function AdminApp() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/academic" element={<Academic />} />
        <Route path="/admissions" element={<Admissions />} />
        <Route path="/attendance" element={<Attendance />} />
        <Route path="/exams" element={<Exams />} />
        <Route path="/fees" element={<Fees />} />
        <Route path="/library" element={<Library />} />
        <Route path="/hostel" element={<Hostel />} />
        <Route path="/hr" element={<HR />} />
        <Route path="/finance" element={<Finance />} />
        <Route path="/store" element={<Store />} />
        <Route path="/asset-tracking" element={<AssetTracking />} />
        <Route path="/homework" element={<HomeworkPage />} />
        <Route path="/activities" element={<ActivitiesPage />} />
        <Route path="/communication" element={<Communication />} />
        <Route path="/transport" element={<Transport />} />
        <Route path="/meals" element={<Meals />} />
        <Route path="/timetable" element={<Timetable />} />
        <Route path="/curriculum" element={<Curriculum />} />
        <Route path="/cms" element={<CMS />} />
        <Route path="/knowledge" element={<KnowledgeBase />} />
        <Route path="/parent-portal" element={<ParentPortalAdmin />} />
        <Route path="/question-bank" element={<QuestionBank />} />
        <Route path="/promotion" element={<Promotion />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/masters" element={<Masters />} />
        <Route path="/branding" element={<Branding />} />
        <Route path="/customize-fields" element={<FieldCustomizer />} />
        <Route path="/users" element={<Users />} />
        <Route path="/audit" element={<Audit />} />
        <Route
          path="/students"
          element={
            <ResourcePage
              entitySlug="student"
              permPrefix="student_information_system"
              title="Students"
              viewPath={(id) => `/students/${id}`}
            />
          }
        />
        <Route path="/students/:id" element={<StudentProfile />} />
        <Route path="/teacher-allocation" element={<TeacherAllocation />} />
        <Route
          path="/employees"
          element={
            <ResourcePage
              entitySlug="employee"
              permPrefix="employee_hrms"
              title="Employees / HR"
              viewPath={(eid) => `/employees/${eid}`}
            />
          }
        />
        <Route path="/employees/:id" element={<EmployeeProfile />} />
        <Route path="/m/:slug" element={<ModulePage />} />
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/apply/:tenantCode" element={<PublicAdmission />} />
      <Route path="/student/*" element={<Guard need="student"><StudentPortal /></Guard>} />
      <Route path="/parent/*" element={<Guard need="parent"><ParentPortal /></Guard>} />
      <Route path="/teacher/*" element={<Guard need="teacher"><TeacherPortal /></Guard>} />
      <Route path="/*" element={<Guard need="admin"><AdminApp /></Guard>} />
    </Routes>
  );
}
