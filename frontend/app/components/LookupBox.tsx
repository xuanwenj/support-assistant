"use client";
import { useState } from "react";
import CustomerDetails, { type CustomerDetail } from "./CustomerDetails";

type CustomerSummary = {
  customer_id: string;
  name: string;
  account_type: string;
  region: string | null;
  email_masked: string;
  phone_masked: string | null;
};

const GENERIC_ERROR = "Something went wrong. Please try again.";
const NETWORK_ERROR = "Could not reach the server. Check your connection and try again.";

export default function LookupBox() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [matches, setMatches] = useState<CustomerSummary[]>([]);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);

  async function fetchDetail(customerId: string) {
    const res = await fetch(`/api/lookup/customers/${customerId}`);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setError(data?.error ?? GENERIC_ERROR);
      return;
    }
    setDetail(data);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (loading || query.trim() === "") return;

    setLoading(true);
    setError(null);
    setNotFound(false);
    setMatches([]);
    setDetail(null);

    try {
      const res = await fetch("/api/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setError(data?.error ?? GENERIC_ERROR);
        return;
      }

      const customers: CustomerSummary[] = data.customers;
      if (customers.length === 0) {
        setNotFound(true);
      } else if (customers.length === 1) {
        // The search result is masked, so one match goes straight to the full details.
        await fetchDetail(customers[0].customer_id);
      } else {
        setMatches(customers);
      }
    } catch {
      setError(NETWORK_ERROR);
    } finally {
      setLoading(false);
    }
  }

  async function handlePick(customerId: string) {
    if (loading) return;

    setLoading(true);
    setError(null);
    try {
      await fetchDetail(customerId);
      setMatches([]);
    } catch {
      setError(NETWORK_ERROR);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-6">
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Order ID, customer name, customer ID, phone or email"
          aria-label="Search for a customer or order"
          maxLength={200}
          className="flex-1 rounded border bg-transparent px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading || query.trim() === ""}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {loading && (
        <p role="status" className="mt-4 text-zinc-600 dark:text-zinc-400">
          Looking up...
        </p>
      )}

      {error && (
        <p role="alert" className="mt-4 text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {notFound && (
        <p role="status" className="mt-4 text-zinc-600 dark:text-zinc-400">
          No customer found. Check the spelling, or try an email, phone number or order ID.
        </p>
      )}

      {matches.length > 0 && (
        <div className="mt-6">
          <p className="font-medium">{matches.length} customers match. Pick one:</p>
          <ul className="mt-2 space-y-2">
            {matches.map((c) => (
              <li key={c.customer_id}>
                <button
                  type="button"
                  onClick={() => handlePick(c.customer_id)}
                  disabled={loading}
                  className="w-full rounded border px-3 py-2 text-left hover:bg-zinc-100 disabled:opacity-50 dark:hover:bg-zinc-800"
                >
                  <span className="font-medium">{c.name}</span>
                  <span className="ml-3 text-sm text-zinc-600 dark:text-zinc-400">
                    {c.customer_id} · {c.account_type}
                    {c.region ? ` · ${c.region}` : ""} · {c.email_masked}
                    {c.phone_masked ? ` · ${c.phone_masked}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail && <CustomerDetails detail={detail} />}
    </div>
  );
}
