const statusConfig = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Pending' },
  accepted: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Accepted' },
  rejected: { bg: 'bg-red-100', text: 'text-red-700', label: 'Rejected' },
  in_progress: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'In Progress' },
  done: { bg: 'bg-green-100', text: 'text-green-700', label: 'Done' },
  overdue: { bg: 'bg-red-100', text: 'text-red-700', label: 'Overdue' },
};

export default function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.pending;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
}
