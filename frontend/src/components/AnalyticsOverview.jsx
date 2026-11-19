import React, { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceDot,
} from 'recharts'
import useThemeColors from '../hooks/useThemeColors'

const ALL_THEMES = [
  'Login Crash',
  'Billing & Payments',
  'Performance & Lag',
  'UI/UX',
  'General',
]

const ALL_CHANNELS = ['App Store', 'Google Play', 'Reddit', 'Discord']

// Custom lightweight tooltip
const ChartTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const dataPoint = payload[0]?.payload
    const isSpike = dataPoint?.isSpike
    const negShare = dataPoint?.negShare ?? 0

    return (
      <div className="bg-surface border border-line p-2.5 rounded shadow-sm text-xs">
        <p className="font-semibold text-ink mb-1">{label}</p>
        {payload.map((entry, index) => (
          <div key={`tip-${index}`} className="flex items-center justify-between gap-4 py-0.5">
            <span className="flex items-center gap-1.5 text-muted">
              <span
                className="w-2 h-2 rounded-sm"
                style={{ backgroundColor: entry.color }}
              />
              <span>{entry.name}</span>
            </span>
            <span className="font-medium text-ink tabular-nums">{entry.value}</span>
          </div>
        ))}
        {isSpike && (
          <p className="mt-1 pt-1 border-t border-line text-negative font-medium">
            Spike: {dataPoint?.negative ?? 0} of {dataPoint?.total ?? 0} negative ({negShare}%)
          </p>
        )}
      </div>
    )
  }
  return null
}

