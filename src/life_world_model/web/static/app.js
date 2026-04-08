/* Life World Model Dashboard — Shared JS */

/**
 * Fetch JSON from an API endpoint and call the callback with parsed data.
 */
function fetchJSON(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', url);
  xhr.onload = function() {
    if (xhr.status === 200) {
      callback(JSON.parse(xhr.responseText));
    } else {
      console.error('API error:', xhr.status, xhr.responseText);
    }
  };
  xhr.onerror = function() {
    console.error('Network error fetching', url);
  };
  xhr.send();
}

/**
 * Format a float as a percentage string (e.g. 0.732 -> "73%").
 */
function formatPercent(value) {
  return Math.round(value * 100) + '%';
}

/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHtml(text) {
  if (!text) return '';
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

/**
 * Map activity names to consistent colors.
 */
var ACTIVITY_COLORS = {
  coding:        '#3b82f6',
  research:      '#8b5cf6',
  browsing:      '#f97316',
  communication: '#eab308',
  meeting:       '#ef4444',
  idle:          '#1a1a1a',
  ai_tooling:    '#06b6d4',
  file_management: '#6b7280',
  walking:       '#22c55e',
  exercise:      '#10b981',
};

function activityColor(activity) {
  return ACTIVITY_COLORS[activity] || '#4b5563';
}

// Set header date to today on page load
document.addEventListener('DOMContentLoaded', function() {
  var dateEl = document.getElementById('header-date');
  if (dateEl && !dateEl.textContent) {
    dateEl.textContent = new Date().toISOString().slice(0, 10);
  }
});
