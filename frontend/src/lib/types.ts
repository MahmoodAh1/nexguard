/** TypeScript mirror of the backend API contracts. */

export type Severity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "new" | "triaged" | "investigating" | "resolved" | "dismissed";
export type ReportConfidence = "low" | "medium" | "high";

export interface Alert {
  id: string;
  session_id: string;
  session_external_id: string;
  dataset: string;
  severity: Severity;
  status: AlertStatus;
  score: number;
  event_count: number;
  created_at: string;
}

export interface FeatureContribution {
  event_id: number;
  template: string | null;
  contribution: number;
}

export interface SequenceEvidence {
  anomaly_score: number;
  confidence: number;
  perplexity: number;
  actual_event: number | null;
  predicted_topk: number[];
  surprising_step_indices: number[];
  suspicious_subsequence: number[];
}

export interface StatisticalEvidence {
  anomaly_score: number;
  important_features: FeatureContribution[];
}

export interface EnsembleEvidence {
  seq_weight: number;
  stat_weight: number;
  seq_score: number;
  stat_score: number;
  final_score: number;
  threshold: number;
  severity: Severity;
}

export interface Provenance {
  session_external_id: string;
  dataset: string;
  event_count: number;
  started_at: string | null;
  ended_at: string | null;
}

export interface Evidence {
  sequence: SequenceEvidence;
  statistical: StatisticalEvidence;
  ensemble: EnsembleEvidence;
  provenance: Provenance;
}

export interface AlertDetail extends Alert {
  evidence: Evidence;
}

export interface MitreHypothesis {
  technique_id: string;
  name: string;
  rationale: string;
  confidence: ReportConfidence;
  is_hypothesis: true;
}

export interface TimelineEntry {
  timestamp: string;
  description: string;
  event_id: number | null;
}

export interface EvidenceRef {
  kind: "event" | "host" | "timestamp" | "component";
  ref: string;
}

export interface IncidentReportPayload {
  summary: string;
  severity: Severity;
  confidence: ReportConfidence;
  timeline: TimelineEntry[];
  affected_components: string[];
  evidence_refs: EvidenceRef[];
  mitre_hypotheses: MitreHypothesis[];
  recommended_investigation_steps: string[];
  recommended_containment_actions: string[];
}

export interface IncidentReport {
  id: string;
  alert_id: string;
  model: string;
  verified: boolean;
  rejected_reasons: string[];
  payload: IncidentReportPayload | null;
  created_at: string;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
  detectors_loaded: boolean;
  llm_provider: string;
  event_bus: string;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_used_mb: number;
  memory_percent: number;
  process_rss_mb: number;
}

export interface AlertCreatedEvent {
  topic: "alert.created";
  event_id: string;
  occurred_at: string;
  alert_id: string;
  session_external_id: string;
  severity: Severity;
  score: number;
}

export type FeedbackLabel = "true_positive" | "false_positive" | "benign" | "unknown";

export interface FeedbackItem {
  id: string;
  alert_id: string;
  analyst_id: string;
  label: FeedbackLabel;
  note: string | null;
  created_at: string;
}

export interface CalibrationSnapshot {
  id: string;
  threshold: number;
  seq_weight: number;
  stat_weight: number;
  feedback_count: number;
  precision_before: number;
  recall_before: number;
  precision_after: number;
  recall_after: number;
  created_at: string;
}

export interface FeedbackSummary {
  total: number;
  counts: Record<string, number>;
  latest_calibration: CalibrationSnapshot | null;
}

export interface LogEventItem {
  event_id: number;
  raw: string;
  line_no: number;
  timestamp: string | null;
}

export interface SessionSummary {
  id: string;
  external_id: string;
  dataset: string;
  event_count: number;
  label: boolean | null;
  created_at: string;
}

export interface SessionDetail extends SessionSummary {
  events: LogEventItem[];
}

export interface TemplateItem {
  event_id: number;
  template: string;
  occurrences: number;
}

export interface ScoreBucket {
  lower: number;
  upper: number;
  count: number;
}

export interface AnalyticsSummary {
  total_alerts: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  score_histogram: ScoreBucket[];
  seq_weight: number;
  stat_weight: number;
  threshold: number;
  detectors_loaded: boolean;
  latest_calibration: CalibrationSnapshot | null;
}

export interface RuntimeConfig {
  seq_weight: number;
  stat_weight: number;
  threshold: number;
  detectors_loaded: boolean;
  llm_provider: string;
  model_name: string;
}

export interface MetricsTick {
  topic: "metrics.tick";
  occurred_at: string;
  cpu_percent: number;
  memory_percent: number;
  process_rss_mb: number;
  active_alerts: number;
}

export interface WsEnvelope {
  topic: string;
  [key: string]: unknown;
}

export const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 3,
  high: 2,
  medium: 1,
  low: 0,
};
