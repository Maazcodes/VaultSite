import { publish, subscribe } from "../lib/pubsub.js";

export default class FileDetailsButtons extends HTMLElement {
  constructor() {
    super();
    this.state = {
      detailsOpen: true,
    };
  }

  connectedCallback() {
    this.innerHTML = `
      <ui5-button design="Transparent"
                  title="Hide details"
                  class="details"
      >
        &#9432;
      </ui5-button>
    `;

    this.detailsButton = this.querySelector("ui5-button.details");

    this.detailsButton.addEventListener(
      "click",
      this.detailsButtonClickHandler.bind(this)
    );

    subscribe(
      "DETAILS_PANEL_CLOSED",
      this.detailsPanelClosedHandler.bind(this)
    );

    subscribe("DETAILS_PANEL_OPEN", this.detailsPanelOpenedHandler.bind(this));
  }

  detailsButtonClickHandler() {
    publish(`${this.state.detailsOpen ? "HIDE" : "SHOW"}_DETAILS_PANEL`);
  }

  detailsPanelClosedHandler() {
    this.state.detailsOpen = false;
    this.detailsButton.title = "Show details";
  }

  detailsPanelOpenedHandler() {
    this.state.detailsOpen = true;
    this.detailsButton.title = "Hide details";
  }
}

customElements.define("file-details-buttons", FileDetailsButtons);
