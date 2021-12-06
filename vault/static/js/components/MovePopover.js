
import { pluralize } from "../lib/lib.js"
import { subscribe } from "../lib/pubsub.js"

export default class MovePopover extends HTMLElement {
  connectedCallback () {
    this.innerHTML = `
      <ui5-popover placement-type="Bottom" horizontal-align="Stretch">
        <em>put single-column tree nav component here</em>
        <div>
          <ui5-button design="Emphasized" style="float: right;" disabled>
          </ui5-button>
        </div>
      </ui5-popover>
    `
    this.popover = this.querySelector("ui5-popover")
    this.button = this.querySelector("ui5-button")

    subscribe(
      "FILE_CONTEXT_MENU_ITEM_SELECTED",
      this.fileContextMenuItemSelectedHandler.bind(this)
    )
  }

  fileContextMenuItemSelectedHandler ({ value, context }) {
    if (value !== "Move") {
      return
    }
    const numItems = context.selectedRows.length
    this.button.textContent =
      `MOVE ${numItems} ${pluralize("ITEM", numItems, "S")} HERE`
    const nameCell = context.currentRow.querySelector(".name")
    this.popover.showAt(nameCell)
  }
}

customElements.define("vault-move-popover", MovePopover)