export default function AnalyticsOverview({
  reviews = [],
  totalReviewsCount = 0,
  alertConfig = null,
  onSelectTheme,
  onClearFilters,
  onOpenModal,
  isLoading = false,
}) {
  const themeColors = useThemeColors()

  // Spike threshold from alertConfig if configured
  const spikeThreshold =
    alertConfig && alertConfig.negative_threshold_pct != null
      ? alertConfig.negative_threshold_pct
      : null

  // Daily Stacked Bar Chart Data - must be declared before any early returns
  const dailyChartData = useMemo(() => {
    if (!reviews || reviews.length === 0) return []

    const groups = {}

    reviews.forEach((r) => {
      const dateKey = r.created_at ? r.created_at.slice(0, 10) : 'Recent'
      if (!groups[dateKey]) {
        groups[dateKey] = {
          date: dateKey,
          negative: 0,
          neutral: 0,
          positive: 0,
          total: 0,
        }
      }
      if (r.sentiment_label === 'Negative') groups[dateKey].negative += 1
      else if (r.sentiment_label === 'Positive') groups[dateKey].positive += 1
      else groups[dateKey].neutral += 1
      groups[dateKey].total += 1
    })

    const sortedDates = Object.keys(groups).sort()

    return sortedDates.map((dateKey) => {
      const grp = groups[dateKey]
      const negShare = grp.total > 0 ? Math.round((grp.negative / grp.total) * 100) : 0
      const isSpike = Boolean(
        spikeThreshold != null && grp.total >= 3 && negShare >= spikeThreshold
      )

      let formattedDate = dateKey
      if (dateKey !== 'Recent') {
        const d = new Date(dateKey + 'T00:00:00')
        if (!isNaN(d.getTime())) {
          formattedDate = d.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
          })
        }
      }

      return {
        date: dateKey,
        formattedDate,
        negative: grp.negative,
        neutral: grp.neutral,
        positive: grp.positive,
        total: grp.total,
        negShare,
        isSpike,
      }
    })
  }, [reviews, spikeThreshold])

  // Themes ranked descending - must be declared before any early returns
  const themeData = useMemo(() => {
    const counts = {}
    ALL_THEMES.forEach((t) => {
      counts[t] = 0
    })

    if (reviews && reviews.length > 0) {
      reviews.forEach((r) => {
        const t = r.category_theme || 'General'
        counts[t] = (counts[t] || 0) + 1
      })
    }

    const list = Object.entries(counts).map(([name, count]) => ({
      name,
      count,
    }))
    list.sort((a, b) => b.count - a.count)
    return list
  }, [reviews])

  const maxThemeCount = Math.max(...themeData.map((t) => t.count), 1)

  // Channels table data - must be declared before any early returns
  const channelData = useMemo(() => {
    const stats = {}
    ALL_CHANNELS.forEach((ch) => {
      stats[ch] = { total: 0, negative: 0 }
    })

    if (reviews && reviews.length > 0) {
      reviews.forEach((r) => {
        const src = r.source || 'App Store'
        if (!stats[src]) stats[src] = { total: 0, negative: 0 }
        stats[src].total += 1
        if (r.sentiment_label === 'Negative') stats[src].negative += 1
      })
    }

    return ALL_CHANNELS.map((name) => {
      const s = stats[name] || { total: 0, negative: 0 }
      const negShare = s.total > 0 ? Math.round((s.negative / s.total) * 100) : 0
      return {
        name,
        total: s.total,
        negShare,
      }
    })
  }, [reviews])

  // Summary Metrics computed from filtered reviews
  const total = reviews.length
  const negativeCount = reviews.filter((r) => r.sentiment_label === 'Negative').length
  const negativePct = total > 0 ? Math.round((negativeCount / total) * 100) : 0
  const openCritical = reviews.filter(
    (r) =>
      ((r.rating && r.rating <= 2) || r.sentiment_label === 'Negative') &&
      (r.status === 'New' || r.status === 'Escalated')
  ).length

  const hasSpikeDays = dailyChartData.some((d) => d.isSpike)

  // Empty & loading states (handled AFTER all hooks are called)
  if (isLoading) {
    return <p className="text-xs text-muted py-12">Loading reviews...</p>
  }

  if (totalReviewsCount === 0) {
    return (
      <div className="py-12 text-xs">
        <p className="text-ink mb-2">No reviews in the database.</p>
        <button
          type="button"
          onClick={onOpenModal}
          className="text-action hover:underline"
        >
          Import reviews or load demo data
        </button>
      </div>
    )
  }

  if (reviews.length === 0) {
    return (
      <div className="py-12 text-xs">
        <p className="text-ink mb-2">No reviews match these filters.</p>
        <button
          type="button"
          onClick={onClearFilters}
          className="text-action hover:underline"
        >
          Clear filters
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Plain sentence summary line */}
      <div className="text-sm text-ink font-medium">
        {total} reviews · {negativePct}% negative · {openCritical} open critical
      </div>

      {/* Hero Stacked Bar Chart */}
      <div className="bg-surface border border-line rounded-md p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-sm font-semibold text-ink">
              Reviews per day by sentiment
            </h3>
            {hasSpikeDays && spikeThreshold != null && (
              <p className="text-xs text-negative mt-0.5">
                Spike threshold ({spikeThreshold}%) exceeded on flagged days.
              </p>
            )}
          </div>

          {/* Simple plain legend */}
          <div className="flex items-center gap-4 text-xs text-muted">
            {hasSpikeDays && (
              <span className="flex items-center gap-1.5">
                <svg width="8" height="8" viewBox="0 0 8 8" className="overflow-visible" aria-hidden="true">
                  <polygon points="4,7 0.5,1 7.5,1" fill={themeColors?.negative || '#C23B2A'} />
                </svg>
                <span>Spike</span>
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: themeColors?.negative || '#C23B2A' }}
              />
              <span>Negative</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: themeColors?.neutral || '#8C96A0' }}
              />
              <span>Neutral</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: themeColors?.positive || '#2F7A63' }}
              />
              <span>Positive</span>
            </span>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={dailyChartData}
              margin={{ top: 16, right: 10, left: -20, bottom: 5 }}
            >
              <CartesianGrid
                stroke={themeColors?.line || '#DDE1E6'}
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="formattedDate"
                stroke={themeColors?.muted || '#5B6670'}
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: themeColors?.line || '#DDE1E6' }}
              />
              <YAxis
                stroke={themeColors?.muted || '#5B6670'}
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: themeColors?.line || '#DDE1E6' }}
                allowDecimals={false}
                domain={[0, (dataMax) => dataMax + 1]}
              />
              <Tooltip content={<ChartTooltip />} />
              <Bar
                dataKey="negative"
                name="Negative"
                stackId="sentiment"
                fill={themeColors?.negative || '#C23B2A'}
              />
              <Bar
                dataKey="neutral"
                name="Neutral"
                stackId="sentiment"
                fill={themeColors?.neutral || '#8C96A0'}
              />
              <Bar
                dataKey="positive"
                name="Positive"
                stackId="sentiment"
                fill={themeColors?.positive || '#2F7A63'}
                radius={[4, 4, 0, 0]}
              />
              {dailyChartData
                .filter((d) => d.isSpike)
                .map((d) => (
                  <ReferenceDot
                    key={d.date}
                    x={d.formattedDate}
                    y={d.total}
                    r={6}
                    isFront={true}
                    ifOverflow="visible"
                    shape={({ cx, cy }) => {
                      if (cx == null || cy == null) return null
                      const yBase = cy - 4
                      const yTop = yBase - 6
                      return (
                        <polygon
                          points={`${cx},${yBase} ${cx - 3.5},${yTop} ${cx + 3.5},${yTop}`}
                          fill={themeColors?.negative || '#C23B2A'}
                        />
                      )
                    }}
                  />
                ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Two-Column Section: Top Themes & Channels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ranked Theme List */}
        <div className="bg-surface border border-line rounded-md p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-ink">Top themes</h3>
            <span className="text-xs text-muted">Click to filter board</span>
          </div>

          <div className="space-y-2">
            {themeData.map((theme) => {
              const themePct =
                maxThemeCount > 0
                  ? Math.min(100, Math.max(0, Math.round((theme.count / maxThemeCount) * 100)))
                  : 0

              return (
                <button
                  key={theme.name}
                  type="button"
                  onClick={() => onSelectTheme(theme.name)}
                  className="w-full text-left p-2 rounded hover:bg-paper transition-colors group"
                >
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-medium text-ink group-hover:text-action">
                      {theme.name}
                    </span>
                    <span className="text-muted tabular-nums">{theme.count}</span>
                  </div>
                  <div
                    className="block w-full bg-track rounded h-[6px] overflow-hidden"
                    aria-hidden="true"
                  >
                    <div
                      className="block bg-muted h-[6px] rounded transition-all"
                      style={{ width: `${themePct}%` }}
                    />
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Compact Channels Table */}
        <div className="bg-surface border border-line rounded-md p-5">
          <h3 className="text-sm font-semibold text-ink mb-3">Channels</h3>

          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="pb-2 font-medium">Channel</th>
                <th className="pb-2 font-medium text-right">Reviews</th>
                <th className="pb-2 font-medium text-right">Negative share</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {channelData.map((ch) => {
                const channelPct =
                  ch.total > 0 ? Math.min(100, Math.max(0, ch.negShare)) : 0

                return (
                  <tr key={ch.name}>
                    <td className="py-2.5 font-medium text-ink">{ch.name}</td>
                    <td className="py-2.5 text-right text-ink tabular-nums">
                      {ch.total}
                    </td>
                    <td className="py-2.5 text-right text-muted tabular-nums">
                      <div className="flex items-center justify-end gap-2">
                        <span>{ch.negShare}%</span>
                        <div
                          className="block w-16 bg-track rounded h-[6px] overflow-hidden"
                          aria-hidden="true"
                        >
                          <div
                            className="block bg-negative h-[6px] rounded transition-all"
                            style={{ width: `${channelPct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
