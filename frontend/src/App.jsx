import React, { useState } from 'react';
import InputForm from './components/InputForm';
import ResultsView from './components/ResultsView';
import ErrorBanner from './components/ErrorBanner';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const CATEGORY_REQUIRED_SPECS = {
  Garments: ['MOQ', 'Lead time', 'Certifications', 'Price tiers', 'Fabric weight (GSM)', 'Fabric composition', 'Available sizing runs'],
  Chemicals: ['MOQ', 'Lead time', 'Certifications', 'Price tiers', 'CAS number', 'Purity %', 'SDS/MSDS sheet availability'],
  Electronics: ['MOQ', 'Lead time', 'Certifications', 'Price tiers', 'Input voltage', 'Safety certifications (CE/FCC)', 'Component datasheet availability'],
  'General/Other': ['MOQ', 'Lead time', 'Certifications', 'Price tiers']
};

const INITIAL_FORM_DATA = {
  category: 'Garments',
  listing: '',
  structured: {
    MOQ: '',
    'Lead time': '',
    Certifications: '',
    'Price tiers': ''
  },
  includeCompetitive: true
};

export default function App() {
  const [formData, setFormData] = useState(INITIAL_FORM_DATA);
  const [isLoading, setIsLoading] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runAnalysis = async (currentFormData) => {
    setError(null);
    const requiredSpecs = CATEGORY_REQUIRED_SPECS[currentFormData.category] || CATEGORY_REQUIRED_SPECS['General/Other'];

    const payload = {
      category: currentFormData.category,
      listing: currentFormData.listing,
      structured: currentFormData.structured,
      requiredSpecs: requiredSpecs,
      includeCompetitive: currentFormData.includeCompetitive
    };

    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let errDetail = 'Failed to analyze listing. Please check your backend connection.';
      try {
        const errData = await response.json();
        if (errData.detail) errDetail = errData.detail;
      } catch (_) {}
      throw new Error(errDetail);
    }

    return await response.json();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.listing.trim()) return;

    setIsLoading(true);
    try {
      const data = await runAnalysis(formData);
      setResult(data);
    } catch (err) {
      console.error('API Error:', err);
      setError(err.message || 'Network error — could not connect to backend server.');
    } finally {
      setIsLoading(false);
    }
  };

  // Change 2: Re-run handler with merged structured specs
  const handleRerunWithSpecs = async (newFilledSpecs) => {
    setIsRerunning(true);
    const updatedFormData = {
      ...formData,
      structured: {
        ...formData.structured,
        ...newFilledSpecs
      }
    };
    setFormData(updatedFormData);

    try {
      const data = await runAnalysis(updatedFormData);
      setResult(data);
    } catch (err) {
      console.error('Re-run API Error:', err);
      setError(err.message || 'Network error during re-run.');
    } finally {
      setIsRerunning(false);
    }
  };

  // Change 3: Reset flow ("Analyze another listing")
  const handleReset = () => {
    setFormData(INITIAL_FORM_DATA);
    setResult(null);
    setError(null);
    setIsLoading(false);
    setIsRerunning(false);
  };

  return (
    <div className="app-layout">
      {/* Navbar Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand-title">
            <span className="brand-logo">SUPROC</span>
            <span className="brand-text">Listing Optimizer</span>
            <span className="brand-tag">PROD V3</span>
          </div>
          {result && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleReset}
              style={{ fontSize: '12px' }}
            >
              Analyze Another Listing
            </button>
          )}
        </div>
      </header>

      {/* Main Content Dashboard */}
      <main className="app-main">
        <div className="dashboard-grid">
          <div className="left-panel">
            <InputForm
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleSubmit}
              isLoading={isLoading}
            />
          </div>

          <div className="right-panel">
            <ErrorBanner message={error} />

            {result ? (
              <ResultsView
                result={result}
                onRerunWithSpecs={handleRerunWithSpecs}
                onReset={handleReset}
                isRerunning={isRerunning}
              />
            ) : (
              <div className="card-panel empty-state">
                <span className="empty-icon">AWAITING LISTING INPUT</span>
                <h3>No Listing Analyzed Yet</h3>
                <p>
                  Paste your supplier text on the left and click <strong>Audit &amp; Optimize Listing</strong>. You'll receive a discoverability score, structured specs, and a zero-trust sanitized copy ready for publication.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
