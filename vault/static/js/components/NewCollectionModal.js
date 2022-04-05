import { subscribe, publish } from "../lib/pubsub.js";

import Modal from "./Modal.js";

export default class NewCollectionModal extends Modal {
  constructor() {
    super();
    this.state = { node: undefined };
  }

  connectedCallback() {
    this.setAttribute("header-text", "Create Collection");
    this.setAttribute("submit-text", "OK");
    this.innerHTML = `
      <input type="text"
             name="name"
             spellcheck="false"
             autocomplete="off"
             placeholder="Enter new collection name"
             class="new-collection-modal-create-collection-input"
      >
      </input>
    `;
    super.connectedCallback();

    this.input = this.querySelector("input[name=name]");

    subscribe(
      "NEW_CTA_MENU_ITEM_SELECTED",
      this.newCtaMenuItemSelectedHandler.bind(this)
    );

    subscribe(
      "CREATE_COLLECTION_RESPONSE",
      this.createCollectionResponseHandler.bind(this)
    );
  }

  newCtaMenuItemSelectedHandler({ value }) {
    if (value !== "collection") {
      return;
    }
    /* clearing the pre-populated field */
    const input = this.querySelector(
      ".new-collection-modal-create-collection-input"
    );
    input.value = "";
    this.open();
  }

  submitHandler(nameInputMap) {
    const name = nameInputMap.get("name").value;
    publish("CREATE_COLLECTION_REQUEST", { name });
    this.setBusyState(true);
  }

  createCollectionResponseHandler({ error }) {
    this.setBusyState(false);
    if (!error) {
      this.close();
      return;
    }
    const { code } = error;
    switch (code) {
      case 409:
        this.error = "A Collection with this name already exists";
        break;
      default:
        this.error = "An error occurred";
    }
    // Reselect the input.
    this.input.select();
  }
}

customElements.define("vault-new-collection-modal", NewCollectionModal);
