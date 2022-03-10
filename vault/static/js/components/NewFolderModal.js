
import { subscribe, publish } from "../lib/pubsub.js"

import Modal from "./Modal.js"


export default class NewFolderModal extends Modal {
  constructor () {
    super()
    this.state = { node: undefined }
  }

  connectedCallback () {
    this.setAttribute("header-text", "Create Folder")
    this.setAttribute("submit-text", "OK")
    this.innerHTML = `
      <input type="text"
             name="name"
             spellcheck="false"
             autocomplete="off"
             placeholder="Enter new folder name"
      >
      </input>
    `
    super.connectedCallback()

    this.input = this.querySelector("input[name=name]")

    subscribe(
      "NEW_CTA_MENU_ITEM_SELECTED",
      this.newCtaMenuItemSelectedHandler.bind(this)
    )

    subscribe("CHANGE_DIRECTORY", this.changeDirectoryHandler.bind(this))
    subscribe(
      "CREATE_FOLDER_RESPONSE",
      this.createFolderResponseHandler.bind(this)
    )
  }

  newCtaMenuItemSelectedHandler ({ value }) {
    if (value !== "folder") {
      return
    }
    this.open()
  }

  submitHandler (nameInputMap) {
    const name = nameInputMap.get("name").value
    const parentNode = this.state.node
    publish("CREATE_FOLDER_REQUEST", { name, parentNode })
    this.setBusyState(true)
  }

  changeDirectoryHandler ({ node}) {
    this.state.node = node;
  }

  createFolderResponseHandler ({ error }) {
    this.setBusyState(false)
    if (!error) {
      this.close()
      return
    }
    const { code } = error
    switch (code) {
      case 409:
        this.error = "A Folder with this name already exists"
        break
      default:
        this.error = "An error occurred"
    }
    // Reselect the input.
    this.input.select()
  }
}

customElements.define("vault-new-folder-modal", NewFolderModal)
