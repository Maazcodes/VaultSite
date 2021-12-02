
import { htmlAttrEncode, joinPath } from "../lib/domLib.js"
import { publish, subscribe } from "../lib/pubsub.js"

import API from "../services/API.js"

import "./FileDetailsButtons.js"
import "./DeleteModal.js"
import "./MovePopover.js"
import "./RenameModal.js"
import "./NewCta.js"
import FileDetails from "./FileDetails.js"
import FileTreeNavigator from "./FileTreeNavigator.js"
import FilesList from "./FilesList.js"

/******************************************************************************
   Conductor
 *****************************************************************************/
class Conductor {
  constructor (basePath, appPath, path) {
    this.basePath = basePath
    this.appPath = appPath
    this.path = path
    this.api = new API(basePath)

    subscribe(
      "CHANGE_DIRECTORY_REQUEST",
      message => this.changeDirectoryRequestHandler(message)
    )

    subscribe(
      "NODE_RENAME_REQUEST",
      message => this.nodeRenameRequestHandler(message)
    )

    subscribe(
      "NODES_DELETE_REQUEST",
      message => this.nodesDeleteRequestHandler(message)
    )

    window.addEventListener("popstate", this.popstateHandler.bind(this))
  }

  set path (path) {
    /* Write the path to the browser history.
     */
    path = path || "/"
    if (!path.startsWith("/")) {
      path = `/${path}`
    }
    history.pushState({ path: path }, '', `${joinPath(this.appPath, path)}`)
  }

  popstateHandler (e) {
    /* Navigate to history state path.
     */
    if (e.state) {
      this.changeDirectoryRequestHandler({ path: e.state.path }, false)
    }
  }

  async changeDirectoryRequestHandler ({ path }, updateHistory = true) {
    /* Retrieve the directory listing from the API and emit it as a
       CHANGE_DIRECTORY command message.
     */
    // Get the directory listing for the specified path.
    const response = await this.api.pathListing(path)
    const data = await response.json()
    // Publish a CHANGE_DIRECTORY command with the requested path listing.
    // data comprises: { node, childNodes, path }
    publish("CHANGE_DIRECTORY", data)
    // Maybe update the browser history stack to reflect the new path.
    if (updateHistory) {
      this.path = path
    }
  }

  async nodeRenameRequestHandler ({ node, newName }) {
    // TODO - make this work
    setTimeout(() => publish("NODE_RENAME_RESPONSE"), 2000)
  }

  async nodesDeleteRequestHandler ({ nodes }) {
    // TODO - make this work
    setTimeout(() => publish("NODES_DELETE_RESPONSE"), 2000)
  }
}

/******************************************************************************
   FilesView Component
 *****************************************************************************/
export default class FilesView extends HTMLElement {
  constructor () {
    super()
    this.conductor = null
  }

  connectedCallback () {
    this.props = {
      basePath: this.getAttribute("base-path"),
      appPath: this.getAttribute("app-path"),
      path: JSON.parse(this.getAttribute("path")),
      node: JSON.parse(this.getAttribute("node")),
      childNodes: JSON.parse(this.getAttribute("child-nodes")),
    }
    // Prepend the internal representation of appPath with basePath.
    this.props.appPath = `${this.props.basePath}${this.props.appPath}`

    // Instantiate the Conductor with the current paths.
    const { basePath, appPath, path } = this.props
    this.conductor = new Conductor(basePath, appPath, path)

    this.innerHTML = `
      <div class="left-panel">
        <div id="new-cta-container">
          <new-cta></new-cta>
        </div>
        <div id="file-tree-navigator-container"></div>
      </div>
      <div class="right-panel">
        <div id="breadcrumbs-container">
          <em style="font-size: 2rem;">
            ${this.props.path.split("/").filter(Boolean).join(" &gt; ") || "My Vault"}
          </em>
          <file-details-buttons></file-details-buttons>
        </div>
        <div class="inner-panel">
          <div id="files-list-container"></div>
          <div id="file-details-container"></div>
        </div>
      </div>
      <vault-delete-modal></vault-delete-modal>
      <vault-move-popover></vault-move-popover>
      <vault-rename-modal></vault-rename-modal>
    `

    // Init the FileTreeNavigator component and append it to the first column.
    this.fileTreeNavigator = Object.assign(new FileTreeNavigator(), {
      props: {
        nodes: this.props.childNodes,
        path: this.props.path
      }
    })
    this.querySelector("#file-tree-navigator-container")
        .appendChild(this.fileTreeNavigator)

    // Init the FilesList component and append it to the second column.
    this.filesList = Object.assign(new FilesList(), {
      props: {
        nodes: this.props.childNodes,
        path: this.props.path,
      }
    })
    this.querySelector("#files-list-container")
        .appendChild(this.filesList)

    // Init the FileDetails component and append it to the last column.
    this.fileDetails = Object.assign(new FileDetails(), {
      props: { node: this.props.node }
    })
    this.querySelector("#file-details-container")
        .appendChild(this.fileDetails)

    subscribe("CHANGE_DIRECTORY", this.changeDirectoryMessageHandler.bind(this))
  }

  changeDirectoryMessageHandler ({ path, childNodes }) {
    Object.assign(this.props, { path, childNodes })

    // DEV - set simple breadcrumbs display
    const el = this.querySelector("#breadcrumbs-container > em")
    el.innerHTML = path.split("/").filter(Boolean).join(" &gt; ") || "My Vault"
  }
}

customElements.define("vault-files-view", FilesView)
