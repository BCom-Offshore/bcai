-- BCom Offshore Database Schema
-- PostgreSQL v18
-- Handles customer networks, sites, links, devices, performance metrics, and KPI data

-- ==================== CORE ENTITIES ====================

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER UNIQUE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_customer_id CHECK (customer_id > 0)
);

CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON customers(customer_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(customer_name);

-- Networks
CREATE TABLE IF NOT EXISTS networks (
    id SERIAL PRIMARY KEY,
    network_id INTEGER UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL,
    network_name VARCHAR(255) NOT NULL,
    network_type VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_network_id CHECK (network_id > 0),
    CONSTRAINT fk_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_networks_network_id ON networks(network_id);
CREATE INDEX IF NOT EXISTS idx_networks_customer_id ON networks(customer_id);
CREATE INDEX IF NOT EXISTS idx_networks_name ON networks(network_name);

-- Sites
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    site_id INTEGER UNIQUE NOT NULL,
    site_name VARCHAR(255) NOT NULL,
    site_type VARCHAR(50),
    country VARCHAR(100),
    city VARCHAR(100),
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_site_id CHECK (site_id > 0)
);

CREATE INDEX IF NOT EXISTS idx_sites_site_id ON sites(site_id);
CREATE INDEX IF NOT EXISTS idx_sites_name ON sites(site_name);
CREATE INDEX IF NOT EXISTS idx_sites_location ON sites(country, city);

-- Links (can belong to multiple sites and networks)
CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    link_id INTEGER UNIQUE NOT NULL,
    site_id INTEGER NOT NULL,
    network_id INTEGER NOT NULL,
    link_name VARCHAR(255) NOT NULL,
    link_type VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_link_id CHECK (link_id > 0),
    CONSTRAINT fk_site FOREIGN KEY (site_id) REFERENCES sites(site_id),
    CONSTRAINT fk_network FOREIGN KEY (network_id) REFERENCES networks(network_id)
);

CREATE INDEX IF NOT EXISTS idx_links_link_id ON links(link_id);
CREATE INDEX IF NOT EXISTS idx_links_site_id ON links(site_id);
CREATE INDEX IF NOT EXISTS idx_links_network_id ON links(network_id);
CREATE INDEX IF NOT EXISTS idx_links_name ON links(link_name);

-- Devices (Antennas/Sensors on Links)
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id INTEGER UNIQUE NOT NULL,
    link_id INTEGER NOT NULL,
    device_api VARCHAR(50),
    device_api_id INTEGER,
    device_source VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_device_id CHECK (device_id > 0),
    CONSTRAINT fk_link FOREIGN KEY (link_id) REFERENCES links(link_id)
);

CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_link_id ON devices(link_id);
CREATE INDEX IF NOT EXISTS idx_devices_api ON devices(device_api);

-- ==================== PERFORMANCE METRICS ====================

-- Site Grades (Daily link performance grades 1-10)
CREATE TABLE IF NOT EXISTS site_grades (
    id BIGINT PRIMARY KEY,
    link_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    availability FLOAT,
    ib_degradation FLOAT,
    ob_degradation FLOAT,
    ib_instability FLOAT,
    ob_instability FLOAT,
    up_time FLOAT,
    status BOOLEAN,
    performance FLOAT,
    congestion FLOAT,
    latency FLOAT,
    grade FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_grade_range CHECK (grade >= 1 AND grade <= 10),
    CONSTRAINT ck_availability_range CHECK (availability >= 0 AND availability <= 100),
    CONSTRAINT fk_link_grades FOREIGN KEY (link_id) REFERENCES links(link_id)
);

