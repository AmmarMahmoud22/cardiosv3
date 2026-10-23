import React, { useMemo } from 'react';
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface EcgWaveformProps {
  samples: number[];
  sampleRateHz: number;
  ariaLabel: string;
}

const ADC_DISPLAY_RANGE = 800;
const ECG_MINOR_GRID_PX = 8;
const ECG_MAJOR_GRID_PX = ECG_MINOR_GRID_PX * 5;

const median = (values: number[]): number => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
};

const EcgWaveform: React.FC<EcgWaveformProps> = ({ samples, sampleRateHz, ariaLabel }) => {
  const safeSampleRateHz = sampleRateHz > 0 ? sampleRateHz : 250;
  const baseline = useMemo(() => median(samples), [samples]);

  const chartSamples = useMemo(
    () =>
      samples.map((amplitude, index) => ({
        amplitude: Math.round(amplitude - baseline),
        rawAmplitude: amplitude,
        seconds: Number((index / safeSampleRateHz).toFixed(3)),
      })),
    [baseline, safeSampleRateHz, samples]
  );
  const durationSeconds = chartSamples.at(-1)?.seconds ?? 0;

  if (!chartSamples.length) {
    return (
      <div className="flex h-80 items-center justify-center rounded-lg border border-dashed border-rose-200 bg-rose-50/40 px-6 text-center text-sm text-slate-600">
        Waiting for the next ECG batch...
      </div>
    );
  }

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className="overflow-hidden rounded-lg border border-rose-200 bg-white shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rose-100 bg-white px-3 py-2 text-xs text-slate-600">
        <span className="font-semibold text-slate-800">ECG strip</span>
        <span className="tabular-nums">
          {durationSeconds.toFixed(1)}s | {safeSampleRateHz} Hz | baseline {Math.round(baseline)} ADC
        </span>
      </div>

      <div
        className="h-80 overflow-hidden p-2 sm:h-96"
        style={{
          backgroundColor: '#fffafa',
          backgroundImage: [
            'linear-gradient(rgba(244, 63, 94, 0.16) 1px, transparent 1px)',
            'linear-gradient(90deg, rgba(244, 63, 94, 0.16) 1px, transparent 1px)',
            'linear-gradient(rgba(190, 18, 60, 0.28) 1px, transparent 1px)',
            'linear-gradient(90deg, rgba(190, 18, 60, 0.28) 1px, transparent 1px)',
          ].join(', '),
          backgroundSize: [
            `${ECG_MINOR_GRID_PX}px ${ECG_MINOR_GRID_PX}px`,
            `${ECG_MINOR_GRID_PX}px ${ECG_MINOR_GRID_PX}px`,
            `${ECG_MAJOR_GRID_PX}px ${ECG_MAJOR_GRID_PX}px`,
            `${ECG_MAJOR_GRID_PX}px ${ECG_MAJOR_GRID_PX}px`,
          ].join(', '),
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartSamples} margin={{ top: 10, right: 14, bottom: 8, left: 4 }}>
            <XAxis
              dataKey="seconds"
              type="number"
              domain={[0, Math.max(durationSeconds, 1)]}
              tick={{ fill: '#475569', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#fda4af' }}
              tickFormatter={(seconds) => `${Number(seconds).toFixed(1)}s`}
            />
            <YAxis
              width={58}
              tick={{ fill: '#475569', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#fda4af' }}
              domain={[-ADC_DISPLAY_RANGE, ADC_DISPLAY_RANGE]}
              ticks={[-800, -400, 0, 400, 800]}
              tickFormatter={(amplitude) => `${Number(amplitude)}`}
            />
            <ReferenceLine y={0} stroke="#64748b" strokeOpacity={0.75} strokeWidth={1.5} />
            <Tooltip
              cursor={{ stroke: '#be123c', strokeOpacity: 0.35, strokeWidth: 1 }}
              contentStyle={{
                borderRadius: 8,
                borderColor: '#fecdd3',
                boxShadow: '0 12px 30px rgba(15, 23, 42, 0.12)',
              }}
              formatter={(amplitude, _name, props) => {
                const rawAmplitude = Number(props.payload.rawAmplitude);
                return [
                  `${Number(amplitude).toFixed(0)} ADC from baseline (${rawAmplitude.toFixed(0)} raw)`,
                  'Amplitude',
                ];
              }}
              labelFormatter={(seconds) => `${Number(seconds).toFixed(3)} seconds`}
            />
            <Line
              type="linear"
              dataKey="amplitude"
              name="ECG amplitude"
              stroke="#0f172a"
              strokeWidth={1.8}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-rose-100 bg-white px-3 py-2 text-xs text-slate-500">
        <span className="tabular-nums">Y-axis: ADC deviation from centered baseline</span>
        <span className="tabular-nums">Paper reference: 5 small boxes per major box</span>
      </div>
    </div>
  );
};

export default EcgWaveform;
