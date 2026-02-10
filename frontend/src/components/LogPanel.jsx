import { useEffect, useRef } from 'react';

function LogPanel({ logs }) {
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    if (logs.length === 0) return null;

    return (
        <div className="log-panel">
            {logs.map((log) => (
                <div key={log.id} className="log-entry">
                    {log.text}
                </div>
            ))}
            <div ref={endRef} />
        </div>
    );
}

export default LogPanel;
