import { Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import { ToastProvider } from "./components/Toasts";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectPage from "./pages/ProjectPage";
import NotFound from "./pages/NotFound";
import CostLibraryPage from "./pages/CostLibraryPage";
import SuppliersPage from "./pages/SuppliersPage";

export default function App() {
  return (
    <ToastProvider>
      <Shell>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="/cost-library" element={<CostLibraryPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Shell>
    </ToastProvider>
  );
}
