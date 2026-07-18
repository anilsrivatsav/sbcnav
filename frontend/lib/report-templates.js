import { CircleAlert, FileText, Timer, TrainFront, Users, Wallet, Wrench } from "lucide-react";

export const reportTemplates = [
  {
    id: "license-overdue",
    label: "Overdue License Fee",
    description: "Units where license fee is already overdue or needs review.",
    icon: CircleAlert,
    reportTab: "alerts",
    filters: { needsActionOnly: true },
    search: "",
  },
  {
    id: "license-next-30",
    label: "Due In 30 Days",
    description: "Contracts and payments needing attention in the next month.",
    icon: Timer,
    reportTab: "alerts",
    filters: { needsActionOnly: false },
    search: "due_next_30_days",
  },
  {
    id: "unit-quality",
    label: "Unit Data Quality",
    description: "Units missing station or license fee information.",
    icon: Users,
    reportTab: "quality",
    filters: { needsActionOnly: true },
    search: "",
  },
  {
    id: "pending-works",
    label: "Pending Works",
    description: "Open sanctioned works filtered for action review.",
    icon: Wrench,
    reportTab: "works",
    filters: { needsActionOnly: true },
    search: "",
  },
  {
    id: "station-coverage",
    label: "Station Coverage",
    description: "Stations with or without linked units, earnings, and works.",
    icon: TrainFront,
    reportTab: "stations",
    filters: { needsActionOnly: false },
    search: "",
  },
  {
    id: "earnings-review",
    label: "Earnings Review",
    description: "Payment and receipt data grouped for collection review.",
    icon: Wallet,
    reportTab: "earnings",
    filters: { needsActionOnly: false },
    search: "",
  },
];

export function templateFilterState(currentFilters, template) {
  return {
    ...currentFilters,
    ...(template.filters || {}),
  };
}

export function templatePreset(template, filters) {
  return {
    id: template.id,
    name: template.label,
    reportTab: template.reportTab,
    reportFilters: templateFilterState(filters, template),
    icon: FileText,
  };
}
