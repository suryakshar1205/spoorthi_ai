"use client";

import { ChevronDown, Mic, MicOff } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { askQuestion, streamQuestion } from "@/lib/api";
import { clearChatHistory } from "@/lib/storage";
import { ChatMessage, StreamEvent } from "@/lib/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { useToast } from "@/components/toast-provider";


declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  }
}


interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}


interface SpeechRecognitionEventLike {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}


const quickQuestionGroups = [
  {
    label: "About Spoorthi Fest",
    questions: [
      "What is Spoorthi Fest?",
      "Where is Spoorthi Fest conducted?",
      "What type of events are there in Spoorthi?",
      "Why should I participate in Spoorthi Fest?",
      "How is Spoorthi different from other college fests?"
    ]
  },
  {
    label: "Organization & Team",
    questions: [
      "Who is the coordinator of Spoorthi Fest?",
      "Who are the student coordinators?",
      "How is Spoorthi Fest organized?",
      "What roles do students play in organizing the fest?",
      "How does organizing Spoorthi help students gain experience?"
    ]
  },
  {
    label: "Workshops & Hackathon",
    questions: [
      "What workshops are conducted in Spoorthi?",
      "What is the PCB workshop about?",
      "What is the AI and IoT workshop?",
      "What is the hackathon and how does it work?",
      "What skills can I gain from workshops and hackathons?"
    ]
  },
  {
    label: "Activities & Experience",
    questions: [
      "What is the flashmob about?",
      "What happens in the Tech Room?",
      "What is the Art Room?",
      "What fun activities are there in Spoorthi?",
      "What can I explore apart from technical events?"
    ]
  },
  {
    label: "Technical Events",
    questions: [
      "What are the main technical events in Spoorthi?",
      "What is Code Clutch?",
      "What is IDEATHON?",
      "What is Tech Treasure Hunt?",
      "Which events are best for beginners?"
    ]
  },
  {
    label: "Legacy & Impact",
    questions: [
      "How long has Spoorthi Fest been conducted?",
      "Why is Spoorthi considered a flagship event?",
      "What impact does Spoorthi have on students?",
      "What social activities are part of Spoorthi?",
      "Why do students participate in Spoorthi every year?"
    ]
  },
  {
    label: "Sponsors & Support",
    questions: [
      "Who are the sponsors of Spoorthi Fest?",
      "How do sponsors support the fest?",
      "What is the role of IEEE in Spoorthi?",
      "How does industry collaboration help students?",
      "Which companies are involved in the fest?"
    ]
  }
];


const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi, I'm Spoorthi Chatbot. Ask me about event locations, timings, registrations, coordinators, or available fest events.",
  createdAt: new Date().toISOString()
};


function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: new Date().toISOString()
  };
}


