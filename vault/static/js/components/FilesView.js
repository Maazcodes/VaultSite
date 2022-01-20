
import { htmlAttrEncode, joinPath } from "../lib/domLib.js"
import { publish, subscribe } from "../lib/pubsub.js"

import API from "../services/API.js"

import "./FileDetailsButtons.js"
import "./NewCollectionModal.js"
import "./NewFolderModal.js"
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
  constructor ({ basePath, appPath, path, node }) {
    const API_BASE_PATH = `${basePath}/api/`

    // The initial node is rendered outside of DRF so doesn't include a url
    // property. So manually add it here.
    node.url = `${API_BASE_PATH}treenodes/${node.id}/`

    this.basePath = basePath
    this.appPath = appPath
    this.path = path
    this.node = node
    this.api = new API(API_BASE_PATH)
    this.state = {
      childQuery: {
        ordering: "-node_type,name",
        limit: 25
      },
      // Define the set of topics to wait for before calling init().
      topicsUntilInit: new Set([
        "API_SERVICE_READY",
        "NEW_CTA_COMPONENT_CONNCECTED",
        "FILE_TREE_NAVIGATOR_COMPONENT_CONNECTED"
      ])
    }

    subscribe(
      "CHANGE_DIRECTORY_REQUEST",
      message => this.changeDirectoryRequestHandler(message)
    )

    subscribe(
      "CREATE_COLLECTION_REQUEST",
      message => this.createCollectionRequestHandler(message)
    )

    subscribe(
      "CREATE_FOLDER_REQUEST",
      message => this.createFolderRequestHandler(message)
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

    // Subscribe the handler to the topics in topicsUntilInit.
    this.state.topicsUntilInit.forEach(topic =>
      subscribe(topic, () => this.untilInitTopicHandler(topic))
    )
  }

  init () {
    /* Publish an initial CHANGE_DIRECTORY_REQUEST message to trigger the
       initial node children load.
     */
    const { node, path } = this
    publish("CHANGE_DIRECTORY_REQUEST", { node, path })
  }

  untilInitTopicHandler (topic) {
    /* Register receipt of the topic message and maybe call init().
     */
    if (this.state.topicsUntilInit.size > 0) {
      // The topic waitlist is not empty, so remove this one.
      this.state.topicsUntilInit.delete(topic)
      // If the waitlist is now empty, call init().
      if (this.state.topicsUntilInit.size == 0) {
        this.init()
      }
    }
  }

  doHistoryUpdate (path, node) {
    /* Write the path to the browser history.
     */
    path = path || "/"
    if (!path.startsWith("/")) {
      path = `/${path}`
    }
    history.pushState({ path, node }, '', `${joinPath(this.appPath, path)}`)
  }

  popstateHandler (e) {
    /* Navigate to history state path.
     */
    if (e.state) {
      this.changeDirectoryRequestHandler(
        { node: e.state.node, path: e.state.path },
        false
      )
    }
  }

  async changeDirectoryRequestHandler ({ node, path }, updateHistory = true) {
    /* Retrieve the directory listing from the API and emit it as a
       CHANGE_DIRECTORY command message.
     */
    // Save the new node and path.
    this.node = node
    this.path = path
    // Fetch the selected node's children.
    const { limit, ordering } = this.state.childQuery
    const childNodesResponse =
      await this.api.treenodes.get(null, { parent: node.id, limit, ordering })
    // Publish a CHANGE_DIRECTORY command with the requested path listing.
    publish("CHANGE_DIRECTORY", { node, childNodesResponse, path })
    // Maybe update the browser history stack to reflect the new path.
    if (updateHistory) {
      this.doHistoryUpdate(path, node)
    }
  }

  async createCollectionRequestHandler ({ name }) {
    const response = await this.api.collections.post({ name })
    const error = await this.api.getResponseErrorDetail(response)
    publish("CREATE_COLLECTION_RESPONSE", { name, error })
    // If creation was successful, publish a CHANGE_DIRECTORY_REQUEST to navigate to
    // the new collection.
    if (!error) {
      const collection = await response.json()
      const node = await (await fetch(collection.tree_node)).json()
      publish("CHANGE_DIRECTORY_REQUEST", { node,  path: `/${node.name}` })
    }
  }

  async createFolderRequestHandler ({ name }) {
    const response = await this.api.treenodes.post({
      name,
      node_type: "FOLDER",
      parent: this.node.url
    })

    const error = await this.api.getResponseErrorDetail(response)
    publish("CREATE_FOLDER_RESPONSE", { name, error })

    // If creation was successful, publish a CHANGE_DIRECTORY_REQUEST to reload the
    // current view.
    // TODO - this more efficiently.
    if (!error) {
      publish("CHANGE_DIRECTORY_REQUEST", { node: this.node,  path: this.path })
    }
  }

  async nodeRenameRequestHandler ({ node, newName }) {
    const response = await this.api.treenodes.patch(node.id, { name: newName })
    const error = await this.api.getResponseErrorDetail(response)
    publish("NODE_RENAME_RESPONSE", { node, newName, error })
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
    }
    // Prepend the internal representation of appPath with basePath.
    this.props.appPath = `${this.props.basePath}${this.props.appPath}`

    // Instantiate the Conductor with the current paths.
    this.conductor = new Conductor(this.props)

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
      <vault-new-collection-modal></vault-new-collection-modal>
      <vault-new-folder-modal></vault-new-folder-modal>
      <vault-delete-modal></vault-delete-modal>
      <vault-move-popover></vault-move-popover>
      <vault-rename-modal></vault-rename-modal>
    `

    // Init the FileTreeNavigator component and append it to the first column.
    this.fileTreeNavigator = Object.assign(new FileTreeNavigator(), {
      props: {
        nodes: [],
        path: this.props.path
      }
    })
    this.querySelector("#file-tree-navigator-container")
        .appendChild(this.fileTreeNavigator)

    // Init the FilesList component and append it to the second column.
    this.filesList = Object.assign(new FilesList(), {
      props: {
        nodes: [],
        path: this.props.path,
      }
    })
    this.querySelector("#files-list-container").appendChild(this.filesList)

    // Init the FileDetails component and append it to the last column.
    this.fileDetails = Object.assign(new FileDetails(), {
      props: {
        node: this.props.node
      }
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
