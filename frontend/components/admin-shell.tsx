"use client";

import Link from "next/link";
import { Activity, LogOut, RefreshCcw, Trash2, UploadCloud } from "lucide-react";
import { motion } from "framer-motion";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  addManualContext,
  adminLogin,
  deleteKnowledgeDoc,
  fetchKnowledgeDocs,
  rebuildKnowledge,
  uploadKnowledge
} from "@/lib/api";
import { clearAdminToken, readAdminToken, saveAdminToken } from "@/lib/storage";
import { KnowledgeDocument } from "@/lib/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { useToast } from "@/components/toast-provider";


function formatDate(value: string) {
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}


export function AdminShell() {
  const { pushToast } = useToast();

  const [token, setToken] = useState("");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const totalChunks = useMemo(
    () => docs.reduce((sum, doc) => sum + doc.chunk_count, 0),
    [docs]
  );

  const resetSession = useCallback((message: string) => {
    clearAdminToken();
    setToken("");
    setDocs([]);
    pushToast(message, "error");
  }, [pushToast]);

  const isAuthError = useCallback((error: unknown) => {
    if (!(error instanceof Error)) {
      return false;
    }
    return /invalid or expired token|authentication required/i.test(error.message);
  }, []);

  const loadDocs = useCallback(async (activeToken: string) => {
    try {
      const items = await fetchKnowledgeDocs(activeToken);
      setDocs(items);
    } catch (error) {
      if (isAuthError(error)) {
        resetSession("Admin session expired. Please log in again.");
        return;
      }
      pushToast(error instanceof Error ? error.message : "Failed to load documents.", "error");
    }
  }, [isAuthError, pushToast, resetSession]);

  useEffect(() => {
    const storedToken = readAdminToken();
    if (!storedToken) {
      return;
    }
    setToken(storedToken);
    void loadDocs(storedToken);
  }, [loadDocs]);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsBusy(true);
    try {
      const nextToken = await adminLogin(username, password);
      saveAdminToken(nextToken);
      setToken(nextToken);
      pushToast("Admin login successful.", "success");
      await loadDocs(nextToken);
      setPassword("");
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Login failed.", "error");
    } finally {
      setIsBusy(false);
    }
  };

  const handleFiles = async (files: File[]) => {
    if (!token || files.length === 0) {
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    try {
      await uploadKnowledge(token, files, setUploadProgress);
      pushToast("Files uploaded and indexed.", "success");
      await loadDocs(token);
    } catch (error) {
      if (isAuthError(error)) {
        resetSession("Admin session expired. Please log in again.");
        return;
      }
      pushToast(error instanceof Error ? error.message : "Upload failed.", "error");
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadProgress(0), 600);
    }
  };

  const handleManualContext = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !title.trim() || !content.trim()) {
      return;
    }

    setIsBusy(true);
    try {
      await addManualContext(token, title, content);
      setTitle("");
      setContent("");
      pushToast("Manual knowledge injected instantly.", "success");
      await loadDocs(token);
    } catch (error) {
      if (isAuthError(error)) {
        resetSession("Admin session expired. Please log in again.");
        return;
      }
      pushToast(error instanceof Error ? error.message : "Could not add context.", "error");
    } finally {
      setIsBusy(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!token) {
      return;
    }

    setIsBusy(true);
    try {
      await deleteKnowledgeDoc(token, documentId);
      pushToast("Document removed from the knowledge base.", "success");
      await loadDocs(token);
    } catch (error) {
      if (isAuthError(error)) {
        resetSession("Admin session expired. Please log in again.");
        return;
      }
      pushToast(error instanceof Error ? error.message : "Delete failed.", "error");
    } finally {
      setIsBusy(false);
    }
  };

  const handleReindex = async () => {
    if (!token) {
      return;
    }

    setIsBusy(true);
    try {
      await rebuildKnowledge(token);
      pushToast("Knowledge base rebuilt successfully.", "success");
      await loadDocs(token);
    } catch (error) {
      if (isAuthError(error)) {
        resetSession("Admin session expired. Please log in again.");
        return;
      }
      pushToast(error instanceof Error ? error.message : "Reindex failed.", "error");
    } finally {
      setIsBusy(false);
    }
  };

  const logout = () => {
    clearAdminToken();
    setToken("");
    setDocs([]);
    pushToast("Signed out.", "success");
  };

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel w-full max-w-md p-8"
        >
          <div className="mb-8 flex items-start justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-stone-500 dark:text-stone-400">
                Admin Access
              </p>
              <h1 className="mt-2 text-4xl text-ink dark:text-white">Knowledge Console</h1>
            </div>
            <ThemeToggle />
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="mb-2 block text-sm text-stone-600 dark:text-stone-300">Username</label>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-2xl border border-stone-200/80 bg-white/80 px-4 py-3 outline-none focus:border-ocean dark:border-white/10 dark:bg-white/5"
              />
            </div>
            <div>
              <label className="mb-2 block text-sm text-stone-600 dark:text-stone-300">Password</label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-2xl border border-stone-200/80 bg-white/80 px-4 py-3 outline-none focus:border-ocean dark:border-white/10 dark:bg-white/5"
              />
            </div>
            <button
              type="submit"
              disabled={isBusy}
              className="w-full rounded-full bg-ink px-5 py-3 text-sm font-medium text-white transition hover:bg-stone-800 disabled:opacity-60 dark:bg-white dark:text-stone-900"
            >
              {isBusy ? "Signing in..." : "Login"}
            </button>
          </form>
        </motion.div>
      </main>
    );
  }

  return (
    <main className="px-4 py-6 text-stone-900 dark:text-stone-100 sm:px-6 lg:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-7xl flex-col gap-6">
        <header className="panel flex flex-col gap-4 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-stone-500 dark:text-stone-400">
              Live Ops
            </p>
            <h1 className="mt-2 text-4xl text-ink dark:text-white">Spoorthi Chatbot Admin Dashboard</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/"
              className="rounded-full border border-stone-300/70 bg-white/80 px-4 py-2 text-sm dark:border-white/10 dark:bg-white/5"
            >
              Back to Chat
            </Link>
            <button
              type="button"
              onClick={handleReindex}
              disabled={isBusy}
              className="inline-flex items-center gap-2 rounded-full border border-stone-300/70 bg-white/80 px-4 py-2 text-sm transition hover:border-ocean hover:text-ocean dark:border-white/10 dark:bg-white/5"
            >
              <RefreshCcw size={16} />
              Reindex
            </button>
            <ThemeToggle />
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm text-white dark:bg-white dark:text-stone-900"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.05fr_1.45fr]">
          <div className="space-y-6">
            <div className="panel p-6">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">
                    Index Health
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-ink dark:text-white">Instant Sync</p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                  <Activity size={14} />
                  Live indexing enabled
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-stone-200/70 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">Documents</p>
                  <p className="mt-2 text-3xl font-semibold">{docs.length}</p>
                </div>
                <div className="rounded-2xl border border-stone-200/70 bg-white/80 p-4 dark:border-white/10 dark:bg-white/5">
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">Chunks</p>
                  <p className="mt-2 text-3xl font-semibold">{totalChunks}</p>
                </div>
              </div>
            </div>

            <div className="panel p-6">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">
                Upload Files
              </p>
              <label
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                  void handleFiles(Array.from(event.dataTransfer.files));
                }}
                className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-[28px] border border-dashed px-6 py-10 text-center transition ${
                  dragActive
                    ? "border-ember bg-ember/10"
                    : "border-stone-300/80 bg-white/65 dark:border-white/10 dark:bg-white/5"
                }`}
              >
                <UploadCloud size={30} className="text-ember" />
                <p className="mt-4 text-base font-medium">Drag and drop PDF, TXT, or MD files</p>
                <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">
                  Documents are chunked, embedded, and appended to FAISS immediately.
                </p>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    void handleFiles(files);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
              {isUploading || uploadProgress > 0 ? (
                <div className="mt-4">
                  <div className="mb-2 flex items-center justify-between text-xs text-stone-500 dark:text-stone-400">
                    <span>Upload progress</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-stone-200 dark:bg-white/10">
                    <div
                      className="h-2 rounded-full bg-ember transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              ) : null}
            </div>

            <form onSubmit={handleManualContext} className="panel p-6">
              <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">
                Add Manual Context
              </p>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Context title"
                className="mt-4 w-full rounded-2xl border border-stone-200/80 bg-white/80 px-4 py-3 outline-none focus:border-ocean dark:border-white/10 dark:bg-white/5"
              />
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="Paste announcement details, FAQs, venue notes, or policy updates..."
                className="mt-3 min-h-[180px] w-full rounded-[24px] border border-stone-200/80 bg-white/80 px-4 py-3 outline-none focus:border-ocean dark:border-white/10 dark:bg-white/5"
              />
              <button
                type="submit"
                disabled={isBusy || !title.trim() || !content.trim()}
                className="mt-4 rounded-full bg-ocean px-5 py-2.5 text-sm font-medium text-white transition hover:bg-[#09595d] disabled:cursor-not-allowed disabled:opacity-60"
              >
                Inject Context
              </button>
            </form>
          </div>

          <div className="panel p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-stone-500 dark:text-stone-400">
                  Knowledge Inventory
                </p>
                <p className="mt-2 text-2xl font-semibold text-ink dark:text-white">
                  Uploaded and live documents
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {docs.length === 0 ? (
                <div className="rounded-[24px] border border-dashed border-stone-300/80 px-5 py-12 text-center text-sm text-stone-500 dark:border-white/10 dark:text-stone-400">
                  No documents indexed yet. Upload files or add manual context to start powering retrieval.
                </div>
              ) : (
                docs.map((doc) => (
                  <div
                    key={doc.document_id}
                    className="rounded-[24px] border border-stone-200/70 bg-white/75 p-4 dark:border-white/10 dark:bg-white/5"
                  >
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-base font-medium text-ink dark:text-white">{doc.file_name}</p>
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                          <span className="rounded-full bg-ocean/10 px-3 py-1 text-ocean dark:bg-ocean/20 dark:text-cyan-200">
                            {doc.source_type}
                          </span>
                          <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-600 dark:bg-white/10 dark:text-stone-300">
                            {doc.chunk_count} chunks
                          </span>
                          <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-600 dark:bg-white/10 dark:text-stone-300">
                            {formatDate(doc.created_at)}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDelete(doc.document_id)}
                        disabled={isBusy}
                        className="inline-flex items-center gap-2 rounded-full border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700 transition hover:bg-red-100 disabled:opacity-60 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-100"
                      >
                        <Trash2 size={16} />
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