CREATE INDEX IF NOT EXISTS idx_site_grades_link_id ON site_grades(link_id);
CREATE INDEX IF NOT EXISTS idx_site_grades_timestamp ON site_grades(timestamp);
CREATE INDEX IF NOT EXISTS idx_site_grades_link_timestamp ON site_grades(link_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_site_grades_grade ON site_grades(grade);
CREATE INDEX IF NOT EXISTS idx_site_grades_status ON site_grades(status);

-- ==================== KPI DATA ====================

-- Device KPI Data (Time-series metrics from devices)
-- Supports both numeric (avg, min, max, std) and categorical (error counts) metrics
CREATE TABLE IF NOT EXISTS kpi_data (
    id BIGSERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL,
    api_connection_channel_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metric_type VARCHAR(20) DEFAULT 'numeric', -- 'numeric' or 'categorical'
    max_value FLOAT,
    min_value FLOAT,
    avg_value FLOAT,
    std_deviation FLOAT,
    total_raw_entries INTEGER,
    metric_data JSONB, -- For categorical data (error counts, status distributions)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_metric_type CHECK (metric_type IN ('numeric', 'categorical')),
    CONSTRAINT fk_device_kpi FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_kpi_device_id ON kpi_data(device_id);
CREATE INDEX IF NOT EXISTS idx_kpi_channel_id ON kpi_data(api_connection_channel_id);
CREATE INDEX IF NOT EXISTS idx_kpi_timestamp ON kpi_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_device_timestamp ON kpi_data(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_metric_type ON kpi_data(metric_type);

-- Partitioning for large KPI tables (optional, if data grows very large)
-- ALTER TABLE kpi_data PARTITION BY RANGE (YEAR(timestamp));

-- ==================== ANOMALY DETECTION ====================

-- Detected Anomalies (Results from ML model)
CREATE TABLE IF NOT EXISTS detected_anomalies (
    id BIGSERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    anomaly_type VARCHAR(100), -- 'signal_degradation', 'error_spike', 'instability', etc.
    severity FLOAT, -- 0-1, higher = more severe
    confidence FLOAT, -- 0-1, higher = more certain
    description TEXT,
    model_version VARCHAR(50),
    raw_data JSONB, -- Store relevant KPI data that triggered anomaly
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100), -- Model name or service name
    CONSTRAINT ck_severity CHECK (severity >= 0 AND severity <= 1),
    CONSTRAINT ck_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT fk_link_anomaly FOREIGN KEY (link_id) REFERENCES links(link_id),
    CONSTRAINT fk_device_anomaly FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_anomalies_link_id ON detected_anomalies(link_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_device_id ON detected_anomalies(device_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON detected_anomalies(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON detected_anomalies(severity DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON detected_anomalies(anomaly_type);

-- ==================== RECOMMENDATIONS ====================

-- Generated Recommendations (from ML model)
CREATE TABLE IF NOT EXISTS recommendations (
    id BIGSERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL,
    device_id INTEGER,
    recommendation_type VARCHAR(100), -- 'maintenance', 'upgrade', 'investigation', etc.
    priority INTEGER DEFAULT 3, -- 1=critical, 2=high, 3=medium, 4=low
    description TEXT NOT NULL,
    action_items TEXT, -- JSON array of recommended actions
    model_version VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'acknowledged', 'resolved', 'dismissed'
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    CONSTRAINT ck_priority CHECK (priority >= 1 AND priority <= 4),
    CONSTRAINT ck_status CHECK (status IN ('pending', 'acknowledged', 'resolved', 'dismissed')),
    CONSTRAINT fk_link_rec FOREIGN KEY (link_id) REFERENCES links(link_id),
    CONSTRAINT fk_device_rec FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_link_id ON recommendations(link_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_device_id ON recommendations(device_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_priority ON recommendations(priority);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_created ON recommendations(created_at DESC);

-- ==================== MODEL METRICS ====================

-- Model Training Metrics (for tracking ML model performance)
CREATE TABLE IF NOT EXISTS model_metrics (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL, -- 'accuracy', 'precision', 'recall', 'f1', 'auc', etc.
    metric_value FLOAT NOT NULL,
    training_date TIMESTAMP,
    test_set_size INTEGER,
    true_positives INTEGER,
    true_negatives INTEGER,
    false_positives INTEGER,
    false_negatives INTEGER,
    metadata JSONB, -- Additional model info
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_metric_value CHECK (metric_value >= 0 AND metric_value <= 1)
);

CREATE INDEX IF NOT EXISTS idx_model_metrics_name ON model_metrics(model_name, model_version);
CREATE INDEX IF NOT EXISTS idx_model_metrics_date ON model_metrics(training_date DESC);

-- ==================== SYSTEM TABLES ====================

-- Data Processing Logs (for tracking data loads and errors)
CREATE TABLE IF NOT EXISTS data_processing_logs (
    id BIGSERIAL PRIMARY KEY,
    process_type VARCHAR(100), -- 'entity_load', 'grade_load', 'kpi_load', etc.
    status VARCHAR(50), -- 'success', 'error', 'warning'
    record_count INTEGER,
    error_message TEXT,
    details JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_process_type ON data_processing_logs(process_type);
CREATE INDEX IF NOT EXISTS idx_logs_status ON data_processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_logs_created ON data_processing_logs(created_at DESC);

-- ==================== SUMMARY VIEWS ====================

-- Network Performance Summary (materialized view for dashboards)
CREATE MATERIALIZED VIEW IF NOT EXISTS network_performance_summary AS
SELECT 
    n.network_id,
    n.network_name,
    c.customer_id,
    c.customer_name,
    COUNT(DISTINCT s.site_id) as site_count,
    COUNT(DISTINCT l.link_id) as link_count,
    COUNT(DISTINCT d.device_id) as device_count,
    COUNT(DISTINCT sg.id) as grade_record_count,
    ROUND(AVG(sg.grade)::numeric, 2) as avg_grade,
    ROUND(MIN(sg.grade)::numeric, 2) as min_grade,
    ROUND(MAX(sg.grade)::numeric, 2) as max_grade,
    ROUND(AVG(sg.availability)::numeric, 2) as avg_availability,
    MAX(sg.timestamp) as latest_update,
    NOW() as view_updated_at
FROM networks n
    LEFT JOIN customers c ON n.customer_id = c.customer_id
    LEFT JOIN sites s ON n.network_id = s.id
    LEFT JOIN links l ON s.id = l.site_id
    LEFT JOIN devices d ON l.id = d.link_id
    LEFT JOIN site_grades sg ON l.link_id = sg.link_id
GROUP BY n.network_id, n.network_name, c.customer_id, c.customer_name;

CREATE INDEX IF NOT EXISTS idx_network_perf_network ON network_performance_summary(network_id);
CREATE INDEX IF NOT EXISTS idx_network_perf_customer ON network_performance_summary(customer_id);

-- Link Health Status View
CREATE MATERIALIZED VIEW IF NOT EXISTS link_health_status AS
SELECT 
    l.link_id,
    l.link_name,
    l.site_id,
    l.network_id,
    COUNT(DISTINCT d.device_id) as device_count,
    COUNT(DISTINCT kpi.device_id) as devices_with_kpi,
    COUNT(DISTINCT sg.id) as grade_count,
    ROUND(AVG(sg.grade)::numeric, 2) as avg_grade,
    MAX(sg.timestamp) as latest_grade_timestamp,
    sg_latest.grade as latest_grade,
    sg_latest.status as latest_status,
    sg_latest.availability as latest_availability,
    COUNT(DISTINCT CASE WHEN sg.grade < 7 THEN sg.id END) as degraded_grades_count,
    NOW() as view_updated_at
FROM links l
    LEFT JOIN devices d ON l.id = d.link_id
    LEFT JOIN kpi_data kpi ON d.device_id = kpi.device_id
    LEFT JOIN site_grades sg ON l.link_id = sg.link_id
    LEFT JOIN LATERAL (
        SELECT * FROM site_grades 
        WHERE link_id = l.link_id 
        ORDER BY timestamp DESC LIMIT 1
    ) sg_latest ON TRUE
GROUP BY l.link_id, l.link_name, l.site_id, l.network_id, 
         sg_latest.grade, sg_latest.status, sg_latest.availability;

CREATE INDEX IF NOT EXISTS idx_link_health_link ON link_health_status(link_id);
CREATE INDEX IF NOT EXISTS idx_link_health_grade ON link_health_status(latest_grade);

-- ==================== INITIALIZATION ====================

-- Insert sample customer if not exists
INSERT INTO customers (customer_id, customer_name)
VALUES (4, 'Orange MALI')
ON CONFLICT (customer_id) DO NOTHING;

-- Log successful schema creation
INSERT INTO data_processing_logs (process_type, status, record_count, details, started_at, completed_at)
VALUES (
    'schema_creation',
    'success',
    NULL,
    jsonb_build_object(
        'tables_created', 15,
        'views_created', 2,
        'indices_created', 30
    ),
    NOW(),
    NOW()
);

COMMIT;
