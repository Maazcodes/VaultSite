
export default class NewCta extends HTMLElement {
  connectedCallback () {
    this.innerHTML = `
      <button>New</button>
      <ui5-popover placement-type="Bottom">
        <ui5-list mode="SingleSelect">
          <ui5-li data-value="folder">Folder</ui5-li>
          <ui5-li data-value="fileUpload">File upload</ui5-li>
          <ui5-li data-value="folderUpload">Folder upload</ui5-li>
        </ui5-list>
      </ui5-popover>
    `

    const [ button, popover ] = this.querySelectorAll(":scope > *")
    this.popover = popover

    button.addEventListener("click", this.buttonClickHandler.bind(this))
    popover.addEventListener("item-click", this.itemClickHandler.bind(this))
  }

  buttonClickHandler (e) {
    e.stopPropagation()
    this.popover.showAt(e.target)
  }

  itemClickHandler (e) {
    // TODO
    // Publish the selection.
    // publish( ... )
    // Close the popover
    this.popover.close()
  }

}

customElements.define("new-cta", NewCta)
