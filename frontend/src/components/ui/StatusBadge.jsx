import { toTitleCase, cn } from '../../lib/utils';

const statusClassMap = {
  COMPLETED: 'bg-emerald-500/20 text-emerald-300',
  INTERVIEW_IN_PROGRESS: 'bg-cyan-500/20 text-cyan-300',
  ANALYZING_RESUME: 'bg-amber-500/20 text-amber-300',
  ANALYSIS_COMPLETED: 'bg-blue-500/20 text-blue-200',
  FAILED_ANALYSIS: 'bg-red-500/20 text-red-300',
  PENDING: 'bg-slate-500/20 text-slate-300',
};

export function StatusBadge({ status }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-xl px-3 py-1 text-[11px] font-code uppercase tracking-[0.08em]',
        statusClassMap[status] || statusClassMap.PENDING,
      )}
    >
      {toTitleCase(status || 'PENDING')}
    </span>
  );
}
