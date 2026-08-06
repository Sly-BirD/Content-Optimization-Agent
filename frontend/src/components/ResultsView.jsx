import React, { useState } from 'react';

export default function ResultsView({
  result,
  onRerunWithSpecs,
  onReset,
  isRerunning
}) {
  const [copied, setCopied] = useState(false);
  const [missingInputs, setMissingInputs] = useState({});

  if (!result) return null;

  const criteria = result.criteria || [];
  const overall = criteria.length
    ? criteria.reduce((sum, c) => sum + Number(c.score || 0), 0) / criteria.length
    : 0;
  const overallRounded = Math.round(overall * 10) / 10;

  const getStatusClass = (score) => {
    if (score >= 7) return 'strong';
    if (score >= 5) return 'ok';
    return 'weak';
  };

  const keySpecs = result.key_specs || [];
  const missingSpecs = result.missing_specs || [];
  const unverifiedClaims = result.unverified_claims || [];
  const compNotes = result.competitive_notes || [];
  const compListings = result.comparable_listings || [];

  const handleCopy = () => {
    let fullText = `${result.rewritten_title || ''}\n\n${result.description_intro || ''}\n\nKey Specifications:\n`;
    keySpecs.forEach(spec => {
      fullText += `• ${spec.label}: ${spec.value}\n`;
    });
    if (result.call_to_action) {
      fullText += `\nCall to Action:\n${result.call_to_action}`;
    }

    navigator.clipboard.writeText(fullText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleMissingInputChange = (specName, value) => {
    setMissingInputs(prev => ({
      ...prev,
      [specName]: value
    }));
  };

  const hasAnyMissingFilled = Object.values(missingInputs).some(val => val && val.trim().length > 0);

  const handleRerunSubmit = (e) => {
    e.preventDefault();
    if (!hasAnyMissingFilled) return;

    // Filter out empty entries
    const filledSpecs = {};
    Object.entries(missingInputs).forEach(([key, val]) => {
      if (val && val.trim()) {
        filledSpecs[key] = val.trim();
      }
    });

    onRerunWithSpecs(filledSpecs);
  };

  return (
    <div className="card-panel">
      {/* Top Header Action Bar with Reset Button (Change 3) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <span className="brand-tag" style={{ fontSize: '12px' }}>AUDIT COMPLETE</span>
        <button
          type="button"
          className="btn-secondary"
          onClick={onReset}
          title="Clear results and start a new listing analysis"
        >
          <span>↺</span> Analyze Another Listing
        </button>
      </div>

      {/* Score Banner */}
      <div className="score-banner">
        <div className="score-badge">
          <span className="score-num">{overallRounded}</span>
          <span className="score-denom">/ 10</span>
        </div>
        <div className="score-meta">
          <h4>Listing Audit Score</h4>
          <p>Scored across 6 B2B discoverability and spec completeness criteria.</p>
        </div>
      </div>

      {/* Criteria Scorecard Grid */}
      <div className="section-subhead">Discoverability Breakdown</div>
      <div className="scorecard-grid">
        {criteria.map((c, i) => (
          <div key={i} className="criterion-card">
            <div className="criterion-top">
              <span className="criterion-title">{c.label}</span>
              <span className="criterion-val">{c.score}/10</span>
            </div>
            <div className="progress-track">
              <div
                className={`progress-fill ${getStatusClass(c.score)}`}
                style={{ width: `${(c.score / 10) * 100}%` }}
              />
            </div>
            <p className="criterion-note">{c.note}</p>
          </div>
        ))}
      </div>

      {/* Automatically Removed Warning Banner */}
      {unverifiedClaims.length > 0 && (
        <div className="removed-banner">
          <div className="banner-title">
            <span>⚠️</span> Automatically Removed — Unverified Claims
          </div>
          <p className="banner-text">
            These details were removed automatically because they weren't found in your original listing or structured specs. Add them yourself if accurate.
          </p>
          <div className="tag-cloud">
            {unverifiedClaims.map((claim, idx) => {
              const label = typeof claim === 'string' ? claim : `${claim.field || ''}: ${claim.claimed_value || ''}`;
              return (
                <span key={idx} className="tag-chip removed">
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Clean Publish-Ready Preview */}
      <div className="section-subhead">Optimized Listing Preview</div>
      <div className="preview-box">
        <button className="btn-copy" onClick={handleCopy}>
          {copied ? '✓ Copied' : 'Copy Listing'}
        </button>

        {result.rewritten_title && (
          <h3 className="preview-title">{result.rewritten_title}</h3>
        )}

        {result.description_intro && (
          <p className="preview-intro">{result.description_intro}</p>
        )}

        {keySpecs.length > 0 && (
          <div className="spec-table-container">
            <div className="section-subhead" style={{ marginBottom: '6px' }}>Key Specifications</div>
            <table className="spec-table">
              <tbody>
                {keySpecs.map((spec, i) => (
                  <tr key={i}>
                    <td className="spec-label">{spec.label}</td>
                    <td className="spec-val">{spec.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result.call_to_action && (
          <div className="cta-box">
            <strong>Call to Action:</strong> {result.call_to_action}
          </div>
        )}
      </div>

      {/* Missing Specs Section & Interactive Fill Prompt (Change 2) */}
      {missingSpecs.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <div className="section-subhead">Missing Required Specs</div>
          <div className="tag-cloud" style={{ marginBottom: '14px' }}>
            {missingSpecs.map((spec, idx) => (
              <span key={idx} className="tag-chip missing">
                Missing: {spec}
              </span>
            ))}
          </div>

          {/* Change 2: Inline missing specs prompt card */}
          <div className="missing-prompt-card">
            <div className="prompt-card-header">
              <span>💡</span> Complete Missing Specifications
            </div>
            <p className="prompt-card-desc">
              Fill in any missing details below to enhance your listing completeness score and generate an updated optimization.
            </p>

            <form onSubmit={handleRerunSubmit}>
              <div className="missing-input-grid">
                {missingSpecs.map((specName, idx) => (
                  <div key={idx} className="missing-input-field">
                    <label htmlFor={`missing-${idx}`}>{specName}</label>
                    <input
                      type="text"
                      id={`missing-${idx}`}
                      className="form-control"
                      placeholder={`Enter ${specName}...`}
                      value={missingInputs[specName] || ''}
                      onChange={(e) => handleMissingInputChange(specName, e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <button
                type="submit"
                className="btn-secondary btn-blueprint"
                disabled={!hasAnyMissingFilled || isRerunning}
              >
                {isRerunning ? (
                  <>
                    <span className="spinner"></span>
                    Re-running Analysis...
                  </>
                ) : (
                  'Add these details and re-run'
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Competitive Scan Section */}
      <div className="competitive-section">
        <div className="section-subhead">Competitive Market Analysis</div>

        {result.competitive_error ? (
          <p className="banner-text" style={{ color: 'var(--text-muted)' }}>
            Competitive scan skipped ({result.competitive_error}). Audit ran normally.
          </p>
        ) : compNotes.length > 0 ? (
          <>
            <ul className="comp-list">
              {compNotes.map((note, idx) => (
                <li key={idx} className="comp-item">{note}</li>
              ))}
            </ul>

            {compListings.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <div className="section-subhead" style={{ fontSize: '10px' }}>Scraped Competitors Found</div>
                <div className="tag-cloud">
                  {compListings.map((c, idx) => (
                    <span key={idx} className="tag-chip" style={{ borderColor: 'var(--accent-blueprint)', color: 'var(--accent-blueprint)' }}>
                      {c.title}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="banner-text" style={{ color: 'var(--text-muted)' }}>
            No competitive notes generated for this run.
          </p>
        )}
      </div>
    </div>
  );
}
