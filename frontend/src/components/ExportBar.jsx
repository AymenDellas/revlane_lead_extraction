function ExportBar({ scanId, leadCount }) {
    const handleExport = (format) => {
        window.open(`/api/scan/${scanId}/export?format=${format}`, '_blank');
    };

    return (
        <div className="export-bar">
            <div className="export-bar-left">
                <span className="export-bar-count">
                    <strong>{leadCount}</strong> lead{leadCount !== 1 ? 's' : ''} ready to export
                </span>
            </div>
            <div className="export-buttons">
                <button className="btn btn-secondary btn-sm" onClick={() => handleExport('csv')}>
                    📄 Export CSV
                </button>
                <button className="btn btn-secondary btn-sm" onClick={() => handleExport('json')}>
                    📋 Export JSON
                </button>
            </div>
        </div>
    );
}

export default ExportBar;
