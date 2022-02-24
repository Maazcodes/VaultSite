import { publish, subscribe } from "../lib/pubsub.js"
export default class FileTreeNavigator extends HTMLElement {
  constructor ({ orgId, parentChildDict}) {
    super()
    this.orgId = orgId
    // parent child dictionary receiving from views.py file - receive data after refresh
    this.parentChildDict = parentChildDict 
    // parentChildDict = {"parent id": [list of children]}
    this.props = {
      nodes: [],
      node: {},
    }
    // parent child dictionary created locally in this file to store data after every publish function call
    this.parentChildDictionary = {} 
  }

  connectedCallback () {
    // Expect this.props.nodes to have been been programmatically populated
    // by FilesView.
    this.render()
    subscribe("NODE_CHILDREN_RESPONSE", this.nodeChildrenResponseHandler.bind(this))
    subscribe("CHANGE_DIRECTORY", this.changeDirectoryHandler.bind(this))
    subscribe("NODE_RENAME_RESPONSE", this.nodeRenameResponseHandler.bind(this))

    // Announce component connection.
    publish("FILE_TREE_NAVIGATOR_COMPONENT_CONNECTED")
  }

  render () {
    const { node, nodes} = this.props;
    this.parentChildDictionary[node.id] = nodes;
    const currentNode = document.getElementById(String(node.id))
    const selectedElements = document.querySelectorAll("ui5-tree-item[selected]")
    selectedElements.forEach(element => element.removeAttribute("selected"))
    if (!!currentNode) {
      currentNode.setAttribute("selected", "");
    }
    if (node.id == this.orgId || !document.getElementById("treeDynamic")) {
      // initiate tree view and add event listeners only at initial stage
      // Add event listeners only if this condition is true - this is done to avoid addition of multiple event listeners
      this.innerHTML = `
        <ui5-tree id="treeDynamic">
          <ui5-tree-item text="Collections" id="${this.orgId}" has-children expanded selected>
            ${this.props.nodes.filter(node => node.node_type !== "FILE").map(node =>
              `<ui5-tree-item text="${node.name}" path="/${node.name}" id="${node.id}" ${node.node_type === "FILE" ? "" : "has-children"}>
                </ui5-tree-item>`
            ).join("")}
          </ui5-tree-item>
        </ui5-tree>
      `
      const dynamicTree = document.getElementById("treeDynamic");
      const firstTreeElement = document.querySelectorAll("ui5-tree-item")[0];
      dynamicTree.addEventListener("item-toggle", async function(event) {
        
        const item = event.detail.item; // get the node that is toggled
        if (item.text != firstTreeElement.text && item.expanded) {
            item.innerHTML = "";
          }
        if (item.text == firstTreeElement.text && !item.expanded) {
          // clearing previous tree data for first element
          firstTreeElement.innerHTML = ""; 
        }
        // show only subfolders after toggle
        if (!item.expanded) {
          // Request API from Conductor class for node's children
          publish("NODE_CHILDREN_REQUEST", {nodeId: item.id, action: "TREE_VIEW"});
        }
      })
      dynamicTree.addEventListener("item-click", async function(event) {
        const nodeItem = event.detail.item; // get the node that is clicked
        const nodeItemId = nodeItem.id;
        const nodePublishPath = $(nodeItem).attr('path');
        if (nodeItem.text == firstTreeElement.text) {
          // publish path for first tree element
          nodePublishPath = "/"
        }
        publish("CHANGE_DIRECTORY_REQUEST", { nodeId: nodeItemId, path: `${nodePublishPath}`});
      })
    } 
    else {
      const nodeElement = document.getElementById(String(node.id));
      const nodePathArray = node.path.split(".");
      if (!nodeElement) {
      // if parent node is not present in tree view, create it with the help of node path
        for (let index = 0; index < nodePathArray.length; index++) {
          const NodeId = nodePathArray[index];
          if (document.getElementById(String(NodeId))) {
            const ParentNode = document.getElementById(String(NodeId));
            this.CreateTreeViewElements(this.parentChildDictionary[NodeId] || this.parentChildDict[NodeId], ParentNode)
          }
        }
      }
      else {
        // toggle the node in tree view by getting parent node if parent node is present in tree view
        this.CreateTreeViewElements(nodes, nodeElement);
      }
    }     
  }

  CreateTreeViewElements(nodesArray, parentNode){
    // create tree elements after clicking on collection table or breadcrumbs
    for (let index = 0; index < nodesArray.length; index++) {
      const childNode = nodesArray[index];
      if (childNode.node_type !== "FILE" && !document.querySelector(`ui5-tree-item[id='${childNode.id}']`)) {
        const newItem = document.createElement("ui5-tree-item");
        newItem.id = String(childNode.id);
        newItem.text = String(childNode.name);
        newItem.setAttribute("path", String($(parentNode).attr('path') || "") + "/" + String(newItem.text))
        newItem.setAttribute("has-children", "");
        parentNode.appendChild(newItem);
      }
    }
    if (!parentNode.expanded) {
      parentNode.expanded = true;
    }
  }

  nodeChildrenResponseHandler ({childResponse, nodeId, action}){
    if (action != "TREE_VIEW") {
      return
    }
    const parentId = nodeId
    const nodesChildrenResponse = childResponse
    if (nodesChildrenResponse.length > 0 ) {
      const parentElement = document.getElementById(String(parentId))
      parentElement.innerHTML = `${nodesChildrenResponse.filter(node => node.node_type !== "FILE").map(node =>
                  `<ui5-tree-item text="${node.name}" path="${$(parentElement).attr('path')}/${node.name}" id="${node.id}" ${node.node_type === "FILE" ? "" : "has-children"}>
                  </ui5-tree-item>`
                ).join("")}`
      this.parentChildDictionary[parentId] = nodesChildrenResponse;
    }
  }

  changeDirectoryHandler ({ childNodesResponse, node}) {
    this.props.node = node;
    this.props.nodes = childNodesResponse.results;
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
