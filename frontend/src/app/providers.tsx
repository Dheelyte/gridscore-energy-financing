import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";

import { TourProvider } from "@/components/tour/GuidedTour";
import { AuthProvider } from "@/lib/auth";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } },
});

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <TourProvider>{children}</TourProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
