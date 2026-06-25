import { useState, useMemo } from 'react'
import { ComposableMap, Geographies, Geography, ZoomableGroup } from 'react-simple-maps'
import './WorldMap.css'

const GEO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

// Market name (from DB) → { isoNumeric, coords [lon,lat], zoom }
const COUNTRY_META = {
  'India':          { isoNumeric: '356', coords: [78.96,  22.59],  zoom: 3   },
  'USA':            { isoNumeric: '840', coords: [-95.71, 37.09],  zoom: 2.5 },
  'UK':             { isoNumeric: '826', coords: [-3.44,  55.38],  zoom: 5   },
  'China':          { isoNumeric: '156', coords: [104.20, 35.86],  zoom: 2.5 },
  'Japan':          { isoNumeric: '392', coords: [138.25, 36.20],  zoom: 4.5 },
  'Brazil':         { isoNumeric: '076', coords: [-51.93,-14.24],  zoom: 2.5 },
  'Sweden':         { isoNumeric: '752', coords: [18.64,  60.13],  zoom: 4   },
  'Indonesia':      { isoNumeric: '360', coords: [113.92, -0.79],  zoom: 3   },
  'Dubai':          { isoNumeric: '784', coords: [55.27,  25.20],  zoom: 6   },
  'Canada':         { isoNumeric: '124', coords: [-96.82, 56.13],  zoom: 2   },
  'Mexico':         { isoNumeric: '484', coords: [-102.55,23.63],  zoom: 3   },
  'Italy':          { isoNumeric: '380', coords: [12.57,  41.87],  zoom: 5   },
  'Thailand':       { isoNumeric: '764', coords: [100.99, 15.87],  zoom: 4   },
  'Germany':        { isoNumeric: '276', coords: [10.45,  51.17],  zoom: 5   },
  'France':         { isoNumeric: '250', coords: [2.21,   46.23],  zoom: 4.5 },
  'Egypt':          { isoNumeric: '818', coords: [30.80,  26.82],  zoom: 4   },
  'South Korea':    { isoNumeric: '410', coords: [127.77, 35.91],  zoom: 5.5 },
  'Korea':          { isoNumeric: '410', coords: [127.77, 35.91],  zoom: 5.5 },
  'Philippines':    { isoNumeric: '608', coords: [122.56, 12.88],  zoom: 4   },
  'Turkey':         { isoNumeric: '792', coords: [35.24,  38.96],  zoom: 4   },
  'Nepal':          { isoNumeric: '524', coords: [84.12,  28.39],  zoom: 6   },
  'Saudi Arabia':   { isoNumeric: '682', coords: [45.08,  23.89],  zoom: 3.5 },
  'KSA':            { isoNumeric: '682', coords: [45.08,  23.89],  zoom: 3.5 },
  'Bangladesh':     { isoNumeric: '050', coords: [90.36,  23.68],  zoom: 6   },
  'Sri Lanka':      { isoNumeric: '144', coords: [80.77,   7.87],  zoom: 7   },
  'Romania':        { isoNumeric: '642', coords: [24.97,  45.94],  zoom: 5.5 },
  'Spain':          { isoNumeric: '724', coords: [-3.75,  40.46],  zoom: 4.5 },
  'Madrid':         { isoNumeric: '724', coords: [-3.75,  40.46],  zoom: 5   },
  'Malaysia':       { isoNumeric: '458', coords: [109.70,  4.21],  zoom: 4   },
  'New Zealand':    { isoNumeric: '554', coords: [174.89,-40.90],  zoom: 4   },
  'South Africa':   { isoNumeric: '710', coords: [22.94, -30.56],  zoom: 3.5 },
  'Finland':        { isoNumeric: '246', coords: [25.75,  61.92],  zoom: 4   },
  'Russia':         { isoNumeric: '643', coords: [105.32, 61.52],  zoom: 2   },
  'Argentina':      { isoNumeric: '032', coords: [-63.62,-38.42],  zoom: 3   },
  'Kenya':          { isoNumeric: '404', coords: [37.91,   0.02],  zoom: 5   },
  'Pakistan':       { isoNumeric: '586', coords: [69.35,  30.38],  zoom: 3.5 },
  'Greece':         { isoNumeric: '300', coords: [21.82,  39.07],  zoom: 5.5 },
  'Australia':      { isoNumeric: '036', coords: [133.78,-25.27],  zoom: 2.5 },
  'Uganda':         { isoNumeric: '800', coords: [32.29,   1.37],  zoom: 5.5 },
  'Poland':         { isoNumeric: '616', coords: [19.15,  51.92],  zoom: 4.5 },
  'Norway':         { isoNumeric: '578', coords: [8.47,   60.47],  zoom: 4   },
  'Switzerland':    { isoNumeric: '756', coords: [8.23,   46.82],  zoom: 6.5 },
  'Belgium':        { isoNumeric: '056', coords: [4.47,   50.50],  zoom: 7   },
  'Ukraine':        { isoNumeric: '804', coords: [31.17,  48.38],  zoom: 4.5 },
  'Vietnam':        { isoNumeric: '704', coords: [108.28, 14.06],  zoom: 4   },
  'Czech Republic': { isoNumeric: '203', coords: [15.47,  49.82],  zoom: 5.5 },
  'Taiwan':         { isoNumeric: '158', coords: [120.97, 23.70],  zoom: 7   },
  'Netherlands':    { isoNumeric: '528', coords: [5.29,   52.13],  zoom: 7   },
  'Colombia':       { isoNumeric: '170', coords: [-74.30,  4.57],  zoom: 3.5 },
  'Columbia':       { isoNumeric: '170', coords: [-74.30,  4.57],  zoom: 3.5 },
  'Tanzania':       { isoNumeric: '834', coords: [34.89,  -6.37],  zoom: 4.5 },
  'Guatemala':      { isoNumeric: '320', coords: [-90.23, 15.78],  zoom: 6   },
  'Guatemela':      { isoNumeric: '320', coords: [-90.23, 15.78],  zoom: 6   },
  'Honduras':       { isoNumeric: '340', coords: [-86.24, 15.20],  zoom: 5.5 },
  'Sao Paulo':      { isoNumeric: '076', coords: [-46.63,-23.55],  zoom: 5   },
  'UAE':            { isoNumeric: '784', coords: [53.85,  23.42],  zoom: 5   },
}

