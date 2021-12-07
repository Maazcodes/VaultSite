
import { camelToKebab, kebabToCamel } from "./lib.js"

export function createElement (DOMString, parentTag="div") {
  // Return an HTML element object for the given DOM string.
  const wrapper = document.createElement(parentTag)
  wrapper.innerHTML = DOMString.trim()
  const el = wrapper.firstChild
  wrapper.removeChild(el)
  return el
}

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

export const removeChildren = el =>
  Array.from(el.children) .forEach(el => el.remove())

export const slugify = s => s.toLowerCase().replace(/[^a-zA-Z0-9\-_]/g, "-")

// Join URL path parts into a string.
export const joinPath = (...xs) => (
  `${xs[0].startsWith("/") ? "/" : ""}` +
  `${xs.flatMap(x => x.split('/')).filter(x => x !== '').join('/')}` +
  `${xs.at(-1).endsWith("/") ? "/" : ""}`
)

export function objToElementPropsStr (obj) {
  /*
     Return a HTML Element attributes string representation of the specified
     object with:
       - object keys converted from camelCase -> kebabCase attribute names
       - object values serialized to JSON with escaped double-quotes

     Example:
       obj: { firstVal: 1, secondVal: [2, 3, 4], thirdVal: "ok" }
       result: `first-val="1" second-val="[2,3,4]" third-val="&quot;ok&quot;"`

     We refer to this encoded form as "props". The original object can be
     reconstituted from an Element via parseElementProps().
   */
  return Object.entries(obj)
               .map(([k, v]) => `${camelToKebab(k)}="${htmlAttrEncode(v)}"`)
               .join(" ")
}

export function parseElementProps (el, objKeys, errorOnMissing = true) {
  /*
     Return an object with the specified objKeys that results from parsing
     an Element's attributes by applying the inverse logic of
     objToElementPropsStr(). In the event of a missing objOkey, you can
     specify an Array-type objKeys value with the a default value as the
     second element, i.e. [ <objKey>, <defaultValue> ]

     Example:
       el: <div first-val="1" second-val="[2,3,4]" third-val="&quot;ok&quot;"`>
       objKeys: [ "firstVal", "secondVal", "thirdVal" ]
       result: { firstVal: 1, secondVal: [2, 3, 4], thirdVal: "ok" }
   */
  const obj = {}
  const missingAttrs = []
  for (let objKey of objKeys) {
    let defaultValue
    if (Array.isArray(objKey)) {
      ;([ objKey, defaultValue ] = objKey)
    }
    const attrName = camelToKebab(objKey)
    if (!el.hasAttribute(attrName)) {
      if (defaultValue !== undefined) {
        obj[objKey] = defaultValue
      } else {
        missingAttrs.push(attrName)
        obj[objKey] = undefined
      }
    } else {
      const attrValue = el.getAttribute(attrName)
      if (attrValue === "") {
        // Interpret a present, empty attribute value as true.
        obj[objKey] = true
      } else {
        obj[objKey] = JSON.parse(attrValue)
      }
    }
  }
  if (missingAttrs.length > 0 && errorOnMissing) {
    console.warn(el)
    throw new Error(`Element is missing required attributes: ${missingAttrs}`)
  }
  return obj
}
