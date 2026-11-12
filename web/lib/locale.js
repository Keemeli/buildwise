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
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // still switch for this visit
  }
  listeners.forEach((listener) => listener());
}

export function useLocale() {
  return useSyncExternalStore(subscribe, readSaved, () => DEFAULT_LOCALE);
}

export function useT() {
  return strings[useLocale()];
}
