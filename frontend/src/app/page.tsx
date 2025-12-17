"use client";

import { useMemo, useState } from "react";

type PoiCounts = Partial<{
  recreation: number;
  community: number;
  transport: number;
  education: number;
  utility: number;
}>;

type Recommendation = {
  suburb_name: string;
  score: number;
  poi_counts?: PoiCounts;
  total_pois: number;
  latitude?: number | null;
  longitude?: number | null;
};

type PreferenceWeights = {
  recreation: number;
  community: number;
  transport: number;
  education: number;
  utility: number;
  latitude?: number | null;
  longitude?: number | null;
  radius_km?: number | null;
};

type NLQueryResponse = {
  interpreted_preferences: PreferenceWeights;
  recommendations: Recommendation[];
};

const defaultWeights = {
  recreation: 25,
  community: 25,
  transport: 25,
  education: 15,
  utility: 10,
};

const defaultNormalized = {
  recreation: 0.25,
  community: 0.25,
  transport: 0.25,
  education: 0.15,
  utility: 0.1,
};

export default function Home() {
  const [weights, setWeights] = useState(defaultWeights);
  const [latitude, setLatitude] = useState<string>("");
  const [longitude, setLongitude] = useState<string>("");
  const [radiusKm, setRadiusKm] = useState<number>(5);
  const [nlQuery, setNlQuery] = useState<string>("");
  const [nlPrefs, setNlPrefs] = useState<PreferenceWeights | null>(null);
  const [usingNL, setUsingNL] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Recommendation[]>([]);

  const totalWeight = useMemo(
    () =>
      Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0),
    [weights]
  );

  const normalizedWeights = useMemo(() => {
    if (totalWeight <= 0) return defaultNormalized;
    return Object.fromEntries(
      Object.entries(weights).map(([k, v]) => [k, Number(v) / totalWeight])
    ) as typeof defaultNormalized;
  }, [weights, totalWeight]);

  const updateWeight = (key: keyof typeof weights, value: number) => {
    setWeights((prev) => ({ ...prev, [key]: value }));
  };

  async function fetchRecommendations() {
    setUsingNL(false);
    setNlPrefs(null);
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
      if (!apiBase) throw new Error("Set NEXT_PUBLIC_API_URL in your environment.");

      const res = await fetch(`${apiBase}/api/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...normalizedWeights,
          latitude: latitude ? Number(latitude) : null,
          longitude: longitude ? Number(longitude) : null,
          radius_km: radiusKm,
        }),
      });

      if (!res.ok) {
        const txt = await res.text();
        let errorMsg = `API ${res.status}: ${txt}`;
        if (res.status === 0 || res.status === 404) {
          errorMsg = `Cannot connect to API. Check that NEXT_PUBLIC_API_URL is set correctly. Current: ${apiBase || 'NOT SET'}`;
        } else if (res.status === 500) {
          errorMsg = `Server error: ${txt}. Check Railway logs.`;
        } else if (res.status === 403 || res.status === 401) {
          errorMsg = `CORS or authentication error. Check ALLOWED_ORIGINS in Railway.`;
        }
        throw new Error(errorMsg);
      }

      const data = (await res.json()) as Recommendation[];
      setResults(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Request failed");
      }
    } finally {
      setLoading(false);
    }
  }

  async function fetchRecommendationsFromNL() {
    if (!nlQuery.trim()) {
      setError("Please describe what you're looking for.");
      return;
    }

    setUsingNL(true);
    setNlPrefs(null);
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
      if (!apiBase) throw new Error("Set NEXT_PUBLIC_API_URL in your environment.");

      const res = await fetch(`${apiBase}/api/nl_query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: nlQuery }),
      });

      if (!res.ok) {
        const txt = await res.text();
        let errorMsg = `API ${res.status}: ${txt}`;
        if (res.status === 0 || res.status === 404) {
          errorMsg = `Cannot connect to API. Check that NEXT_PUBLIC_API_URL is set correctly. Current: ${apiBase || "NOT SET"}`;
        } else if (res.status === 500) {
          errorMsg = `Server error: ${txt}. Check Railway logs.`;
        } else if (res.status === 403 || res.status === 401) {
          errorMsg = `CORS or authentication error. Check ALLOWED_ORIGINS in Railway.`;
        }
        throw new Error(errorMsg);
      }

      const data = (await res.json()) as NLQueryResponse;
      setNlPrefs(data.interpreted_preferences);
      setResults(data.recommendations);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Request failed");
      }
    } finally {
      setLoading(false);
    }
  }

  const handleGeoLocate = () => {
    if (!navigator.geolocation) {
      setError("Geolocation not supported in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(String(pos.coords.latitude));
        setLongitude(String(pos.coords.longitude));
      },
      () => setError("Unable to get your location. Please enter it manually.")
    );
  };

  const weightMeta: Array<{
    key: keyof typeof weights;
    label: string;
    helper: string;
  }> = [
    { key: "recreation", label: "Recreation & Sports", helper: "Parks, sports facilities, entertainment" },
    { key: "community", label: "Community", helper: "Community centres, libraries, cultural spaces" },
    { key: "transport", label: "Transport", helper: "Public transport, accessibility" },
    { key: "education", label: "Education", helper: "Schools, universities, learning hubs" },
    { key: "utility", label: "Utilities", helper: "Essential services and amenities" },
  ];

  return (
    <main className="page">
      <div className="hero">
        <p className="pill">Beta</p>
        <h1>NSW Suburb Finder</h1>
        <p>Rank Sydney suburbs by what matters to you—amenities, transport, community, and more.</p>
      </div>

      <section className="glass-card" style={{ marginTop: 16 }}>
        <div className="section-title">
          <span>Describe your ideal suburb</span>
          <span className="muted">Natural language search (experimental)</span>
        </div>
        <div className="grid">
          <div className="slider-row">
            <label>
              <span>Your description</span>
            </label>
            <textarea
              rows={3}
              value={nlQuery}
              onChange={(e) => setNlQuery(e.target.value)}
              placeholder='e.g. "Quiet, family-friendly suburb with good schools and decent public transport near Parramatta."'
            />
            <small>
              We&apos;ll interpret this into weights for recreation, community, transport, education and utilities using a local model.
            </small>
            <button className="btn-secondary" onClick={fetchRecommendationsFromNL} type="button" disabled={loading}>
              {loading && usingNL ? "Searching from description…" : "Search by description"}
            </button>
          </div>
        </div>
        {nlPrefs && (
          <div className="stat-wrap" style={{ marginTop: 8 }}>
            <span className="stat-chip">Recreation {(nlPrefs.recreation * 100).toFixed(0)}%</span>
            <span className="stat-chip">Community {(nlPrefs.community * 100).toFixed(0)}%</span>
            <span className="stat-chip">Transport {(nlPrefs.transport * 100).toFixed(0)}%</span>
            <span className="stat-chip">Education {(nlPrefs.education * 100).toFixed(0)}%</span>
            <span className="stat-chip">Utilities {(nlPrefs.utility * 100).toFixed(0)}%</span>
          </div>
        )}
      </section>

      <section className="glass-card">
        <div className="section-title">
          <span>Preference sliders</span>
          <span className="stat-chip">Total weight: {totalWeight || 0}%</span>
        </div>
        <div className="grid">
          {weightMeta.map(({ key, label, helper }) => (
            <div className="slider-row" key={key}>
              <label>
                <span>{label}</span>
                <span>{weights[key]}%</span>
              </label>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={weights[key]}
                onChange={(e) => updateWeight(key, Number(e.target.value))}
              />
              <small>{helper}</small>
            </div>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          We normalize your sliders automatically so the API receives balanced weights.
        </p>
      </section>

      <section className="glass-card" style={{ marginTop: 16 }}>
        <div className="section-title">
          <span>Location filter (optional)</span>
          <span className="pill">{radiusKm} km radius</span>
        </div>
        <div className="grid">
          <div className="slider-row">
            <label>
              <span>Latitude</span>
            </label>
            <input
              placeholder="-33.8688"
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              type="text"
            />
            <label>
              <span>Longitude</span>
            </label>
            <input
              placeholder="151.2093"
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              type="text"
            />
            <button className="btn-secondary" onClick={handleGeoLocate} type="button">
              Use my location
            </button>
          </div>
          <div className="slider-row">
            <label>
              <span>Search radius</span>
              <span>{radiusKm} km</span>
            </label>
            <input
              type="range"
              min={1}
              max={20}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
            />
            <small>Leave blank coordinates to rank suburbs without a location filter.</small>
          </div>
        </div>
      </section>

      <div className="actions" style={{ marginTop: 16 }}>
        <button className="btn-primary" onClick={fetchRecommendations} disabled={loading}>
          {loading ? "Finding suburbs…" : "Get recommendations"}
        </button>
        <div className="stat-wrap">
          <span className="stat-chip">Recreation {(normalizedWeights.recreation * 100).toFixed(0)}%</span>
          <span className="stat-chip">Community {(normalizedWeights.community * 100).toFixed(0)}%</span>
          <span className="stat-chip">Transport {(normalizedWeights.transport * 100).toFixed(0)}%</span>
          <span className="stat-chip">Education {(normalizedWeights.education * 100).toFixed(0)}%</span>
          <span className="stat-chip">Utilities {(normalizedWeights.utility * 100).toFixed(0)}%</span>
        </div>
      </div>
      {error && <div className="inline-error">{error}</div>}

      <section className="glass-card" style={{ marginTop: 20 }}>
        <div className="section-title">
          <span>Top matches</span>
          <span className="muted">
            {usingNL ? "Interpreted from your description via FastAPI backend" : "Live data from your FastAPI backend"}
          </span>
        </div>

        {loading ? (
          <div className="results-grid">
            <div className="skeleton" />
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        ) : results.length === 0 ? (
          <p className="muted">Run a search to see ranked suburbs.</p>
        ) : (
          <div className="results-grid">
            {results.map((rec, idx) => (
              <div className="recommend-card" key={`${rec.suburb_name}-${idx}`}>
                <div className="section-title" style={{ marginBottom: 4 }}>
                  <h3>
                    #{idx + 1} {rec.suburb_name}
                  </h3>
                  <span className="stat-chip">{rec.total_pois} POIs</span>
                </div>
                <div className="score">{(rec.score * 100).toFixed(1)}%</div>
                <div className="poi-grid">
                  {Object.entries(rec.poi_counts || {}).map(([k, v]) => (
                    <div className="poi-chip" key={k}>
                      <strong style={{ display: "block", textTransform: "capitalize" }}>{k}</strong>
                      <span className="muted">{v ?? 0} places</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
