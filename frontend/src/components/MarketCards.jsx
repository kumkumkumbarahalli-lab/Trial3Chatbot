import './MarketCards.css'

export default function MarketCards({ marketBreakdown, loading, selectedMarket }) {
  if (!selectedMarket) {
    return (
      <div className="market-cards-hint">
        Click a highlighted country on the map or use the Market slicer to explore category and brand breakdowns.
      </div>
    )
  }

  if (loading) {
    return <div className="market-cards-loading">Loading data for {selectedMarket}…</div>
  }

  if (!marketBreakdown) return null

  const { categories_subcategories = [], brands = [] } = marketBreakdown

  return (
    <div className="market-cards-grid">
      {/* Left — Category × Subcategory */}
      <section className="chart-card market-card">
        <div className="chart-head-row">
          <h3>Categories &amp; Subcategories</h3>
          <span className="market-card-tag">{selectedMarket}</span>
        </div>
        <p className="rows-label">{categories_subcategories.length} combinations</p>
        {categories_subcategories.length > 0 ? (
          <div className="market-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Subcategory</th>
                  <th>#</th>
                </tr>
              </thead>
              <tbody>
                {categories_subcategories.map((row, i) => (
                  <tr key={i}>
                    <td>{row.category}</td>
                    <td>{row.subcategory}</td>
                    <td className="count-cell">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="chart-empty">No category data for this market.</p>
        )}
      </section>

      {/* Right — Brands */}
      <section className="chart-card market-card">
        <div className="chart-head-row">
          <h3>Brands</h3>
          <span className="market-card-tag">{selectedMarket}</span>
        </div>
        <p className="rows-label">{brands.length} brands</p>
        {brands.length > 0 ? (
          <div className="market-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Brand</th>
                  <th>#</th>
                </tr>
              </thead>
              <tbody>
                {brands.map((b, i) => (
                  <tr key={i}>
                    <td>{b.label}</td>
                    <td className="count-cell">{b.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="chart-empty">No brand data for this market.</p>
        )}
      </section>
    </div>
  )
}
