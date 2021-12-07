
// Escape a string for interpolation as a text node value.
export const escapeHtml = s =>
  s.replace(/&/g, "&amp;")
   .replace(/</g, "&lt;")
   .replace(/>/g, "&gt;")
   .replace(/"/g, "&quot;")
   .replace(/'/g, "&#039;")

// Escape a string for inclusion as an element attribute value.
export const htmlAttrEscape = s => s.replace(/"/g, "&quot;")

// Encode an object for inclusion as an element attribute value.
export const htmlAttrEncode = o => htmlAttrEscape(JSON.stringify(o))

// Join URL path parts into a string.
export const joinPath = (...xs) => (
  `${xs[0].startsWith("/") ? "/" : ""}` +
  `${xs.flatMap(x => x.split('/')).filter(x => x !== '').join('/')}` +
  `${xs.at(-1).endsWith("/") ? "/" : ""}`
)
