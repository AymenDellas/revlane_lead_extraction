import { useState } from 'react';

function ScanForm({ onSubmit, isRunning }) {
    const [niche, setNiche] = useState('');
    const [location, setLocation] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!niche.trim()) return;
        onSubmit(niche.trim(), location.trim() || 'Remote/Global');
    };

    return (
        <div className="glass-card">
            <div className="card-title">
                <span className="icon">🔎</span>
                Target Configuration
            </div>
            <form className="scan-form" onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label" htmlFor="niche">Niche / Industry</label>
                    <input
                        id="niche"
                        className="form-input"
                        type="text"
                        placeholder='e.g. "SaaS Founder", "Marketing Agency"'
                        value={niche}
                        onChange={(e) => setNiche(e.target.value)}
                        disabled={isRunning}
                        required
                    />
                </div>
                <div className="form-group">
                    <label className="form-label" htmlFor="location">Location</label>
                    <input
                        id="location"
                        className="form-input"
                        type="text"
                        placeholder='e.g. "New York", "Remote/Global"'
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        disabled={isRunning}
                    />
                </div>
                <button className="btn btn-primary" type="submit" disabled={isRunning || !niche.trim()}>
                    {isRunning ? (
                        <>
                            <span className="spinner"></span>
                            Scanning…
                        </>
                    ) : (
                        <>⚡ Launch Scan</>
                    )}
                </button>
            </form>
        </div>
    );
}

export default ScanForm;
