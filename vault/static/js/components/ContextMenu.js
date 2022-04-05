import { publish } from "../lib/pubsub.js";

export default class ContextMenu extends HTMLElement {
  connectedCallback() {
    // Expect this.props to have been been programmatically populated
    // by the instantiator.

    // Append a small, invisible element to the exact location where
    // the click occurred so that we can pass this to the popover
    // component to make it display at the click site instead of
    // left/bottom-aligned with the corresponding element.
    const disabledOptions = this.props.disabledOptions;
    this.innerHTML = `
      <span style="position: absolute;
                   left: ${this.props.x}px;
                   top: ${this.props.y}px;
                   display: inline-block;
                   height: 0.5rem;"
      >
      </span>

      <ui5-popover placement-type="Bottom">
        <ui5-list mode="SingleSelect">
          ${this.props.options
            .map(
              (option) =>
                `<ui5-li data-value="${option}"
                     ${
                       disabledOptions && disabledOptions.includes(option)
                         ? "disabled"
                         : ""
                     }
             >${option}</ui5-li>`
            )
            .join("\n")}
        </ui5-list>
      </ui5-popover>
    `;
    const [spec, popover] = this.querySelectorAll(":scope > *");
    this.popover = popover;

    popover.addEventListener("item-click", this.itemClickHandler.bind(this));
    // Remove this element after the popover has closed to ensure that focus has
    // been restored to the previously-focused element.
    popover.addEventListener("after-close", () => this.remove());

    // Disable events that we don't want escaping.
    popover.addEventListener("click", (e) => e.stopPropagation());
    popover.addEventListener("selection-change", (e) => e.stopPropagation());
    popover.addEventListener("_focused", (e) => e.stopPropagation());

    this.popover.showAt(spec);

    // HACK - wait a short time before manually applying focus to the ui5-list
    // component in order to give that component a chance to initialize and
    // respond to the focus by providing keyboard control.
    setTimeout(() => this.popover.applyFocus(), 50);
  }

  itemClickHandler(e) {
    // Publish the selection.
    publish(this.props.topic, {
      value: e.detail.item.dataset.value,
      context: this.props.context,
    });
    // Close the popover.
    this.popover.close();
  }
}

customElements.define("vault-context-menu", ContextMenu);