export function ChatShell() {
  const { pushToast } = useToast();
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const defaultQuickQuestionCategory = quickQuestionGroups[0]?.label ?? "";

  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [input, setInput] = useState("");
  const [selectedQuickCategory, setSelectedQuickCategory] = useState(defaultQuickQuestionCategory);
  const [selectedQuickQuestion, setSelectedQuickQuestion] = useState("");
  const [isQuickQuestionsOpen, setIsQuickQuestionsOpen] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceAvailable, setVoiceAvailable] = useState(false);

  const activeQuickQuestionGroup =
    quickQuestionGroups.find((group) => group.label === selectedQuickCategory) ?? quickQuestionGroups[0];

  useEffect(() => {
    clearChatHistory();
    setMessages([welcomeMessage]);

    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (Recognition) {
      setVoiceAvailable(true);
      const recognition = new Recognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-IN";
      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript ?? "";
        setInput((current) => `${current} ${transcript}`.trim());
      };
      recognition.onend = () => setIsListening(false);
      recognitionRef.current = recognition;
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  const updateAssistantMessage = (id: string, updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((current) =>
      current.map((message) => (message.id === id ? updater(message) : message))
    );
  };

  const handleStreamEvent = (assistantId: string, event: StreamEvent) => {
    if (event.type === "status") {
      setStatusText(event.message ?? "");
      return;
    }

    if (event.type === "meta") {
      if (event.session_id) {
        setSessionId(event.session_id);
      }
      return;
    }

    if (event.type === "token") {
      updateAssistantMessage(assistantId, (message) => ({
        ...message,
        content: `${message.content}${event.content ?? ""}`
      }));
      return;
    }

    if (event.type === "error") {
      updateAssistantMessage(assistantId, (message) => ({
        ...message,
        content: event.message ?? "I could not complete that request right now.",
        source: undefined,
        confidence: undefined
      }));
      setStatusText("");
      pushToast(event.message ?? "I could not complete that request right now.", "error");
      return;
    }

    if (event.type === "done") {
      setStatusText("");
    }
  };

  const submitQuestion = async (question: string) => {
    const query = question.trim();
    if (!query || isLoading) {
      return;
    }

    setIsLoading(true);
    setStatusText("Spoorthi Chatbot is typing...");

    const userMessage = createMessage("user", query);
    const assistantMessage = createMessage("assistant", "");
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");

    try {
      await streamQuestion(query, sessionId, (event) => handleStreamEvent(assistantMessage.id, event));
    } catch (streamError) {
      try {
        const response = await askQuestion(query, sessionId);
        if (response.session_id) {
          setSessionId(response.session_id);
        }
        updateAssistantMessage(assistantMessage.id, (message) => ({
          ...message,
          content: response.answer
        }));
        setStatusText("");
      } catch (fallbackError) {
        const detail =
          fallbackError instanceof Error
            ? fallbackError.message
            : streamError instanceof Error
              ? streamError.message
              : "I could not complete that request right now.";
        updateAssistantMessage(assistantMessage.id, (message) => ({
          ...message,
          content: detail
        }));
        setStatusText("");
        pushToast(
          detail,
          "error"
        );
      }
    } finally {
      setIsLoading(false);
      setIsListening(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitQuestion(input);
  };

  const handleInputKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    await submitQuestion(input);
  };

  const resetChat = () => {
    setMessages([welcomeMessage]);
    setSessionId(crypto.randomUUID());
    setInput("");
    setSelectedQuickCategory(defaultQuickQuestionCategory);
    setSelectedQuickQuestion("");
    setIsQuickQuestionsOpen(false);
    setStatusText("");
    clearChatHistory();
  };

  const toggleListening = () => {
    if (!voiceAvailable || !recognitionRef.current) {
      pushToast("Voice input is not available in this browser.", "error");
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    recognitionRef.current.start();
    setIsListening(true);
  };

  return (
    <main className="relative overflow-hidden px-4 py-6 text-stone-900 dark:text-stone-100 sm:px-6 lg:px-10">
      <div className="mesh pointer-events-none absolute inset-0 opacity-70" />
      <div className="relative mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-4 rounded-[32px] border border-white/50 bg-white/55 px-6 py-5 backdrop-blur-xl dark:border-white/10 dark:bg-white/5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl leading-tight text-ink dark:text-white sm:text-5xl">Spoorthi Chatbot</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={resetChat}
              className="rounded-full border border-stone-300/70 bg-white/80 px-4 py-2 text-sm font-medium text-stone-900 transition hover:border-ember hover:text-ember dark:border-white/10 dark:bg-white/5 dark:text-stone-100"
            >
              New Chat
            </button>
            <ThemeToggle />
          </div>
        </header>

        <section className="flex-1">
          <motion.section
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel flex min-h-[72vh] flex-col overflow-hidden"
          >
            <div className="flex items-center justify-between border-b border-stone-200/70 px-5 py-4 dark:border-white/10">
              <div>
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">Spoorthi Chatbot</p>
                <p className="text-xs text-stone-500 dark:text-stone-400">
                  {statusText || "Ask anything about the fest."}
                </p>
              </div>
              {isLoading ? (
                <div className="flex items-center gap-2 rounded-full bg-stone-900 px-3 py-1 text-xs text-white dark:bg-white dark:text-stone-900">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                  Typing
                </div>
              ) : null}
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-5">
              <div className="rounded-[20px] border border-stone-200/70 bg-white/70 p-3 dark:border-white/10 dark:bg-white/5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-stone-500 dark:text-stone-400">
                      Prefetched Questions
                    </p>
                    <p className="mt-1 text-sm text-stone-600 dark:text-stone-300">
                      {selectedQuickCategory} · {activeQuickQuestionGroup?.questions.length ?? 0} questions
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsQuickQuestionsOpen((current) => !current)}
                    className="inline-flex items-center gap-2 rounded-full border border-stone-300/70 bg-white/80 px-4 py-2 text-sm font-medium text-stone-800 transition hover:border-ember hover:text-ember dark:border-white/10 dark:bg-white/5 dark:text-stone-100"
                  >
                    {isQuickQuestionsOpen ? "Hide" : "Open"}
                    <ChevronDown
                      size={16}
                      className={`transition-transform ${isQuickQuestionsOpen ? "rotate-180" : ""}`}
                    />
                  </button>
                </div>

                <AnimatePresence initial={false}>
                  {isQuickQuestionsOpen ? (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeOut" }}
                      className="overflow-hidden"
                    >
                      <div className="mt-3 flex flex-col gap-3">
                        <div>
                          <label
                            htmlFor="quick-question-category"
                            className="mb-2 block text-[11px] font-medium uppercase tracking-[0.18em] text-stone-500 dark:text-stone-400"
                          >
                            Quick Question Category
                          </label>
                          <select
                            id="quick-question-category"
                            value={selectedQuickCategory}
                            onChange={(event) => {
                              setSelectedQuickCategory(event.target.value);
                              setSelectedQuickQuestion("");
                            }}
                            disabled={isLoading}
                            className="quick-question-select w-full rounded-xl border border-stone-300/70 bg-white px-3 py-2.5 text-sm text-stone-800 outline-none transition focus:border-ember dark:border-white/10 dark:bg-white/5 dark:text-stone-100"
                          >
                            {quickQuestionGroups.map((group) => (
                              <option key={group.label} value={group.label}>
                                {group.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.18em] text-stone-500 dark:text-stone-400">
                            Pick a Question
                          </p>
                          <div className="max-h-44 space-y-2 overflow-y-auto pr-1">
                            {activeQuickQuestionGroup?.questions.map((question) => {
                              const isActive = selectedQuickQuestion === question;
                              return (
                                <button
                                  key={question}
                                  type="button"
                                  onClick={() => {
                                    setSelectedQuickQuestion(question);
                                    void submitQuestion(question);
                                  }}
                                  disabled={isLoading}
                                  className={`w-full rounded-2xl border px-3 py-3 text-left text-sm transition ${
                                    isActive
                                      ? "border-ember bg-ember/10 text-ember dark:border-ember dark:bg-ember/15 dark:text-orange-200"
                                      : "border-stone-200/80 bg-white/85 text-stone-800 hover:border-ocean hover:text-ocean dark:border-white/10 dark:bg-white/5 dark:text-stone-100 dark:hover:border-cyan-300 dark:hover:text-cyan-200"
                                  } disabled:cursor-not-allowed disabled:opacity-60`}
                                >
                                  {question}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>

              <AnimatePresence initial={false}>
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-[24px] px-4 py-3 text-sm leading-7 shadow-sm sm:text-[15px] ${
                        message.role === "user"
                          ? "bg-ink text-white dark:bg-white dark:text-stone-900"
                          : "border border-stone-200/70 bg-white/80 text-stone-800 dark:border-white/10 dark:bg-white/5 dark:text-stone-100"
                      }`}
                    >
                      <div className="whitespace-pre-wrap">
                        {message.content || (isLoading ? "Spoorthi Chatbot is typing..." : "")}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              <div ref={bottomRef} />
            </div>

            <form onSubmit={handleSubmit} className="border-t border-stone-200/70 p-4 dark:border-white/10 sm:p-5">
              <div className="rounded-[28px] border border-stone-200/70 bg-white/80 p-3 shadow-sm dark:border-white/10 dark:bg-white/5">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    void handleInputKeyDown(event);
                  }}
                  placeholder="Ask about schedules, venues, registrations, or event details..."
                  className="min-h-[96px] w-full resize-none bg-transparent px-2 py-2 text-sm text-stone-900 outline-none placeholder:text-stone-400 dark:text-stone-100 dark:placeholder:text-stone-500"
                />
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-xs text-stone-500 dark:text-stone-400">Ask your question and press send.</div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={toggleListening}
                      className="inline-flex items-center gap-2 rounded-full border border-stone-300/70 px-4 py-2 text-sm text-stone-700 transition hover:border-ocean hover:text-ocean disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-stone-200"
                      disabled={!voiceAvailable}
                    >
                      {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                      {isListening ? "Stop" : "Voice"}
                    </button>
                    <button
                      type="submit"
                      disabled={isLoading || input.trim().length < 2}
                      className="rounded-full bg-ember px-5 py-2.5 text-sm font-medium text-white transition hover:bg-[#bf4327] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isLoading ? "Typing..." : "Send"}
                    </button>
                  </div>
                </div>
              </div>
            </form>
          </motion.section>
        </section>
      </div>
    </main>
  );
}
