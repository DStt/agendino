/* Shared escaping and HTML-sanitization helpers.
 * Exposed on window so the standalone page scripts can reuse them.
 */
(function () {
  "use strict";

  if (typeof window.escapeHtml !== "function") {
    window.escapeHtml = function (text) {
      if (text === null || text === undefined) return "";
      return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    };
  }

  // Strip dangerous markup from any HTML that is inserted with innerHTML.
  window.sanitizeHtml = function (html) {
    if (html === null || html === undefined) return "";
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
      return window.DOMPurify.sanitize(String(html), { USE_PROFILES: { html: true } });
    }
    // Fail safe: if the sanitizer did not load, escape instead of trusting.
    return window.escapeHtml(html);
  };

  // Only allow simple hex colors where a value lands in a style attribute.
  window.safeColor = function (color, fallback) {
    var value = String(color || "");
    if (/^#[0-9a-fA-F]{3,8}$/.test(value)) return value;
    return fallback || "var(--bs-primary)";
  };

  // Render Markdown to sanitized HTML. marked is loaded on pages that need it.
  window.renderMarkdown = function (markdown) {
    var source = markdown === null || markdown === undefined ? "" : String(markdown);
    if (typeof window.marked !== "undefined" && window.marked && typeof window.marked.parse === "function") {
      return window.sanitizeHtml(window.marked.parse(source));
    }
    return window.escapeHtml(source).replace(/\n/g, "<br>");
  };
})();
