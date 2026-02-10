function PipelinePhases({ phases }) {
    return (
        <div className="pipeline">
            {phases.map((p) => (
                <div
                    key={p.phase}
                    className={`phase-card ${p.status === 'running' ? 'active' : ''} ${p.status === 'done' ? 'done' : ''}`}
                >
                    <div className="phase-number">Phase {p.phase}</div>
                    <div className="phase-name">{p.name}</div>
                    <div className="phase-status">
                        {p.status === 'idle' && '— Waiting'}
                        {p.status === 'running' && '⏳ In Progress…'}
                        {p.status === 'done' && `✓ Complete${p.count != null ? ` (${p.count})` : ''}`}
                    </div>
                </div>
            ))}
        </div>
    );
}

export default PipelinePhases;
