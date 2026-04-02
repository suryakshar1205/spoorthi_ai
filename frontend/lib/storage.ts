import { ChatMessage } from "@/lib/types";


const CHAT_HISTORY_KEY = "spoorthi-chat-history";
const ADMIN_TOKEN_KEY = "spoorthi-admin-token";
const THEME_KEY = "spoorthi-theme";


export function readChatHistory(): ChatMessage[] {
  return [];
}


export function saveChatHistory(messages: ChatMessage[]): void {
  void messages;
}


export function clearChatHistory(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(CHAT_HISTORY_KEY);
}


export function readAdminToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
}


export function saveAdminToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
}


export function clearAdminToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
}


export function readTheme(): string {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.localStorage.getItem(THEME_KEY) ?? "light";
}


export function saveTheme(theme: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(THEME_KEY, theme);
}
