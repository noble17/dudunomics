"use client";
import { create } from "zustand";

interface CommandState {
  open: boolean;
  focusedTicker: string | null;
  openPalette: () => void;
  closePalette: () => void;
  setFocusedTicker: (ticker: string | null) => void;
}

export const useCommandStore = create<CommandState>((set) => ({
  open: false,
  focusedTicker: null,
  openPalette: () => set({ open: true }),
  closePalette: () => set({ open: false }),
  setFocusedTicker: (ticker) => set({ focusedTicker: ticker }),
}));
