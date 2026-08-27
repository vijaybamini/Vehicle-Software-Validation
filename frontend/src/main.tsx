import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, BarChart3, Battery, FileSearch, History, RefreshCw } from 'lucide-react';
import './styles.css';

type VehicleStatus = {
  state: string;
  gear: string;
  speed_deci_kph: number;
  torque_nm: number;
  soc_percent: number;
  battery_temperature_celsius: number;
  motor_temperature_celsius: number;
  fault: string;
};

type SchedulerResult = {
  strategy: string;
  time_to_first_defect: number | null;
  defects_within_budget: number;
  total_duration: number;
};

type TestCase = {
  name: string;
  estimated_duration_seconds: number;
  historical_failure_rate: number;
  priority: number;
};

type RunSummary = {
  run_id: string;
  started_at: string;
  total: number;
  passed: number;
  failed: number;
};

type DiagnosticRecord = {
  event: string;
  payload: {
    test_name?: string;
    expected?: string;
    actual?: string;
    fault?: string;
    duration_seconds?: number;
  };
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function App() {
  const [status, setStatus] = useState<VehicleStatus | null>(null);
  const [tests, setTests] = useState<TestCase[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerResult[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticRecord[]>([]);
  const [error, setError] = useState('');

  const refresh = async () => {
    try {
      const [vehicleStatus, testCatalog, schedulerComparison, runHistory, diagnosticRecords] = await Promise.all([
        getJson<VehicleStatus>('/vehicle/status'),
        getJson<TestCase[]>('/tests'),
        getJson<SchedulerResult[]>('/scheduler/comparison'),
        getJson<RunSummary[]>('/runs'),
        getJson<DiagnosticRecord[]>('/diagnostics'),
      ]);
      setStatus(vehicleStatus);
      setTests(testCatalog);
      setScheduler(schedulerComparison);
      setRuns(runHistory);
      setDiagnostics(diagnosticRecords);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load dashboard data');
    }
  };

  useEffect(() => {
    refresh();
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${window.location.host}/api/ws/status`);
    socket.onmessage = (event) => {
      setStatus(JSON.parse(event.data));
    };
    socket.onerror = () => {
      socket.close();
    };
    return () => socket.close();
  }, []);

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">Validation Console</p>
          <h1>Vehicle Software Validation</h1>
        </div>
        <button className="iconButton" onClick={refresh} title="Refresh dashboard">
          <RefreshCw size={18} />
          Refresh
        </button>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="grid">
        <Panel title="Vehicle Status" icon={<Battery size={18} />}>
          {status ? (
            <div className="metrics">
              <Metric label="State" value={status.state} />
              <Metric label="Gear" value={status.gear} />
              <Metric label="Speed" value={`${(status.speed_deci_kph / 10).toFixed(1)} kph`} />
              <Metric label="Torque" value={`${status.torque_nm} Nm`} />
              <Metric label="SOC" value={`${status.soc_percent}%`} />
              <Metric label="Fault" value={status.fault} />
            </div>
          ) : (
            <p className="muted">Waiting for backend data.</p>
          )}
        </Panel>

        <Panel title="Scheduler Comparison" icon={<BarChart3 size={18} />}>
          <table>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>First Defect</th>
                <th>Defects</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {scheduler.map((item) => (
                <tr key={item.strategy}>
                  <td>{item.strategy}</td>
                  <td>{item.time_to_first_defect ?? 'n/a'}</td>
                  <td>{item.defects_within_budget}</td>
                  <td>{item.total_duration.toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Test Catalog" icon={<Activity size={18} />}>
          <table>
            <thead>
              <tr>
                <th>Test</th>
                <th>Duration</th>
                <th>Failure Rate</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((test) => (
                <tr key={test.name}>
                  <td>{test.name}</td>
                  <td>{test.estimated_duration_seconds.toFixed(1)}s</td>
                  <td>{Math.round(test.historical_failure_rate * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Run History" icon={<History size={18} />}>
          {runs.length ? (
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Passed</th>
                  <th>Failed</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.run_id}</td>
                    <td>{run.passed}</td>
                    <td>{run.failed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No saved runs yet.</p>
          )}
        </Panel>

        <Panel title="Diagnostics" icon={<FileSearch size={18} />}>
          {diagnostics.length ? (
            <div className="diagnostics">
              {diagnostics.map((record, index) => (
                <article className="diagnostic" key={`${record.event}-${index}`}>
                  <div>
                    <strong>{record.payload.test_name ?? record.event}</strong>
                    <span>{record.payload.fault ?? 'none'}</span>
                  </div>
                  <p>{record.payload.expected ?? 'No expectation recorded.'}</p>
                  <p>{record.payload.actual ?? 'No actual result recorded.'}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted">No diagnostics yet.</p>
          )}
        </Panel>
      </section>
    </main>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>
        {icon}
        {title}
      </h2>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
