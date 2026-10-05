"use client";
import { useState } from "react";
import MarkdownAnswer from "./MarkdownAnswer";

type AskResult = {
  answer: string;
  tools_used: string[];
  sources: string[];
};

export default function QuestionBox() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (loading || question.trim() === "") return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setError(data?.error ?? "Something went wrong. Please try again.");
        return;
      }
      setResult(data);
    } catch {
      setError("Could not reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-6">
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          maxLength={2000}
          className="flex-1 rounded border bg-transparent px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading || question.trim() === ""}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {loading ? "Asking..." : "Ask"}
        </button>
      </form>

      {loading && (
        <p role="status" className="mt-4 text-zinc-600 dark:text-zinc-400">
          Looking through the documents and order data. This can take several seconds...
        </p>
      )}

      {error && (
        <p role="alert" className="mt-4 text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-4">
          <MarkdownAnswer>{result.answer}</MarkdownAnswer>
          {result.sources.length > 0 && (
            <div className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">
              <p className="font-medium">Sources</p>
              <ul className="list-disc pl-5">
                {result.sources.map((source) => (
                  <li key={source}>{source}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
