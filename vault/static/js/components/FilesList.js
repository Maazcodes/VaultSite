import ContextMenu from "./ContextMenu.js";
import { publish, subscribe } from "./../lib/pubsub.js";
import { createElement, escapeHtml, joinPath } from "./../lib/domLib.js";
import { humanBytes } from "./../lib/lib.js";

export default class FilesList extends HTMLElement {
  constructor() {
    super();
    this.props = {
      nodes: [],
      path: undefined,
      basePath: "",
    };
    this.state = {
      detailsPanelClosed: false,
      selectedRows: [],
      selectedNodes: [],
      nextChildBatchUrl: null,
    };
    this.table = null;
  }

  connectedCallback() {
    // Expect this.props.files to have been been programmatically populated
    // by FilesView.
    this.nodesChangedHandler();

    this.addEventListener("_focused", this.rowFocusedHandler.bind(this));
    this.addEventListener("dblclick", this.selectHandler.bind(this));
    this.addEventListener("keydown", this.keyHandler.bind(this));
    this.addEventListener(
      "selection-change",
      this.selectionChangeHandler.bind(this)
    );
    this.addEventListener("contextmenu", this.contextmenuHandler.bind(this));

    subscribe(
      "DETAILS_PANEL_CLOSED",
      () => (this.state.detailsPanelClosed = true)
    );
    subscribe(
      "DETAILS_PANEL_OPEN",
      () => (this.state.detailsPanelClosed = false)
    );
    subscribe(
      "CHANGE_DIRECTORY",
      this.changeDirectoryMessageHandler.bind(this)
    );
    subscribe(
      "NODE_RENAME_RESPONSE",
      this.nodeRenameResponseMessageHandler.bind(this)
    );
    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedMessageHandler.bind(this)
    );
    subscribe(
      "NODES_DELETE_RESPONSE",
      this.nodesDeleteResponseHandler.bind(this)
    );
  }

  nodeToUI5TableRow(node, index) {
    /* Return a <ui5-table-row> element for the given node and index.
     */
    return createElement(`
      <ui5-table-row data-index="${index}" data-name="${node.name}">
        <ui5-table-cell class="name ${node.node_type}"
                        title="${escapeHtml(node.name)}"
        >${escapeHtml(node.name)}</ui5-table-cell>
        <ui5-table-cell class="uploaded-by">
          ${node.uploaded_by?.username || "&mdash;"}
        </ui5-table-cell>
        <ui5-table-cell class="modified-at">
          ${node.modified_at}
        </ui5-table-cell>
        <ui5-table-cell class="size">${
          !!node.size ? humanBytes(node.size) : "&mdash;"
        }</ui5-table-cell>
      </ui5-table-row>
      `);
  }

  appendChildNodes(nodes) {
    /* Append nodes to the table.
     */
    let i = this.props.nodes.length;
    for (const node of nodes) {
      this.props.nodes.push(node);
      this.table.appendChild(this.nodeToUI5TableRow(node, i));
      i += 1;
    }
  }

  nodesChangedHandler() {
    // Reset selectedNodes.
    this.state.selectedRows = [];
    this.state.selectedNodes = [];

    // Re-render.
    const noDataText = !this.innerHTML ? "Loading..." : "No items found";
    this.innerHTML = `
      <ui5-table mode="MultiSelect" sticky-column-header growing="Scroll"
        no-data-text="${noDataText}">
        <ui5-table-column slot="columns">Name</ui5-table-column>
        <ui5-table-column slot="columns">Uploaded by</ui5-table-column>
        <ui5-table-column slot="columns">Last modified</ui5-table-column>
        <ui5-table-column slot="columns">File size</ui5-table-column>
      </ui5-table>
    `;

    // Save a reference to the table.
    this.table = this.querySelector("ui5-table");

    // Append the node rows.
    this.props.nodes.forEach((node, i) =>
      this.table.appendChild(this.nodeToUI5TableRow(node, i))
    );

    // Register the ui5-table load-more event handler.
    this.table.addEventListener("load-more", this.loadMoreHandler.bind(this));
  }

  getRowTarget(e) {
    const { target } = e;
    return target.tagName === "UI5-TABLE-ROW"
      ? target
      : target.closest("ui5-table-row");
  }

  rowFocusedHandler(e) {
    /* Publish a FILE_ROW_SELECTED message.
     */
    const tr = this.getRowTarget(e);
    tr.parentElement._itemNavigation.setCurrentItem(tr);
    const node = this.props.nodes[parseInt(tr.dataset.index)];
    publish("FILE_ROW_SELECTED", { node });
  }

  selectHandler(e) {
    /* Publish either a CHANGE_DIRECTORY or OPEN_FILE message.
     */
    e.stopPropagation();
    // Set the UI5 Table component's busy flag.
    const node = this.props.nodes[parseInt(this.getRowTarget(e).dataset.index)];
    publish(
      node.node_type === "FILE"
        ? "OPEN_FILE_REQUEST"
        : "CHANGE_DIRECTORY_REQUEST",
      { node, path: `${joinPath(this.props.path, node.name)}` }
    );
  }

  keyHandler(e) {
    /* Fire the selectHandle when Enter is pressed on an active row.
     */
    switch (e.key) {
      case "Enter": {
        const tr = this.getRowTarget(e);
        if (tr) {
          this.selectHandler(e);
        }
        break;
      }
    }
  }

  selectionChangeHandler(e) {
    /* Save the array of selected rows.
     */
    this.state.selectedRows = e.detail.selectedRows;
    this.state.selectedNodes = e.detail.selectedRows.map(
      (tr) => this.props.nodes[parseInt(tr.dataset.index)]
    );
  }

  async contextmenuHandler(e) {
    /* Handle context menu, i.e. right, clicks but presenting our
       own custom context menu.
     */
    // If the Control key is pressed, show the default browser menu.
    if (e.ctrlKey) {
      return;
    }

    const tr = this.getRowTarget(e);
    // Abort if no row target is found, e.g. in the case of a right-click
    // on an already-open custom context menu.
    if (!tr) {
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    e.target.click();

    // If rows are selected but the row on which the context menu was
    // activated is not among them, deselect all currently selected rows.
    if (
      this.state.selectedNodes.length > 0 &&
      !this.state.selectedRows
        .map((x) => x.dataset.index)
        .includes(tr.dataset.index)
    ) {
      this.state.selectedRows.forEach((ui5Tr) => (ui5Tr.selected = false));
      // Manually reset selectedRows/Nodes because settings selectedf=false
      // does not appear to trigger the selectionChanged handler.
      this.state.selectedRows = [];
      this.state.selectedNodes = [];
    }

    // Build the options array based on the current state of things.
    const numSelectedNodes = this.state.selectedNodes.length;
    const node = this.props.nodes[parseInt(tr.dataset.index)];
    const isCollection = node.node_type === "COLLECTION";
    const isFolder = node.node_type === "FOLDER";
    const isDownloadable = !!node.content_url;
    const options = [
      this.state.detailsPanelClosed && "View Details",
      // node.node_type === "FILE" && numSelectedNodes < 2 && "Preview",
      numSelectedNodes < 2 && "Rename",
      !isCollection && "Move",
      node.node_type === "FILE" &&
        isDownloadable &&
        numSelectedNodes < 2 &&
        "Download",
      !isCollection && "Delete",
      isFolder && numSelectedNodes === 0 && "Deposit Here",
    ].filter((x) => x !== false);

    this.appendChild(
      Object.assign(new ContextMenu(), {
        props: {
          x: e.clientX,
          y: e.clientY + window.scrollY,
          options,
          context: {
            currentRow: tr,
            selectedRows: this.state.selectedRows.length
              ? this.state.selectedRows
              : [tr],
            selectedNodes: this.state.selectedNodes.length
              ? this.state.selectedNodes
              : [node],
            nodes: this.props.nodes,
          },
          topic: "FILE_CONTEXT_MENU_ITEM_SELECTED",
        },
      })
    );
  }

  changeDirectoryMessageHandler({ path, childNodesResponse }) {
    /* Update props and re-render.
     */
    this.state.nextChildrenUrl = childNodesResponse.next;
    Object.assign(this.props, { path, nodes: childNodesResponse.results });
    this.nodesChangedHandler();
  }

  nodeRenameResponseMessageHandler({ node, newName, error }) {
    /* Update the corresponding table row and name cell elements with the
       new name.
     */
    // Ignore error responses.
    if (error) {
      return;
    }
    const ui5TableRow = this.table.querySelector(
      `ui5-table-row[data-name="${node.name}"]`
    );
    const ui5TableCell = ui5TableRow.querySelector(
      ":scope > ui5-table-cell.name"
    );
    ui5TableRow.dataset["name"] = newName;
    ui5TableCell.textContent = newName;
  }

  fileContextMenuItemSelectedMessageHandler({ value: contextAction, context }) {
    // eslint-disable-next-line no-unused-vars
    const { currentRow, selectedRows, selectedNodes } = context;
    switch (contextAction) {
      case "Download": {
        const contentUrl = selectedNodes[0]?.content_url;
        if (contentUrl) {
          window.open(contentUrl, "_blank");
        }
        break;
      }
      case "Deposit Here": {
        const parentId = selectedNodes[0].id;
        const url = `${this.props.basePath}/deposit/flow?parentId=${parentId}`;
        window.location = url;
        break;
      }
    }
  }

  nodesDeleteResponseHandler({ results }) {
    const deletedNodeIds = new Set(
      results.filter(({ error }) => !error).map(({ node }) => node.id)
    );

    this.props.nodes = this.props.nodes.filter(
      ({ id }) => !deletedNodeIds.has(id)
    );
    this.nodesChangedHandler();
  }

  async loadMoreHandler(_e) {
    /* If there are more child nodes, load them and append them to the table.
     */
    if (!this.state.nextChildrenUrl) {
      return;
    }
    this.table.busy = true;
    const childNodesResponse = await (
      await fetch(this.state.nextChildrenUrl)
    ).json();
    this.state.nextChildrenUrl = childNodesResponse.next;
    this.appendChildNodes(childNodesResponse.results);
    this.table.busy = false;
  }
}

customElements.define("vault-files-list", FilesList);
