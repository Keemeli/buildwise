// UI language, chosen by the user and remembered in this browser.
//
// The server always renders the default language (strings.ts → DEFAULT_LOCALE); the browser
// switches to the saved choice right after loading. useSyncExternalStore keeps that switch
// free of hydration mismatches.
//
// Client components read their texts with `const t = useT()`.

import { useSyncExternalStore } from "react";
import { strings, DEFAULT_LOCALE } from "@/strings";

const STORAGE_KEY = "buildwise:locale";
const listeners = new Set();
// The choice made during this visit. Kept in memory so switching works even when
// localStorage is blocked (private mode, blocked site data): then it just isn't remembered.
let current = null;

function readSaved() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && saved in strings ? saved : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE; // storage blocked or unavailable
  }
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setLocale(locale) {
  if (!(locale in strings)) return;
  current = locale;
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // Not remembered, but `current` still switches the language for this visit.
  }
  listeners.forEach((listener) => listener());
}

function getSnapshot() {
  return current ?? readSaved();
}

export function useLocale() {
  return useSyncExternalStore(subscribe, getSnapshot, () => DEFAULT_LOCALE);
}

export function useT() {
  return strings[useLocale()];
}
