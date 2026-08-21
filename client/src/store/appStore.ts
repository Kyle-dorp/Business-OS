import { create } from 'zustand';

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  certificate?: string;
}

interface AppState {
  user: User | null;
  setUser: (user: User | null) => void;
  selectedTab: string;
  setSelectedTab: (tab: string) => void;
  dailyBudget: number;
  setDailyBudget: (budget: number) => void;
}

export const useStore = create<AppState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  selectedTab: 'dashboard',
  setSelectedTab: (selectedTab) => set({ selectedTab }),
  dailyBudget: 5000,
  setDailyBudget: (dailyBudget) => set({ dailyBudget }),
}));
