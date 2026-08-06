import React from 'react';

const EXAMPLE_LISTING = `High Quality Cotton T-Shirts

We manufacture t-shirts for various markets. Good quality material, competitive prices. Available in different sizes and colors. Contact us for more details. We have been in this business for many years and serve many happy customers.`;

export default function InputForm({
  formData,
  setFormData,
  onSubmit,
  isLoading
}) {
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    if (type === 'checkbox') {
      setFormData(prev => ({ ...prev, [name]: checked }));
    } else if (name.startsWith('structured.')) {
      const field = name.split('.')[1];
      setFormData(prev => ({
        ...prev,
        structured: { ...prev.structured, [field]: value }
      }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleLoadExample = () => {
    setFormData({
      category: 'Garments',
      listing: EXAMPLE_LISTING,
      structured: {
        MOQ: '',
        'Lead time': '',
        Certifications: '',
        'Price tiers': ''
      },
      includeCompetitive: true
    });
  };

  return (
    <div className="card-panel">
      <div className="panel-header">
        <h2 className="panel-title">Listing & Specifications</h2>
        <p className="panel-desc">Paste your raw supplier text and any verified structured specifications.</p>
      </div>

      <form onSubmit={onSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="category">Category</label>
          <select
            id="category"
            name="category"
            className="form-control"
            value={formData.category}
            onChange={handleChange}
          >
            <option value="Garments">Garments</option>
            <option value="Chemicals">Chemicals</option>
            <option value="Electronics">Electronics</option>
            <option value="General/Other">General / Other</option>
          </select>
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="form-label" htmlFor="listing">Listing Text</label>
            <button
              type="button"
              className="btn-text"
              onClick={handleLoadExample}
            >
              Load example listing
            </button>
          </div>
          <textarea
            id="listing"
            name="listing"
            className="form-control"
            placeholder="Paste your title, description, and specs here..."
            value={formData.listing}
            onChange={handleChange}
            required
          />
        </div>

        <div className="panel-header" style={{ marginTop: '24px', marginBottom: '12px' }}>
          <h3 className="panel-title" style={{ fontSize: '15px' }}>
            Structured Specs <span className="opt-tag">(Optional)</span>
          </h3>
        </div>

        <div className="specs-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="moq">MOQ</label>
            <input
              type="text"
              id="moq"
              name="structured.MOQ"
              className="form-control"
              placeholder="e.g. 500 units"
              value={formData.structured.MOQ || ''}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="leadtime">Lead Time</label>
            <input
              type="text"
              id="leadtime"
              name="structured.Lead time"
              className="form-control"
              placeholder="e.g. 10-14 days"
              value={formData.structured['Lead time'] || ''}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="certs">Certifications</label>
            <input
              type="text"
              id="certs"
              name="structured.Certifications"
              className="form-control"
              placeholder="e.g. ISO 9001"
              value={formData.structured.Certifications || ''}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="pricetiers">Price Tiers</label>
            <input
              type="text"
              id="pricetiers"
              name="structured.Price tiers"
              className="form-control"
              placeholder="e.g. $2.50 / unit"
              value={formData.structured['Price tiers'] || ''}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="toggle-group" onClick={() => setFormData(prev => ({ ...prev, includeCompetitive: !prev.includeCompetitive }))}>
          <input
            type="checkbox"
            id="includeCompetitive"
            name="includeCompetitive"
            checked={formData.includeCompetitive}
            onChange={handleChange}
          />
          <label className="toggle-label" htmlFor="includeCompetitive">
            Include real-time IndiaMART competitive scan
          </label>
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={isLoading || !formData.listing.trim()}
        >
          {isLoading ? (
            <>
              <span className="spinner"></span>
              Analyzing &amp; Optimizing...
            </>
          ) : (
            'Audit &amp; Optimize Listing'
          )}
        </button>
      </form>
    </div>
  );
}
