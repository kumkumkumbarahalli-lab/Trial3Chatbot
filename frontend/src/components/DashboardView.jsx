import { useState, useCallback } from 'react'
import './DashboardView.css'
import WorldMap from './WorldMap'
import MarketCards from './MarketCards'

const DONUT_COLORS = [
  '#1f7ae0', '#34c759', '#aa59e0', '#ff9f0a', '#ff375f',
  '#5ac8fa', '#ffd60a', '#8e8e93', '#5856d6', '#30d158',
  '#ff6b35', '#00c7be', '#bf5af2', '#ffcc00', '#3a86ff',
  '#e63946', '#2ec4b6', '#f4a261', '#264653', '#e9c46a',
]

export default function DashboardView({ data, loading, error, onCategoryChange }) {
  const [barShowPct, setBarShowPct] = useState(false)
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [marketBreakdown, setMarketBreakdown] = useState(null)
  const [marketLoading, setMarketLoading] = useState(false)

  const handleMarketSelect = useCallback(async (market) => {
    setSelectedMarket(market)
    setMarketLoading(true)
    try {
      const res = await fetch(`http://localhost:8000/api/market-breakdown?market=${encodeURIComponent(market)}`)
      const json = await res.json()
      setMarketBreakdown(json)
    } catch {
      setMarketBreakdown(null)
    } finally {
      setMarketLoading(false)
    }
  }, [])

  if (loading) {
    return <div className="dashboard-view"><div className="dashboard-loading">Loading dashboard insights...</div></div>
  }
  if (error) {
    return <div className="dashboard-view"><div className="dashboard-error">{error}</div></div>
  }
  if (!data) {
    return <div className="dashboard-view"><div className="dashboard-empty">No dashboard data available.</div></div>
  }

  const kpis = data.kpis || {}
  const charts = data.charts || {}
  const slicers = data.slicers || {}
  const brandDistribution = charts.brand_distribution_for_selected_category || []
  const allCategoriesByBrandCount = charts.top_categories_by_brand_count || []
  const topCategoriesByBrandCount = allCategoriesByBrandCount.slice(0, 10)
  const selectedCategory = slicers.selected_category || ''
  const categoryOptions = slicers.category_options || []

  const allMarkets = charts.all_markets || []
  const marketOptions = slicers.market_options || []
  const totalBrands = brandDistribution.reduce((s, i) => s + i.count, 0)
  const barMax = topCategoriesByBrandCount[0]?.count || 1
  // Use ALL categories as denominator so % reflects share of full dataset, not just top 10
  const barTotal = allCategoriesByBrandCount.reduce((s, i) => s + i.count, 0)
  const barPctMax = barTotal > 0
    ? Math.round((topCategoriesByBrandCount[0]?.count / barTotal) * 100)
    : 1

  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <h2>Database Insights</h2>
        <p>Aggregation analytics and structural coverage of the consolidate taxonomy</p>
      </div>

      <div className="kpi-grid">
        <KpiCard label="Total Records"       value={kpis.total_records}        color="#4b6cff" />
        <KpiCard label="Unique Categories"   value={kpis.unique_categories}    color="#0dbf6f" />
        <KpiCard label="Unique Subcategories" value={kpis.unique_subcategories} color="#9b5dff" />
        <KpiCard label="Unique Clients"      value={kpis.unique_clients}       color="#ff8b00" />
        <KpiCard label="Unique Brands"       value={kpis.unique_brands}        color="#ff2f92" />
        <KpiCard label="Unique Markets"      value={kpis.unique_markets}       color="#00a3ff" />
      </div>

      <div className="dashboard-charts">
        {/* LEFT — Bar chart */}
        <section className="chart-card bars-card">
          <div className="chart-head-row">
            <h3>Top Categories by Number of Brands</h3>
            <button
              className="toggle-btn"
              onClick={() => setBarShowPct(p => !p)}
              title={barShowPct ? 'Show counts' : 'Show percentages'}
            >
              {barShowPct ? 'Show counts' : 'Show %'}
            </button>
          </div>
          <div className="bars-list">
            {topCategoriesByBrandCount.length > 0 ? topCategoriesByBrandCount.map((item) => {
              const pct = barTotal > 0 ? Math.round((item.count / barTotal) * 100) : 0
              return (
                <BarRow
                  key={item.label}
                  label={item.label}
                  value={barShowPct ? pct : item.count}
                  displayValue={barShowPct ? `${pct}%` : item.count}
                  max={barShowPct ? barPctMax : barMax}
                />
              )
            }) : <p className="chart-empty">No category brand count data.</p>}
          </div>
        </section>

        {/* RIGHT — Donut chart */}
        <section className="chart-card donut-card">
          <div className="chart-head-row">
            <h3>Distribution of Brands by Category</h3>
            <label className="category-slicer">
              <span>Category</span>
              <select value={selectedCategory} onChange={(e) => onCategoryChange?.(e.target.value)}>
                {categoryOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="donut-layout">
            <div className="donut-wrapper">
              <div className="donut" style={buildDonutStyle(brandDistribution)}>
                <div className="donut-inner">
                  <span className="donut-total">{totalBrands.toLocaleString()}</span>
                  <small>Projects</small>
                </div>
              </div>
            </div>
            <div className="legend-list">
              {brandDistribution.length > 0 ? brandDistribution.map((item, idx) => (
                <div key={item.label} className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: DONUT_COLORS[idx % DONUT_COLORS.length] }}></span>
                  <span className="legend-label">{item.label}</span>
                  <span className="legend-value">{item.count} <span className="legend-pct">({item.percentage}%)</span></span>
                </div>
              )) : <p className="chart-empty">No brand distribution data.</p>}
            </div>
          </div>
        </section>
      </div>

      <WorldMap
        markets={allMarkets}
        marketOptions={marketOptions}
        selectedMarket={selectedMarket}
        onMarketSelect={handleMarketSelect}
      />

      <MarketCards
        marketBreakdown={marketBreakdown}
        loading={marketLoading}
        selectedMarket={selectedMarket}
      />
    </div>
  )
}

function KpiCard({ label, value, color }) {
  return (
    <div className="kpi-card">
      <div>
        <p className="kpi-label">{label}</p>
        <p className="kpi-value">{(value || 0).toLocaleString()}</p>
      </div>
      <span className="kpi-dot" style={{ backgroundColor: color }}></span>
    </div>
  )
}

function BarRow({ label, value, displayValue, max }) {
  const width = Math.max(4, Math.round((value / max) * 100))
  return (
    <div className="bar-row">
      <div className="bar-labels">
        <span>{label}</span>
        <span>{displayValue}</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${width}%` }}></div>
      </div>
    </div>
  )
}

function buildDonutStyle(series) {
  const total = series.reduce((s, i) => s + i.count, 0)
  if (!total) return { background: 'conic-gradient(#d9e0ea 0deg 360deg)' }

  let cursor = 0
  const stops = series.map((item, idx) => {
    const angle = (item.count / total) * 360
    const from = cursor
    const to = cursor + angle
    cursor = to
    return `${DONUT_COLORS[idx % DONUT_COLORS.length]} ${from}deg ${to}deg`
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
}
