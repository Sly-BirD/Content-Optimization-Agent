import React from 'react';

export default function ErrorBanner({ message }) {
  if (!message) return null;

  return (
    <div className="error-banner">
      <strong>Unable to complete request:</strong> {message}
    </div>
  );
}
