"use client";

import { useEffect } from "react";
import { strings } from "@/strings";
import { setLocale, useLocale, useT } from "@/lib/locale";

// FI / EN switch in the header. The choice is remembered in this browser.
export default function LanguageSwitch() {
  const locale = useLocale();
  const t = useT();

  // Keep <html lang> in step, so screen readers pronounce the page in the right language.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    <div className="language-switch-wrap">
      <span id="language-switch-label" className="language-switch-label">
        {t.switchLanguage}
      </span>
      <div className="language-switch" role="group" aria-labelledby="language-switch-label">
      {Object.keys(strings).map((code) => (
        <button
          key={code}
          type="button"
          lang={code}
          className={code === locale ? "on" : ""}
          aria-pressed={code === locale}
          title={strings[code].languageName}
          onClick={() => setLocale(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
      </div>
    </div>
  );
}
