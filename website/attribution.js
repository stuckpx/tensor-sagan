/* Records how a visitor arrived so a signup can be credited to a channel.
 *
 * First-party only: no cookies, no third-party requests, no fingerprinting,
 * nothing sent anywhere unless the visitor actually subscribes. That keeps it
 * outside consent-banner territory and means the data we keep is limited to
 * people who chose to give us their email.
 *
 * First touch wins, held in sessionStorage: someone may land on a sermon page
 * from Google, browse to the homepage, and subscribe there. Reading the
 * referrer at submit time would credit that to ourselves.
 */
(function () {
  var KEY = 'hf_attribution';

  function stored() {
    try { return JSON.parse(sessionStorage.getItem(KEY)); } catch (e) { return null; }
  }

  function capture() {
    var existing = stored();
    if (existing) return existing;

    var params = new URLSearchParams(window.location.search);
    var ref = document.referrer || '';
    try {
      var u = new URL(ref);
      // Drop the query string — search pages can carry personal terms.
      ref = u.origin + u.pathname;
      // Internal navigation isn't an acquisition source.
      if (u.origin === window.location.origin) ref = '';
    } catch (e) {
      ref = '';
    }

    var attribution = {
      utm_source: params.get('utm_source') || '',
      utm_medium: params.get('utm_medium') || '',
      utm_campaign: params.get('utm_campaign') || '',
      referrer: ref,
      landing_page: window.location.pathname
    };

    // Only lock in a touch that actually names a source. A direct visit says
    // nothing, and persisting it would mean a later arrival in the same
    // session — via a flyer QR or a search result — got credited to nobody.
    if (attribution.utm_source || attribution.utm_medium ||
        attribution.utm_campaign || attribution.referrer) {
      try { sessionStorage.setItem(KEY, JSON.stringify(attribution)); } catch (e) {}
    }
    return attribution;
  }

  window.haramainAttribution = capture;
  capture();
})();
