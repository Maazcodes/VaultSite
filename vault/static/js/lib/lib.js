

/******************************************************************************
   Generic Helpers
******************************************************************************/

export const pluck = (k, objs) => objs.reduce((acc, obj) => [...acc, obj[k]], [])

export const uniq = xs => Array.from(new Set(xs))

export const isUpper = c => /[A-Z]/.test(c)

export const capitalize = s => `${s.charAt(0).toUpperCase()}${s.substr(1)}`

export const camelToKebab = s => Array.from(s).reduce(
  (acc, c, i) => acc + (isUpper(c) ? `${i ? "-" : ""}${c.toLowerCase()}` : c),
  ""
)

export function humanBytes (bytes, decPlaces = 3) {
  for (const prefix of ["", "Ki", "Mi", "Gi", "Ti", "Pi"]) {
    if (bytes < 1024) {
      const [ whole, frac ] = bytes.toString().split(".")
      return `${whole}${frac ? `.${frac.slice(0, decPlaces)}` : ""} ${prefix}B`
    }
    bytes /= 1024
  }
}

export function kebabToCamel (s) {
  const splits = s.split("-")
  return splits[0] + splits.slice(1).map(capitalize).join("")
}

export const pluralize = (s, num = 2, suffix = "s") => num > 1 ? s + suffix : s

export function populateTemplate (template, obj) {
  /* Return the result of interpolating the template string with
     the referenced obj properties.
     Example template: "/:account/collections/:collection"

     References with the suffix "|json" will be encoded as HTML-escaped JSON.
   */
  // Maybe need to support non-whole-path-segment replacements, but
  // let's just do that for now.
  const regex = /:[a-z_|]+/g
  return template.replaceAll(regex, match => {
    const splits = match.slice(1).split('|')
    switch (splits.length) {
      case 1:
        return obj[splits[0]]
        break;
      case 2:
        if (splits[1] !== "json") {
          throw new Error("Unsupported template filter: " + splits[1])
        }
        return JSON.stringify(obj[splits[0]]).replace(/"/g, "&quot;")
        break;
      default:
        throw new Error("Unparsable template reference: " + match)
    }
  })
}

/******************************************************************************
   Javascript Helpers
******************************************************************************/

export const getBoundMethod = (ins, methodName) => ins[methodName].bind(ins)

// Define a function to make a function that supports a callback awaitable by
// wrapping it in a Promise and passing resolve() as the callback argument.
export const makeAwaitable = (func, callbackArgIndex) => (...args) => new Promise(
  resolve => func(...(args.splice(callbackArgIndex, 1, resolve) && args))
)

export function ThrottledLIFO (minIntervalMs = 300) {
  /*
     Return a function that accepts a single (async) function argument
     whose invocations will be throttled based on minIntervalMs with only
     the last invocation being executed.
   */
  let handle = undefined
  let _reject = () => undefined
  // Return a promise that will be resolved in the case of execution or
  // rejected in the case of a throttle.
  return func => {
    _reject("throttled")
    clearTimeout(handle)
    return new Promise((resolve, reject) => {
      handle = setTimeout(async () => resolve(await func()), minIntervalMs)
      _reject = reject
    })
  }
}
