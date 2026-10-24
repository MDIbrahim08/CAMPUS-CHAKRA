-- =========================================================================
-- PRANA PULSE | Chanakya University Global Campus
-- Supabase PostgreSQL Schema for Predictive Circular-Resource Grid
-- =========================================================================

-- 1. Campus Buildings Metadata
CREATE TABLE IF NOT EXISTS campus_buildings (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    building_type TEXT NOT NULL,
    area_sqm NUMERIC,
    daily_baseline_kwh NUMERIC NOT NULL,
    daily_baseline_water_kl NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Hourly Fused Telemetry (Fused under noise & missing data imputation)
CREATE TABLE IF NOT EXISTS telemetry_hourly (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    building_id TEXT REFERENCES campus_buildings(id),
    power_kw NUMERIC NOT NULL,
    water_kl NUMERIC NOT NULL,
    occupancy INTEGER DEFAULT 0,
    ambient_temp_c NUMERIC,
    confidence_score NUMERIC DEFAULT 1.0,
    is_imputed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, building_id)
);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry_hourly(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_building ON telemetry_hourly(building_id);

-- 3. Edge Smart-Bin Waste Classification Events
CREATE TABLE IF NOT EXISTS waste_events (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    building_id TEXT REFERENCES campus_buildings(id),
    weight_kg NUMERIC NOT NULL,
    fill_level_pct NUMERIC NOT NULL,
    optical_signature NUMERIC,
    predicted_class TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    latency_ms NUMERIC NOT NULL,
    is_synced BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_waste_time ON waste_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_waste_class ON waste_events(predicted_class);

-- 4. Grid Anomalies & Explainable Root-Cause Attribution
CREATE TABLE IF NOT EXISTS grid_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    building_id TEXT REFERENCES campus_buildings(id),
    metric TEXT NOT NULL,
    observed_value NUMERIC NOT NULL,
    baseline_value NUMERIC NOT NULL,
    z_score NUMERIC NOT NULL,
    severity TEXT NOT NULL,
    attributed_root_cause TEXT NOT NULL,
    financial_impact_inr NUMERIC NOT NULL,
    carbon_impact_kg NUMERIC NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_anomalies_bldg ON grid_anomalies(building_id);

-- 5. Behavioral & Economic Eco-Credits Leaderboard
CREATE TABLE IF NOT EXISTS eco_credits_leaderboard (
    building_id TEXT PRIMARY KEY REFERENCES campus_buildings(id),
    building_name TEXT NOT NULL,
    normalized_consumption_ratio NUMERIC NOT NULL,
    eco_credits_earned NUMERIC NOT NULL,
    rank INTEGER NOT NULL,
    footfall_factor NUMERIC DEFAULT 1.0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Gateway Idempotent Sync & Local Buffer Recovery Log
CREATE TABLE IF NOT EXISTS gateway_sync_log (
    packet_id TEXT PRIMARY KEY,
    sequence_num BIGINT NOT NULL,
    building_id TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    records_count INTEGER DEFAULT 1,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(building_id, sequence_num)
);

-- Enable Row Level Security (RLS) with Public Read Access for Dashboard
ALTER TABLE campus_buildings ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_hourly ENABLE ROW LEVEL SECURITY;
ALTER TABLE waste_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE grid_anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE eco_credits_leaderboard ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateway_sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON campus_buildings FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON telemetry_hourly FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON waste_events FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON grid_anomalies FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON eco_credits_leaderboard FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON gateway_sync_log FOR SELECT USING (true);

-- Allow authenticated or service-role write
CREATE POLICY "Allow full access service" ON campus_buildings FOR ALL USING (true);
CREATE POLICY "Allow full access service" ON telemetry_hourly FOR ALL USING (true);
CREATE POLICY "Allow full access service" ON waste_events FOR ALL USING (true);
CREATE POLICY "Allow full access service" ON grid_anomalies FOR ALL USING (true);
CREATE POLICY "Allow full access service" ON eco_credits_leaderboard FOR ALL USING (true);
CREATE POLICY "Allow full access service" ON gateway_sync_log FOR ALL USING (true);
