import { publish, subscribe } from "../lib/pubsub.js";

export default class NewCta extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <button>New</button>
      <ui5-popover placement-type="Bottom">
        <ui5-list mode="SingleSelect">
          <ui5-li data-value="collection">Collection</ui5-li>
          <ui5-li data-value="folder">Folder</ui5-li>
        </ui5-list>
      </ui5-popover>
    `;

    const [button, popover] = this.querySelectorAll(":scope > *");

    this.popover = popover;

    button.addEventListener("click", this.buttonClickHandler.bind(this));
    popover.addEventListener("item-click", this.itemClickHandler.bind(this));

    subscribe(
      "CHANGE_DIRECTORY",
      this.changeDirectoryMessageHandler.bind(this)
    );
    publish("NEW_CTA_COMPONENT_CONNCECTED");
  }

  buttonClickHandler(e) {
    e.stopPropagation();
    this.popover.showAt(e.target);
  }

  itemClickHandler(e) {
    /* Publish a NEW_CTA_MENU_ITEM_SELECTED message and close the popover.
     */
    publish("NEW_CTA_MENU_ITEM_SELECTED", {
      value: e.detail.item.dataset.value,
    });
    this.popover.close();
  }

  changeDirectoryMessageHandler({ path, childNodes }) {
    /* Set the "folder" option enabled stated based on the current path.
     */
    const folderEl = this.querySelector("ui5-li[data-value=folder]");
    if (path === "/") {
      folderEl.setAttribute("disabled", "");
    } else {
      folderEl.removeAttribute("disabled");
    }
  }
}

customElements.define("new-cta", NewCta);
