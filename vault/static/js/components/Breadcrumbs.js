class Breadcrumbs extends HTMLElement {
  constructor() {
    super();

    const breadcrumbs = JSON.parse(this.dataset.breadcrumbs);

    let generalTemplate = document.getElementById("general-breadcrumbs");
    let generalTemplateContent = generalTemplate.content;
    const shadowRoot = this.attachShadow({ mode: "open" }).appendChild(
      generalTemplateContent.cloneNode(true)
    );

    this.shadowRoot.innerHTML = `${breadcrumbs
      .map(
        (crumb) => `
        <li class = "general_breadcrumbs_list" style="display: inline; color: #888; margin-top: 18px; margin-right: 10px; margin-left: 10px; list-style: none;">
        <a href="/vault/${
          crumb[crumb.length - 1]
        }" style="color: #888; font-size: 0.6875rem; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">${
          typeof crumb === "string" ? crumb : crumb[0]
        }</a>
        </li>
       `
      )
      .join("/")}`;
  }
}
customElements.define("general-breadcrumbs", Breadcrumbs);
