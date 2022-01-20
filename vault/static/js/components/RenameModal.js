
import { subscribe, publish } from "../lib/pubsub.js"

import Modal from "./Modal.js"


export default class RenameModal extends Modal {
  constructor () {
    super()
    this.state = { node: undefined }
  }

  connectedCallback () {
    this.setAttribute("header-text", "Rename")
    this.setAttribute("submit-text", "OK")
    this.innerHTML = `
      <input type="text" name="newName" spellcheck="false" autocomplete="off"></input>
    `
    super.connectedCallback()

    this.input = this.querySelector("input[name=newName]")

    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedHandler.bind(this)
    )

    subscribe(
      "NODE_RENAME_RESPONSE",
      this.nodeRenameResponseHandler.bind(this)
    )
  }

  open () {
    // Set the input to the current node.name and pre-select it.
    this.input.value = this.state.node.name
    this.input.select()
    super.open()
  }

  fileContextMenuItemSelectedHandler ({ value, context }) {
    if (value !== "Rename") {
      return
    }
    this.state.node = context.selectedNodes[0]
    this.open()
  }

  submitHandler (nameInputMap) {
    const { node } = this.state
    const newName = nameInputMap.get("newName").value
    if (newName === node.name) {
      this.close()
      return
    }
    publish("NODE_RENAME_REQUEST", { node, newName })
    this.setBusyState(true)
  }

  nodeRenameResponseHandler ({ error }) {
    this.setBusyState(false)
    if (!error) {
      this.close()
      return
    }
    const { code } = error
    switch (code) {
      case 409:
        this.error = "An item with this name already exists"
        break
      default:
        this.error = "An error occurred"
    }
    // Reselect the input.
    this.input.select()
  }
}

customElements.define("vault-rename-modal", RenameModal)
