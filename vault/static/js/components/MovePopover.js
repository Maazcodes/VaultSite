import { subscribe, publish } from "../lib/pubsub.js"
const STRING_TRUNCATION_THRESHOLD = 17
const APPLICATION_JSON = "application/json"
export default class MovePopover extends HTMLElement {
  constructor(){
    super()
    this.allNodes = []
    this.contextElement = {}
    this.parentNodeId = 0
    this.childParentIdDict = {}
    this._parentNode = {}
    this.selectedNodeParentId = ""
    this.nodePathList = []
    this.sourceId = ""
  }
  connectedCallback () {
    this.innerHTML = `
      <div>
      <ui5-popover placement-type="Bottom" id="move-popover-content" style = " border-radius: 6px;" horizontal-align="Stretch">
        <div>
          <ui5-button design="Emphasized" style="float: right;" disabled>
          </ui5-button>
        </div>
      </ui5-popover>
      </div>
    `
    this.popover = this.querySelector("ui5-popover[id='move-popover-content']")
    
    subscribe("NODE_CHILDREN_RESPONSE", this.moveChildrenResponseHandler.bind(this))
    subscribe("NODE_RESPONSE", this.nodeResponseHandler.bind(this))
    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedHandler.bind(this)
    )
  }

  render (){
    const contextEle = this.contextElement
    this.sourceId = contextEle.selectedNodes[0].id 
    const parentNode = this._parentNode
    this.nodePathList = contextEle.selectedNodes[0].path.split(".")
    const AllNodes = this.allNodes    
    this.allNodes.forEach((element)=>{
      const elementPath = element.path.split(".")
      // extracting the second last number from node path
      const parentNodeid = elementPath.slice(elementPath.length-2, elementPath.length-1)
      // Storing parent's id with respect to child's id in childParentIdDict dictionary using node path
      // e.g. {childId: parentId}
      this.childParentIdDict[element.id] = parentNodeid[0]
    })
    const ChildParentIdDict = this.childParentIdDict
    const ParentNodeId = this.parentNodeId
    const fileParentId = ChildParentIdDict[this.sourceId]
    this.popover.innerHTML = `
    <div id="heading-part">
      <ui5-button design="Default" id="back-button"> <div style='font-size:20px; color: black;'><b>&#8617;</b></div>
            </ui5-button>
      <div id="move-popover-container" style="display:inline-block; text-align: center; width: 100%; height: 40px; vertical-align: middle; font-weight: bold; margin-top:-38px; margin-left: 16px;"></div>
    </div>
    <ui5-list mode="SingleSelect" id="folder-selector" no-data-text="No Data Available" >
    ${this.allNodes.filter(node=> node.node_type != "FILE").map(node => `<ui5-li data-value="${node.name}" id="${node.id}" url="${node.url}">${node.name}</ui5-li>`).join("")}
    </ui5-list>
    <div style="display: flex; justify-content: center; align-items: center;">
      <ui5-button design="Emphasized" id="move-button" style = "margin-top: 10px; margin-left: 0px;"> MOVE HERE</ui5-button>
    </div>
    `
    const moveButton = document.getElementById("move-button")
    // Disable move button initially
    moveButton.setAttribute("disabled",true) 
    const ParentElement = document.getElementById("move-popover-container")
    if (this.popover.style.width < "152"){
      if (ParentElement.classList.contains("move-popover-container-general")){
        ParentElement.classList.remove("move-popover-container-general")
      }
      ParentElement.classList.add("move-popover-container-narrow")
    }
    else{
      if (ParentElement.classList.contains("move-popover-container-narrow")){
        ParentElement.classList.remove("move-popover-container-narrow")
      }
      ParentElement.classList.add("move-popover-container-general")
    }
    if(!!parentNode.name){
      // if parent node name is not equal to undefined truncate it
      ParentElement.innerHTML = this.truncate(parentNode.name)
    }
    if (parentNode.id == this.nodePathList[0]) {
      // disable back button if the parent id == org id
      document.getElementById("back-button").setAttribute("disabled",true)
      ParentElement.innerHTML = 'Collections'  
    }
    
    // folder selector
    this.folderSelectorEventHandler(moveButton, fileParentId)

    // Move Item Button
    this.moveButtonEventHandler(this.popover, this.contextElement, this.sourceId)
    
    // Back Button
    this.backButtonEventHandler(ChildParentIdDict, ParentNodeId, AllNodes)
  } 

  moveButtonEventHandler(popover, contextElement, sourceId){
    const tableParentElement = document.querySelector("ui5-table")
    const selectedRowIndex = contextElement.selectedRows[0].attributes[0].value
    const selectedItemName = contextElement.selectedNodes[0].name
    const selectedItemNodeType = contextElement.selectedNodes[0].node_type
    const sourceNodeUrl = contextElement.selectedNodes[0].url    
    this.button = this.querySelector("ui5-button[id='move-button']")
    this.button.addEventListener("click", async function(){
      let payload = {parent: destinationNodeUrl}
      let options = {
        credentials: "same-origin",
        method: 'PATCH', 
        headers: {
          "Accept": APPLICATION_JSON,
          'Content-Type': APPLICATION_JSON
        },
        body: JSON.stringify(payload)
      }
      let response = await fetch(sourceNodeUrl, options)
      if (response.status >= 400){        
        console.error('Server error - response status', response.status)
        return
      }      
      // Close move popover content after clicking on move button
      popover.close();
      // Hide the selected row
      const selectedElement = document.querySelector(`ui5-table-row[data-index = "${selectedRowIndex}"]`)
      tableParentElement.removeChild(selectedElement)
      if(selectedItemNodeType!="FILE"){
        // Update tree view
        const ParentNode = document.querySelector(`ui5-tree-item[id='${destinationId}']`)
        const SourceTreeNode = document.querySelector(`ui5-tree-item[id='${sourceId}']`)
        // remove the source node from tree view and append it to destination node in tree view
        SourceTreeNode.parentNode.removeChild(SourceTreeNode)
        SourceTreeNode.setAttribute("path", `${$(ParentNode).attr('path') || ""}/${selectedItemName}` )
        ParentNode.appendChild(SourceTreeNode)
      }
    }
    )
  }

  folderSelectorEventHandler(moveButton, fileParentId){
    const folderSelectorElement = document.getElementById('folder-selector')
    folderSelectorElement.addEventListener("selection-change", function (event){
      const selectedItem = event.detail.selectedItems;
      globalThis.destinationNodeUrl = selectedItem[0].getAttribute("url")
      globalThis.destinationNodeName = selectedItem[0].textContent
      // making destination id global so as to use in move button event listener
      globalThis.destinationId = selectedItem[0].id
      if (fileParentId == destinationId || this.sourceId == destinationId){
        // disable move button if the parent element of source element is selected OR source id == destination id
        moveButton.setAttribute("disabled",true)
      }
      else{
        // enable move button if other element is selected
        moveButton.removeAttribute("disabled")
      }
    })   
    folderSelectorElement.addEventListener("dblclick", function(event){
      const selectedItemId = event.target.id
      if (this.sourceId == selectedItemId){
        // No action if double clicked on the source element
        return
      }
      publish("NODE_CHILDREN_REQUEST", {nodeId: selectedItemId, action: "MOVE"})
      publish("NODE_REQUEST", selectedItemId)
    })
  }

  backButtonEventHandler(ChildParentIdDict, ParentNodeId, AllNodes){
    this.backButton = this.querySelector("ui5-button[id='back-button']")
    let BackNodeId = ""
    this.backButton.addEventListener("click", function(){
      if (AllNodes.length == 0){
        // if there is no children of parent, call the parent id of the current node and call its children after clicking on back button
        BackNodeId = ChildParentIdDict[ParentNodeId]
      } 
      else{
        // if there are children of parent, call the grand parent id of current node and call its children after clicking on back button
        const moveChildPath = AllNodes[0].path.split(".")
        BackNodeId = moveChildPath.slice(moveChildPath.length-3, moveChildPath.length-2)[0]
      }
      // Calling an api for the children of grand parent id
      publish("NODE_CHILDREN_REQUEST", {nodeId: BackNodeId, action: "MOVE"})
      // Calling an api for parent node 
      publish("NODE_REQUEST", BackNodeId)  
    })
  }

  fileContextMenuItemSelectedHandler ({ value, context }) {
    if (value !== "Move") {
      return
    }
    const parentUrlList = context.selectedNodes[0].parent.split("/")
    this.selectedNodeParentId = parentUrlList.slice(parentUrlList.length-2, parentUrlList.length-1)[0]
    publish("NODE_REQUEST", this.selectedNodeParentId)
    this.contextElement = context
    this.allNodes = context.nodes
    const nameCell = context.currentRow.querySelector(".name")
    this.popover.showAt(nameCell)
    this.render()
  }

  moveChildrenResponseHandler ({childResponse, nodeId, action}){
    if (action !== "MOVE") {
      this.parentNodeId = nodeId
      return
    }
    this.parentNodeId = nodeId
    const moveChildrenResponse = childResponse
    this.allNodes = moveChildrenResponse
    this.render()
  }

  nodeResponseHandler(nodeResponse){
    this._parentNode = nodeResponse[0]
    this.render()    
  }

  truncate(input) {
   if (input.length > STRING_TRUNCATION_THRESHOLD) {
      return input.substring(0, 14) + '...';
   }
   return input;
};
}

customElements.define("vault-move-popover", MovePopover)
