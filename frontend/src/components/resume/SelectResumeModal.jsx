import { useEffect, useState } from 'react';
import { FileText, Upload, X } from 'lucide-react';

import { getResumes, uploadResume } from '../../lib/api/resumeApi';
import { Button } from '../ui/Button';
import { formatDateTime } from '../../lib/utils';

export function SelectResumeModal({ open, onClose, onConfirm }) {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!open) return;

    const loadResumes = async () => {
      setLoading(true);
      setError('');

      try {
        const data = await getResumes();
        setResumes(data);
        if (data.length > 0) {
          setSelectedResumeId(String(data[0].id));
        }
      } catch (err) {
        setError(err?.response?.data?.detail || 'Failed to load resumes.');
      } finally {
        setLoading(false);
      }
    };

    loadResumes();
  }, [open]);

  const onUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError('');

    try {
      const created = await uploadResume(file);
      const next = [created, ...resumes];
      setResumes(next);
      setSelectedResumeId(String(created.id));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Resume upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirm = () => {
    if (!selectedResumeId) return;
    onConfirm(selectedResumeId);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 px-4">
      <div className="glass-card w-full max-w-2xl rounded-lg p-6">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">Resume Selection</p>
            <h2 className="mt-2 font-headline text-2xl">Select Resume</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-outline-variant/60 p-2 text-on-surface-variant hover:text-on-surface"
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
            {error}
          </div>
        )}

        <div className="space-y-3">
          {loading ? (
            <div className="rounded-md border border-outline-variant/50 bg-surface-container-low p-4 text-sm text-on-surface-variant">
              Loading resumes...
            </div>
          ) : resumes.length === 0 ? (
            <div className="rounded-md border border-dashed border-outline-variant/80 bg-surface-container-low p-4 text-sm text-on-surface-variant">
              No resumes found. Upload your first PDF below.
            </div>
          ) : (
            resumes.map((resume) => {
              const resumeId = String(resume.id);
              return (
                <label
                  key={resumeId}
                  className="flex cursor-pointer items-center gap-3 rounded-md border border-outline-variant/70 bg-surface-container-low p-4 transition hover:border-primary/70"
                >
                  <input
                    type="radio"
                    checked={selectedResumeId === resumeId}
                    onChange={() => setSelectedResumeId(resumeId)}
                    className="accent-cyan-400"
                  />
                  <FileText size={18} className="text-primary" />
                  <div>
                    <p className="text-sm font-semibold text-on-surface">Resume {resumeId.slice(0, 8)}</p>
                    <p className="text-xs text-on-surface-variant">
                      Uploaded {formatDateTime(resume.created_at)}
                    </p>
                  </div>
                </label>
              );
            })
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-outline-variant bg-surface-container-low px-4 py-2 text-sm text-on-surface transition hover:bg-surface-container-high">
            <Upload size={16} />
            {uploading ? 'Uploading...' : 'Upload PDF'}
            <input
              type="file"
              className="hidden"
              accept="application/pdf"
              onChange={onUpload}
              disabled={uploading}
            />
          </label>

          <div className="ml-auto flex items-center gap-3">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={!selectedResumeId || loading || uploading}>
              Confirm Resume
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
