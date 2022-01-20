
import { publish, subscribe } from "../lib/pubsub.js"

export default class FileDetails extends HTMLElement {
  constructor () {
    super()
    this.props = { node: undefined }
  }

  connectedCallback () {
    // Expect this.props.node to have been been programmatically populated
    // by FilesView.
    this.style.display = "block"
    this.render()

    subscribe("FILE_ROW_SELECTED", this.fileRowSelectedHandler.bind(this))
    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectHandler.bind(this)
    )
    subscribe(
      "CHANGE_DIRECTORY",
      ({ node }) => this.changeDirectoryHandler(node)
    )
    subscribe("HIDE_DETAILS_PANEL", this.hide.bind(this))
    subscribe("SHOW_DETAILS_PANEL", this.show.bind(this))
    subscribe("NODE_RENAME_RESPONSE", this.nodeRenameResponseHandler.bind(this))
  }

  render () {
    const { node } = this.props

    if (!node || node.node_type === "ORGANIZATION") {
      this.innerHTML = `
        <p>
          <em>Select a file or folder to view its details</em>
        </p>
      `
      return
    }

    this.innerHTML = `
      <h2>
        <span class="name ${node.node_type}">${node.name}</span>
        <button class="close">x</button>
      </h2>

      <ui5-tabcontainer class="full-width" collapsed fixed show-overflow>
        <ui5-tab text="Details" selected></ui5-tab>
        <ui5-tab text="Activity" collapsed></ui5-tab>
      </ui5-tabcontainer>

      <div class="details">
        <dl style="font-size: 0.8rem;">
          ${Object.keys(node).sort().map(
            k => node[k] === null ? null : `<dt>${k}</dt><dd>${node[k]}</dd>`
          ).filter(s => s !== null).join("")}
        </dl>
      </div>

      <div class="activity hidden">
        TODO
      </div>
    `

    this.querySelector("button.close")
        .addEventListener("click", this.hide.bind(this))

    this.tabContainer = this.querySelector("ui5-tabcontainer")
    this.detailsEl = this.querySelector(".details")
    this.activityEl = this.querySelector(".activity")

    this.tabContainer.addEventListener("click", e => e.stopPropagation())
    this.tabContainer.addEventListener("tab-select", this.tabSelectHandler.bind(this))
  }

  hide () {
    this.style.display = "none"
    publish("DETAILS_PANEL_CLOSED")
  }

  show () {
    this.style.display = "block"
    publish("DETAILS_PANEL_OPEN")
  }

  fileContextMenuItemSelectHandler ({ value }) {
    if (value === "View Details") {
      this.show()
    }
  }

  attributeChangedCallback (name, oldValue, newValue) {
    this.props[name] = JSON.parse(newValue)
    this.render()
  }

  fileRowSelectedHandler (message) {
    const { node } = message
    this.props.node = node
    this.render()
  }

  nodeRenameResponseHandler ({ node, newName, error }) {
    // Ignore error responses.
    if (error) {
      return
    }
    if (this.props.node.url === node.url) {
      this.props.node.name = newName
      this.render()
    }
  }

  tabSelectHandler (e) {
    const showDetails = e.detail.tabIndex === 0
    this.detailsEl.classList[showDetails ? "remove" : "add"]("hidden")
    this.activityEl.classList[showDetails ? "add" : "remove"]("hidden")
  }

  changeDirectoryHandler (node) {
    this.props.node = node
    this.render()
  }
}

customElements.define("vault-file-details", FileDetails)
