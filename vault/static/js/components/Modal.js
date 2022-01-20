
export default class Modal extends HTMLElement {
  constructor () {
    super()
    this.state = {
      open: false,
      busy: false,
    }
  }

  connectedCallback () {
    this.props = {
      submitText: this.getAttribute("submit-text") || "SUBMIT",
      submitDesign: this.getAttribute("submit-design") || "Emphasized",
      busySubmitText: this.getAttribute("busy-submit-text") || "WORKING",
      cancelText: this.getAttribute("cancel-text") || "CANCEL",
      headerText: this.getAttribute("header-text"),
    }

    // Expect the initial innerHTML to comprise 0 or more <input> elements that
    // specify a name property, a input.name -> input map of which will be passed
    // to submitHandler().
    this.innerHTML = `
      <ui5-dialog>
        <div>
          <ui5-busy-indicator style="display: block;">
          ${this.innerHTML}
          </ui5-busy-indicator>
          <div class="error"></div>
        </div>
        <div slot="footer">
          <ui5-button data-name="cancel" design="Transparent">
            ${this.props.cancelText}
          </ui5-button>
          <ui5-button data-name="submit" design="${this.props.submitDesign}">
            ${this.props.submitText}
          </ui5-button>
        </div>
      </ui5-dialog>
    `
    this.dialog = this.querySelector("ui5-dialog")
    this.busy = this.querySelector("ui5-busy-indicator")
    this.errorDiv = this.querySelector("div.error")
    this.cancelButton = this.querySelector("ui5-button[data-name=cancel]")
    this.submitButton = this.querySelector("ui5-button[data-name=submit]")
    // Collect all non-disabled inputs and buttons for disabling while busy.
    this.disablableEls =
      this.querySelectorAll("input:not(:disabled), ui5-button:not(:disabled)")
    // Create a input.name -> input map for reference within submitHandler().
    this.nameInputMap = new Map(Array.from(this.querySelectorAll("input[name]"))
                                     .map(el => [ el.getAttribute("name"), el ]))

    // Maybe set the header text.
    if (this.props.headerText) {
      this.dialog.headerText = this.props.headerText
    }

    this.addEventListener("click", this.clickHandler.bind(this))

    // Reset the error when dialog is closed.
    this.dialog.addEventListener("after-close", () => this.error = "")
  }

  open () {
    // Show the dialog.
    this.dialog.show()
    // Register a global keydown handler with useCapture=true so that we can
    // prevent Escape from closing a busy modal.
    // Save the bound handler function so that we can successfully remove it later.
    this.boundKeydownHandler = this.keydownHandler.bind(this)
    document.addEventListener("keydown", this.boundKeydownHandler, true)
  }

  set error (error) {
    this.errorDiv.textContent = error
  }

  close () {
    // Close the dialog.
    this.dialog.close()
    // Remove the global keydown handler.
    document.removeEventListener("keydown", this.boundKeydownHandler, true)
  }

  setInputsDisabledState (disabled) {
    for (const el of this.disablableEls) {
      if (disabled) {
        el.setAttribute("disabled", "")
      } else {
        el.removeAttribute("disabled")
      }
    }
  }

  setBusyState (busy) {
    this.state.busy = busy
    this.setInputsDisabledState(busy)
    this.busy.active = busy
    const { submitText, busySubmitText } = this.props
    this.submitButton.textContent = busy ? busySubmitText : submitText
  }

  clickHandler (e) {
    e.stopPropagation()
    if (e.target.tagName !== "UI5-BUTTON") {
      return
    }
    const button = e.target
    switch (button.dataset.name) {
      case "cancel":
        this.close()
        break
      case "submit":
        this.submitHandler(this.nameInputMap)
        break
    }
  }

  keydownHandler (e) {
    switch (e.key) {
      case "Enter":
        if (e.target.tagName === "INPUT") {
          this.submitHandler(this.nameInputMap)
        }
        break
      case "Escape":
        // Prevent Escape from closing the dialog if busy.
        if (this.state.busy) {
          e.stopPropagation()
        }
        break
    }
  }

  submitHandler (nameInputMap) {
    /* Implement in subclass.
     */
  }
}

customElements.define("vault-modal", Modal)
