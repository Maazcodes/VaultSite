
import { publish } from "../lib/pubsub.js"

const encodeSearchParams = x => x ? `?${new URLSearchParams(x).toString()}` : ''

export default class API {
  /* Class to interact with a Django Rest Framework API.

     Available resources will be automatically discovered and made available
     as instance attributes, to be accessed as follows:

       api.{resourceName}.{methodName}

     For example:

       api.users.get(id, params)
   */

  constructor (basePath = '/api') {
    // Collect the request method names and function that we want to bind
    // to each resource.
    const nameMethodPairs = [ 'get' ].map(k => [ k, this[k].bind(this) ])

    // Request the name -> url map of all available resource from the server.
    this.getJSON(basePath).then(resourceURLMap => {
      // For each available resource, make each request method available as
      // a property of this API instance as:
      //   api.{resourceName}.{methodName}
      // For example:
      //   api.treenodes.get(id, params)
      Object.entries(resourceURLMap).forEach(([ resource, url ]) =>
        this[resource] = Object.fromEntries(
          nameMethodPairs.map(([ name, func ]) =>
            [ name, (...args) => func(url, ...args) ]
          )
        )
      )
      // Announce readiness.
      publish("API_SERVICE_READY")
    })
  }

  async getJSON (url) {
    /* Make a GET request for JSON data from the specified URL.
     */
    return await (
      await fetch(
        url, {
          credentials: "same-origin",
          headers: {
            "accept": "application/json"
          }
        }
      )
    ).json()
  }

  async get (resourceUrl, id, params) {
    /* Make a GET request with optional params.
     */
    return await this.getJSON(
      `${resourceUrl}${id ? `${id}` : ""}${encodeSearchParams(params)}`
    )
  }
}