function getIsoForMarket(name) {
  if (!name) return null
  if (COUNTRY_META[name]) return COUNTRY_META[name].isoNumeric
  if (name.startsWith('India')) return '356'
  if (name.startsWith('Sweden')) return '752'
  return null
}

function getMetaForMarket(name) {
  if (!name) return null
  if (COUNTRY_META[name]) return COUNTRY_META[name]
  if (name.startsWith('India')) return COUNTRY_META['India']
  if (name.startsWith('Sweden')) return COUNTRY_META['Sweden']
  return null
}

function countToFill(count, maxCount) {
  if (!count) return '#e8edf4'
  const t = Math.sqrt(count / maxCount)
  const r = Math.round(199 - 178 * t)
  const g = Math.round(221 - 133 * t)
  const b = Math.round(243 - 75  * t)
  return `rgb(${r},${g},${b})`
}

export default function WorldMap({ markets = [], marketOptions = [], selectedMarket, onMarketSelect }) {
  const [position, setPosition] = useState({ coordinates: [10, 10], zoom: 1 })
  const [tooltip, setTooltip] = useState(null)

  const isoCountMap = useMemo(() => {
    const map = {}
    markets.forEach(({ label, count }) => {
      const iso = getIsoForMarket(label)
      if (iso) map[iso] = (map[iso] || 0) + count
    })
    return map
  }, [markets])

  const maxCount = useMemo(() => Math.max(...Object.values(isoCountMap), 1), [isoCountMap])

  // ISO → canonical market name (highest-count entry wins for that country)
  const isoToMarket = useMemo(() => {
    const map = {}
    markets.forEach(({ label, count }) => {
      const iso = getIsoForMarket(label)
      if (!iso) return
      if (!map[iso] || count > map[iso].count) map[iso] = { label, count }
    })
    return Object.fromEntries(Object.entries(map).map(([iso, { label }]) => [iso, label]))
  }, [markets])

  const selectedIso = useMemo(() => getIsoForMarket(selectedMarket), [selectedMarket])

  function zoomToMarket(name) {
    const meta = getMetaForMarket(name)
    if (meta) setPosition({ coordinates: meta.coords, zoom: meta.zoom || 3 })
  }

  function handleSlicerChange(e) {
    const name = e.target.value
    if (!name) return
    onMarketSelect?.(name)
    zoomToMarket(name)
  }

  function handleGeoClick(geo) {
    const iso = String(geo.id)
    const name = isoToMarket[iso]
    if (!name) return
    onMarketSelect?.(name)
    zoomToMarket(name)
  }

  return (
    <section className="chart-card map-card">
      <div className="chart-head-row">
        <h3>Brand Model Presence Across Markets</h3>
        {marketOptions.length > 0 && (
          <label className="category-slicer">
            <span>Market</span>
            <select value={selectedMarket || ''} onChange={handleSlicerChange}>
              <option value="">Select a market…</option>
              {marketOptions.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="map-wrapper">
        <ComposableMap
          projectionConfig={{ scale: 147, center: [10, 10] }}
          style={{ width: '100%', height: '100%' }}
        >
          <ZoomableGroup
            zoom={position.zoom}
            center={position.coordinates}
            onMoveEnd={setPosition}
          >
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map((geo) => {
                  const iso = String(geo.id)
                  const count = isoCountMap[iso] || 0
                  const isSelected = iso === selectedIso
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={isSelected ? '#1558a8' : countToFill(count, maxCount)}
                      stroke={isSelected ? '#0d3d7a' : '#b0bdd0'}
                      strokeWidth={isSelected ? 1.5 : 0.4}
                      onClick={() => handleGeoClick(geo)}
                      onMouseEnter={(e) => {
                        const name = isoToMarket[iso]
                        if (name || count) setTooltip({ label: name || '', count, x: e.clientX, y: e.clientY })
                      }}
                      onMouseMove={(e) => setTooltip(t => t ? { ...t, x: e.clientX, y: e.clientY } : null)}
                      onMouseLeave={() => setTooltip(null)}
                      style={{
                        default: { outline: 'none', cursor: count || isoToMarket[iso] ? 'pointer' : 'default' },
                        hover:   { outline: 'none', fill: count ? '#6ab0f5' : '#dde3ec' },
                        pressed: { outline: 'none' },
                      }}
                    />
                  )
                })
              }
            </Geographies>
          </ZoomableGroup>
        </ComposableMap>

        {tooltip && tooltip.label && (
          <div className="map-tooltip" style={{ left: tooltip.x + 14, top: tooltip.y - 50 }}>
            <strong>{tooltip.label}</strong>
            <span>{tooltip.count} project{tooltip.count !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      <div className="map-scale-row">
        <span className="map-scale-text">Fewer projects</span>
        <div className="map-scale-bar" />
        <span className="map-scale-text">More projects</span>
      </div>
    </section>
  )
}

