
/******************************************************************************
   Generic Helpers
******************************************************************************/

export function humanBytes (bytes, decPlaces = 3) {
  for (const prefix of ["", "Ki", "Mi", "Gi", "Ti", "Pi"]) {
    if (bytes < 1024) {
      const [ whole, frac ] = bytes.toString().split(".")
      return `${whole}${frac ? `.${frac.slice(0, decPlaces)}` : ""} ${prefix}B`
    }
    bytes /= 1024
  }
}

export const pluralize = (s, num = 2, suffix = "s") => num > 1 ? s + suffix : s

export function toTitleCase(text){
    if (text.includes("_")){
      text = text.replaceAll("_", " ")
    }
    let textArray = text.split(" ")
    // Eg: pre_deposit_modified_at ---> Pre Deposit Modified At
    return textArray.map(word=> {
      return word[0].toUpperCase() + word.slice(1, word.length)
    }).join(" ")
  }