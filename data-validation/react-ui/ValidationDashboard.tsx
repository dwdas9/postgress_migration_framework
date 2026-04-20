/**
 * PostgreSQL Migration Validation Dashboard
 * React Component - Main Application
 * 
 * Purpose: Real-time monitoring and validation of PostgreSQL migration
 * to Azure PostgreSQL v14
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// ============================================================================
// Component: Validation Dashboard
// ============================================================================

interface ValidationResult {
  id: string;
  table_name: string;
  timestamp_utc: string;
  phase: string;
  validations: Validation[];
  overall_status: 'PASS' | 'FAIL' | 'ERROR';
}

interface Validation {
  validation_id: string;
  validation_name: string;
  status: 'PASS' | 'FAIL' | 'ERROR' | 'SKIP';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'INFO';
  source_count?: number;
  target_count?: number;
  error?: string;
}

interface MigrationMetrics {
  pass_rate_percent: number;
  tables_passed: number;
  tables_failed: number;
  tables_total: number;
  data_accuracy_percent: number;
  replication_lag_seconds: number;
  total_rows_validated: number;
}

// ============================================================================
// Main App Component
// ============================================================================

const ValidationDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<MigrationMetrics>({
    pass_rate_percent: 0,
    tables_passed: 0,
    tables_failed: 0,
    tables_total: 0,
    data_accuracy_percent: 0,
    replication_lag_seconds: 0,
    total_rows_validated: 0
  });

  const [validationResults, setValidationResults] = useState<ValidationResult[]>([]);
  const [selectedTable, setSelectedTable] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(5000); // 5 seconds

  // Fetch metrics from API
  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/migration/metrics');
      setMetrics(response.data);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch validation results
  const fetchValidationResults = async () => {
    try {
      const response = await axios.get('/api/migration/validations?limit=50');
      setValidationResults(response.data.results);
    } catch (error) {
      console.error('Failed to fetch validation results:', error);
    }
  };

  // Auto-refresh data
  useEffect(() => {
    fetchMetrics();
    fetchValidationResults();

    const interval = setInterval(() => {
      fetchMetrics();
      fetchValidationResults();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  // Status badge renderer
  const StatusBadge: React.FC<{ status: string; severity?: string }> = ({ status, severity }) => {
    const statusColors: Record<string, string> = {
      'PASS': '#28a745',
      'FAIL': '#dc3545',
      'ERROR': '#ff6b6b',
      'SKIP': '#6c757d',
      'WARNING': '#ffc107'
    };

    return (
      <span
        style={{
          display: 'inline-block',
          padding: '0.5rem 0.75rem',
          borderRadius: '0.25rem',
          backgroundColor: statusColors[status] || '#6c757d',
          color: 'white',
          fontWeight: 'bold',
          fontSize: '0.875rem'
        }}
      >
        {status}
      </span>
    );
  };

  // Metrics card component
  const MetricCard: React.FC<{ title: string; value: string | number; unit?: string; color?: string }> = 
    ({ title, value, unit = '', color = '#007bff' }) => (
    <div style={{
      backgroundColor: 'white',
      border: `2px solid ${color}`,
      borderRadius: '0.5rem',
      padding: '1.5rem',
      marginBottom: '1rem',
      boxShadow: '0 0.125rem 0.25rem rgba(0,0,0,0.075)'
    }}>
      <h5 style={{ margin: '0 0 0.5rem 0', color: '#6c757d', fontSize: '0.875rem' }}>
        {title}
      </h5>
      <p style={{ margin: 0, fontSize: '2rem', fontWeight: 'bold', color }}>
        {value} <span style={{ fontSize: '1rem', color: '#6c757d' }}>{unit}</span>
      </p>
    </div>
  );

  // Render main dashboard
  return (
    <div style={{ fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif' }}>
      {/* Header */}
      <header style={{
        backgroundColor: '#1a237e',
        color: 'white',
        padding: '2rem',
        marginBottom: '2rem',
        borderBottom: '4px solid #0066cc'
      }}>
        <h1 style={{ margin: '0 0 0.5rem 0' }}>
          PostgreSQL Migration Validation Dashboard
        </h1>
        <p style={{ margin: 0, opacity: 0.8 }}>
          Real-time monitoring: On-Premise v11 → Azure PostgreSQL v14
        </p>
      </header>

      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '0 1rem' }}>
        {/* Control Panel */}
        <div style={{
          display: 'flex',
          gap: '1rem',
          marginBottom: '2rem',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <label style={{ marginRight: '0.5rem', fontWeight: 'bold' }}>
              Auto-refresh:
            </label>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
              style={{
                padding: '0.5rem',
                borderRadius: '0.25rem',
                border: '1px solid #ced4da'
              }}
            >
              <option value={5000}>5 seconds</option>
              <option value={10000}>10 seconds</option>
              <option value={30000}>30 seconds</option>
              <option value={60000}>1 minute</option>
            </select>
          </div>
          <button
            onClick={() => {
              fetchMetrics();
              fetchValidationResults();
            }}
            disabled={loading}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '0.25rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>

        {/* Metrics Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem'
        }}>
          <MetricCard
            title="Data Accuracy"
            value={metrics.data_accuracy_percent.toFixed(2)}
            unit="%"
            color={metrics.data_accuracy_percent >= 99.9 ? '#28a745' : '#ffc107'}
          />
          <MetricCard
            title="Pass Rate"
            value={metrics.pass_rate_percent.toFixed(2)}
            unit="%"
            color={metrics.pass_rate_percent === 100 ? '#28a745' : '#dc3545'}
          />
          <MetricCard
            title="Tables Passed"
            value={metrics.tables_passed}
            unit={`/ ${metrics.tables_total}`}
            color="#28a745"
          />
          <MetricCard
            title="Replication Lag"
            value={metrics.replication_lag_seconds}
            unit="sec"
            color={metrics.replication_lag_seconds < 30 ? '#28a745' : '#ffc107'}
          />
          <MetricCard
            title="Rows Validated"
            value={(metrics.total_rows_validated / 1000000).toFixed(1)}
            unit="M"
            color="#007bff"
          />
        </div>

        {/* Validation Results Table */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          boxShadow: '0 0.125rem 0.25rem rgba(0,0,0,0.075)',
          marginBottom: '2rem'
        }}>
          <h2 style={{ marginTop: 0, marginBottom: '1rem' }}>Recent Validation Results</h2>
          
          <div style={{
            overflowX: 'auto',
            marginBottom: '1rem'
          }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.875rem'
            }}>
              <thead>
                <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                  <th style={{ padding: '0.75rem', textAlign: 'left' }}>Table Name</th>
                  <th style={{ padding: '0.75rem', textAlign: 'center' }}>Status</th>
                  <th style={{ padding: '0.75rem', textAlign: 'right' }}>Validations</th>
                  <th style={{ padding: '0.75rem', textAlign: 'center' }}>Phase</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left' }}>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {validationResults.map((result, index) => (
                  <tr
                    key={index}
                    style={{
                      borderBottom: '1px solid #dee2e6',
                      cursor: 'pointer',
                      backgroundColor: selectedTable?.id === result.id ? '#e7f3ff' : 'transparent',
                      transition: 'background-color 0.2s'
                    }}
                    onClick={() => setSelectedTable(result)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#f8f9fa';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = selectedTable?.id === result.id ? '#e7f3ff' : 'transparent';
                    }}
                  >
                    <td style={{ padding: '0.75rem', fontWeight: 'bold' }}>{result.table_name}</td>
                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                      <StatusBadge status={result.overall_status} />
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                      {result.validations.length} checks
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'center', fontSize: '0.75rem' }}>
                      {result.phase}
                    </td>
                    <td style={{ padding: '0.75rem', fontSize: '0.75rem', color: '#6c757d' }}>
                      {new Date(result.timestamp_utc).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detailed Validation View */}
        {selectedTable && (
          <div style={{
            backgroundColor: 'white',
            borderRadius: '0.5rem',
            padding: '1.5rem',
            boxShadow: '0 0.125rem 0.25rem rgba(0,0,0,0.075)',
            marginBottom: '2rem'
          }}>
            <h2 style={{ marginTop: 0, marginBottom: '1rem' }}>
              Validation Details: {selectedTable.table_name}
              <button
                onClick={() => setSelectedTable(null)}
                style={{
                  float: 'right',
                  padding: '0.25rem 0.5rem',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.25rem',
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </h2>

            {selectedTable.validations.map((validation, index) => (
              <div
                key={index}
                style={{
                  marginBottom: '1rem',
                  padding: '1rem',
                  border: `1px solid ${
                    validation.status === 'PASS' ? '#d4edda' :
                    validation.status === 'FAIL' ? '#f8d7da' : '#e2e3e5'
                  }`,
                  backgroundColor: {
                    'PASS': '#d4edda',
                    'FAIL': '#f8d7da',
                    'ERROR': '#f5c6cb',
                    'SKIP': '#e2e3e5'
                  }[validation.status] || '#fff3cd',
                  borderRadius: '0.25rem'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h5 style={{ margin: 0 }}>{validation.validation_name}</h5>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <StatusBadge status={validation.status} severity={validation.severity} />
                    <span style={{
                      padding: '0.25rem 0.5rem',
                      backgroundColor: {
                        'CRITICAL': '#dc3545',
                        'HIGH': '#fd7e14',
                        'MEDIUM': '#ffc107',
                        'INFO': '#17a2b8'
                      }[validation.severity] || '#6c757d',
                      color: 'white',
                      borderRadius: '0.25rem',
                      fontSize: '0.75rem',
                      fontWeight: 'bold'
                    }}>
                      {validation.severity}
                    </span>
                  </div>
                </div>
                
                {validation.source_count !== undefined && (
                  <div style={{ fontSize: '0.875rem', color: '#495057' }}>
                    <p style={{ margin: '0.25rem 0' }}>
                      Source: <strong>{validation.source_count.toLocaleString()}</strong> rows
                    </p>
                    <p style={{ margin: '0.25rem 0' }}>
                      Target: <strong>{validation.target_count?.toLocaleString()}</strong> rows
                    </p>
                    <p style={{ margin: '0.25rem 0' }}>
                      Difference: <strong>{validation.target_count ? validation.target_count - (validation.source_count || 0) : 0}</strong>
                    </p>
                  </div>
                )}
                
                {validation.error && (
                  <div style={{ fontSize: '0.875rem', color: '#721c24', marginTop: '0.5rem' }}>
                    Error: {validation.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer style={{
        backgroundColor: '#f8f9fa',
        padding: '1.5rem',
        marginTop: '2rem',
        borderTop: '1px solid #dee2e6',
        textAlign: 'center',
        color: '#6c757d',
        fontSize: '0.875rem'
      }}>
        <p style={{ margin: 0 }}>
          PostgreSQL Migration Validation Framework v2.0 | 
          Last Updated: {new Date().toLocaleString()} UTC
        </p>
      </footer>
    </div>
  );
};

export default ValidationDashboard;
