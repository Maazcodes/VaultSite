
import { publish, subscribe } from "../lib/pubsub.js"
import {humanBytes, toTitleCase } from "../lib/lib.js"
export default class FileDetails extends HTMLElement {
  constructor () {
    super()
    this.props = {
      node: undefined,
      basePath: "",
      collectionIdDict: {},
      // collectionNodeSize: {},
      // folderNodeSize:{},
      path: undefined
    }
    this.nodeSize = ""
    this.folderNodeId = ""
  }

  connectedCallback () {
    // Expect this.props.node to have been been programmatically populated
    // by FilesView.
    this.style.display = "block"
    this.render()
    subscribe("NODE_RESPONSE", this.nodeResponseHandler.bind(this))
    subscribe("FILE_ROW_SELECTED", this.fileRowSelectedHandler.bind(this))
    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectHandler.bind(this)
    )
    subscribe(
      "CHANGE_DIRECTORY",
      ({ node,path }) => this.changeDirectoryHandler(node,path)
    )
    subscribe("HIDE_DETAILS_PANEL", this.hide.bind(this))
    subscribe("SHOW_DETAILS_PANEL", this.show.bind(this))
    subscribe("NODE_RENAME_RESPONSE", this.nodeRenameResponseHandler.bind(this))
  }

  render () {
    const { node,path } = this.props
    if (!node || node.node_type === "ORGANIZATION") {
      this.innerHTML = `
        <p>
          <em>Select a file or folder to view its details</em>
        </p>
      `
      return
    }

    const nodeSize = this.nodeSize
    const contentUrl = node?.content_url
    const attributesToExclude = ["id", "comment", "url", "path", "parent", "content_url"]
    const nodeKeys = Object.keys(node).filter(key=> !attributesToExclude.includes(key))
    this.innerHTML = `
      <h2>
        <span class="name ${node.node_type}">${node.name}</span>
        <button class="close">x</button>
      </h2>

      <ui5-tabcontainer class="full-width" collapsed fixed>
        <ui5-tab text="Details" selected></ui5-tab>
        <ui5-tab text="Activity" collapsed></ui5-tab>
      </ui5-tabcontainer>

      <div class="details">
        <dl style="font-size: 0.8rem;">` + this.detailSection(nodeKeys) +
          `${node.node_type !== "COLLECTION"?`<dt>Location</dt><dd class="location-detail">${path}</dd>`:""}</dl>
        ${contentUrl?`<ui5-button design="Default" id="download-file-btn">Download</ui5-button>`: ""}
      </div>
      <div class="activity hidden">
      <div id="events-container" style="height: 420px; overflow-y: scroll;"></div>
      </div>
    `
    if(!!contentUrl){
      document.getElementById("download-file-btn").addEventListener("click", function(){
        window.open(contentUrl, "_blank")
      })
    }

    if(!!document.querySelector(".copy-hash-btn")){
      const copyButtons = document.querySelectorAll(".copy-hash-btn")
      copyButtons.forEach(element=>{
        const previousElementId = $(element).prev().attr("id")
        element.addEventListener("click", ()=> {
          const hashData = element.getAttribute("data")
          navigator.clipboard.writeText(hashData)
          document.getElementById(previousElementId).innerHTML = "Text Copied";
        })
        element.addEventListener("mouseout", ()=>{
          document.getElementById(previousElementId).innerHTML = "Copy Text";
        })
      })
    }
    this.querySelector("button.close").addEventListener("click", this.hide.bind(this))
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

  detailSection(nodeKeys){
    const { node } = this.props
    let str = ""
    nodeKeys.forEach(key => {
          if (node[key] !== null){
            if(key === "uploaded_by"){
              str += `<dt>${toTitleCase(key)}</dt><dd>${node[key].username}</dd>`
            }
            else if (key.endsWith("sum")){
              // For hash elements
              const hashString = key.slice(0,key.length-4).toUpperCase()
              str += `
                      <dt style="margin-bottom: -29px;">${hashString}</dt>
                      <dd style="display: inline-block;">${node[key].slice(0,8)}</dd>
                      <div class="tooltipElement">
                        <span class="tooltiptext" id="hover-text-${hashString.slice(hashString.length-1,)}">Copy Text</span>
                      <div class="copy-hash-btn" data="${node[key]}" ><img src="/vault/static/favicon/copyIcon.png" alt="Copy Icon" class="copy-img"></div>
                      </div>
                      `
            }
            else if(key === "node_type"){
              str += `<dt>Type</dt><dd>${node[key]}</dd>`
            }
            else if (key === "size"){
                str+=`<dt>${toTitleCase(key)}</dt><dd class="size-text">${ node.id == this.folderNodeId ? humanBytes(this.nodeSize) : humanBytes(node.size)}</dd>`
            }
            else{
              str+=`<dt>${toTitleCase(key)}</dt><dd>${node[key]}</dd>`
            }
          }
        })
    return str
  }

  fileRowSelectedHandler (message) {
    const { node} = message
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

  async tabSelectHandler (e) {
    const {node,basePath,collectionIdDict} = this.props
    const showDetails = e.detail.tabIndex === 0
    const eventsContainer = document.getElementById("events-container")
    eventsContainer.innerHTML = ""
    this.detailsEl.classList[showDetails ? "remove" : "add"]("hidden")
    this.activityEl.classList[showDetails ? "add" : "remove"]("hidden")
    if(node.node_type === "COLLECTION" && !showDetails){
      // call api only when Activity tab is clicked
      let collectionId = collectionIdDict[node.id]
      const response = await fetch(`${basePath}/api/get_events/${collectionId}`)
      .then(data=>data.json())
      .catch((error)=>
      {
        console.error("Server error ", error)
        return
      })
      let events = response["formatted_events"]
      if (events.length !== 0){
        events.forEach((event)=>{
        eventsContainer.innerHTML += `
        <ui5-card class="small activity-card">
          <div class="activity-content">
              ${Object.keys(event).map(k=> k!== "Event Id"?`<div class="content-group">
              <ui5-title level="H6" class="activity-title-desc" style="margin-bottom: 0.5rem;">${k}</ui5-title>
              <ui5-label class="activity-title-desc">${k === "Total Size"? humanBytes(event[k]):event[k]}</ui5-label>
              </div>`:"").join("")}
              <ui5-link class="view-details-link activity-title-desc" href = "${basePath}/${(event["Event Type"] === "Deposit" || event["Event Type"] === "Migration")?"deposit":"reports"}/${event["Event Id"]}" target = "_blank">View Details</ui5-link>
          </div>
      </ui5-card>`
      })
      } else{
        eventsContainer.innerHTML = "No Events Available"
      }
    } else if(!showDetails){
      // for files and folders
      eventsContainer.innerHTML = "No Events Available"
    }
  }

  nodeResponseHandler({nodeResponse,action}){
    this._parentNode = nodeResponse[0]
    if (action === "MOVE"){
      this.folderNodeId = nodeResponse[0].id
      this.nodeSize = nodeResponse[0].size
    }
    this.render()
  }

  changeDirectoryHandler (node,path) {
    this.props.node = node
    this.props.path = path
    this.render()
  }
}

customElements.define("vault-file-details", FileDetails)
