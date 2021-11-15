
import { pluralize } from "../lib/lib.js"
import { subscribe, publish } from "../lib/pubsub.js"

import Modal from "./Modal.js"


export default class DeleteModal extends Modal {
  constructor () {
    super()
    this.state = { nodes: undefined }
  }

  connectedCallback () {
    this.setAttribute("header-text", "Delete?")
    this.setAttribute("submit-text", "DELETE")
    this.setAttribute("submit-design", "Negative")
    this.innerHTML = `<p class="delete-message"></p>`
    super.connectedCallback()

    this.message = this.querySelector("p.delete-message")

    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedHandler.bind(this)
    )

    subscribe(
      "NODES_DELETE_RESPONSE",
      this.nodeDeleteResponseHandler.bind(this)
    )
  }

  open () {
    // Set the input to the current node.name and pre-select it.
    const numNodes = this.state.nodes.length
    this.message.textContent =
      `${numNodes} ${pluralize("item", numNodes)} will be deleted.`
    super.open()
  }

  fileContextMenuItemSelectedHandler ({ value, context }) {
    if (value !== "Delete") {
      return
    }
    this.state.nodes = context.selectedNodes
    this.open()
  }

  submitHandler (nameInputMap) {
    const { nodes } = this.state
    publish("NODES_DELETE_REQUEST", { nodes })
    this.setBusyState(true)
  }

  nodeDeleteResponseHandler (message) {
    // TODO - handle errors
    this.setBusyState(false)
    this.close()
  }
}

customElements.define("vault-delete-modal", DeleteModal)
