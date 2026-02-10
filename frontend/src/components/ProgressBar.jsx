function ProgressBar({ progress, isRunning }) {
    return (
        <div className="progress-wrapper">
            <div className="progress-bar-track">
                <div
                    className="progress-bar-fill"
                    style={{ width: `${progress}%` }}
                ></div>
            </div>
            <div className="progress-text">
                <span>{isRunning ? 'Pipeline active…' : progress >= 100 ? 'Complete' : 'Ready'}</span>
                <span>{Math.round(progress)}%</span>
            </div>
        </div>
    );
}

export default ProgressBar;
