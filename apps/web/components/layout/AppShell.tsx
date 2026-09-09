import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

// Application shell: fixed sidebar (≥ md), sticky topbar, scrollable main
// content. Purely presentational — pages slot into `children`.
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
