import { publish, subscribe } from "../lib/pubsub.js";
export default class BreadcrumbsView extends HTMLElement {
  constructor() {
    super();
    this.props = {
      nodes: [],
      path: undefined,
      node: {},
    }    
  }

  connectedCallback() {
    // Expect this.props.nodes to have been been programmatically populated
    // by FilesView.
    this.render();
    subscribe("CHANGE_DIRECTORY", this.changeDirectoryHandler.bind(this));
    this.addEventListener("click", this.clickHandler.bind(this), true);
  }

  render() {
    const { path, node, appPath } = this.props;
    this.pathParts = path === "/" ? [] : path.replace(/^\//, "").split("/");    
    this.node = node;
    this.nodePathArray = this.node.path.split(".");
    this.innerHTML = `<ol class="main-breadcrumbs-list"><li class="my-collection"><a href="${appPath}">Collections </a></li>
    ${this.pathParts
      .map(
        (pathElement, pathIndex) =>                                                                 
            `<li class="crumb-elements" id="${pathIndex}"><a href="${this.pathLink(appPath, this.pathParts, pathIndex)}">${pathElement}</a></li>`)
      .join("")}</ol>
    `;
    if (this.pathParts.length > 2) {
      this.innerHTML = `<ol class="main-breadcrumbs-list"><li class="my-collection"><a href="${appPath}">Collections </a></li><li class="crumb-elements" id="openPopoverButton" >...</li>
      ${this.pathParts.slice(this.pathParts.length-2,)
      .map(
        (pathElement, pathIndex) =>                                                                 
            `<li class="crumb-elements" id="${pathIndex + this.pathParts.length-2}"><a href="${this.pathLink(appPath, this.pathParts, pathIndex)}">${pathElement}</a></li>`)
      .join("")}</ol>
      `;
      this.innerHTML += `
      <ui5-popover id="breadcrumbs-popover-content" placement-type="Bottom">
        <ol style = "list-style: none; margin: 10px;">
          ${this.pathParts.slice(0,this.pathParts.length-2)
          .map(
            (pathElement, pathIndex) =>                                                                 
                `<li id="${pathIndex}"><a href="${this.pathLink(appPath, this.pathParts, pathIndex)}">${pathElement}</a></li>`)
          .join("")}
        </ol>
      </ui5-popover>
      `
      var popoverOpener = document.getElementById("openPopoverButton");
	    var breadcrumbsPopover = document.getElementById("breadcrumbs-popover-content");
      popoverOpener.addEventListener("click", function() {
        breadcrumbsPopover.showAt(popoverOpener);
      });
    }
  }
  
  async clickHandler (e) {
    if (e.ctrlKey) {
      return
    }
    // prevent from re-loading the page
    e.preventDefault();
    const { target } = e;
    if (target.tagName !== "A") {
      return
    }
    this.targetId = target.parentElement.id;
    this.pathIndex = parseInt(this.targetId);
    this.nodeId = this.nodePathArray[this.pathIndex+1]; // getting node id from node path array
    if (!this.nodeId) { // For first element of Breadcrumb
      this.nodeId = parseInt(this.nodePathArray[0]);
    } 
    publish("CHANGE_DIRECTORY_REQUEST", {
      nodeId: this.nodeId, path: `/${this.pathParts.slice(0, this.pathIndex + 1).join("/")}`,
      })
  }

  pathLink(appPath, pathParts, pathIndex) {
    return appPath + "/" + pathParts.slice(0, pathIndex + 1).join("/")
  }

  changeDirectoryHandler({childNodesResponse, path, node}) {
    this.props.node = node;
    this.props.path = path;
    this.props.nodes = childNodesResponse.results;
    this.render();
  }
}

customElements.define("vault-breadcrumbs", BreadcrumbsView);
