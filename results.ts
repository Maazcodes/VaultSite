import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
@customElement('results-view')
export class Results extends LitElement {
  static styles = css`
    h2 {
      text-align: center;
    }
    #multiple-tabs {
      display: inline-block;
      margin-left: 20px;
    }

    #multiple-tabs {
      width: fit-content;
    }

    #multiple-tabs li.not-selected {
      background-color: #d3d3d366;
    }

    #multiple-tabs li.selected {
      background-color: #ffdab95e;
    }

    #multiple-tabs .main-tab {
      display: inline;
      list-style-type: none;
      padding: 10px;
      border-radius: 5px 5px 0px 0px;
      color: #292a0a;
      font-weight: bold;
      cursor: pointer;
    }

    #multiple-tabs .tab_content {
      background-color: #ffdab95e;
      padding: 10px;
      margin-top: 9px;
      border-radius: 0px 5px 5px 5px;
      color: #2e2e2e;
      line-height: 1.6em;
      word-spacing: 2px;
      display: inline-block;
      width: 500px;
      font-size: 13px;
      overflow: auto;
      height: 500px;
    }

    .tab_content > ul {
      list-style-type: none;
    }
  `;

  @property({ type: Array }) collections = [];

  @property({ type: String }) selectedTabId = 'tab-1';

  @property({type: Array}) SearchResults = [];
   
  constructor(searchResults:Array<string>) { 
    super()
    this.SearchResults = searchResults 
   }

  getSeeds = async () => {
      try {
        const response = await fetch(`http://127.0.0.1:7000/api/collection/2/`);
        const collItems = await response.json();
        this.collections = collItems.seed_data;
      } catch (errors) {
        console.error(errors);
      }
      return 'Calling Api...';
    };

  render() {

    window.onload = () => this.getSeeds();

    const tab1Content = () => {
      if (this.SearchResults && this.SearchResults.length !== 0){
        return html`
         <div class="tab_content" >
            <h2>${this.SearchResults.length} Total Results</h2>
            <ul>
              ${this.SearchResults.map(
                seed => html`
                  <li><h3>Title: ${seed.title}</h3></li>
                  <li><strong>Filetype:</strong> ${seed.type}</li>
                  <li><strong>Site:</strong> ${seed.description}</li>
                  <li><strong>Capture Date: </strong>${seed.data}</li>
                  <li><strong>Collection:</strong> ${seed.collection}</li>
                  <hr />
                `
              )}
            </ul>
          </div>
        `;
      }

     else if (this.collections.length !== 0) {
        return html`
          <div class="tab_content" >
            <h2>${this.collections.length} Total Results</h2>
            <ul>
              ${this.collections.map(
                seed => html`
                  <li><h3>Title: ${seed.title}</h3></li>
                  <li><strong>URL:</strong> ${seed.url}</li>
                  <li><strong>Description:</strong> ${seed.description}</li>
                  <li><strong>Subject: </strong>${seed.subject}</li>
                  <li><strong>Creator:</strong> ${seed.creator}</li>
                  <li><strong>Publisher:</strong> ${seed.publisher}</li>
                  <li><strong>Language:</strong> ${seed.language}</li>
                  <li><strong>Date:</strong> ${seed.date}</li>
                  <li><strong>Rights:</strong> ${seed.rights}</li>
                  <li><strong>Identifier: </strong>${seed.identifier}</li>
                  <li><strong>Collector:</strong> ${seed.collector}</li>
                  <hr />
                `
              )}
            </ul>
          </div>
        `;
      }
      return html`
        <div class="tab_content">
          <h2>Loading Data...</h2>
        </div>
      `;
    };

    const tab2Content = () => html`
      <div class="tab_content">
        Please enter terms above to search for archived content.
      </div>
    `;
    
    const tabContents = { 
      'tab-1': tab1Content(),
      'tab-2': tab2Content(),
    };

    return html`
      <div id="multiple-tabs">
        <li
          class="selected main-tab"
          @click="${this.changeTab}"
          @keydown="${this.changeTab}"
          id="tab-1"
        >
          Sites
        </li>
        <li
          class="not-selected main-tab"
          @click="${this.changeTab}"
          @keydown="${this.changeTab}"
          id="tab-2"
        >
          Search Page Text
        </li>
        ${tabContents[`${this.selectedTabId}`]}
      </div>      
    `;
  }

  changeTab(event) {
    const targetId = event.target.id;
    this.selectedTabId = targetId;
    const tabHeaders = this.renderRoot.querySelectorAll("[id^='tab-']");
    for (const tabheader of tabHeaders) {
      tabheader.className = 'not-selected main-tab';
    }

    (<HTMLInputElement>(
      this.renderRoot.querySelector(`#${targetId.toString()}`)
    )).className = 'selected main-tab';
  }
}
