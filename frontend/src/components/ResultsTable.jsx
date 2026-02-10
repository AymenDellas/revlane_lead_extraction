function StatusBadge({ status }) {
    const labels = {
        valid: '✓ Valid',
        invalid: '✗ Invalid',
        'catch-all': '⚠ Catch-All',
        unknown: '? Unknown',
    };
    const cls = `badge badge-${status || 'unknown'}`;
    return <span className={cls}>{labels[status] || labels.unknown}</span>;
}

function ResultsTable({ leads }) {
    return (
        <div className="glass-card">
            <div className="card-title">
                <span className="icon">📊</span>
                Discovered Leads
            </div>
            <div className="table-wrapper">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Name</th>
                            <th>Title / Description</th>
                            <th>Domain</th>
                            <th>Email</th>
                            <th>Status</th>
                            <th>LinkedIn</th>
                            <th>Twitter</th>
                        </tr>
                    </thead>
                    <tbody>
                        {leads.map((lead, i) => (
                            <tr key={lead.url || i}>
                                <td>{i + 1}</td>
                                <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                                    {lead.name || '—'}
                                </td>
                                <td title={lead.description || lead.title}>
                                    {lead.title?.substring(0, 60) || lead.description?.substring(0, 60) || '—'}
                                </td>
                                <td>
                                    {lead.domain ? (
                                        <a className="link" href={lead.url} target="_blank" rel="noopener noreferrer">
                                            {lead.domain}
                                        </a>
                                    ) : (
                                        '—'
                                    )}
                                </td>
                                <td style={{ color: lead.verified_email ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                    {lead.verified_email || lead.emails?.[0] || '—'}
                                </td>
                                <td>
                                    <StatusBadge status={lead.email_status} />
                                </td>
                                <td>
                                    {lead.linkedin ? (
                                        <a className="link" href={lead.linkedin} target="_blank" rel="noopener noreferrer">
                                            Profile
                                        </a>
                                    ) : (
                                        '—'
                                    )}
                                </td>
                                <td>
                                    {lead.twitter ? (
                                        <a className="link" href={lead.twitter} target="_blank" rel="noopener noreferrer">
                                            Profile
                                        </a>
                                    ) : (
                                        '—'
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default ResultsTable;
