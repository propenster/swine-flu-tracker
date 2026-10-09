"use client";
import { useState, useEffect } from "react";

// 1. fetch the manifest!
const R2_BASE_URL = process.env.NEXT_PUBLIC_R2_BASE_URL || "https://pub-ca1ade7624504f70b2f2bbe90cdb1c73.r2.dev";

const US_STATES = [
  "Iowa", "Minnesota", "North Carolina", "Illinois", "Indiana",
  "Nebraska", "Missouri", "Ohio", "Kansas", "Oklahoma", "Texas"
];

type ManifestEntry = {
  state: string;
  subtypes: string[];
  date_range?: { min: string; max: string };
};

export default function Dashboard() {
  const [selectedState, setSelectedState] = useState<string>("Iowa");
  const [subtype, setSubtype] = useState<string>("H1");
  const [availableStates, setAvailableStates] = useState<string[]>(US_STATES);
  const [manifest, setManifest] = useState<ManifestEntry[]>([]);

  useEffect(() => {
    fetch(`${R2_BASE_URL}/manifest.json`)
      .then((res) => res.json())
      .then((data: ManifestEntry[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setManifest(data);
          const names = data.map((d) => d.state);
          setAvailableStates(names);
          setSelectedState((prev) => (names.includes(prev) ? prev : names[0]));
        }
      })
      .catch(() => { });
  }, []);

  const currentEntry = manifest.find((m) => m.state === selectedState);
  const availableSubtypes = currentEntry?.subtypes ?? ["H1", "H3"];

  // If user had H3 selected but state only has H1, snap to H1
  useEffect(() => {
    if (currentEntry && !currentEntry.subtypes.includes(subtype)) {
      setSubtype(currentEntry.subtypes[0] ?? "H1");
    }
  }, [currentEntry, subtype]);

  const safeState = selectedState.replace(/ /g, "_");

  // Nextstrain Fetch API needs the URL
  const strippedUrl = R2_BASE_URL.replace(/^https?:\/\//, "");
  const datasetPath = `${strippedUrl}/auspice_${safeState}_${subtype}.json`;
  const auspiceViewerUrl = `https://nextstrain.org/fetch/${datasetPath}`;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">

      {/* Top Header */}
      <header className="bg-slate-950 border-b border-slate-800 px-6 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></span>
            <h1 className="text-xl font-bold tracking-tight text-white">US Swine Influenza HA Tracker</h1>
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            Automated clade classification (octoFLU) &amp; Nextstrain Auspice phylogenetic visualization
          </p>
          {currentEntry?.date_range?.min && currentEntry?.date_range?.max && (
            <p className="text-slate-500 text-xs mt-0.5">
              Showing {currentEntry.date_range.min} → {currentEntry.date_range.max}
              {" "}({currentEntry.subtypes.join(", ")})
            </p>
          )}
        </div>

        {/* State Selection Dropdown & Subtype Toggle */}
        <div className="flex flex-wrap items-center gap-3">

          {/* State Dropdown */}
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5">
            <label htmlFor="state-select" className="text-xs text-slate-400 font-medium">State:</label>
            <select
              id="state-select"
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="bg-transparent text-sm font-semibold text-white focus:outline-none cursor-pointer"
            >
              {availableStates.map((st) => (
                <option key={st} value={st} className="bg-slate-900 text-white">
                  {st}
                </option>
              ))}
            </select>
          </div>

          {/* Subtype Toggle */}
          <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
            {["H1", "H3"].map((s) => {
              const enabled = availableSubtypes.includes(s);
              return (
                <button
                  key={s}
                  disabled={!enabled}
                  onClick={() => setSubtype(s)}
                  className={`px-3 py-1 rounded text-xs font-bold transition-all ${
                    subtype === s
                      ? "bg-blue-600 text-white shadow-sm"
                      : enabled
                      ? "text-slate-400 hover:text-white"
                      : "text-slate-700 cursor-not-allowed"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>

        </div>
      </header>

      {/* Main Auspice Viewer Section */}
      <main className="flex-grow p-4 bg-slate-950">
        <div className="w-full h-[calc(100vh-110px)] bg-white rounded-xl shadow-2xl overflow-hidden border border-slate-800">
          <iframe
            key={`${selectedState}-${subtype}`}
            src={auspiceViewerUrl}
            className="w-full h-full border-0"
            title={`Auspice Tree - ${selectedState} (${subtype})`}
            allowFullScreen
          />
        </div>
      </main>

    </div>
  );
}