import { subscribe, publish } from "../lib/pubsub.js"
export default class MovePopover extends HTMLElement {
  constructor(){
    super()
    this.allNodes = []
    this.contextElement = {}
    this.parentNodeId = 0
    this.childParentIdDict = {}
    this._parentNode = {}
    this.selectedNodeParentId = ""
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
    var contextEle = this.contextElement
    var sourceId = contextEle.selectedNodes[0].id 
    var nodePath = contextEle.selectedNodes[0].path
    var parentNode = this._parentNode
    var nodePathList = nodePath.split(".")
    const AllNodes = this.allNodes
    const popoverElement = this.popover
    const selectedRowIndex = contextEle.selectedRows[0].attributes[0].value
    const selectedItemName = contextEle.selectedNodes[0].name
    const selectedItemNodeType = contextEle.selectedNodes[0].node_type
    for (let index = 0; index < this.allNodes.length; index++) {
      const element = this.allNodes[index];
      const elementPath = element.path.split(".")
      var parentNodeid = elementPath.slice(elementPath.length-2, elementPath.length-1)
      this.childParentIdDict[element.id] = parentNodeid[0]
    }
    var ChildParentIdDict = this.childParentIdDict
    var ParentNodeId = this.parentNodeId
    this.popover.innerHTML = `
    <div id="heading-part">
      <ui5-button design="Default" id="back-button"> <div style='font-size:20px; color: black;'><b>&#8617;</b></div>
            </ui5-button>
      <div id="parent-name" style="display:inline-block; text-align: center; width: 100%; height: 40px; vertical-align: middle; font-weight: bold; margin-top:-38px; margin-left: 16px;"></div>
    </div>
    <ui5-list mode="SingleSelect" id="folder-selector" no-data-text="No Data Available" separators="None">
    ${this.allNodes.filter(node=> node.node_type != "FILE").map(node => `<ui5-li data-value="${node.name}" id="${node.id}">${node.name}</ui5-li>`).join("")}
    </ui5-list>
    <div style="display: flex; justify-content: center; align-items: center;">
      <ui5-button design="Emphasized" id="move-button" style = "margin-top: 10px; margin-left: 0px;"> MOVE HERE</ui5-button>
    </div>
    `
    if (this.popover.style.width < "152"){
      document.getElementById("parent-name").style.width = "82px"
      document.getElementById("parent-name").style.height = "50px"
    }
    var ParentElement = document.getElementById("parent-name")
    if(!!parentNode.name){
      ParentElement.innerHTML = `${this.truncate(parentNode.name)}`
    }
    if (parentNode.id == nodePathList[0]) {
      // disable back button if the parent id == org id
      document.getElementById("back-button").setAttribute("disabled",true)
      ParentElement.innerHTML = 'Collections'  
    }
    document.getElementById('folder-selector').addEventListener("selection-change", function (event){
      var selectedItem = event.detail.selectedItems;
      globalThis.destinationId = selectedItem[0].id
      globalThis.fileParentId = ChildParentIdDict[sourceId]
      if (fileParentId == destinationId || sourceId == destinationId){
        // disable move button if the parent element of source element is selected OR source id == destination id
        document.getElementById("move-button").setAttribute("disabled",true)
      }
      else{
        // enable move button if other element is selected
        document.getElementById("move-button").removeAttribute("disabled")
      }
    })   
    document.getElementById('folder-selector').addEventListener("dblclick", function(event){
      var selectedItemId = event.target.id
      if (sourceId == selectedItemId){
        // No action if double clicked on the source element
        return
      }
      publish("NODE_CHILDREN_REQUEST", [selectedItemId,"MOVE"])
      publish("NODE_REQUEST", selectedItemId)
    })

    // Move Item Button
    this.button = this.querySelector("ui5-button[id='move-button']")
    this.button.addEventListener("click", function(){
      let xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/move_file");
      xhr.setRequestHeader("Content-Type", "application/json");
      let payload = {"sourceId": sourceId.toString(), "destinationId": destinationId}
      xhr.send(JSON.stringify(payload))
      // Close move popover content after clicking on move button
      popoverElement.close();
      // Hide the selected row
      document.querySelector(`ui5-table-row[data-index = "${selectedRowIndex}"]`).style.display = "none";
      if(selectedItemNodeType!="FILE"){
        const ParentNode = document.querySelector(`ui5-tree-item[id='${destinationId}']`)
        const SourceTreeNode = document.querySelector(`ui5-tree-item[id='${sourceId}']`)
        SourceTreeNode.parentNode.removeChild(SourceTreeNode)
        SourceTreeNode.setAttribute("path", `${$(ParentNode).attr('path') || ""}/${selectedItemName}` )
        ParentNode.appendChild(SourceTreeNode)
      }
    }
    )
    // Back Button
    this.backButton = this.querySelector("ui5-button[id='back-button']")
    this.backButton.addEventListener("click", function(){
      if (AllNodes.length == 0){
        // if there is no children of parent, call the parent id of the current node and call its children after clicking on back button
        var BackNodeId = ChildParentIdDict[ParentNodeId]
      } 
      else{
        // if there are children of parent, call the grand parent id of current node and call its children after clicking on back button
        var moveChildPath = AllNodes[0].path.split(".")
        var BackNodeId = moveChildPath.slice(moveChildPath.length-3, moveChildPath.length-2)[0]
      }
      publish("NODE_CHILDREN_REQUEST", [BackNodeId, "MOVE"]) 
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

  moveChildrenResponseHandler (moveChildrenResponse){
    if (moveChildrenResponse[2] != "MOVE") {
      this.parentNodeId = moveChildrenResponse[1]
      return
    }
    this.parentNodeId = moveChildrenResponse[1]
    var moveChildrenResponse = moveChildrenResponse[0]
    this.allNodes = moveChildrenResponse
    this.render()
  }

  nodeResponseHandler(nodeResponse){
    this._parentNode = nodeResponse[0]
    this.render()    
  }

  truncate(input) {
   if (input.length > 17) {
      return input.substring(0, 14) + '...';
   }
   return input;
};
}

customElements.define("vault-move-popover", MovePopover)
