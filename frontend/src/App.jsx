import { useState, useRef, useCallback } from 'react';
import ScanForm from './components/ScanForm';
import PipelinePhases from './components/PipelinePhases';
import ProgressBar from './components/ProgressBar';
import LogPanel from './components/LogPanel';
import ResultsTable from './components/ResultsTable';
import ExportBar from './components/ExportBar';

const PHASE_NAMES = ['The Searcher', 'The Crawler', 'The Identity Lab', 'The Verifier'];

function App() {
    const [scanId, setScanId] = useState(null);
    const [isRunning, setIsRunning] = useState(false);
    const [phases, setPhases] = useState(PHASE_NAMES.map((name, i) => ({ phase: i + 1, name, status: 'idle' })));
    const [leads, setLeads] = useState([]);
    const [logs, setLogs] = useState([]);
    const [progress, setProgress] = useState(0);
    const [isDone, setIsDone] = useState(false);
    const eventSourceRef = useRef(null);

    const addLog = useCallback((msg) => {
        setLogs((prev) => [...prev.slice(-200), { id: Date.now() + Math.random(), text: msg }]);
    }, []);

    const startScan = useCallback(async (niche, location) => {
        // Reset state
        setLeads([]);
        setLogs([]);
        setProgress(0);
        setIsDone(false);
        setIsRunning(true);
        setPhases(PHASE_NAMES.map((name, i) => ({ phase: i + 1, name, status: 'idle' })));

        try {
            const res = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ niche, location }),
            });
            const data = await res.json();
            const id = data.scan_id;
            setScanId(id);
            addLog(`Scan started — ID: ${id}`);

            // Open SSE stream
            const es = new EventSource(`/api/scan/${id}/stream`);
            eventSourceRef.current = es;

            es.addEventListener('phase', (e) => {
                const d = JSON.parse(e.data);
                setPhases((prev) =>
                    prev.map((p) => (p.phase === d.phase ? { ...p, status: d.status, count: d.count } : p))
                );
                // Update progress based on active phase
                const baseProgress = (d.phase - 1) * 25;
                if (d.status === 'done') {
                    setProgress(d.phase * 25);
                } else {
                    setProgress(baseProgress + 5);
                }
                addLog(`Phase ${d.phase} (${d.name}): ${d.status}${d.count != null ? ` — ${d.count} items` : ''}`);
            });

            es.addEventListener('progress', (e) => {
                const d = JSON.parse(e.data);
                addLog(d.message);
            });

            es.addEventListener('lead', (e) => {
                const lead = JSON.parse(e.data);
                setLeads((prev) => {
                    // Upsert by URL
                    const idx = prev.findIndex((l) => l.url === lead.url);
                    if (idx >= 0) {
                        const updated = [...prev];
                        updated[idx] = lead;
                        return updated;
                    }
                    return [...prev, lead];
                });
            });

            es.addEventListener('done', (e) => {
                const d = JSON.parse(e.data);
                addLog(`✅ Scan complete — ${d.total} leads found.`);
                setProgress(100);
                setIsRunning(false);
                setIsDone(true);
                es.close();
            });

            es.addEventListener('error', (e) => {
                try {
                    const d = JSON.parse(e.data);
                    addLog(`❌ Error: ${d.message}`);
                } catch {
                    addLog('❌ Stream connection lost.');
                }
                setIsRunning(false);
                es.close();
            });

            es.onerror = () => {
                // SSE native error (connection lost)
                if (es.readyState === EventSource.CLOSED) return;
                addLog('⚠ Connection interrupted. Check the backend.');
                setIsRunning(false);
                es.close();
            };
        } catch (err) {
            addLog(`❌ Failed to start scan: ${err.message}`);
            setIsRunning(false);
        }
    }, [addLog]);

    return (
        <div className="app-wrapper">
            {/* Header */}
            <header className="header">
                <div className="container header-inner">
                    <div className="logo">
                        <div className="logo-icon">⚡</div>
                        <span className="logo-text">Revlane Engine</span>
                        <span className="logo-badge">v1.0</span>
                    </div>
                    <div className="header-status">
                        <span className="status-dot"></span>
                        System Online
                    </div>
                </div>
            </header>

            {/* Main */}
            <main className="main-content">
                <div className="container">
                    {/* Scan Form */}
                    <ScanForm onSubmit={startScan} isRunning={isRunning} />

                    {/* Pipeline Phases */}
                    {(isRunning || isDone) && (
                        <>
                            <div className="section-gap">
                                <PipelinePhases phases={phases} />
                            </div>
                            <ProgressBar progress={progress} isRunning={isRunning} />
                            <LogPanel logs={logs} />
                        </>
                    )}

                    {/* Results */}
                    {leads.length > 0 && (
                        <div className="section-gap">
                            <ResultsTable leads={leads} />
                            {isDone && scanId && <ExportBar scanId={scanId} leadCount={leads.length} />}
                        </div>
                    )}

                    {/* Empty state */}
                    {!isRunning && !isDone && leads.length === 0 && (
                        <div className="empty-state section-gap">
                            <div className="empty-state-icon">🎯</div>
                            <div className="empty-state-title">Ready to Discover Leads</div>
                            <div className="empty-state-text">
                                Enter a niche and location above to launch the four-phase pipeline.
                                Results stream live as they're discovered.
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

export default App;
