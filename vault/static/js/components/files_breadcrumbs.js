class CollectionBreadcrumbs extends HTMLElement {
  constructor() {
    super();

    const path = JSON.parse(this.dataset.path).split("/").slice(1);

    const template = document.getElementById("collection-breadcrumbs");
    const templateContent = template.content;
    const shadowRoot = this.attachShadow({ mode: "open" }).appendChild(
      templateContent.cloneNode(true)
    );
    shadowRoot.innerHTML +=
      '<li class = "breadcrumbs_list"><a href="/vault/meta/files" style="margin-left: -7px;">All Collections</a></li><div style="display: inline; margin-left: -1px; margin-right: -2px; text-decoration: none;">/</div>';

    shadowRoot.innerHTML += `${path
      .map(
        (pathElement) =>
          `<li class = "breadcrumbs_list" ><a href="/vault/meta/files/${path
            .slice(0, path.indexOf(pathElement) + 1)
            .join("/")}" >${pathElement}</a></li>`
      )
      .join("/")}`;
  }
}

customElements.define("collection-breadcrumbs", CollectionBreadcrumbs);
