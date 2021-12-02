
import { publish, subscribe } from "../lib/pubsub.js"

const ENDPOINTS = Object.freeze({
  PATH_LISTING: "/path_listing"
})

export default class API {
  constructor (basePath = '') {
    this.basePath = basePath
  }

  async GET (endpoint, params) {
    const paramsStr = params
                    ? `?${new URLSearchParams(params).toString()}`
                    : ''
    return await fetch(
      `${this.basePath}/api${endpoint}${paramsStr}`, {
        credentials: "same-origin",
        headers: {
          "accept": "application/json"
        }
      }
    )
  }

  async pathListing (path) {
    return await this.GET(ENDPOINTS.PATH_LISTING, { path })
  }
}

subscribe("API_REQUEST", async ({ method, endpoint, args = [] }) => {
  const response = await API[method](endpoint, ...args)
  const data = await response.json()
  publish("API_RESPONSE", [ { method, endpoint, args }, data ])
  console.log([ [ endpoint, ...args ], data ])
})
