"use client";

import { useState } from "react";

type Suburb = {
  suburb_name: string;
  score: number;
  total_pois: number;
};

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Suburb[]>([]);

  async function getRecommendations() {
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      if (!apiBase) throw new Error("NEXT_PUBLIC_API_URL not set");

      const res = await fetch(`${apiBase}/api/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recreation: 0.25,
          community: 0.25,
          transport: 0.25,
          education: 0.15,
          utility: 0.1,
        }),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`API ${res.status}: ${txt}`);
      }

      const data = await res.json();
      setResults(data as Suburb[]);
    } catch (e: any) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 900, margin: "40px auto", padding: 20 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>NSW Suburb Finder</h1>
      <p style={{ color: "#666", marginBottom: 16 }}>
        Click the button to fetch recommendations from the backend API.
      </p>

      <button onClick={getRecommendations} disabled={loading} style={{ padding: "10px 16px", borderRadius: 6, border: "1px solid #ddd" }}>
        {loading ? "Loading…" : "Get Recommendations"}
      </button>

      {error && (
        <div style={{ color: "crimson", marginTop: 16 }}>{error}</div>
      )}

      <div style={{ marginTop: 24 }}>
        {results.map((r, i) => (
          <div key={i} style={{ padding: 12, border: "1px solid #eee", borderRadius: 8, marginBottom: 12 }}>
            <div style={{ fontWeight: 600 }}>{i + 1}. {r.suburb_name}</div>
            <div>Score: {(r.score * 100).toFixed(1)}%</div>
            <div>Total POIs: {r.total_pois}</div>
          </div>
        ))}
      </div>
    </main>
  );
}
