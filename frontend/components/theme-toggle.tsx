"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useEffect, useState } from "react";

import { readTheme, saveTheme } from "@/lib/storage";


export function ThemeToggle() {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const nextTheme = readTheme();
    setTheme(nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    saveTheme(nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="inline-flex items-center gap-2 rounded-full border border-stone-300/70 bg-white/80 px-4 py-2 text-sm font-medium text-stone-900 backdrop-blur transition hover:border-ember hover:text-ember dark:border-white/10 dark:bg-white/5 dark:text-stone-100"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? <SunMedium size={16} /> : <MoonStar size={16} />}
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
