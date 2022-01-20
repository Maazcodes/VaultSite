
import { publish, subscribe } from "../lib/pubsub.js"

export default class FileTreeNavigator extends HTMLElement {
  constructor () {
    super()
    this.props = {
      nodes: [],
      path: undefined
    }
  }

  connectedCallback () {
    // Expect this.props.nodes to have been been programmatically populated
    // by FilesView.
    this.render()

    subscribe("CHANGE_DIRECTORY", this.changeDirectoryHandler.bind(this))
    subscribe("NODE_RENAME_RESPONSE", this.nodeRenameResponseHandler.bind(this))

    // Announce component connection.
    publish("FILE_TREE_NAVIGATOR_COMPONENT_CONNECTED")
  }

  render () {
    const { path } = this.props
    const pathParts = path === "/" ? [] : path.replace(/^\//, "").split("/")
    const lastPartI = pathParts.length - 1

    this.innerHTML = `
      <ui5-tree>
        <ui5-tree-item text="My Vault" expanded>
          ${pathParts.map((pp, i) =>
            `<ui5-tree-item text="${pp}" expanded ${i === lastPartI ? "selected" : ""}>`
          ).join("")}
            ${this.props.nodes.filter(node => node.node_type !== "FILE").map(node =>
              `<ui5-tree-item data-url="${node.url}" text="${node.name}"
                            ${node.node_type === "FILE" ? "" : "has-children"}>
               </ui5-tree-item>`
            ).join("")}
          ${pathParts.map(() => `</ui5-tree-item>`).join("")}
        </ui5-tree-item>
      </ui5-tree>
    `
  }

  changeDirectoryHandler ({ childNodesResponse, path }) {
    this.props.path = path
    this.props.nodes = childNodesResponse.results
    this.render()
  }

  nodeRenameResponseHandler ({ node, newName, error }) {
    /* Update the corresponding ui5-tree-item with the new name.
     */
    // Ignore error and FILE-type node responses.
    if (error || node.node_type === "FILE") {
      return
    }
    this.querySelector(`ui5-tree-item[data-url="${node.url}"]`)
        .setAttribute("text", newName)
  }
}

customElements.define("vault-file-tree-navigator", FileTreeNavigator)
