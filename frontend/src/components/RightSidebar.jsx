import './RightSidebar.css'

export default function RightSidebar({
  lastRoute,
  lastProjects,
  lastFactors,
  lastRetrievalNote,
  width,
  onStartResize,
}) {
  // Dynamically extract columns from data
  const projectColumns = lastProjects.length > 0
    ? Object.keys(lastProjects[0])
    : []

  const factorColumns = lastFactors.length > 0
    ? Object.keys(lastFactors[0]).filter(col => col !== 'sequence')
    : []

  return (
    <div className="right-sidebar" style={{ width: `${width}px`, flexBasis: `${width}px` }}>
      <div
        className="sidebar-resize-handle left"
        onMouseDown={onStartResize}
        role="separator"
        aria-label="Resize right sidebar"
        aria-orientation="vertical"
      ></div>

      <div className="right-sidebar-content">
        <div className="sidebar-header">
          <div className="sidebar-header-row">
            <h3>Retrieval output</h3>
          </div>
          <p className="hint">Latest retrieval trace from your most recent question</p>
        </div>

        <div className="retrieval-note">
          <p>{lastRetrievalNote}</p>
        </div>

        <div className="section">
          <div className="section-header static">
            <span className="section-title">Matched projects</span>
          </div>
          <div className="section-content">
            <p className="rows-label">Rows: {lastProjects.length}</p>
            {lastProjects.length > 0 ? (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      {projectColumns.map((column) => (
                        <th key={column}>{formatColumnLabel(column)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lastProjects.slice(0, 10).map((project, idx) => (
                      <tr key={idx}>
                        {projectColumns.map((column) => (
                          <td key={column}>{project[column] || 'NULL'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">No projects matched</p>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header static">
            <span className="section-title">Matched factors</span>
          </div>
          <div className="section-content">
            <p className="rows-label">Rows: {lastFactors.length}</p>
            {lastFactors.length > 0 ? (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      {factorColumns.map((column) => (
                        <th key={column}>{formatColumnLabel(column)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {lastFactors.map((factor, idx) => (
                      <tr key={idx}>
                        {factorColumns.map((column) => (
                          <td key={column}>{factor[column] || 'NULL'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">No factors matched</p>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header static">
            <span className="section-title">Route JSON</span>
          </div>
          <div className="section-content">
            {lastRoute ? (
              <pre className="json-display">{JSON.stringify(lastRoute, null, 2)}</pre>
            ) : (
              <p className="empty-state">No route data yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function formatColumnLabel(column) {
  return column.replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
}
