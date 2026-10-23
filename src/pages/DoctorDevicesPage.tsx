import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Edit3, MonitorDot, Power, Save, Unplug } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuthStore } from '../stores/authStore';
import {
  getDeviceManagementData,
  retireDevice,
  saveDeviceAssignment,
} from '../services/deviceManagement';
import type {
  DeviceAssignmentStatus,
  DoctorPatientOption,
  ManagedDevice,
  SaveDeviceAssignmentInput,
} from '../types';

const emptyForm: SaveDeviceAssignmentInput = {
  deviceId: '',
  displayName: '',
  patientId: null,
  status: 'active',
};

const formatDate = (value: string | null): string => {
  if (!value) return 'No check-in yet';
  return new Date(value).toLocaleString();
};

const DoctorDevicesPage: React.FC = () => {
  const { user } = useAuthStore();
  const [patients, setPatients] = useState<DoctorPatientOption[]>([]);
  const [devices, setDevices] = useState<ManagedDevice[]>([]);
  const [form, setForm] = useState<SaveDeviceAssignmentInput>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const selectedDevice = useMemo(
    () => devices.find((device) => device.id === form.id) ?? null,
    [devices, form.id]
  );

  const loadData = React.useCallback(async () => {
    if (!user?.id) return;
    setLoading(true);
    setError('');
    try {
      const data = await getDeviceManagementData(user.id);
      setPatients(data.patients);
      setDevices(data.devices);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not load devices.');
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const resetForm = () => {
    setForm(emptyForm);
    setSuccess('');
    setError('');
  };

  const editDevice = (device: ManagedDevice) => {
    setForm({
      id: device.id,
      deviceId: device.deviceId,
      displayName: device.displayName,
      patientId: device.patientId,
      status: device.status,
    });
    setSuccess('');
    setError('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user?.id) return;
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await saveDeviceAssignment(user.id, form);
      setSuccess(form.id ? 'Device assignment updated.' : 'Device assignment saved.');
      setForm(emptyForm);
      await loadData();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not save device.');
    } finally {
      setSaving(false);
    }
  };

  const handleRetire = async (device: ManagedDevice) => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await retireDevice(device.id);
      setSuccess(`${device.displayName} retired.`);
      if (form.id === device.id) setForm(emptyForm);
      await loadData();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not retire device.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-5">
          <div className="h-44 rounded-[32px] bg-emerald-100/70" />
          <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="h-96 rounded-[28px] bg-emerald-100/70" />
            <div className="h-96 rounded-[28px] bg-emerald-100/70" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <Link
        to="/doctor"
        className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-sm font-semibold text-emerald-800 transition-colors hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to doctor dashboard
      </Link>

      <section className="mt-4 rounded-[32px] bg-[#08251a] px-6 py-8 text-white sm:px-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
              Device management
            </p>
            <h1 className="mt-4 font-sora text-3xl font-semibold sm:text-4xl">
              Assign ECG devices to patients
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-emerald-50/80">
              Rename devices, connect them to assigned patients, check last contact, and retire
              hardware that should no longer feed monitoring data.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/10 p-4">
            <MonitorDot className="h-8 w-8 text-emerald-100" />
          </div>
        </div>
      </section>

      {error ? (
        <div className="mt-5 rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="mt-5 rounded-[24px] border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-800">
          {success}
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[0.78fr_1.22fr]">
        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
                {selectedDevice ? 'Edit device' : 'New device'}
              </p>
              <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                Device assignment
              </h2>
            </div>
            {selectedDevice ? (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-full border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
              >
                Clear
              </button>
            ) : null}
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <Field label="Device ID">
              <input
                value={form.deviceId}
                onChange={(event) => setForm((current) => ({ ...current, deviceId: event.target.value }))}
                placeholder="esp32-ad8232-a1b2"
                disabled={!!form.id}
                className="min-h-11 w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
                required
              />
            </Field>

            <Field label="Display name">
              <input
                value={form.displayName}
                onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                placeholder="Mohamed Ali ECG device"
                className="min-h-11 w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                required
              />
            </Field>

            <Field label="Assigned patient">
              <select
                value={form.patientId ?? ''}
                onChange={(event) =>
                  setForm((current) => ({ ...current, patientId: event.target.value || null }))
                }
                className="min-h-11 w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="">Unassigned</option>
                {patients.map((patient) => (
                  <option key={patient.patientId} value={patient.patientId}>
                    {patient.patientName} - {patient.email}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Status">
              <select
                value={form.status}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    status: event.target.value as DeviceAssignmentStatus,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="retired">Retired</option>
              </select>
            </Field>

            <Button type="submit" className="w-full" disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? 'Saving...' : form.id ? 'Update device' : 'Save device'}
            </Button>
          </form>
        </Card>

        <Card>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
                Device registry
              </p>
              <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                Assigned ECG hardware
              </h2>
            </div>
            <p className="text-sm text-slate-500">{devices.length} devices visible</p>
          </div>

          {devices.length === 0 ? (
            <div className="mt-6 rounded-[24px] border border-dashed border-emerald-200 bg-emerald-50/50 px-5 py-8 text-center">
              <MonitorDot className="mx-auto h-8 w-8 text-emerald-700" />
              <h3 className="mt-4 font-sora text-xl font-semibold text-slate-950">
                No devices assigned yet
              </h3>
              <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-slate-600">
                Add the ESP32 device ID, give it a patient-readable name, and assign it to one of
                your active care-team patients.
              </p>
            </div>
          ) : (
            <div className="mt-6 space-y-3">
              {devices.map((device) => (
                <DeviceRow
                  key={device.id}
                  device={device}
                  onEdit={() => editDevice(device)}
                  onRetire={() => void handleRetire(device)}
                  saving={saving}
                />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <label className="block text-sm font-semibold text-slate-700">
    {label}
    <div className="mt-2">{children}</div>
  </label>
);

const DeviceRow = ({
  device,
  onEdit,
  onRetire,
  saving,
}: {
  device: ManagedDevice;
  onEdit: () => void;
  onRetire: () => void;
  saving: boolean;
}) => (
  <article className="rounded-[24px] border border-slate-100 bg-white px-4 py-4 shadow-sm">
    <div className="grid gap-4 lg:grid-cols-[1fr_0.9fr_0.7fr] lg:items-center">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-sora text-lg font-semibold text-slate-950">{device.displayName}</h3>
          <span
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${
              device.connected
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-slate-200 bg-slate-50 text-slate-600'
            }`}
          >
            {device.connected ? 'Online' : 'Offline'}
          </span>
        </div>
        <p className="mt-1 font-mono text-xs text-slate-500">{device.deviceId}</p>
        <p className="mt-2 text-sm text-slate-600">
          Patient: <span className="font-semibold text-slate-900">{device.patientName ?? 'Unassigned'}</span>
        </p>
      </div>

      <div className="grid gap-2 text-sm text-slate-600">
        <p>
          Status: <span className="font-semibold capitalize text-slate-900">{device.status}</span>
        </p>
        <p>Last contact: {formatDate(device.lastSeenAt)}</p>
        <p>Updated: {formatDate(device.updatedAt)}</p>
      </div>

      <div className="flex flex-wrap gap-2 lg:justify-end">
        <button
          type="button"
          onClick={onEdit}
          className="inline-flex min-h-11 items-center gap-2 rounded-full border border-emerald-200 px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-50"
        >
          <Edit3 className="h-4 w-4" />
          Edit
        </button>
        <button
          type="button"
          onClick={onRetire}
          disabled={saving || device.status === 'retired'}
          className="inline-flex min-h-11 items-center gap-2 rounded-full border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {device.status === 'retired' ? <Unplug className="h-4 w-4" /> : <Power className="h-4 w-4" />}
          Retire
        </button>
      </div>
    </div>
  </article>
);

export default DoctorDevicesPage;
