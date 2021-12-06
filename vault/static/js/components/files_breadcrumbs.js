class CollectionBreadcrumbs extends HTMLElement {
  constructor() {
    super();

    const path = JSON.parse(this.dataset.path).split("/").slice(1);

    let template = document.getElementById("collection-breadcrumbs");
    let templateContent = template.content;
    const shadowRoot = this.attachShadow({ mode: "open" }).appendChild(
      templateContent.cloneNode(true)
    );
    this.shadowRoot.innerHTML +=
      '<li class = "breadcrumbs_list"><a href="/vault/meta/files" style="margin-left: -7px;">All Collections</a></li><div style="display: inline; margin-left: -1px; margin-right: -2px; text-decoration: none;">/</div>';

    this.shadowRoot.innerHTML += `${path
      .map(
        (path_element) =>
          `<li class = "breadcrumbs_list" ><a href="/vault/meta/files/${path
            .slice(0, path.indexOf(path_element) + 1)
            .join("/")}" >${path_element}</a></li>`
      )
      .join("/")}`;
  }
}

customElements.define("collection-breadcrumbs", CollectionBreadcrumbs);
