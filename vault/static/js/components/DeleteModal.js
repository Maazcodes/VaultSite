import { pluralize } from "../lib/lib.js";
import { subscribe, publish } from "../lib/pubsub.js";

import Modal from "./Modal.js";

export default class DeleteModal extends Modal {
  constructor() {
    super();
    this.state = { nodes: undefined };
  }

  connectedCallback() {
    this.setAttribute("header-text", "Delete?");
    this.setAttribute("submit-text", "DELETE");
    this.setAttribute("submit-design", "Negative");
    this.innerHTML = `<p class="delete-message"></p>`;
    super.connectedCallback();

    this.message = this.querySelector("p.delete-message");

    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedHandler.bind(this)
    );

    subscribe(
      "NODES_DELETE_RESPONSE",
      this.nodeDeleteResponseHandler.bind(this)
    );
  }

  open() {
    // TODO: show the recursive sum of nodes in all selected subtrees to be
    // deleted, not just the number of nodes selected in the UI.
    // https://webarchive.jira.com/browse/WT-1191
    const numNodes = this.state.nodes.length;
    this.message.textContent = `${numNodes} ${pluralize(
      "item",
      numNodes
    )} will be deleted.`;
    super.open();
  }

  fileContextMenuItemSelectedHandler({ value: contextAction, context }) {
    if (contextAction !== "Delete") {
      return;
    }
    this.state.nodes = context.selectedNodes;
    this.open();
  }

  submitHandler(_nameInputMap) {
    const { nodes } = this.state;
    publish("NODES_DELETE_REQUEST", { nodes });
    this.setBusyState(true);
  }

  nodeDeleteResponseHandler({ results }) {
    this.setBusyState(false);

    const success = results.every(({ error }) => !error);

    if (!success) {
      this.error =
        "An error occurred which prevented all selected files from being deleted.";
      return;
    }

    this.close();
  }
}

customElements.define("vault-delete-modal", DeleteModal);
