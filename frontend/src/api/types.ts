// Mirrors backend/app/schemas/portal.py. Keep in sync when the API changes.

export interface OrgRef {
  org_id: string;
  name: string;
}

export interface OrganizationSummary extends OrgRef {
  run_count: number;
  finding_count: number;
  high_severity_count: number;
  last_survey_at: string | null;
  last_site_name: string | null;
}

export interface RunSummary {
  run_id: string;
  site_name: string;
  started_at: string;
  ended_at: string | null;
  status: 'complete' | 'incomplete' | string;
  aircraft_id: string | null;
  finding_count: number;
  counts_by_type: Record<string, number>;
  counts_by_severity: Record<string, number>;
  data_warning_count: number;
  findings_with_warnings: number;
}

export interface GeoJSONGeometry {
  type: string;
  coordinates: unknown;
}

export interface DataWarning {
  code: string;
  message: string | null;
  geometry: GeoJSONGeometry | null;
}

export interface LocalFrameOrigin {
  lat: number;
  lon: number;
  alt_m?: number | null;
  heading_deg?: number | null;
}

export interface RunDetail extends RunSummary {
  organization: OrgRef;
  operator: string | null;
  software_version: string;
  schema_version: string;
  local_frame_origin: LocalFrameOrigin | null;
  flight_path: { type: 'LineString'; coordinates: number[][] } | null;
  data_warnings: DataWarning[];
  ingested_at: string;
}

export interface Measurement {
  value: number;
  unit: string;
}

export interface FindingListItem {
  finding_id: string;
  detected_at: string;
  defect_type: string;
  subtype: string | null;
  severity: 'low' | 'medium' | 'high' | null;
  confidence: number | null;
  detection_source: 'image' | 'lidar' | 'fused' | null;
  lat: number | null;
  lon: number | null;
  gps_accuracy_m: number | null;
  local_x_m: number | null;
  local_y_m: number | null;
  measurements: Record<string, Measurement>;
  warning_codes: string[];
  evidence_count: number;
  thumb_url: string | null;
}

export interface BoundingBox {
  label: string;
  bbox: [number, number, number, number];
  confidence?: number | null;
}

export interface Evidence {
  file: string;
  kind: string;
  caption: string | null;
  captured_at: string | null;
  content_type: string;
  size_bytes: number;
  is_image: boolean;
  width_px: number | null;
  height_px: number | null;
  url: string;
  preview_url: string | null;
  thumb_url: string | null;
  bounding_boxes: BoundingBox[];
}

export interface QualityWarning {
  code: string;
  message?: string | null;
}

export interface FindingDetail extends FindingListItem {
  run_id: string;
  site_name: string;
  organization: OrgRef;
  description: string | null;
  alt_m: number | null;
  quality_warnings: QualityWarning[];
  evidence: Evidence[];
  prev_finding_id: string | null;
  next_finding_id: string | null;
  position_in_run: number;
  findings_in_run: number;
}
